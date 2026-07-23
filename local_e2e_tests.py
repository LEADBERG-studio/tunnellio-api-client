from __future__ import annotations

import argparse
import http.server
import json
import os
import shutil
import socketserver
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
SRC_DIR = ROOT / 'src'
sys.path.insert(0, str(SRC_DIR))

from tunnellio.client import ApiClient, build_ssl_context
from tunnellio.config import load_runtime_config
from tunnellio.planner import Planner, PlanOptions


def utc_stamp() -> str:
    return time.strftime('%Y%m%d-%H%M%S', time.gmtime())


def console(message: str) -> None:
    stamp = time.strftime('%H:%M:%S')
    print(f'[local-e2e {stamp}] {message}', flush=True)


def json_safe(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_safe(v) for v in value]
    return value


class Report:
    def __init__(self, report_path: Path):
        self.path = report_path
        self.data: dict[str, Any] = {
            'startedAt': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            'environment': {
                'python': sys.version,
                'platform': sys.platform,
                'cwd': str(ROOT),
            },
            'tls': {},
            'api': {},
            'cli': {},
            'ssh': {},
            'persistentFlow': {},
            'ephemeralFlow': {},
            'cleanup': {},
            'errors': [],
            'timeline': [],
        }

    def note(self, stage: str, message: str) -> None:
        self.data.setdefault('timeline', []).append(
            {
                'time': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                'stage': stage,
                'message': message,
            }
        )
        self.flush()

    def add_error(self, stage: str, exc: Exception) -> None:
        self.data.setdefault('errors', []).append(
            {
                'stage': stage,
                'error': repr(exc),
            }
        )
        self.flush()

    def flush(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(json_safe(self.data), indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


class MarkerHandler(http.server.BaseHTTPRequestHandler):
    marker = ''

    def do_GET(self) -> None:
        body = self.marker.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        return


class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Local Tunnellio end-to-end test runner')
    parser.add_argument('--token', help='Tunnellio API token. Defaults to TUNNELLIO_API_TOKEN env var.')
    parser.add_argument('--base-url', default='https://api.tunnellio.ru')
    parser.add_argument('--state-dir', default=None)
    parser.add_argument('--mode', choices=['api', 'full'], default='full')
    parser.add_argument('--local-port', type=int, default=32123)
    parser.add_argument('--local-host', default='127.0.0.1')
    parser.add_argument('--allow-insecure-tls-fallback', action='store_true')
    parser.add_argument('--allow-insecure-public-url-probe', action='store_true')
    parser.add_argument('--report-dir', default='test-artifacts')
    parser.add_argument('--prefix', default='local-e2e')
    parser.add_argument('--verbose', action='store_true')
    return parser


def make_client(token: str, base_url: str, state_dir: str | None, insecure_tls: bool, verbose: bool) -> tuple[ApiClient, Any]:
    if verbose:
        os.environ['TUNNELLIO_VERBOSE'] = '1'
    cfg = load_runtime_config(
        token=token,
        base_url=base_url,
        state_dir=state_dir,
        insecure_tls=insecure_tls,
    )
    return ApiClient(cfg), cfg


def run_cli(report: Report, token: str, base_url: str, insecure_tls: bool, verbose: bool) -> None:
    console('Running CLI smoke test: tunnellio meta')
    cmd = [sys.executable, '-m', 'tunnellio.cli', '--token', token, '--base-url', base_url]
    if insecure_tls:
        cmd.append('--insecure-tls')
    if verbose:
        cmd.append('--verbose')
    cmd.append('meta')
    env = os.environ.copy()
    env['PYTHONPATH'] = str(SRC_DIR) + (os.pathsep + env['PYTHONPATH'] if env.get('PYTHONPATH') else '')
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=60, env=env)
    report.data['cli']['meta'] = {
        'command': cmd,
        'returncode': proc.returncode,
        'stdout': proc.stdout[-4000:],
        'stderr': proc.stderr[-4000:],
    }
    report.note('cli', f'CLI meta finished rc={proc.returncode}')


def probe_tls(report: Report, token: str, base_url: str, state_dir: str | None, allow_fallback: bool, verbose: bool) -> tuple[ApiClient, Any, bool]:
    console('Probing API TLS with normal certificate validation')
    secure_client, secure_cfg = make_client(token, base_url, state_dir, insecure_tls=False, verbose=verbose)
    report.data['tls']['secureBackend'] = secure_client.tls_backend
    try:
        meta = secure_client.fetch_meta()
        caps = secure_client.fetch_capabilities()
        report.data['tls'].update({'secure': True, 'fallbackUsed': False})
        report.data['api']['meta'] = meta
        report.data['api']['capabilities'] = caps
        report.note('tls', f'Secure TLS probe succeeded via {secure_client.tls_backend}')
        return secure_client, secure_cfg, False
    except Exception as exc:
        report.data['tls'].update(
            {
                'secure': False,
                'secureError': repr(exc),
                'fallbackUsed': False,
            }
        )
        report.note('tls', f'Secure TLS probe failed via {secure_client.tls_backend}')
        if not allow_fallback:
            raise

    console('Falling back to insecure TLS for API diagnostics')
    insecure_client, insecure_cfg = make_client(token, base_url, state_dir, insecure_tls=True, verbose=verbose)
    report.data['tls']['insecureBackend'] = insecure_client.tls_backend
    meta = insecure_client.fetch_meta()
    caps = insecure_client.fetch_capabilities()
    report.data['tls']['fallbackUsed'] = True
    report.data['api']['meta'] = meta
    report.data['api']['capabilities'] = caps
    report.note('tls', 'Insecure TLS fallback for API succeeded')
    return insecure_client, insecure_cfg, True


def inspect_ssh(report: Report) -> tuple[str, str]:
    console('Checking local ssh and ssh-keygen availability')
    ssh_path = shutil.which('ssh')
    ssh_keygen_path = shutil.which('ssh-keygen')
    report.data['ssh']['sshPath'] = ssh_path
    report.data['ssh']['sshKeygenPath'] = ssh_keygen_path
    if ssh_path:
        proc = subprocess.run([ssh_path, '-V'], capture_output=True, text=True, timeout=20)
        report.data['ssh']['sshVersion'] = {
            'returncode': proc.returncode,
            'stdout': proc.stdout[-1000:],
            'stderr': proc.stderr[-1000:],
        }
    if ssh_keygen_path:
        proc = subprocess.run([ssh_keygen_path, '-?'], capture_output=True, text=True, timeout=20)
        report.data['ssh']['sshKeygenHelp'] = {
            'returncode': proc.returncode,
            'stdout': proc.stdout[-1000:],
            'stderr': proc.stderr[-1000:],
        }
    report.note('ssh', 'SSH inspection finished')
    if not ssh_path or not ssh_keygen_path:
        raise RuntimeError('ssh or ssh-keygen is not available on this machine')
    return ssh_path, ssh_keygen_path


def wait_for_url(url: str, marker: str, *, timeout_seconds: int = 35, insecure_tls: bool = False, verbose: bool = False) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    attempts: list[dict[str, Any]] = []
    ctx, tls_backend = build_ssl_context(
        insecure_tls=insecure_tls,
        logger=console if verbose else None,
    )
    attempt_no = 0
    console(f'Probing public URL: {url} (insecure_tls={insecure_tls}, tls_backend={tls_backend})')
    while time.time() < deadline:
        attempt_no += 1
        try:
            with urllib.request.urlopen(url, timeout=6, context=ctx) as response:
                body = response.read().decode('utf-8', errors='replace')
                attempts.append({'status': response.status, 'body': body[:500]})
                if verbose:
                    console(f'Probe attempt {attempt_no}: HTTP {response.status}')
                if marker in body:
                    console(f'Probe attempt {attempt_no}: marker found')
                    return {
                        'ok': True,
                        'attempts': attempts,
                        'insecureTls': insecure_tls,
                        'tlsBackend': tls_backend,
                    }
        except Exception as exc:
            attempts.append({'error': repr(exc)})
            if verbose:
                console(f'Probe attempt {attempt_no}: {exc!r}')
        time.sleep(2)
    return {
        'ok': False,
        'attempts': attempts,
        'insecureTls': insecure_tls,
        'tlsBackend': tls_backend,
    }


def main() -> int:
    args = build_parser().parse_args()
    token = args.token or os.getenv('TUNNELLIO_API_TOKEN')
    if not token:
        raise SystemExit('Token is required. Pass --token or set TUNNELLIO_API_TOKEN.')

    if args.verbose:
        os.environ['TUNNELLIO_VERBOSE'] = '1'

    run_id = f'{args.prefix}-{utc_stamp()}'
    report_dir = ROOT / args.report_dir / run_id
    report = Report(report_dir / 'report.json')
    report.data['runId'] = run_id
    report.data['settings'] = {
        'mode': args.mode,
        'baseUrl': args.base_url,
        'localHost': args.local_host,
        'localPort': args.local_port,
        'allowInsecureTlsFallback': args.allow_insecure_tls_fallback,
        'allowInsecurePublicUrlProbe': args.allow_insecure_public_url_probe,
        'verbose': args.verbose,
    }
    report.flush()

    created_key_id: int | None = None
    created_domain_id: int | None = None
    created_session_id: str | None = None
    key_path: Path | None = None
    pub_path: Path | None = None
    ssh_process: subprocess.Popen[str] | None = None
    httpd: ReusableTCPServer | None = None

    try:
        console(f'Starting test run {run_id}')
        client, cfg, used_fallback = probe_tls(
            report,
            token=token,
            base_url=args.base_url,
            state_dir=args.state_dir,
            allow_fallback=args.allow_insecure_tls_fallback,
            verbose=args.verbose,
        )
        run_cli(report, token, args.base_url, insecure_tls=used_fallback, verbose=args.verbose)

        console('Loading existing keys and domains')
        report.data['api']['keysBefore'] = client.list_keys()
        report.data['api']['domainsBefore'] = client.list_domains()
        report.note('api', 'Loaded keysBefore and domainsBefore')

        if args.mode == 'api':
            console(f'API-only test finished. Report: {report.path}')
            return 0

        _ssh_path, ssh_keygen_path = inspect_ssh(report)

        key_name = f'{args.prefix}-{int(time.time())}'
        domain_name = f'{args.prefix}-{int(time.time())}'
        marker = f'marker-{run_id}'
        key_dir = Path.home() / '.tunnellio' / 'keys'
        key_dir.mkdir(parents=True, exist_ok=True)
        key_path = key_dir / key_name
        pub_path = key_dir / f'{key_name}.pub'
        report.data['ssh']['generatedKeyPath'] = str(key_path)
        report.data['ssh']['generatedPubPath'] = str(pub_path)

        console(f'Generating temporary SSH key: {key_name}')
        proc = subprocess.run(
            [ssh_keygen_path, '-q', '-t', 'ed25519', '-N', '', '-f', str(key_path), '-C', key_name],
            capture_output=True,
            text=True,
            timeout=30,
        )
        report.data['ssh']['sshKeygenRun'] = {
            'returncode': proc.returncode,
            'stdout': proc.stdout[-2000:],
            'stderr': proc.stderr[-2000:],
        }
        report.note('ssh', f'ssh-keygen finished rc={proc.returncode}')
        if proc.returncode != 0:
            raise RuntimeError(f'ssh-keygen failed: {proc.stderr}')

        public_key = pub_path.read_text(encoding='utf-8').strip()

        console('Creating temporary key in Tunnellio')
        created_key = client.create_key(name=key_name, public_key=public_key, requested_lifetime_days=1)
        created_key_id = int(created_key['id'])
        report.data['persistentFlow']['createdKey'] = created_key
        report.note('persistent', f'Created key id={created_key_id}')

        console(f'Checking domain availability: {domain_name}')
        availability = client.check_domain_availability(domain_name)
        report.data['persistentFlow']['domainCheck'] = availability
        if not availability.get('available'):
            raise RuntimeError(f'Domain name is not available: {domain_name}')

        console('Creating temporary persistent domain')
        created_domain = client.create_domain(
            hostname=domain_name,
            key_id=created_key_id,
            local_port=args.local_port,
            note='local e2e test',
            requested_lifetime_days=1,
        )
        created_domain_id = int(created_domain['id'])
        report.data['persistentFlow']['createdDomain'] = created_domain
        report.note('persistent', f'Created domain id={created_domain_id}')

        console('Fetching connection profile for persistent domain')
        profile = client.get_connection_profile(
            domain_id=created_domain_id,
            local_host=args.local_host,
            local_port=args.local_port,
        )
        report.data['persistentFlow']['connectionProfile'] = profile

        planner = Planner(client, cfg)
        console('Building persistent planner result')
        persistent_plan = planner.build_plan(
            PlanOptions(
                domain_selector=f'existing:{domain_name}',
                local_host=args.local_host,
                local_port=args.local_port,
                mode='plan',
            )
        )
        report.data['persistentFlow']['planner'] = {
            'publicUrl': persistent_plan.connection_profile.public_url,
            'domain': persistent_plan.domain.to_dict(),
        }
        report.note('persistent', 'Planner built for persistent domain')

        console(f'Starting local HTTP server on {args.local_host}:{args.local_port}')
        MarkerHandler.marker = marker
        httpd = ReusableTCPServer((args.local_host, args.local_port), MarkerHandler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()

        console('Building ephemeral planner result')
        ephemeral_plan = planner.build_plan(
            PlanOptions(
                domain_selector='random',
                key_selector=f'existing:{key_name}',
                local_host=args.local_host,
                local_port=args.local_port,
                note='local e2e ephemeral test',
                mode='connect',
            )
        )
        if ephemeral_plan.session is None:
            raise RuntimeError('Ephemeral flow did not return a session')
        created_session_id = ephemeral_plan.session.id
        report.data['ephemeralFlow']['planner'] = {
            'session': ephemeral_plan.session.to_dict(),
            'domain': ephemeral_plan.domain.to_dict(),
            'publicUrl': ephemeral_plan.connection_profile.public_url,
            'sshCommand': ephemeral_plan.connection_profile.ssh_command,
            'sshArgs': ephemeral_plan.connection_profile.ssh_args,
        }
        report.note('ephemeral', f'Ephemeral session created id={created_session_id}')

        ssh_stdout = report_dir / 'ssh-stdout.log'
        ssh_stderr = report_dir / 'ssh-stderr.log'
        expanded_args = [os.path.expanduser(arg) if '~' in arg else arg for arg in ephemeral_plan.connection_profile.ssh_args]
        report.data['ephemeralFlow']['expandedSshArgs'] = expanded_args
        report.note('ephemeral', 'Expanded SSH args prepared')
        console('Starting SSH bridge process')
        console(f'SSH command: {ephemeral_plan.connection_profile.ssh_command}')
        with ssh_stdout.open('w', encoding='utf-8') as out, ssh_stderr.open('w', encoding='utf-8') as err:
            ssh_process = subprocess.Popen(expanded_args, stdout=out, stderr=err, cwd=ROOT, text=True)
            report.data['ephemeralFlow']['sshPid'] = ssh_process.pid
            report.note('ephemeral', f'SSH process started pid={ssh_process.pid}')
            probe = wait_for_url(
                ephemeral_plan.connection_profile.public_url,
                marker,
                insecure_tls=args.allow_insecure_public_url_probe,
                verbose=args.verbose,
            )
            report.data['ephemeralFlow']['probe'] = probe
            report.data['ephemeralFlow']['sshReturnCodeDuringProbe'] = ssh_process.poll()
            report.flush()

        if not report.data['ephemeralFlow']['probe'].get('ok'):
            report.data['ephemeralFlow']['sshStdoutTail'] = ssh_stdout.read_text(encoding='utf-8', errors='replace')[-4000:]
            report.data['ephemeralFlow']['sshStderrTail'] = ssh_stderr.read_text(encoding='utf-8', errors='replace')[-4000:]
            report.note('ephemeral', 'Probe failed before marker appeared')
            raise RuntimeError('Public URL did not serve the expected marker')

        console('Marker reached through public URL')
        if ssh_process and ssh_process.poll() is None:
            console('Stopping SSH bridge after successful probe')
            ssh_process.terminate()
            try:
                ssh_process.wait(timeout=10)
            except Exception:
                ssh_process.kill()
        ssh_process = None

        console(f'Completing ephemeral session {created_session_id}')
        completed = client.complete_session(created_session_id)
        report.data['ephemeralFlow']['completedSession'] = completed
        report.note('ephemeral', f'Completed session id={created_session_id}')
        created_session_id = None

        console('Full local e2e test finished successfully')
        print(f'Report: {report.path}', flush=True)
        return 0

    except Exception as exc:
        report.add_error('main', exc)
        raise
    finally:
        if ssh_process and ssh_process.poll() is None:
            console('Cleaning up SSH process')
            try:
                ssh_process.terminate()
                ssh_process.wait(timeout=10)
            except Exception:
                try:
                    ssh_process.kill()
                except Exception:
                    pass
        if httpd is not None:
            console('Stopping local HTTP server')
            try:
                httpd.shutdown()
                httpd.server_close()
            except Exception:
                pass

        cleanup_client = None
        cleanup_needed = any(value is not None for value in (created_session_id, created_domain_id, created_key_id))
        if cleanup_needed:
            try:
                cleanup_client, _, _ = probe_tls(
                    report,
                    token=token,
                    base_url=args.base_url,
                    state_dir=args.state_dir,
                    allow_fallback=True,
                    verbose=args.verbose,
                )
            except Exception as cleanup_exc:
                report.add_error('cleanup-client', cleanup_exc)
                cleanup_client = None

        if cleanup_client is not None and created_session_id is not None:
            console(f'Cleanup: completing session {created_session_id}')
            try:
                report.data['cleanup']['completedSessionOnExit'] = cleanup_client.complete_session(created_session_id)
            except Exception as exc:
                report.add_error('cleanup-session', exc)
        if cleanup_client is not None and created_domain_id is not None:
            console(f'Cleanup: deleting domain {created_domain_id}')
            try:
                report.data['cleanup']['deletedDomainOnExit'] = cleanup_client._request('/v1/domains/delete', {'domainId': created_domain_id})
            except Exception as exc:
                report.add_error('cleanup-domain', exc)
        if cleanup_client is not None and created_key_id is not None:
            console(f'Cleanup: deleting key {created_key_id}')
            try:
                report.data['cleanup']['deletedKeyOnExit'] = cleanup_client._request('/v1/keys/delete', {'keyId': created_key_id})
            except Exception as exc:
                report.add_error('cleanup-key', exc)
        if key_path and key_path.exists():
            console(f'Cleanup: removing local key {key_path}')
            key_path.unlink()
        if pub_path and pub_path.exists():
            console(f'Cleanup: removing local public key {pub_path}')
            pub_path.unlink()
        report.data['finishedAt'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        report.flush()


if __name__ == '__main__':
    raise SystemExit(main())
