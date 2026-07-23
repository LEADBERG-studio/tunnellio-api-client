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
