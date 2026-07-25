from __future__ import annotations

import argparse
import copy
import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Sequence

from .client import ApiClient, build_ssl_context
from .config import (
    DEFAULT_LOCAL_HOST,
    DEFAULT_LOCAL_PORT,
    build_launch_config_template,
    get_default_launch_config_path,
    load_launch_config,
    load_runtime_config,
    normalize_launch_config,
    resolve_state_dir,
    save_launch_config,
)
from .errors import ExitCode, TunnellioError, ValidationError
from .models import Capabilities, Meta, PlanResult, SessionSummary
from .output import OutputWriter
from .planner import PlanOptions, Planner

COMMAND_TO_SECTION = {
    'meta': 'meta',
    'capabilities': 'capabilities',
    'plan': 'plan',
    'connect': 'connect',
    'status': 'status',
    'stop': 'stop',
    'show-config': 'showConfig',
}

GLOBAL_FIELD_MAP = {
    'token': 'token',
    'base_url': 'baseUrl',
    'state_dir': 'stateDir',
    'insecure_tls': 'insecureTls',
    'verbose': 'verbose',
}

SECTION_FIELD_MAPS: dict[str, dict[str, str]] = {
    'meta': {
        'output': 'output',
    },
    'capabilities': {
        'output': 'output',
    },
    'plan': {
        'output': 'output',
        'key_selector': 'keySelector',
        'public_key_path': 'publicKeyPath',
        'domain_selector': 'domainSelector',
        'key_lifetime_days': 'keyLifetimeDays',
        'domain_lifetime_days': 'domainLifetimeDays',
        'note': 'note',
        'local_host': 'localHost',
        'local_port': 'localPort',
        'save_profile': 'saveProfile',
        'requested_auth_mode': 'requestedAuthMode',
        'connection_mode': 'connectionMode',
        'oauth_client_policy': 'oauthClientPolicy',
        'runtime_name': 'runtimeName',
        'use_discovery': 'useDiscovery',
        'session_strategy': 'sessionStrategy',
        'enable_pkce': 'enablePkce',
    },
    'connect': {
        'output': 'output',
        'key_selector': 'keySelector',
        'public_key_path': 'publicKeyPath',
        'domain_selector': 'domainSelector',
        'key_lifetime_days': 'keyLifetimeDays',
        'domain_lifetime_days': 'domainLifetimeDays',
        'note': 'note',
        'local_host': 'localHost',
        'local_port': 'localPort',
        'save_profile': 'saveProfile',
        'requested_auth_mode': 'requestedAuthMode',
        'connection_mode': 'connectionMode',
        'oauth_client_policy': 'oauthClientPolicy',
        'runtime_name': 'runtimeName',
        'use_discovery': 'useDiscovery',
        'session_strategy': 'sessionStrategy',
        'enable_pkce': 'enablePkce',
        'run': 'run',
        'watch': 'watch',
        'name': 'name',
        'health_path': 'healthPath',
        'health_interval': 'healthInterval',
        'health_timeout': 'healthTimeout',
        'health_failures': 'healthFailures',
        'restart_delay': 'restartDelay',
        'max_restarts': 'maxRestarts',
        'log_file': 'logFile',
        'status_file': 'statusFile',
        'stop_file': 'stopFile',
    },
    'status': {
        'output': 'output',
        'name': 'name',
        'pid': 'pid',
    },
    'stop': {
        'output': 'output',
        'all': 'all',
        'name': 'name',
        'pid': 'pid',
        'force': 'force',
        'grace_seconds': 'graceSeconds',
    },
    'show-config': {
        'output': 'output',
        'name': 'name',
        'pid': 'pid',
    },
}


class RuntimeLogger:
    def __init__(self, *, verbose: bool, log_file: str | None = None):
        self.verbose = verbose
        self.log_path = Path(log_file).expanduser() if log_file else None
        if self.log_path is not None:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, message: str) -> None:
        stamp = time.strftime('%H:%M:%S')
        line = f'[tunnellio-cli {stamp}] {message}'
        print(line, file=sys.stderr, flush=True)
        if self.log_path is not None:
            with self.log_path.open('a', encoding='utf-8') as handle:
                handle.write(line + '\n')

    def debug(self, message: str) -> None:
        if self.verbose:
            self.log(message)


class TunnelStopRequested(Exception):
    pass


class TunnelUnhealthy(Exception):
    pass


class TunnelProcessExited(Exception):
    def __init__(self, return_code: int | None):
        self.return_code = return_code
        super().__init__(f'SSH process exited with code {return_code}')



def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='tunnellio')
    parser.add_argument('--config')
    parser.add_argument('--config-overwrite', choices=['ask', 'yes', 'no'], default='ask')
    parser.add_argument('--token')
    parser.add_argument('--base-url')
    parser.add_argument('--state-dir')
    parser.add_argument('--insecure-tls', action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument('--verbose', action=argparse.BooleanOptionalAction, default=None)

    subparsers = parser.add_subparsers(dest='command', required=False)

    meta_parser = subparsers.add_parser('meta')
    meta_parser.add_argument('--output', choices=['json', 'text'], default=None)

    capabilities_parser = subparsers.add_parser('capabilities')
    capabilities_parser.add_argument('--output', choices=['json', 'text'], default=None)

    status_parser = subparsers.add_parser('status')
    status_parser.add_argument('--output', choices=['json', 'text'], default=None)
    status_parser.add_argument('--name', default=None)
    status_parser.add_argument('--pid', type=int, default=None)

    stop_parser = subparsers.add_parser('stop')
    stop_parser.add_argument('--output', choices=['json', 'text'], default=None)
    stop_parser.add_argument('--all', action='store_true', default=None)
    stop_parser.add_argument('--name', default=None)
    stop_parser.add_argument('--pid', type=int, default=None)
    stop_parser.add_argument('--force', action=argparse.BooleanOptionalAction, default=None)
    stop_parser.add_argument('--grace-seconds', type=int, default=None)

    runtime_config_parser = subparsers.add_parser('show-config')
    runtime_config_parser.add_argument('--output', choices=['json', 'text'], default=None)
    runtime_config_parser.add_argument('--name', default=None)
    runtime_config_parser.add_argument('--pid', type=int, default=None)

    for command_name in ('plan', 'connect'):
        sub = subparsers.add_parser(command_name)
        sub.add_argument('--output', choices=['json', 'text'], default=None)
        sub.add_argument('--key', dest='key_selector', default=None)
        sub.add_argument('--public-key-path', default=None)
        sub.add_argument('--domain', dest='domain_selector', default=None)
        sub.add_argument('--key-lifetime-days', type=int, default=None)
        sub.add_argument('--domain-lifetime-days', type=int, default=None)
        sub.add_argument('--note', default=None)
        sub.add_argument('--local-host', default=None)
        sub.add_argument('--local-port', type=int, default=None)
        sub.add_argument('--save-profile', action=argparse.BooleanOptionalAction, default=None)
        sub.add_argument('--requested-auth-mode', default=None)
        sub.add_argument('--connection-mode', default=None)
        sub.add_argument('--oauth-client-policy', default=None)
        sub.add_argument('--runtime-name', default=None)
        sub.add_argument('--use-discovery', action=argparse.BooleanOptionalAction, default=None)
        sub.add_argument('--session-strategy', default=None)
        sub.add_argument('--enable-pkce', action=argparse.BooleanOptionalAction, default=None)
        if command_name == 'connect':
            sub.add_argument('--run', action=argparse.BooleanOptionalAction, default=None)
            sub.add_argument('--watch', action=argparse.BooleanOptionalAction, default=None)
            sub.add_argument('--name', default=None)
            sub.add_argument('--health-path', default=None)
            sub.add_argument('--health-interval', type=int, default=None)
            sub.add_argument('--health-timeout', type=int, default=None)
            sub.add_argument('--health-failures', type=int, default=None)
            sub.add_argument('--restart-delay', type=int, default=None)
            sub.add_argument('--max-restarts', type=int, default=None)
            sub.add_argument('--log-file', default=None)
            sub.add_argument('--status-file', default=None)
            sub.add_argument('--stop-file', default=None)

    return parser


def log_progress(enabled: bool, message: str) -> None:
    if enabled:
        stamp = time.strftime('%H:%M:%S')
        print(f'[tunnellio-cli {stamp}] {message}', file=sys.stderr, flush=True)


def _expand_optional_path(path: str | None) -> Path | None:
    return Path(path).expanduser() if path else None


def _slugify_runtime_name(value: str) -> str:
    cleaned = ''.join(ch if ch.isalnum() or ch in {'-', '_'} else '-' for ch in value.strip())
    collapsed = '-'.join(part for part in cleaned.split('-') if part)
    return collapsed[:80] or f'tunnel-{int(time.time())}'


def _generate_runtime_name(domain_selector: str | None, local_port: int | None) -> str:
    parts = ['tunnel']
    if domain_selector:
        parts.append(domain_selector)
    elif local_port is not None:
        parts.append(str(local_port))
    parts.append(str(int(time.time())))
    return _slugify_runtime_name('-'.join(parts))


def _ensure_connect_name(config_payload: dict[str, Any]) -> dict[str, Any]:
    if config_payload.get('command') != 'connect':
        return config_payload
    candidate = copy.deepcopy(config_payload)
    connect = candidate.setdefault('connect', {})
    raw_name = connect.get('name')
    if raw_name:
        connect['name'] = _slugify_runtime_name(str(raw_name))
    else:
        connect['name'] = _generate_runtime_name(
            connect.get('domainSelector'),
            connect.get('localPort'),
        )
    return candidate


def _default_runtime_paths(runtime_dir: Path, runtime_name: str) -> tuple[Path, Path, Path]:
    base = runtime_dir / runtime_name
    return base.with_suffix('.json'), base.with_suffix('.stop'), base.with_suffix('.config.json')


def _make_health_url(public_url: str, health_path: str) -> str:
    if not health_path or health_path == '/':
        return public_url
    base = public_url if public_url.endswith('/') else public_url + '/'
    return urllib.parse.urljoin(base, health_path.lstrip('/'))


def _write_status(status_path: Path | None, payload: dict[str, Any]) -> None:
    if status_path is None:
        return
    status_path.parent.mkdir(parents=True, exist_ok=True)
    prepared = dict(payload)
    prepared['updatedAt'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    status_path.write_text(json.dumps(prepared, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def _load_status_file(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return None


def _load_runtime_statuses(runtime_dir: Path) -> list[dict[str, Any]]:
    statuses: list[dict[str, Any]] = []
    for path in sorted(runtime_dir.glob('*.json')):
        if path.name.endswith('.config.json'):
            continue
        payload = _load_status_file(path)
        if payload is None:
            continue
        payload['statusFile'] = str(path)
        statuses.append(payload)
    return statuses


def _find_runtime_status(
    statuses: list[dict[str, Any]],
    *,
    name: str | None = None,
    pid: int | None = None,
) -> list[dict[str, Any]]:
    if name:
        return [item for item in statuses if item.get('name') == name]
    if pid is not None:
        return [item for item in statuses if item.get('pid') == pid]
    return statuses


def _write_runtime_connection_snapshot(
    path: Path,
    *,
    runtime_name: str,
    execution_config: dict[str, Any],
    result: PlanResult,
    status_path: Path,
    stop_path: Path,
) -> None:
    payload = {
        'runtimeName': runtime_name,
        'savedAt': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'statusFile': str(status_path),
        'stopFile': str(stop_path),
        'launchConfig': execution_config,
        'auth': result.auth,
        'runtime': {
            **(result.runtime or {}),
            'name': runtime_name,
            'statusFile': str(status_path),
            'stopFile': str(stop_path),
        },
        'transport': {
            'publicUrl': result.connection_profile.public_url,
            'sshHost': result.connection_profile.ssh_host,
            'sshPort': result.connection_profile.ssh_port,
            'sshUser': result.connection_profile.ssh_user,
            'remoteHostname': result.connection_profile.remote_hostname,
            'localHost': result.connection_profile.local_host,
            'localPort': result.connection_profile.local_port,
        },
        'connection': result.to_dict(),
    }
    if result.session is not None:
        payload['session'] = result.session.to_dict()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def _probe_health_url(url: str, *, insecure_tls: bool, timeout: int, verbose: bool) -> tuple[bool, str, str]:
    context, backend = build_ssl_context(insecure_tls=insecure_tls)
    try:
        with urllib.request.urlopen(url, timeout=timeout, context=context) as response:
            response.read(256)
            return True, f'HTTP {response.status}', backend
    except urllib.error.HTTPError as exc:
        return False, f'HTTP {exc.code}', backend
    except Exception as exc:
        if verbose:
            return False, repr(exc), backend
        return False, exc.__class__.__name__, backend


def _sleep_with_stop_check(seconds: int, stop_file: Path | None) -> None:
    for _ in range(max(seconds, 0)):
        if stop_file is not None and stop_file.exists():
            raise TunnelStopRequested()
        time.sleep(1)


def _serialize_session(session: SessionSummary | None) -> dict[str, Any]:
    if session is None:
        return {}
    return {
        'sessionId': session.id,
        'sessionStatus': session.status,
        'resumeToken': session.resume_token,
        'proxySessionId': session.proxy_session_id,
        'routeState': session.route_state,
        'lastHeartbeatAt': session.last_heartbeat_at,
        'authMode': session.auth_mode,
        'connectionMode': session.connection_mode,
    }


def _complete_ephemeral_session(client: ApiClient, session: SessionSummary | None, logger: RuntimeLogger) -> bool:
    if session is None or not session.delete_on_disconnect:
        return False
    logger.log(f'Completing ephemeral session {session.id}')
    client.complete_session(session.id)
    return True


def _open_runtime_session(
    client: ApiClient,
    result: PlanResult,
    *,
    logger: RuntimeLogger,
    runtime_name: str,
    resume_execution: dict[str, Any] | None = None,
) -> tuple[SessionSummary | None, str]:
    if resume_execution:
        resume_token = resume_execution.get('resumeToken')
        session_id = resume_execution.get('sessionId')
        if resume_token or session_id:
            logger.log('Resuming server-side session')
            payload = {
                'runtimeName': runtime_name,
                'publicUrl': result.connection_profile.public_url,
            }
            session_data = client.resume_session(
                session_id=str(session_id) if session_id else None,
                resume_token=str(resume_token) if resume_token else None,
                payload=payload,
            )
            return SessionSummary.from_api(session_data), 'resume'

    if result.session_open_payload:
        logger.log('Opening server-side session')
        session_data = client.open_session(result.session_open_payload)
        return SessionSummary.from_api(session_data), 'open'

    if result.session is not None:
        return result.session, 'launch_spec'
    return None, 'none'


def _heartbeat_runtime_session(
    client: ApiClient,
    session: SessionSummary | None,
    *,
    runtime_name: str,
    public_url: str,
) -> SessionSummary | None:
    if session is None:
        return None
    session_data = client.heartbeat_session(
        session_id=session.id,
        resume_token=session.resume_token,
        payload={
            'runtimeName': runtime_name,
            'publicUrl': public_url,
        },
    )
    return SessionSummary.from_api(session_data)


def _close_runtime_session(
    client: ApiClient,
    session: SessionSummary | None,
    *,
    logger: RuntimeLogger,
    reason: str,
) -> bool:
    if session is None:
        return False
    try:
        client.close_session(session_id=session.id, resume_token=session.resume_token, reason=reason)
        logger.log(f'Closed server-side session {session.id}')
        return True
    except Exception as exc:
        logger.log(f'Failed to close session {session.id}: {exc}')
        return False


def _announce_plan(logger: RuntimeLogger, result: PlanResult, health_url: str) -> None:
    logger.log(f'Runtime name: {result.connection_profile.remote_hostname if False else ""}')
    logger.log(f'Public URL: {result.connection_profile.public_url}')
    logger.log(f'Health URL: {health_url}')
    logger.log(
        'SSH target: '
        f'{result.connection_profile.ssh_user}@{result.connection_profile.ssh_host}:{result.connection_profile.ssh_port}'
    )
    logger.debug(f'SSH args: {result.connection_profile.ssh_args}')


def _signal_process(pid: int, *, force: bool) -> bool:
    try:
        sig = signal.SIGTERM if force else signal.SIGINT
        os.kill(pid, sig)
        return True
    except Exception:
        return False


def _request_stop_for_status(status: dict[str, Any], *, force: bool, grace_seconds: int) -> dict[str, Any]:
    stop_file_str = status.get('stopFile')
    pid = status.get('pid')
    stop_requested = False
    force_signal_sent = False
    if stop_file_str:
        stop_path = Path(str(stop_file_str)).expanduser()
        stop_path.parent.mkdir(parents=True, exist_ok=True)
        stop_path.write_text('stop\n', encoding='utf-8')
        stop_requested = True
    if force and isinstance(pid, int):
        time.sleep(max(grace_seconds, 0))
        force_signal_sent = _signal_process(pid, force=True)
    return {
        'name': status.get('name'),
        'pid': pid,
        'state': status.get('state'),
        'publicUrl': status.get('publicUrl'),
        'stopRequested': stop_requested,
        'forceSignalSent': force_signal_sent,
        'statusFile': status.get('statusFile'),
    }


def _extract_explicit_fields(args: argparse.Namespace) -> dict[str, Any]:
    explicit: dict[str, Any] = {}
    for name, value in vars(args).items():
        if name in {'config', 'config_overwrite'}:
            continue
        if value is not None:
            explicit[name] = value
    return explicit


def _apply_explicit_overrides(base_config: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    candidate = copy.deepcopy(base_config)
    explicit = _extract_explicit_fields(args)
    if args.command is not None:
        candidate['command'] = args.command
    for arg_name, config_name in GLOBAL_FIELD_MAP.items():
        if arg_name in explicit:
            candidate['global'][config_name] = explicit[arg_name]
    effective_command = candidate.get('command')
    if effective_command in SECTION_FIELD_MAPS:
        section_key = COMMAND_TO_SECTION[effective_command]
        section = candidate.setdefault(section_key, {})
        for arg_name, config_name in SECTION_FIELD_MAPS[effective_command].items():
            if arg_name in explicit:
                section[config_name] = explicit[arg_name]
    return candidate


def _is_interactive() -> bool:
    return bool(sys.stdin and sys.stdin.isatty())


def _prompt_overwrite(path: Path) -> bool:
    if not _is_interactive():
        raise ValidationError(
            'Config already exists and overwrite confirmation is required.',
            details={
                'path': str(path),
                'hint': 'Use --config-overwrite yes to rewrite or --config-overwrite no to keep the file unchanged for this run.',
            },
        )
    answer = input(f'Config {path} already exists. Overwrite it with current CLI parameters? [y/N]: ').strip().lower()
    return answer in {'y', 'yes'}


def _resolve_selected_config_path(args: argparse.Namespace) -> tuple[Path, bool, Path]:
    bootstrap_state_dir = resolve_state_dir(args.state_dir)
    if args.config:
        return Path(args.config).expanduser(), True, bootstrap_state_dir
    return get_default_launch_config_path(bootstrap_state_dir), False, bootstrap_state_dir


def _prepare_execution_config(args: argparse.Namespace) -> tuple[dict[str, Any], Path | None, bool]:
    selected_path, explicit_config, bootstrap_state_dir = _resolve_selected_config_path(args)
    config_exists = selected_path.exists()
    base_config = load_launch_config(selected_path, state_dir_hint=bootstrap_state_dir) if config_exists else build_launch_config_template(bootstrap_state_dir)

    if args.command is None and not config_exists:
        raise ValidationError(
            'No saved config was found and no command was provided.',
            details={'hint': 'Run the client once with parameters to seed the default config, or pass --config with a client config path.'},
        )

    candidate_config = normalize_launch_config(_apply_explicit_overrides(base_config, args), state_dir_hint=bootstrap_state_dir)
    candidate_config = _ensure_connect_name(candidate_config)
    config_would_change = candidate_config != base_config

    if explicit_config:
        if config_exists and config_would_change:
            decision = args.config_overwrite
            overwrite = _prompt_overwrite(selected_path) if decision == 'ask' else decision == 'yes'
            if overwrite:
                saved = save_launch_config(selected_path, candidate_config, state_dir_hint=bootstrap_state_dir)
                return saved, selected_path, True
            return candidate_config, None, False
        if not config_exists:
            saved = save_launch_config(selected_path, candidate_config, state_dir_hint=bootstrap_state_dir)
            return saved, selected_path, True
        return candidate_config, selected_path, False

    if (not config_exists) or config_would_change:
        saved = save_launch_config(selected_path, candidate_config, state_dir_hint=bootstrap_state_dir)
        return saved, selected_path, True
    return candidate_config, selected_path, False


def _writer_for_config(config_payload: dict[str, Any]) -> OutputWriter:
    command = str(config_payload.get('command'))
    section_key = COMMAND_TO_SECTION[command]
    output = str(config_payload.get(section_key, {}).get('output', 'json'))
    return OutputWriter(output)


def _print_runtime_statuses(writer: OutputWriter, statuses: list[dict[str, Any]]) -> None:
    if writer.output_format == 'json':
        writer.write_payload({'runtimes': statuses})
        return
    if not statuses:
        print('No managed runtimes found.')
        return
    for item in statuses:
        print(f"- {item.get('name', 'unnamed')}")
        print(f"  state: {item.get('state')}")
        if item.get('pid') is not None:
            print(f"  pid: {item.get('pid')}")
        if item.get('publicUrl'):
            print(f"  public URL: {item.get('publicUrl')}")
        if item.get('healthUrl'):
            print(f"  health URL: {item.get('healthUrl')}")
        if item.get('reason'):
            print(f"  reason: {item.get('reason')}")
        if item.get('runtimeConfigFile'):
            print(f"  runtime config: {item.get('runtimeConfigFile')}")
        if item.get('statusFile'):
            print(f"  status file: {item.get('statusFile')}")
        if item.get('stopFile'):
            print(f"  stop file: {item.get('stopFile')}")


def _run_once(
    client: ApiClient,
    result: PlanResult,
    *,
    logger: RuntimeLogger,
    insecure_tls: bool,
    runtime_name: str,
    runtime_config_path: Path,
    health_path: str,
    health_interval: int,
    health_timeout: int,
    health_failures: int,
    status_path: Path,
    stop_file: Path,
    resume_execution: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if stop_file.exists():
        stop_file.unlink()
    if not result.connection_profile.ssh_args:
        raise ValidationError('Connection profile did not contain sshArgs for execution.')

    health_url = _make_health_url(result.connection_profile.public_url, health_path)
    logger.log(f'Runtime name: {runtime_name}')
    _announce_plan(logger, result, health_url)

    active_session, session_action = _open_runtime_session(
        client,
        result,
        logger=logger,
        runtime_name=runtime_name,
        resume_execution=resume_execution,
    )
    result.session = active_session

    expanded_args = [os.path.expanduser(arg) if '~' in arg else arg for arg in result.connection_profile.ssh_args]
    logger.log('Launching SSH bridge')
    process = subprocess.Popen(expanded_args)
    logger.log(f'SSH pid: {process.pid}')

    _write_status(
        status_path,
        {
            'name': runtime_name,
            'state': 'starting',
            'pid': process.pid,
            'publicUrl': result.connection_profile.public_url,
            'healthUrl': health_url,
            'tlsBackend': client.tls_backend,
            'mode': 'connect',
            'sessionAction': session_action,
            'stopFile': str(stop_file),
            'runtimeConfigFile': str(runtime_config_path),
            **_serialize_session(active_session),
        },
    )

    consecutive_failures = 0
    healthy_once = False
    stop_requested = False
    interrupted = False
    reason = 'process_exit'
    return_code: int | None = None
    session_completed = False
    session_closed = False

    try:
        while True:
            if stop_file.exists():
                stop_requested = True
                reason = 'stop_file'
                raise TunnelStopRequested()

            if process.poll() is not None:
                return_code = process.returncode
                reason = 'process_exit'
                raise TunnelProcessExited(return_code)

            ok, detail, tls_backend = _probe_health_url(
                health_url,
                insecure_tls=insecure_tls,
                timeout=health_timeout,
                verbose=logger.verbose,
            )
            if ok:
                if active_session is not None:
                    try:
                        active_session = _heartbeat_runtime_session(
                            client,
                            active_session,
                            runtime_name=runtime_name,
                            public_url=result.connection_profile.public_url,
                        )
                        result.session = active_session
                    except Exception as exc:
                        reason = 'session_heartbeat_failed'
                        logger.log(f'Session heartbeat failed: {exc}')
                        _write_status(
                            status_path,
                            {
                                'name': runtime_name,
                                'state': 'degraded',
                                'pid': process.pid,
                                'publicUrl': result.connection_profile.public_url,
                                'healthUrl': health_url,
                                'tlsBackend': tls_backend,
                                'healthy': False,
                                'detail': str(exc),
                                'reason': reason,
                                'stopFile': str(stop_file),
                                'runtimeConfigFile': str(runtime_config_path),
                                **_serialize_session(active_session),
                            },
                        )
                        raise TunnelUnhealthy()
                if not healthy_once or consecutive_failures > 0:
                    logger.log(f'Health OK via {tls_backend}: {detail}')
                healthy_once = True
                consecutive_failures = 0
                _write_status(
                    status_path,
                    {
                        'name': runtime_name,
                        'state': 'healthy',
                        'pid': process.pid,
                        'publicUrl': result.connection_profile.public_url,
                        'healthUrl': health_url,
                        'tlsBackend': tls_backend,
                        'healthy': True,
                        'detail': detail,
                        'sessionAction': session_action,
                        'stopFile': str(stop_file),
                        'runtimeConfigFile': str(runtime_config_path),
                        **_serialize_session(active_session),
                    },
                )
            else:
                consecutive_failures += 1
                logger.log(f'Health failed via {tls_backend} ({consecutive_failures}/{health_failures}): {detail}')
                _write_status(
                    status_path,
                    {
                        'name': runtime_name,
                        'state': 'unhealthy',
                        'pid': process.pid,
                        'publicUrl': result.connection_profile.public_url,
                        'healthUrl': health_url,
                        'tlsBackend': tls_backend,
                        'healthy': False,
                        'detail': detail,
                        'consecutiveFailures': consecutive_failures,
                        'stopFile': str(stop_file),
                        'runtimeConfigFile': str(runtime_config_path),
                        **_serialize_session(active_session),
                    },
                )
                if consecutive_failures >= health_failures:
                    reason = 'health_failures'
                    raise TunnelUnhealthy()

            _sleep_with_stop_check(health_interval, stop_file)
    except KeyboardInterrupt:
        interrupted = True
        reason = 'keyboard_interrupt'
        logger.log('Interrupted by user')
    except TunnelStopRequested:
        stop_requested = True
        reason = 'stop_file'
        logger.log('Stop requested')
    except TunnelUnhealthy:
        logger.log('Health failure threshold reached; restarting tunnel')
    except TunnelProcessExited as exc:
        logger.log(f'SSH process exited with code {exc.return_code}')
    finally:
        if process.poll() is None:
            logger.log('Stopping SSH bridge')
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                logger.log('SSH did not stop gracefully; killing process')
                process.kill()
                process.wait(timeout=10)
        return_code = process.returncode
        session_closed = _close_runtime_session(client, active_session, logger=logger, reason=reason)
        session_completed = _complete_ephemeral_session(client, active_session, logger)
        _write_status(
            status_path,
            {
                'name': runtime_name,
                'state': 'stopped',
                'pid': process.pid,
                'publicUrl': result.connection_profile.public_url,
                'healthUrl': health_url,
                'healthyOnce': healthy_once,
                'reason': reason,
                'returnCode': return_code,
                'sessionAction': session_action,
                'sessionClosed': session_closed,
                'sessionCompleted': session_completed,
                'stopFile': str(stop_file),
                'runtimeConfigFile': str(runtime_config_path),
                **_serialize_session(active_session),
            },
        )

    return {
        'pid': process.pid,
        'returnCode': return_code,
        'interrupted': interrupted,
        'stopRequested': stop_requested,
        'sessionAction': session_action,
        'sessionClosed': session_closed,
        'sessionCompleted': session_completed,
        'healthyOnce': healthy_once,
        'reason': reason,
        'runtimeName': runtime_name,
        'statusFile': str(status_path),
        'stopFile': str(stop_file),
        'runtimeConfigFile': str(runtime_config_path),
        **_serialize_session(active_session),
    }


def _run_watch_loop(
    planner: Planner,
    client: ApiClient,
    options: PlanOptions,
    *,
    logger: RuntimeLogger,
    insecure_tls: bool,
    runtime_name: str,
    runtime_config_path: Path,
    health_path: str,
    health_interval: int,
    health_timeout: int,
    health_failures: int,
    restart_delay: int,
    max_restarts: int,
    status_path: Path,
    stop_file: Path,
) -> tuple[PlanResult, dict[str, Any]]:
    restart_count = 0
    last_result: PlanResult | None = None
    last_execution: dict[str, Any] | None = None

    while True:
        if max_restarts and restart_count > max_restarts:
            raise ValidationError('Maximum restart count reached.', details={'maxRestarts': max_restarts})

        if stop_file.exists():
            logger.log('Stop requested before launch')
            _write_status(status_path, {'name': runtime_name, 'state': 'stopped', 'reason': 'stop_file_before_launch', 'stopFile': str(stop_file), 'runtimeConfigFile': str(runtime_config_path)})
            if last_result is None or last_execution is None:
                raise ValidationError('Tunnel was stopped before launch.', details={'stopFile': str(stop_file)})
            return last_result, last_execution

        logger.log(f'Preparing launch plan (attempt {restart_count + 1})')
        result = planner.build_plan(options)
        try:
            execution = _run_once(
                client,
                result,
                logger=logger,
                insecure_tls=insecure_tls,
                runtime_name=runtime_name,
                runtime_config_path=runtime_config_path,
                health_path=health_path,
                health_interval=health_interval,
                health_timeout=health_timeout,
                health_failures=health_failures,
                status_path=status_path,
                stop_file=stop_file,
                resume_execution=last_execution,
            )
        except TunnellioError as exc:
            restart_count += 1
            logger.log(f'Launch failed: {exc}')
            _write_status(
                status_path,
                {
                    'name': runtime_name,
                    'state': 'restarting',
                    'restartCount': restart_count,
                    'reason': getattr(exc, 'code', 'launch_error'),
                    'error': exc.to_payload().get('error'),
                    'stopFile': str(stop_file),
                    'runtimeConfigFile': str(runtime_config_path),
                },
            )
            if max_restarts and restart_count > max_restarts:
                raise
            _sleep_with_stop_check(restart_delay, stop_file)
            continue
        last_result = result
        last_execution = execution

        if execution.get('reason') in {'keyboard_interrupt', 'stop_file'}:
            return result, execution

        restart_count += 1
        logger.log(f'Restarting tunnel in {restart_delay}s (restart #{restart_count})')
        _write_status(
            status_path,
            {
                'name': runtime_name,
                'state': 'restarting',
                'restartCount': restart_count,
                'reason': execution.get('reason'),
                'publicUrl': result.connection_profile.public_url,
                'stopFile': str(stop_file),
                'runtimeConfigFile': str(runtime_config_path),
                **_serialize_session(result.session),
            },
        )
        _sleep_with_stop_check(restart_delay, stop_file)


def _execute_from_config(config_payload: dict[str, Any]) -> int:
    command = str(config_payload.get('command'))
    if command not in COMMAND_TO_SECTION:
        raise ValidationError('Saved config does not contain a supported command.', details={'command': command})

    section_key = COMMAND_TO_SECTION[command]
    writer = _writer_for_config(config_payload)
    global_config = dict(config_payload.get('global', {}))
    verbose = bool(global_config.get('verbose'))
    if verbose:
        os.environ['TUNNELLIO_VERBOSE'] = '1'

    runtime = load_runtime_config(
        token=global_config.get('token'),
        base_url=global_config.get('baseUrl'),
        state_dir=global_config.get('stateDir'),
        insecure_tls=global_config.get('insecureTls'),
        require_token=command not in {'status', 'stop', 'show-config'},
    )

    if command == 'status':
        settings = dict(config_payload.get('status', {}))
        statuses = _find_runtime_status(
            _load_runtime_statuses(runtime.runtime_dir),
            name=settings.get('name'),
            pid=settings.get('pid'),
        )
        _print_runtime_statuses(writer, statuses)
        return int(ExitCode.SUCCESS)

    if command == 'stop':
        settings = dict(config_payload.get('stop', {}))
        all_flag = bool(settings.get('all')) and not settings.get('name') and settings.get('pid') is None
        statuses = _find_runtime_status(
            _load_runtime_statuses(runtime.runtime_dir),
            name=settings.get('name'),
            pid=settings.get('pid'),
        ) if not all_flag else _load_runtime_statuses(runtime.runtime_dir)
        if not statuses:
            raise ValidationError('No matching managed runtimes found.')
        results = [
            _request_stop_for_status(
                item,
                force=bool(settings.get('force')),
                grace_seconds=int(settings.get('graceSeconds') or 0),
            )
            for item in statuses
        ]
        writer.write_payload({'stopped': results}, title='Stop results')
        return int(ExitCode.SUCCESS)

    if command == 'show-config':
        settings = dict(config_payload.get('showConfig', {}))
        statuses = _find_runtime_status(
            _load_runtime_statuses(runtime.runtime_dir),
            name=settings.get('name'),
            pid=settings.get('pid'),
        )
        if not statuses:
            raise ValidationError('No matching managed runtimes found.')
        if len(statuses) > 1:
            raise ValidationError('More than one runtime matched. Narrow the selection by name or pid.')
        runtime_config_file = statuses[0].get('runtimeConfigFile')
        if not runtime_config_file:
            raise ValidationError('Runtime config snapshot was not found for the selected tunnel.')
        payload = _load_status_file(Path(str(runtime_config_file)))
        if payload is None:
            raise ValidationError('Runtime config snapshot file could not be read.', details={'path': runtime_config_file})
        writer.write_payload(payload, title='Runtime config')
        return int(ExitCode.SUCCESS)

    client = ApiClient(runtime)

    if command == 'meta':
        log_progress(verbose, 'Fetching API metadata')
        writer.write_meta(Meta.from_api(client.fetch_meta()))
        return int(ExitCode.SUCCESS)

    if command == 'capabilities':
        log_progress(verbose, 'Fetching capabilities')
        writer.write_capabilities(Capabilities.from_api(client.fetch_capabilities()))
        return int(ExitCode.SUCCESS)

    settings = dict(config_payload.get(section_key, {}))
    if command == 'connect' and settings.get('watch') and not settings.get('run'):
        raise ValidationError('--watch requires run=true in config.')

    planner = Planner(client, runtime)
    options = PlanOptions(
        key_selector=settings.get('keySelector'),
        domain_selector=settings.get('domainSelector'),
        local_host=str(settings.get('localHost') or DEFAULT_LOCAL_HOST),
        local_port=int(settings.get('localPort') or DEFAULT_LOCAL_PORT),
        public_key_path=settings.get('publicKeyPath'),
        key_lifetime_days=settings.get('keyLifetimeDays'),
        domain_lifetime_days=settings.get('domainLifetimeDays'),
        note=settings.get('note'),
        save_profile=bool(settings.get('saveProfile')),
        mode=command,
        requested_auth_mode=settings.get('requestedAuthMode'),
        connection_mode=settings.get('connectionMode'),
        oauth_client_policy=settings.get('oauthClientPolicy'),
        runtime_name=settings.get('runtimeName') or settings.get('name'),
        use_discovery=bool(settings.get('useDiscovery', True)),
        session_strategy=settings.get('sessionStrategy'),
        enable_pkce=bool(settings.get('enablePkce')),
    )
    log_progress(verbose, f'Building {command} plan')
    result = planner.build_plan(options)

    if command == 'connect' and settings.get('run'):
        runtime_name = str(settings.get('runtimeName') or settings.get('name') or _generate_runtime_name(settings.get('domainSelector'), settings.get('localPort')))
        status_path_default, stop_path_default, runtime_config_path_default = _default_runtime_paths(runtime.runtime_dir, runtime_name)
        status_path = _expand_optional_path(settings.get('statusFile')) or status_path_default
        stop_file = _expand_optional_path(settings.get('stopFile')) or stop_path_default
        runtime_config_path = runtime_config_path_default
        _write_runtime_connection_snapshot(
            runtime_config_path,
            runtime_name=runtime_name,
            execution_config=config_payload,
            result=result,
            status_path=status_path,
            stop_path=stop_file,
        )
        logger = RuntimeLogger(verbose=verbose, log_file=settings.get('logFile'))
        if settings.get('watch'):
            logger.log('Starting supervised tunnel mode')
            result, execution = _run_watch_loop(
                planner,
                client,
                options,
                logger=logger,
                insecure_tls=bool(runtime.insecure_tls),
                runtime_name=runtime_name,
                runtime_config_path=runtime_config_path,
                health_path=str(settings.get('healthPath') or '/'),
                health_interval=int(settings.get('healthInterval') or 15),
                health_timeout=int(settings.get('healthTimeout') or 10),
                health_failures=int(settings.get('healthFailures') or 3),
                restart_delay=int(settings.get('restartDelay') or 5),
                max_restarts=int(settings.get('maxRestarts') or 0),
                status_path=status_path,
                stop_file=stop_file,
            )
        else:
            logger.log('Starting one-shot tunnel mode')
            execution = _run_once(
                client,
                result,
                logger=logger,
                insecure_tls=bool(runtime.insecure_tls),
                runtime_name=runtime_name,
                runtime_config_path=runtime_config_path,
                health_path=str(settings.get('healthPath') or '/'),
                health_interval=int(settings.get('healthInterval') or 15),
                health_timeout=int(settings.get('healthTimeout') or 10),
                health_failures=int(settings.get('healthFailures') or 3),
                status_path=status_path,
                stop_file=stop_file,
            )
        writer.write_exec_result(result, execution)
        return int(ExitCode.SUCCESS)

    writer.write_plan(result)
    return int(ExitCode.SUCCESS)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        config_payload, config_path, config_written = _prepare_execution_config(args)
        if config_written and config_path is not None:
            log_progress(bool(config_payload.get('global', {}).get('verbose')), f'Updated config: {config_path}')
        return _execute_from_config(config_payload)
    except TunnellioError as exc:
        writer = OutputWriter('json' if (getattr(args, 'output', None) == 'json') else 'text')
        writer.write_error(exc)
        return int(exc.exit_code)
    except KeyboardInterrupt:
        writer = OutputWriter('text')
        writer.write_error(ValidationError('Interrupted by user.'))
        return int(ExitCode.GENERIC)


if __name__ == '__main__':
    raise SystemExit(main())
