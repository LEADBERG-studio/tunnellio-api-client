from __future__ import annotations

import json
import os
import ssl
import sys
import time
from typing import Any, Callable
from urllib import error, request

from .config import RuntimeConfig
from .errors import ApiError, error_from_api


def _load_truststore_module() -> Any | None:
    try:
        import truststore  # type: ignore
    except ImportError:
        return None
    return truststore


def build_ssl_context(
    *,
    insecure_tls: bool,
    platform: str | None = None,
    logger: Callable[[str], None] | None = None,
) -> tuple[ssl.SSLContext, str]:
    current_platform = platform or sys.platform
    if insecure_tls:
        context = ssl._create_unverified_context()
        backend = 'insecure'
    elif current_platform.startswith('win'):
        truststore = _load_truststore_module()
        if truststore is not None:
            context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.check_hostname = True
            context.verify_mode = ssl.CERT_REQUIRED
            backend = 'windows-truststore'
        else:
            context = ssl.create_default_context()
            backend = 'openssl-default-missing-truststore'
    else:
        context = ssl.create_default_context()
        backend = 'openssl-default'

    if logger is not None:
        logger(f'tls_backend={backend}')
    return context, backend


class ApiClient:
    def __init__(self, config: RuntimeConfig):
        self._config = config
        self._verbose = str(os.getenv('TUNNELLIO_VERBOSE', '')).strip().lower() in {'1', 'true', 'yes', 'on'}
        self._ssl_context, self._tls_backend = build_ssl_context(
            insecure_tls=config.insecure_tls,
            logger=self._log if self._verbose else None,
        )

    @property
    def tls_backend(self) -> str:
        return self._tls_backend

    def _log(self, message: str) -> None:
        if not self._verbose:
            return
        stamp = time.strftime('%H:%M:%S')
        print(f'[tunnellio-client {stamp}] {message}', file=sys.stderr, flush=True)

    def _request(self, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f'{self._config.base_url}{path}'
        body_payload = payload or {}
        body = json.dumps(body_payload).encode('utf-8')
        headers = {
            'Authorization': f'Bearer {self._config.token}',
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        }
        self._log(
            f'POST {url} insecure_tls={self._config.insecure_tls} tls_backend={self._tls_backend}'
        )
        self._log(f'payload={json.dumps(body_payload, ensure_ascii=False)}')
        req = request.Request(url, data=body, headers=headers, method='POST')
        try:
            with request.urlopen(req, context=self._ssl_context) as response:
                raw = response.read().decode('utf-8')
                self._log(f'response_status={response.status}')
                self._log(f'response_body={raw[:2000]}')
                return self._parse_response(raw, status=response.status)
        except error.HTTPError as exc:
            raw = exc.read().decode('utf-8', errors='replace')
            self._log(f'http_error_status={exc.code}')
            self._log(f'http_error_body={raw[:2000]}')
            return self._parse_response(raw, status=exc.code)
        except error.URLError as exc:
            self._log(f'url_error={exc.reason!r}')
            self._log(f'url_error_tls_backend={self._tls_backend}')
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
