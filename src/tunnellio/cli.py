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

from .bridge import TcpBridgeProcess, launch_bridge
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
from .errors import ExitCode, PlanRequiredError, TunnellioError, ValidationError
from .models import Capabilities, DiscoveryMetadata, Meta, PlanResult, SessionSummary
from .oauth import OAuthTokenRecord, build_token_storage_name, generate_pkce_pair, load_token_record, save_token_record
from .output import OutputWriter
from .modes import (
    MODE_SSH_STABLE,
    MODE_TCP_RANDOM,
    MODE_TCP_STABLE,
    describe_modes,
    resolve_mode,
)
from .planner import PlanOptions, Planner, _split_selector

COMMAND_TO_SECTION = {
    'meta': 'meta',
    'capabilities': 'capabilities',
    'plan': 'plan',
    'connect': 'connect',
    'bridge': 'bridge',
    'status': 'status',
    'stop': 'stop',
    'show-config': 'showConfig',
    'oauth-login': 'oauthLogin',
    'oauth-refresh': 'oauthRefresh',
    'oauth-introspect': 'oauthIntrospect',
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
        'transport': 'transport',
        'tcp_bridge_password': 'tcpBridgePassword',
        'bridge_key': 'bridgeKey',
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
        'transport': 'transport',
        'tcp_bridge_password': 'tcpBridgePassword',
        'bridge_key': 'bridgeKey',
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
    'bridge': {
        'output': 'output',
        'domain_selector': 'domainSelector',
        'note': 'note',
        'local_host': 'localHost',
        'local_port': 'localPort',
        'save_profile': 'saveProfile',
        'runtime_name': 'runtimeName',
        'tcp_bridge_password': 'tcpBridgePassword',
        'bridge_key': 'bridgeKey',
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
    'oauth-login': {
        'output': 'output',
        'domain_selector': 'domainSelector',
        'client_id': 'clientId',
        'client_secret': 'clientSecret',
        'redirect_uri': 'redirectUri',
        'scopes': 'scopes',
        'discovery_url': 'discoveryUrl',
        'authorize_url': 'authorizeUrl',
        'token_url': 'tokenUrl',
        'introspect_url': 'introspectUrl',
        'token_name': 'tokenName',
        'token_file': 'tokenFile',
        'save_token': 'saveToken',
        'use_discovery': 'useDiscovery',
        'enable_pkce': 'enablePkce',
    },
    'oauth-refresh': {
        'output': 'output',
        'token_name': 'tokenName',
        'token_file': 'tokenFile',
        'client_id': 'clientId',
        'client_secret': 'clientSecret',
        'discovery_url': 'discoveryUrl',
        'token_url': 'tokenUrl',
        'introspect_url': 'introspectUrl',
        'use_discovery': 'useDiscovery',
        'save_token': 'saveToken',
    },
    'oauth-introspect': {
        'output': 'output',
        'token_name': 'tokenName',
        'token_file': 'tokenFile',
        'access_token': 'accessToken',
        'client_id': 'clientId',
        'client_secret': 'clientSecret',
        'discovery_url': 'discoveryUrl',
        'introspect_url': 'introspectUrl',
        'use_discovery': 'useDiscovery',
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
    def __init__(self, return_code: int | None, transport: str = 'ssh'):
        self.return_code = return_code
        self.transport = transport
        super().__init__(f'{transport} process exited with code {return_code}')



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

    oauth_login_parser = subparsers.add_parser('oauth-login')
    oauth_login_parser.add_argument('--output', choices=['json', 'text'], default=None)
    oauth_login_parser.add_argument('--domain', dest='domain_selector', default=None)
    oauth_login_parser.add_argument('--client-id', default=None)
    oauth_login_parser.add_argument('--client-secret', default=None)
    oauth_login_parser.add_argument('--redirect-uri', default=None)
    oauth_login_parser.add_argument('--scopes', default=None)
    oauth_login_parser.add_argument('--discovery-url', default=None)
    oauth_login_parser.add_argument('--authorize-url', default=None)
    oauth_login_parser.add_argument('--token-url', default=None)
    oauth_login_parser.add_argument('--introspect-url', default=None)
    oauth_login_parser.add_argument('--token-name', default=None)
    oauth_login_parser.add_argument('--token-file', default=None)
    oauth_login_parser.add_argument('--save-token', action=argparse.BooleanOptionalAction, default=None)
    oauth_login_parser.add_argument('--use-discovery', action=argparse.BooleanOptionalAction, default=None)
    oauth_login_parser.add_argument('--enable-pkce', action=argparse.BooleanOptionalAction, default=None)

    oauth_refresh_parser = subparsers.add_parser('oauth-refresh')
    oauth_refresh_parser.add_argument('--output', choices=['json', 'text'], default=None)
    oauth_refresh_parser.add_argument('--token-name', default=None)
    oauth_refresh_parser.add_argument('--token-file', default=None)
    oauth_refresh_parser.add_argument('--client-id', default=None)
    oauth_refresh_parser.add_argument('--client-secret', default=None)
    oauth_refresh_parser.add_argument('--discovery-url', default=None)
    oauth_refresh_parser.add_argument('--token-url', default=None)
    oauth_refresh_parser.add_argument('--introspect-url', default=None)
    oauth_refresh_parser.add_argument('--save-token', action=argparse.BooleanOptionalAction, default=None)
    oauth_refresh_parser.add_argument('--use-discovery', action=argparse.BooleanOptionalAction, default=None)

    oauth_introspect_parser = subparsers.add_parser('oauth-introspect')
    oauth_introspect_parser.add_argument('--output', choices=['json', 'text'], default=None)
    oauth_introspect_parser.add_argument('--token-name', default=None)
    oauth_introspect_parser.add_argument('--token-file', default=None)
    oauth_introspect_parser.add_argument('--access-token', default=None)
    oauth_introspect_parser.add_argument('--client-id', default=None)
    oauth_introspect_parser.add_argument('--client-secret', default=None)
    oauth_introspect_parser.add_argument('--discovery-url', default=None)
    oauth_introspect_parser.add_argument('--introspect-url', default=None)
    oauth_introspect_parser.add_argument('--use-discovery', action=argparse.BooleanOptionalAction, default=None)

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
        sub.add_argument('--transport', choices=['ssh', 'tcp-bridge', 'auto'], default=None,
                         help='Force transport: ssh, tcp-bridge, or auto (try ssh, fall back to tcp bridge)')
        sub.add_argument('--tcp-bridge-password', default=None,
                         help='Password for TCP bridge when the domain requires one')
        sub.add_argument('--bridge-key', default=None,
                         help='Owner key of a reserved bridge subdomain; take it from the domain card in the console')
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

    bridge_parser = subparsers.add_parser('bridge',
        help='Launch a keyless TCP bridge tunnel (no API token, no SSH key)')
    bridge_parser.add_argument('--output', choices=['json', 'text'], default=None)
    bridge_parser.add_argument('--domain', dest='domain_selector', default=None,
        help='Optional hostname (new:my-app or bare my-app). Omit for a generated ephemeral subdomain.')
    bridge_parser.add_argument('--note', default=None)
    bridge_parser.add_argument('--local-host', default=None)
    bridge_parser.add_argument('--local-port', type=int, default=None)
    bridge_parser.add_argument('--save-profile', action=argparse.BooleanOptionalAction, default=None)
    bridge_parser.add_argument('--runtime-name', default=None)
    bridge_parser.add_argument('--tcp-bridge-password', default=None,
        help='Password for TCP bridge when the domain requires one')
    bridge_parser.add_argument('--bridge-key', default=None,
        help='Owner key of a reserved bridge subdomain; take it from the domain card in the console')
    bridge_parser.add_argument('--run', action=argparse.BooleanOptionalAction, default=None)
    bridge_parser.add_argument('--watch', action=argparse.BooleanOptionalAction, default=None)
    bridge_parser.add_argument('--name', default=None)
    bridge_parser.add_argument('--health-path', default=None)
    bridge_parser.add_argument('--health-interval', type=int, default=None)
    bridge_parser.add_argument('--health-timeout', type=int, default=None)
    bridge_parser.add_argument('--health-failures', type=int, default=None)
    bridge_parser.add_argument('--restart-delay', type=int, default=None)
    bridge_parser.add_argument('--max-restarts', type=int, default=None)
    bridge_parser.add_argument('--log-file', default=None)
    bridge_parser.add_argument('--status-file', default=None)
    bridge_parser.add_argument('--stop-file', default=None)

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
    if config_payload.get('command') not in {'connect', 'bridge'}:
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
            'effectiveTransport': result.connection_profile.effective_transport,
            'requiresSshKey': result.connection_profile.requires_ssh_key,
            'tcpBridge': result.connection_profile.tcp_bridge.to_dict() if result.connection_profile.tcp_bridge else None,
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
    cp = result.connection_profile
    # Имя запуска печатает вызывающий: здесь оно было пустым и вылезало в вывод
    # второй строкой "Runtime name:" без значения.
    logger.log(f'Public URL: {cp.public_url}')
    logger.log(f'Health URL: {health_url}')
    if cp.is_tcp_bridge:
        transport = 'tcp_bridge'
        tb = cp.tcp_bridge
        if tb:
            logger.log(f'Transport: {transport} (no SSH key required)')
            if tb.public_port is not None:
                logger.log(f'Public TCP port: {tb.public_port}')
            if tb.host:
                logger.log(f'Bridge host: {tb.host}:{tb.control_port}')
        logger.debug(f'Bridge args: {cp.effective_args}')
    else:
        logger.log(
            'SSH target: '
            f'{cp.ssh_user}@{cp.ssh_host}:{cp.ssh_port}'
        )
        logger.debug(f'SSH args: {cp.ssh_args}')


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
        # --name задаёт человек, и оно должно побеждать значение, осевшее в
        # конфиге от прошлого запуска. Раньше старшим считался runtimeName, и
        # забытое там имя молча подменяло то, что просили в командной строке:
        # процесс поднимался под чужим именем, а status/stop его не находили.
        # Явный --runtime-name по-прежнему сильнее: он адресует то же поле.
        if 'name' in explicit and 'runtime_name' not in explicit:
            section['runtimeName'] = explicit['name']
    return candidate


def _health_failures(settings: dict[str, Any]) -> int:
    """Сколько подряд неудачных проверок считать поводом для перезапуска.

    Ноль означает "не перезапускать никогда": проверка остаётся, её результат
    виден в журнале и в status, но решения о жизни туннеля не принимает.
    Через `or 3` ноль было не выразить - он молча превращался в тройку.
    """
    value = settings.get('healthFailures')
    if value is None or value == '':
        return 3
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 3
    return max(parsed, 0)


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


def _coerce_scopes(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    text = str(value).replace(',', ' ')
    return [part for part in text.split() if part]


def _resolve_existing_domain(planner: Planner, domain_selector: str) -> Any:
    mode, value = _split_selector(domain_selector, label='domain')
    if mode not in {'existing', 'id', 'existing-id'}:
        raise ValidationError('OAuth login currently supports only existing domains.', details={'domainSelector': domain_selector})
    return planner._resolve_domain(mode, value)


def _resolve_oauth_endpoints(
    client: ApiClient,
    *,
    use_discovery: bool,
    discovery_url: str | None,
    authorize_url: str | None = None,
    token_url: str | None = None,
    introspect_url: str | None = None,
) -> tuple[Meta | None, DiscoveryMetadata | None, str | None, str | None, str | None, str | None]:
    meta = None
    discovery = None
    resolved_discovery_url = discovery_url
    resolved_authorize_url = authorize_url
    resolved_token_url = token_url
    resolved_introspect_url = introspect_url
    if use_discovery and (not resolved_authorize_url or not resolved_token_url or not resolved_introspect_url or not resolved_discovery_url):
        try:
            meta = Meta.from_api(client.fetch_meta())
        except PlanRequiredError:
            # Advisory endpoint. Explicit URLs (or none) are still workable.
            meta = None
        resolved_discovery_url = resolved_discovery_url or (meta.oauth_authorization_server if meta else None)
        if resolved_discovery_url:
            discovery = DiscoveryMetadata.from_api(client.fetch_oauth_authorization_server(discovery_url=resolved_discovery_url))
            resolved_authorize_url = resolved_authorize_url or discovery.authorization_endpoint
            resolved_token_url = resolved_token_url or discovery.token_endpoint
            resolved_introspect_url = resolved_introspect_url or discovery.introspection_endpoint
    return meta, discovery, resolved_discovery_url, resolved_authorize_url, resolved_token_url, resolved_introspect_url


def _resolve_token_path(runtime: Any, *, token_name: str | None = None, token_file: str | None = None) -> Path:
    if token_file:
        return Path(str(token_file)).expanduser()
    if not token_name:
        raise ValidationError('OAuth token name or file is required.', details={'hint': 'Use --token-name or --token-file.'})
    safe_name = ''.join(ch if ch.isalnum() or ch in {'-', '_'} else '-' for ch in str(token_name))
    return runtime.oauth_tokens_dir / f'{safe_name}.json'


def _run_oauth_login(client: ApiClient, runtime: Any, settings: dict[str, Any]) -> dict[str, Any]:
    domain_selector = settings.get('domainSelector')
    client_id = settings.get('clientId')
    redirect_uri = settings.get('redirectUri')
    if not domain_selector:
        raise ValidationError('OAuth login requires a domain selector.', details={'hint': 'Use --domain existing:<name>.'})
    if not client_id:
        raise ValidationError('OAuth login requires clientId.', details={'hint': 'Use --client-id.'})
    if not redirect_uri:
        raise ValidationError('OAuth login requires redirectUri.', details={'hint': 'Use --redirect-uri.'})

    planner = Planner(client, runtime)
    domain = _resolve_existing_domain(planner, str(domain_selector))
    meta, discovery, resolved_discovery_url, authorize_url, token_url, introspect_url = _resolve_oauth_endpoints(
        client,
        use_discovery=bool(settings.get('useDiscovery', True)),
        discovery_url=settings.get('discoveryUrl'),
        authorize_url=settings.get('authorizeUrl'),
        token_url=settings.get('tokenUrl'),
        introspect_url=settings.get('introspectUrl'),
    )
    if not authorize_url or not token_url:
        raise ValidationError('OAuth authorize/token endpoints could not be resolved.', details={'authorizeUrl': authorize_url, 'tokenUrl': token_url})

    scopes = _coerce_scopes(settings.get('scopes'))
    if not scopes and discovery is not None:
        scopes = discovery.scopes_supported
    if not scopes:
        raise ValidationError('OAuth scopes are required.', details={'hint': 'Use --scopes or enable discovery with advertised scopes.'})

    pkce_pair = generate_pkce_pair() if bool(settings.get('enablePkce', True)) else None
    authorize_payload: dict[str, Any] = {
        'domainId': domain.id,
        'redirectUri': str(redirect_uri),
        'clientId': str(client_id),
        'scopes': scopes,
    }
    if pkce_pair is not None:
        authorize_payload['codeChallenge'] = pkce_pair.challenge
        authorize_payload['codeChallengeMethod'] = pkce_pair.method

    authorize_result = client.authorize_oauth_code(authorize_url=authorize_url, payload=authorize_payload)
    authorization_code = authorize_result.get('authorizationCode') or authorize_result.get('code')
    if not authorization_code:
        raise ValidationError('OAuth authorize response did not contain an authorization code.', details={'response': authorize_result})

    form_payload = {
        'grant_type': 'authorization_code',
        'clientId': client_id,
        'clientSecret': settings.get('clientSecret'),
        'code': authorization_code,
        'redirectUri': redirect_uri,
        'codeVerifier': (pkce_pair.verifier if pkce_pair is not None else None),
    }
    token_payload = client.exchange_oauth_token(token_url=token_url, form_payload=form_payload)

    token_name = settings.get('tokenName') or build_token_storage_name(client_id=str(client_id), domain_slug=domain.hostname)
    token_record = OAuthTokenRecord.from_token_response(
        name=str(token_name),
        client_id=str(client_id),
        client_secret=settings.get('clientSecret'),
        token_payload=token_payload,
        resource=(meta.api_base_url if meta is not None else None),
        redirect_uri=str(redirect_uri),
        authorize_url=authorize_url,
        token_url=token_url,
        introspect_url=introspect_url,
        discovery_url=resolved_discovery_url,
        authorization_server=(discovery.issuer if discovery is not None else None),
        domain_selector=str(domain_selector),
    )
    token_path = _resolve_token_path(runtime, token_name=str(token_name), token_file=settings.get('tokenFile'))
    if bool(settings.get('saveToken', True)):
        save_token_record(token_path, token_record)

    introspection = None
    if introspect_url:
        introspection = client.introspect_oauth_token(
            introspect_url=introspect_url,
            token=token_record.access_token,
            client_id=token_record.client_id,
            client_secret=token_record.client_secret,
        )

    return {
        'ok': True,
        'mode': 'oauth-login',
        'domain': domain.to_dict(),
        'authorize': authorize_result,
        'token': token_record.to_dict(),
        'savedTokenPath': str(token_path),
        'introspection': introspection,
    }


def _run_oauth_refresh(client: ApiClient, runtime: Any, settings: dict[str, Any]) -> dict[str, Any]:
    token_path = _resolve_token_path(runtime, token_name=settings.get('tokenName'), token_file=settings.get('tokenFile'))
    record = load_token_record(token_path)
    if not record.refresh_token:
        raise ValidationError('Saved OAuth token does not contain a refresh token.', details={'path': str(token_path)})

    _, discovery, resolved_discovery_url, _, token_url, introspect_url = _resolve_oauth_endpoints(
        client,
        use_discovery=bool(settings.get('useDiscovery', True)),
        discovery_url=settings.get('discoveryUrl') or record.discovery_url,
        token_url=settings.get('tokenUrl') or record.token_url,
        introspect_url=settings.get('introspectUrl') or record.introspect_url,
    )
    token_url = token_url or record.token_url
    introspect_url = introspect_url or record.introspect_url
    if not token_url:
        raise ValidationError('OAuth token endpoint could not be resolved for refresh.', details={'path': str(token_path)})

    token_payload = client.exchange_oauth_token(
        token_url=token_url,
        form_payload={
            'grant_type': 'refresh_token',
            'clientId': settings.get('clientId') or record.client_id,
            'clientSecret': settings.get('clientSecret') or record.client_secret,
            'refresh_token': record.refresh_token,
        },
    )
    refreshed = OAuthTokenRecord.from_token_response(
        name=record.name,
        client_id=str(settings.get('clientId') or record.client_id),
        client_secret=(settings.get('clientSecret') or record.client_secret),
        token_payload=token_payload,
        resource=record.resource,
        redirect_uri=record.redirect_uri,
        authorize_url=record.authorize_url,
        token_url=token_url,
        introspect_url=introspect_url,
        discovery_url=resolved_discovery_url or record.discovery_url,
        authorization_server=(discovery.issuer if discovery is not None else record.authorization_server),
        domain_selector=record.domain_selector,
        fallback_refresh_token=record.refresh_token,
    )
    if bool(settings.get('saveToken', True)):
        save_token_record(token_path, refreshed)

    introspection = None
    if introspect_url:
        introspection = client.introspect_oauth_token(
            introspect_url=introspect_url,
            token=refreshed.access_token,
            client_id=refreshed.client_id,
            client_secret=refreshed.client_secret,
        )

    return {
        'ok': True,
        'mode': 'oauth-refresh',
        'token': refreshed.to_dict(),
        'savedTokenPath': str(token_path),
        'introspection': introspection,
    }


def _run_oauth_introspect(client: ApiClient, runtime: Any, settings: dict[str, Any]) -> dict[str, Any]:
    record = None
    token_path = None
    access_token = settings.get('accessToken')
    client_id = settings.get('clientId')
    client_secret = settings.get('clientSecret')
    introspect_url = settings.get('introspectUrl')
    discovery_url = settings.get('discoveryUrl')

    if settings.get('tokenName') or settings.get('tokenFile'):
        token_path = _resolve_token_path(runtime, token_name=settings.get('tokenName'), token_file=settings.get('tokenFile'))
        record = load_token_record(token_path)
        access_token = access_token or record.access_token
        client_id = client_id or record.client_id
        client_secret = client_secret or record.client_secret
        introspect_url = introspect_url or record.introspect_url
        discovery_url = discovery_url or record.discovery_url

    if not access_token:
        raise ValidationError('OAuth introspection requires an access token or a saved token reference.', details={'hint': 'Use --access-token or --token-name.'})

    _, _, _, _, _, introspect_url = _resolve_oauth_endpoints(
        client,
        use_discovery=bool(settings.get('useDiscovery', True)),
        discovery_url=discovery_url,
        introspect_url=introspect_url,
    )
    if not introspect_url:
        raise ValidationError('OAuth introspection endpoint could not be resolved.', details={'hint': 'Use --introspect-url or enable discovery.'})

    introspection = client.introspect_oauth_token(
        introspect_url=introspect_url,
        token=str(access_token),
        client_id=(str(client_id) if client_id else None),
        client_secret=(str(client_secret) if client_secret else None),
    )
    payload: dict[str, Any] = {'ok': True, 'mode': 'oauth-introspect', 'introspection': introspection}
    if record is not None:
        payload['token'] = record.to_dict()
        payload['savedTokenPath'] = str(token_path)
    return payload


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
        if item.get('transport'):
            print(f"  transport: {item.get('transport')}")
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

    cp = result.connection_profile
    transport = cp.effective_transport
    is_native_bridge = transport == 'tcp_bridge' and cp.tcp_bridge is not None and cp.tcp_bridge.enabled

    if not is_native_bridge and not cp.effective_args:
        raise ValidationError('Connection profile did not contain executable args for tunnel launch.')

    health_url = _make_health_url(cp.public_url, health_path)
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

    if is_native_bridge:
        tb = cp.tcp_bridge
        assert tb is not None
        # Ключ отдаём всегда, когда сервер его прислал, а не только когда он
        # объявил authRequired. Признак говорит "без ключа не пустят", но
        # прислать ключ полезно и в мягком режиме: сервер тогда знает, что перед
        # ним владелец адреса, а не случайный клиент, знающий имя.
        secret = tb.token
        hello_template = None
        if tb.client_protocol and tb.client_protocol.hello:
            hello_template = dict(tb.client_protocol.hello)
        # Пароль моста и служебный токен - разные вещи. Токен выдаётся сервером
        # на сеанс, пароль задаёт владелец домена, и подставлять первый вместо
        # второго значило гарантированный отказ invalid_bridge_password.
        password = None
        if tb.password_required and not password:
            if settings.get('tcpBridgePassword'):
                password = str(settings.get('tcpBridgePassword'))
            elif os.getenv('TUNNELLIO_TCP_BRIDGE_PASSWORD'):
                password = os.getenv('TUNNELLIO_TCP_BRIDGE_PASSWORD')
            else:
                raise ValidationError(
                    'TCP bridge password is required for this domain.',
                    details={'hint': 'Use --tcp-bridge-password or TUNNELLIO_TCP_BRIDGE_PASSWORD.'},
                )
        process = launch_bridge(
            host=tb.host or '',
            control_port=tb.control_port or 7835,
            local_host=tb.local_host or cp.local_host or '127.0.0.1',
            local_port=tb.local_port or cp.local_port or 3000,
            requested_port=tb.public_port or 0,
            secret=secret,
            logger=logger.log,
            hello_template=hello_template,
            password=password,
            password_required=bool(tb.password_required),
            hostname=tb.hostname,
        )
        logger.log('Launching native TCP bridge')
    else:
        expanded_args = [os.path.expanduser(arg) if '~' in arg else arg for arg in cp.effective_args]
        logger.log('Launching SSH bridge')
        process = subprocess.Popen(expanded_args)
    logger.log(f'{transport} pid: {process.pid}')

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
            'transport': result.connection_profile.effective_transport,
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
                raise TunnelProcessExited(return_code, transport=result.connection_profile.effective_transport)

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
                limit = health_failures if health_failures > 0 else 'наблюдение'
                logger.log(f'Health failed via {tls_backend} ({consecutive_failures}/{limit}): {detail}')
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
                # health_failures = 0 - только наблюдать, не перезапускать.
                # Проверка ходит снаружи, через чужую инфраструктуру, и её 404
                # не означает, что мост мёртв. Убивать рабочий туннель по
                # чужому ответу - худшее из решений: мост умеет держать связь и
                # восстанавливать её сам, а перезапуск начинает всё с нуля.
                if health_failures > 0 and consecutive_failures >= health_failures:
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
        logger.log(f'{exc.transport} process exited with code {exc.return_code}')
    finally:
        if process.poll() is None:
            logger.log(f'Stopping {result.connection_profile.effective_transport} bridge')
            process.terminate()
            try:
                process.wait(timeout=10)
            except (subprocess.TimeoutExpired, OSError):
                logger.log('Process did not stop gracefully; killing')
                process.kill()
                try:
                    process.wait(timeout=10)
                except OSError:
                    pass
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
    original_connection_mode = options.connection_mode
    auto_fell_back_to_tcp_bridge = False

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
            if original_connection_mode == 'auto' and not auto_fell_back_to_tcp_bridge:
                auto_fell_back_to_tcp_bridge = True
                options.connection_mode = 'tcp_bridge'
                logger.log('Auto-fallback: switching from SSH to TCP bridge')
                _write_status(
                    status_path,
                    {
                        'name': runtime_name,
                        'state': 'restarting',
                        'restartCount': restart_count,
                        'reason': 'auto_fallback_to_tcp_bridge',
                        'stopFile': str(stop_file),
                        'runtimeConfigFile': str(runtime_config_path),
                    },
                )
                _sleep_with_stop_check(restart_delay, stop_file)
                continue
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

        if original_connection_mode == 'auto' and not auto_fell_back_to_tcp_bridge and result.connection_profile.effective_transport == 'ssh':
            if execution.get('reason') == 'process_exit' and execution.get('returnCode') is not None and execution.get('healthyOnce') is False:
                auto_fell_back_to_tcp_bridge = True
                options.connection_mode = 'tcp_bridge'
                logger.log('SSH exited quickly; auto-fallback to TCP bridge on next attempt')

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

    section_settings = dict(config_payload.get(section_key, {})) if section_key else {}
    decision = resolve_mode(
        command=command,
        transport=section_settings.get('transport'),
        connection_mode=section_settings.get('connectionMode'),
        domain_selector=section_settings.get('domainSelector'),
    )
    local_only_commands = {'status', 'stop', 'show-config'}
    needs_token = command not in local_only_commands and decision.requires_api_token

    runtime = load_runtime_config(
        token=global_config.get('token'),
        base_url=global_config.get('baseUrl'),
        state_dir=global_config.get('stateDir'),
        insecure_tls=global_config.get('insecureTls'),
        require_token=needs_token,
    )
    if not needs_token and command not in local_only_commands:
        log_progress(verbose, f'Mode {decision.mode}: {decision.reason}')

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
        try:
            writer.write_meta(Meta.from_api(client.fetch_meta()))
        except PlanRequiredError as exc:
            # Say plainly that the token is fine and the plan is the limit.
            raise PlanRequiredError(
                f'{exc} Your API token is valid; this endpoint is not part of the plan. '
                'Tunnels do not require it.',
                exc.details,
                code=exc.code,
            ) from exc
        return int(ExitCode.SUCCESS)

    if command == 'capabilities':
        log_progress(verbose, 'Fetching capabilities')
        writer.write_capabilities(Capabilities.from_api(client.fetch_capabilities()))
        return int(ExitCode.SUCCESS)

    if command in {'oauth-login', 'oauth-refresh', 'oauth-introspect'}:
        settings = dict(config_payload.get(section_key, {}))
        if command == 'oauth-login':
            writer.write_payload(_run_oauth_login(client, runtime, settings))
        elif command == 'oauth-refresh':
            writer.write_payload(_run_oauth_refresh(client, runtime, settings))
        else:
            writer.write_payload(_run_oauth_introspect(client, runtime, settings))
        return int(ExitCode.SUCCESS)

    settings = dict(config_payload.get(section_key, {}))
    if command in {'connect', 'bridge'} and settings.get('watch') and not settings.get('run'):
        raise ValidationError('--watch requires run=true in config.')

    is_bridge_command = command == 'bridge'

    transport_preference = settings.get('transport')
    connection_mode = settings.get('connectionMode')
    if transport_preference == 'tcp-bridge' and not connection_mode:
        connection_mode = 'tcp_bridge'
    elif transport_preference == 'tcp-bridge':
        connection_mode = 'tcp_bridge'
    elif transport_preference == 'auto' and not connection_mode:
        connection_mode = 'auto'
    if is_bridge_command:
        connection_mode = 'tcp_bridge'

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
        connection_mode=connection_mode,
        oauth_client_policy=settings.get('oauthClientPolicy'),
        runtime_name=settings.get('runtimeName') or settings.get('name'),
        use_discovery=bool(settings.get('useDiscovery', True)),
        session_strategy=settings.get('sessionStrategy'),
        enable_pkce=bool(settings.get('enablePkce')),
        tcp_bridge_password=settings.get('tcpBridgePassword'),
        # Переменная окружения нужна не для удобства: ключ в командной строке
        # виден в списке процессов и остаётся в истории оболочки.
        bridge_key=settings.get('bridgeKey') or os.getenv('TUNNELLIO_BRIDGE_KEY') or None,
    )
    log_progress(verbose, f'Building {command} plan')
    # With an API token the full flow covers every mode. Without one, the
    # tokenless modes still work and must not be blocked.
    tokenless = not runtime.token and not decision.requires_api_token
    if is_bridge_command or (tokenless and decision.mode in {MODE_TCP_STABLE, MODE_TCP_RANDOM}):
        result = planner.build_keyless_bridge_plan(options)
    elif tokenless and decision.mode == MODE_SSH_STABLE:
        result = planner.build_offline_ssh_plan(options)
    else:
        result = planner.build_plan(options)

    if command in {'connect', 'bridge'} and settings.get('run'):
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
            if is_bridge_command:
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
                    health_failures=_health_failures(settings),
                    status_path=status_path,
                    stop_file=stop_file,
                )
            else:
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
                    health_failures=_health_failures(settings),
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
                health_failures=_health_failures(settings),
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
