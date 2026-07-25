from __future__ import annotations

import copy
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
CONFIG_SCHEMA_VERSION = 1
DEFAULT_LAUNCH_CONFIG_FILENAME = 'default-launch.json'


@dataclass(slots=True)
class RuntimeConfig:
    token: str | None
    base_url: str
    state_dir: Path
    profiles_dir: Path
    keys_dir: Path
    logs_dir: Path
    state_data_dir: Path
    runtime_dir: Path
    client_configs_dir: Path
    oauth_tokens_dir: Path
    default_launch_config_path: Path
    insecure_tls: bool = False

    def ensure_directories(self) -> None:
        for path in [
            self.state_dir,
            self.profiles_dir,
            self.keys_dir,
            self.logs_dir,
            self.state_data_dir,
            self.runtime_dir,
            self.client_configs_dir,
            self.oauth_tokens_dir,
        ]:
            path.mkdir(parents=True, exist_ok=True)



def _load_json_file(path: Path) -> dict[str, Any]:
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



def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged



def resolve_state_dir(state_dir: str | None) -> Path:
    return Path(state_dir).expanduser() if state_dir else DEFAULT_STATE_DIR



def get_default_launch_config_path(state_dir: Path) -> Path:
    return state_dir / DEFAULT_LAUNCH_CONFIG_FILENAME



def get_client_configs_dir(state_dir: Path) -> Path:
    return state_dir / 'configs'



def build_launch_config_template(state_dir: Path | None = None) -> dict[str, Any]:
    resolved_state_dir = resolve_state_dir(str(state_dir) if state_dir else None)
    runtime_dir = resolved_state_dir / 'state' / 'runtimes'
    return {
        'schemaVersion': CONFIG_SCHEMA_VERSION,
        'command': 'connect',
        'global': {
            'token': None,
            'baseUrl': DEFAULT_BASE_URL,
            'stateDir': str(resolved_state_dir),
            'insecureTls': False,
            'verbose': False,
        },
        'meta': {
            'output': 'json',
        },
        'capabilities': {
            'output': 'json',
        },
        'plan': {
            'output': 'json',
            'keySelector': None,
            'publicKeyPath': None,
            'domainSelector': None,
            'keyLifetimeDays': None,
            'domainLifetimeDays': None,
            'note': None,
            'localHost': DEFAULT_LOCAL_HOST,
            'localPort': DEFAULT_LOCAL_PORT,
            'saveProfile': False,
            'requestedAuthMode': None,
            'connectionMode': None,
            'oauthClientPolicy': None,
            'runtimeName': None,
            'useDiscovery': True,
            'sessionStrategy': None,
            'enablePkce': False,
        },
        'connect': {
            'output': 'text',
            'keySelector': None,
            'publicKeyPath': None,
            'domainSelector': None,
            'keyLifetimeDays': None,
            'domainLifetimeDays': None,
            'note': None,
            'localHost': DEFAULT_LOCAL_HOST,
            'localPort': DEFAULT_LOCAL_PORT,
            'saveProfile': False,
            'requestedAuthMode': None,
            'connectionMode': None,
            'oauthClientPolicy': None,
            'runtimeName': None,
            'useDiscovery': True,
            'sessionStrategy': None,
            'enablePkce': False,
            'run': True,
            'watch': True,
            'name': None,
            'healthPath': '/',
            'healthInterval': 15,
            'healthTimeout': 10,
            'healthFailures': 3,
            'restartDelay': 5,
            'maxRestarts': 0,
            'logFile': str(resolved_state_dir / 'logs' / 'tunnel.log'),
            'statusFile': None,
            'stopFile': None,
        },
        'status': {
            'output': 'text',
            'name': None,
            'pid': None,
        },
        'stop': {
            'output': 'text',
            'all': True,
            'name': None,
            'pid': None,
            'force': False,
            'graceSeconds': 3,
        },
        'showConfig': {
            'output': 'json',
            'name': None,
            'pid': None,
        },
        'oauthLogin': {
            'output': 'json',
            'domainSelector': None,
            'clientId': None,
            'clientSecret': None,
            'redirectUri': None,
            'scopes': None,
            'discoveryUrl': None,
            'authorizeUrl': None,
            'tokenUrl': None,
            'introspectUrl': None,
            'tokenName': None,
            'tokenFile': None,
            'saveToken': True,
            'useDiscovery': True,
            'enablePkce': True,
        },
        'oauthRefresh': {
            'output': 'json',
            'tokenName': None,
            'tokenFile': None,
            'clientId': None,
            'clientSecret': None,
            'discoveryUrl': None,
            'tokenUrl': None,
            'introspectUrl': None,
            'useDiscovery': True,
            'saveToken': True,
        },
        'oauthIntrospect': {
            'output': 'json',
            'tokenName': None,
            'tokenFile': None,
            'accessToken': None,
            'clientId': None,
            'clientSecret': None,
            'discoveryUrl': None,
            'introspectUrl': None,
            'useDiscovery': True,
        },
        'paths': {
            'defaultConfig': str(get_default_launch_config_path(resolved_state_dir)),
            'clientConfigsDir': str(get_client_configs_dir(resolved_state_dir)),
            'runtimeDir': str(runtime_dir),
        },
    }



def normalize_launch_config(payload: dict[str, Any], state_dir_hint: Path | None = None) -> dict[str, Any]:
    raw_state_dir = (
        payload.get('global', {}).get('stateDir')
        or (str(state_dir_hint) if state_dir_hint is not None else None)
        or str(DEFAULT_STATE_DIR)
    )
    template = build_launch_config_template(Path(raw_state_dir).expanduser())
    return _deep_merge(template, payload)



def load_launch_config(path: Path, state_dir_hint: Path | None = None) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    return normalize_launch_config(_load_json_file(path), state_dir_hint=state_dir_hint)



def save_launch_config(path: Path, payload: dict[str, Any], state_dir_hint: Path | None = None) -> dict[str, Any]:
    normalized = normalize_launch_config(payload, state_dir_hint=state_dir_hint)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(normalized, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return normalized



def load_runtime_config(
    *,
    token: str | None,
    base_url: str | None,
    state_dir: str | None,
    insecure_tls: bool | None = None,
    require_token: bool = True,
) -> RuntimeConfig:
    resolved_state_dir = resolve_state_dir(state_dir)
    config_path = resolved_state_dir / 'config.json'
    config_file = _load_json_file(config_path)

    resolved_token = token or os.getenv('TUNNELLIO_API_TOKEN') or config_file.get('token')
    if require_token and not resolved_token:
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
        token=(str(resolved_token) if resolved_token is not None else None),
        base_url=cleaned_base_url,
        state_dir=resolved_state_dir,
        profiles_dir=resolved_state_dir / 'profiles',
        keys_dir=resolved_state_dir / 'keys',
        logs_dir=resolved_state_dir / 'logs',
        state_data_dir=resolved_state_dir / 'state',
        runtime_dir=resolved_state_dir / 'state' / 'runtimes',
        client_configs_dir=get_client_configs_dir(resolved_state_dir),
        oauth_tokens_dir=resolved_state_dir / 'oauth_tokens',
        default_launch_config_path=get_default_launch_config_path(resolved_state_dir),
        insecure_tls=bool(resolved_insecure_tls),
    )
    runtime.ensure_directories()
    return runtime
