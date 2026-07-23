from pathlib import Path
import textwrap

files = {
    'src/tunnellio/config.py': '''
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import AuthError, ValidationError

DEFAULT_BASE_URL = 'https://api.tunnellio.ru'
DEFAULT_STATE_DIR = Path.home() / '.tunnellio'
DEFAULT_LOCAL_HOST = '127.0.0.1'
DEFAULT_LOCAL_PORT = 3000


@dataclass(slots=True)
class RuntimeConfig:
    token: str
    base_url: str
    state_dir: Path
    profiles_dir: Path
    keys_dir: Path
    logs_dir: Path
    state_data_dir: Path
    insecure_tls: bool = False

    def ensure_directories(self) -> None:
        for path in [self.state_dir, self.profiles_dir, self.keys_dir, self.logs_dir, self.state_data_dir]:
            path.mkdir(parents=True, exist_ok=True)



def _load_config_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open('r', encoding='utf-8') as handle:
        return json.load(handle)



def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {'1', 'true', 'yes', 'on'}



def load_runtime_config(
    *,
    token: str | None,
    base_url: str | None,
    state_dir: str | None,
    insecure_tls: bool | None = None,
) -> RuntimeConfig:
    resolved_state_dir = Path(state_dir).expanduser() if state_dir else DEFAULT_STATE_DIR
    config_path = resolved_state_dir / 'config.json'
    config_file = _load_config_file(config_path)

    resolved_token = token or os.getenv('TUNNELLIO_API_TOKEN') or config_file.get('token')
    if not resolved_token:
        raise AuthError(
            'API token is required.',
            details={'hint': 'Provide --token, TUNNELLIO_API_TOKEN, or ~/.tunnellio/config.json.'},
        )

    resolved_base_url = (
        base_url
        or os.getenv('TUNNELLIO_BASE_URL')
        or config_file.get('baseUrl')
        or DEFAULT_BASE_URL
    )
    cleaned_base_url = str(resolved_base_url).rstrip('/')
    if not cleaned_base_url.startswith(('http://', 'https://')):
        raise ValidationError('Base URL must start with http:// or https://')

    resolved_insecure_tls = (
        insecure_tls
        if insecure_tls is not None
        else _parse_bool(os.getenv('TUNNELLIO_INSECURE_TLS')) or _parse_bool(config_file.get('insecureTls'))
    )

    runtime = RuntimeConfig(
        token=str(resolved_token),
        base_url=cleaned_base_url,
        state_dir=resolved_state_dir,
        profiles_dir=resolved_state_dir / 'profiles',
        keys_dir=resolved_state_dir / 'keys',
        logs_dir=resolved_state_dir / 'logs',
        state_data_dir=resolved_state_dir / 'state',
        insecure_tls=bool(resolved_insecure_tls),
    )
    runtime.ensure_directories()
    return runtime
''',
    'src/tunnellio/client.py': '''
from __future__ import annotations

import json
import ssl
from typing import Any
from urllib import error, request

from .config import RuntimeConfig
from .errors import ApiError, error_from_api


class ApiClient:
    def __init__(self, config: RuntimeConfig):
        self._config = config
        self._ssl_context = ssl._create_unverified_context() if config.insecure_tls else ssl.create_default_context()

    def _request(self, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f'{self._config.base_url}{path}'
        body = json.dumps(payload or {}).encode('utf-8')
        headers = {
            'Authorization': f'Bearer {self._config.token}',
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        }
        req = request.Request(url, data=body, headers=headers, method='POST')
        try:
            with request.urlopen(req, context=self._ssl_context) as response:
                raw = response.read().decode('utf-8')
                return self._parse_response(raw, status=response.status)
        except error.HTTPError as exc:
            raw = exc.read().decode('utf-8', errors='replace')
            return self._parse_response(raw, status=exc.code)
        except error.URLError as exc:
            raise ApiError('Unable to reach API server.', details={'reason': str(exc.reason)}) from exc

    def _parse_response(self, raw: str, *, status: int) -> dict[str, Any]:
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError as exc:
            raise ApiError('API returned invalid JSON.', details={'status': status, 'body': raw}) from exc

        if isinstance(payload, dict) and payload.get('ok') is True:
            data = payload.get('data')
            if isinstance(data, dict):
                return data
            raise ApiError('API success response did not contain a data object.', details={'response': payload})

        if isinstance(payload, dict) and payload.get('ok') is False and isinstance(payload.get('error'), dict):
            error_payload = payload['error']
            raise error_from_api(
                code=str(error_payload.get('code', 'api_error')),
                message=str(error_payload.get('message', 'API request failed.')),
                details=error_payload.get('details'),
                status=status,
            )

        raise ApiError('Unexpected API response.', details={'status': status, 'response': payload})

    def fetch_meta(self) -> dict[str, Any]:
        return self._request('/v1/meta', {})

    def fetch_capabilities(self) -> dict[str, Any]:
        return self._request('/v1/capabilities', {})

    def list_keys(self) -> list[dict[str, Any]]:
        return self._request('/v1/keys/list', {}).get('keys', [])

    def create_key(
        self,
        *,
        name: str,
        public_key: str,
        requested_lifetime_days: int | None = None,
    ) -> dict[str, Any]:
        payload = {
            'name': name,
            'publicKey': public_key,
            'requestedLifetimeDays': requested_lifetime_days,
        }
        return self._request('/v1/keys', payload).get('key', {})

    def list_domains(self) -> list[dict[str, Any]]:
        return self._request('/v1/domains/list', {}).get('domains', [])

    def check_domain_availability(self, hostname: str) -> dict[str, Any]:
        return self._request('/v1/domains/check', {'hostname': hostname})

    def create_domain(
        self,
        *,
        hostname: str,
        key_id: int,
        local_port: int,
        note: str | None = None,
        requested_lifetime_days: int | None = None,
    ) -> dict[str, Any]:
        payload = {
            'hostname': hostname,
            'keyId': key_id,
            'localPort': local_port,
            'note': note or '',
            'requestedLifetimeDays': requested_lifetime_days,
        }
        return self._request('/v1/domains', payload).get('domain', {})

    def get_connection_profile(
        self,
        *,
        domain_id: int,
        local_host: str | None = None,
        local_port: int | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {'domainId': domain_id}
        if local_host is not None:
            payload['localHost'] = local_host
        if local_port is not None:
            payload['localPort'] = local_port
        return self._request('/v1/domains/connection-profile', payload).get('connectionProfile', {})

    def create_ephemeral_session(
        self,
        *,
        key_id: int,
        local_host: str | None = None,
        local_port: int | None = None,
        note: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {'keyId': key_id}
        if local_host is not None:
            payload['localHost'] = local_host
        if local_port is not None:
            payload['localPort'] = local_port
        if note is not None:
            payload['note'] = note
        return self._request('/v1/sessions/ephemeral', payload)

    def complete_session(self, session_id: str) -> dict[str, Any]:
        return self._request('/v1/sessions/complete', {'sessionId': session_id})

    def get_launch_spec(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request('/v1/launch-spec', payload)
''',
    'src/tunnellio/cli.py': '''
from __future__ import annotations

import argparse
import signal
import subprocess
from typing import Sequence

from .client import ApiClient
from .config import DEFAULT_LOCAL_HOST, DEFAULT_LOCAL_PORT, load_runtime_config
from .errors import ExitCode, TunnellioError, ValidationError
from .models import Capabilities, Meta, PlanResult
from .output import OutputWriter
from .planner import PlanOptions, Planner



def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='tunnellio')
    parser.add_argument('--token')
    parser.add_argument('--base-url')
    parser.add_argument('--state-dir')
    parser.add_argument('--insecure-tls', action='store_true')

    subparsers = parser.add_subparsers(dest='command', required=True)

    meta_parser = subparsers.add_parser('meta')
    meta_parser.add_argument('--output', choices=['json', 'text'], default='json')

    capabilities_parser = subparsers.add_parser('capabilities')
    capabilities_parser.add_argument('--output', choices=['json', 'text'], default='json')

    for command_name in ('plan', 'connect'):
        sub = subparsers.add_parser(command_name)
        sub.add_argument('--output', choices=['json', 'text'], default='json' if command_name == 'plan' else 'text')
        sub.add_argument('--key', dest='key_selector')
        sub.add_argument('--public-key-path')
        sub.add_argument('--domain', dest='domain_selector')
        sub.add_argument('--key-lifetime-days', type=int)
        sub.add_argument('--domain-lifetime-days', type=int)
        sub.add_argument('--note')
        sub.add_argument('--local-host', default=DEFAULT_LOCAL_HOST)
        sub.add_argument('--local-port', type=int, default=DEFAULT_LOCAL_PORT)
        sub.add_argument('--save-profile', action='store_true')
        if command_name == 'connect':
            sub.add_argument('--run', action='store_true')

    return parser



def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    writer = OutputWriter(getattr(args, 'output', 'json'))

    try:
        config = load_runtime_config(
            token=args.token,
            base_url=args.base_url,
            state_dir=args.state_dir,
            insecure_tls=args.insecure_tls,
        )
        client = ApiClient(config)

        if args.command == 'meta':
            writer.write_meta(Meta.from_api(client.fetch_meta()))
            return int(ExitCode.SUCCESS)

        if args.command == 'capabilities':
            writer.write_capabilities(Capabilities.from_api(client.fetch_capabilities()))
            return int(ExitCode.SUCCESS)

        planner = Planner(client, config)
        options = PlanOptions(
            key_selector=args.key_selector,
            domain_selector=args.domain_selector,
            local_host=args.local_host,
            local_port=args.local_port,
            public_key_path=args.public_key_path,
            key_lifetime_days=args.key_lifetime_days,
            domain_lifetime_days=args.domain_lifetime_days,
            note=args.note,
            save_profile=args.save_profile,
            mode=args.command,
        )
        result = planner.build_plan(options)

        if args.command == 'connect' and args.run:
            execution = _run_launch_command(client, result)
            writer.write_exec_result(result, execution)
        else:
            writer.write_plan(result)
        return int(ExitCode.SUCCESS)
    except TunnellioError as exc:
        writer.write_error(exc)
        return int(exc.exit_code)
    except KeyboardInterrupt:
        writer.write_error(ValidationError('Interrupted by user.'))
        return int(ExitCode.GENERIC)



def _run_launch_command(client: ApiClient, result: PlanResult) -> dict[str, int | str | bool | None]:
    if not result.connection_profile.ssh_args:
        raise ValidationError('Connection profile did not contain sshArgs for execution.')

    process = subprocess.Popen(result.connection_profile.ssh_args)
    interrupted = False
    try:
        return_code = process.wait()
    except KeyboardInterrupt:
        interrupted = True
        process.send_signal(signal.SIGINT)
        return_code = process.wait()

    session_completed = False
    if result.session is not None and result.session.delete_on_disconnect:
        client.complete_session(result.session.id)
        session_completed = True

    execution: dict[str, int | str | bool | None] = {
        'pid': process.pid,
        'returnCode': return_code,
        'interrupted': interrupted,
        'sessionId': result.session.id if result.session else None,
        'sessionCompleted': session_completed,
    }
    return execution


if __name__ == '__main__':
    raise SystemExit(main())
''',
    'tests/test_cli.py': '''
from tunnellio.cli import build_parser


def test_plan_defaults() -> None:
    parser = build_parser()
    args = parser.parse_args(['plan'])
    assert args.command == 'plan'
    assert args.output == 'json'
    assert args.local_port == 3000



def test_connect_defaults() -> None:
    parser = build_parser()
    args = parser.parse_args(['connect'])
    assert args.command == 'connect'
    assert args.output == 'text'
    assert args.run is False
    assert args.local_port == 3000



def test_meta_defaults() -> None:
    parser = build_parser()
    args = parser.parse_args(['meta'])
    assert args.command == 'meta'
    assert args.output == 'json'



def test_insecure_tls_flag() -> None:
    parser = build_parser()
    args = parser.parse_args(['--insecure-tls', 'meta'])
    assert args.insecure_tls is True
''',
}

for path_str, content in files.items():
    path = Path(path_str)
    path.write_text(textwrap.dedent(content).lstrip('\n'), encoding='utf-8')

print(f'Wrote {len(files)} files')
