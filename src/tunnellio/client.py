from __future__ import annotations

import json
import os
import ssl
import sys
import time
from typing import Any, Callable
from urllib import error, parse, request

from .config import RuntimeConfig
from .discovery import build_discovery_url, build_protected_resource_metadata_url
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

    def _request_json(
        self,
        *,
        method: str,
        path: str | None = None,
        url: str | None = None,
        payload: dict[str, Any] | None = None,
        form: dict[str, Any] | None = None,
        include_auth: bool = True,
        expect_envelope: bool = True,
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        target_url = url or f'{self._config.base_url}{path or ""}'
        body: bytes | None = None
        headers: dict[str, str] = {
            'Accept': 'application/json',
        }
        if include_auth and self._config.token:
            headers['Authorization'] = f'Bearer {self._config.token}'
        if form is not None:
            prepared_form = {key: value for key, value in form.items() if value is not None}
            body = parse.urlencode(prepared_form).encode('utf-8')
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
        elif method.upper() != 'GET' or payload is not None:
            body_payload = payload or {}
            body = json.dumps(body_payload).encode('utf-8')
            headers['Content-Type'] = 'application/json'
        if extra_headers:
            headers.update(extra_headers)

        self._log(f'{method.upper()} {target_url} insecure_tls={self._config.insecure_tls} tls_backend={self._tls_backend}')
        if payload is not None:
            self._log(f'payload={json.dumps(payload, ensure_ascii=False)}')
        if form is not None:
            self._log(f'form={json.dumps(form, ensure_ascii=False)}')

        req = request.Request(target_url, data=body, headers=headers, method=method.upper())
        try:
            with request.urlopen(req, context=self._ssl_context) as response:
                raw = response.read().decode('utf-8')
                self._log(f'response_status={response.status}')
                self._log(f'response_body={raw[:2000]}')
                return self._parse_response(raw, status=response.status, expect_envelope=expect_envelope)
        except error.HTTPError as exc:
            raw = exc.read().decode('utf-8', errors='replace')
            self._log(f'http_error_status={exc.code}')
            self._log(f'http_error_body={raw[:2000]}')
            return self._parse_response(raw, status=exc.code, expect_envelope=expect_envelope)
        except error.URLError as exc:
            self._log(f'url_error={exc.reason!r}')
            self._log(f'url_error_tls_backend={self._tls_backend}')
            raise ApiError('Unable to reach API server.', details={'reason': str(exc.reason)}) from exc

    def _parse_response(self, raw: str, *, status: int, expect_envelope: bool) -> dict[str, Any]:
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError as exc:
            raise ApiError('API returned invalid JSON.', details={'status': status, 'body': raw}) from exc

        if not isinstance(payload, dict):
            raise ApiError('Unexpected API response.', details={'status': status, 'response': payload})

        if not expect_envelope:
            return payload

        if payload.get('ok') is True:
            data = payload.get('data')
            if isinstance(data, dict):
                return data
            raise ApiError('API success response did not contain a data object.', details={'response': payload})

        if payload.get('ok') is False and isinstance(payload.get('error'), dict):
            error_payload = payload['error']
            raise error_from_api(
                code=str(error_payload.get('code', 'api_error')),
                message=str(error_payload.get('message', 'API request failed.')),
                details=error_payload.get('details'),
                status=status,
            )

        raise ApiError('Unexpected API response.', details={'status': status, 'response': payload})

    @staticmethod
    def _unwrap_named_object(data: dict[str, Any], *keys: str) -> dict[str, Any]:
        for key in keys:
            value = data.get(key)
            if isinstance(value, dict):
                return value
        return data

    def fetch_meta(self) -> dict[str, Any]:
        return self._request_json(method='POST', path='/v1/meta', payload={})

    def fetch_capabilities(self) -> dict[str, Any]:
        return self._request_json(method='POST', path='/v1/capabilities', payload={})

    def fetch_oauth_authorization_server(
        self,
        *,
        discovery_url: str | None = None,
        auth_domain: str | None = None,
    ) -> dict[str, Any]:
        resolved_url = build_discovery_url(auth_domain=auth_domain, explicit_url=discovery_url)
        if not resolved_url:
            raise ApiError('Discovery URL could not be resolved.')
        return self._request_json(method='GET', url=resolved_url, include_auth=False, expect_envelope=False)

    def fetch_oauth_protected_resource(
        self,
        *,
        resource_metadata_url: str | None = None,
        resource_url: str | None = None,
    ) -> dict[str, Any]:
        resolved_url = build_protected_resource_metadata_url(
            resource_url=resource_url,
            explicit_url=resource_metadata_url,
        )
        if not resolved_url:
            raise ApiError('Protected resource metadata URL could not be resolved.')
        return self._request_json(method='GET', url=resolved_url, include_auth=False, expect_envelope=False)

    @staticmethod
    def _unwrap_oauth_payload(payload: dict[str, Any]) -> dict[str, Any]:
        if payload.get('ok') is True and isinstance(payload.get('data'), dict):
            return payload['data']
        return payload

    def authorize_oauth_code(self, *, authorize_url: str, payload: dict[str, Any]) -> dict[str, Any]:
        raw_payload = self._request_json(method='POST', url=authorize_url, payload=payload, include_auth=False, expect_envelope=False)
        return self._unwrap_oauth_payload(raw_payload)

    def list_keys(self) -> list[dict[str, Any]]:
        return self._request_json(method='POST', path='/v1/keys/list', payload={}).get('keys', [])

    def create_key(self, *, name: str, public_key: str, requested_lifetime_days: int | None = None) -> dict[str, Any]:
        payload = {
            'name': name,
            'publicKey': public_key,
            'requestedLifetimeDays': requested_lifetime_days,
        }
        data = self._request_json(method='POST', path='/v1/keys', payload=payload)
        return self._unwrap_named_object(data, 'key')

    def list_domains(self) -> list[dict[str, Any]]:
        return self._request_json(method='POST', path='/v1/domains/list', payload={}).get('domains', [])

    def check_domain_availability(self, hostname: str) -> dict[str, Any]:
        return self._request_json(method='POST', path='/v1/domains/check', payload={'hostname': hostname})

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
        data = self._request_json(method='POST', path='/v1/domains', payload=payload)
        return self._unwrap_named_object(data, 'domain')

    def get_connection_profile(self, *, domain_id: int, local_host: str | None = None, local_port: int | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {'domainId': domain_id}
        if local_host is not None:
            payload['localHost'] = local_host
        if local_port is not None:
            payload['localPort'] = local_port
        data = self._request_json(method='POST', path='/v1/domains/connection-profile', payload=payload)
        return self._unwrap_named_object(data, 'connectionProfile')

    def create_ephemeral_session(self, *, key_id: int, local_host: str | None = None, local_port: int | None = None, note: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {'keyId': key_id}
        if local_host is not None:
            payload['localHost'] = local_host
        if local_port is not None:
            payload['localPort'] = local_port
        if note is not None:
            payload['note'] = note
        return self._request_json(method='POST', path='/v1/sessions/ephemeral', payload=payload)

    def open_session(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = self._request_json(method='POST', path='/v1/sessions/open', payload=payload)
        return self._unwrap_named_object(data, 'session')

    def heartbeat_session(
        self,
        *,
        session_id: str,
        resume_token: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        request_payload = {'sessionId': session_id}
        if resume_token is not None:
            request_payload['resumeToken'] = resume_token
        if payload:
            request_payload.update(payload)
        data = self._request_json(method='POST', path='/v1/sessions/heartbeat', payload=request_payload)
        return self._unwrap_named_object(data, 'session', 'status')

    def resume_session(self, *, session_id: str | None = None, resume_token: str | None = None, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        request_payload = dict(payload or {})
        if session_id is not None:
            request_payload['sessionId'] = session_id
        if resume_token is not None:
            request_payload['resumeToken'] = resume_token
        data = self._request_json(method='POST', path='/v1/sessions/resume', payload=request_payload)
        return self._unwrap_named_object(data, 'session')

    def close_session(
        self,
        *,
        session_id: str,
        resume_token: str | None = None,
        reason: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {'sessionId': session_id}
        if resume_token is not None:
            payload['resumeToken'] = resume_token
        if reason:
            payload['reason'] = reason
        data = self._request_json(method='POST', path='/v1/sessions/close', payload=payload)
        return self._unwrap_named_object(data, 'session', 'status')

    def get_session_status(self, *, session_id: str) -> dict[str, Any]:
        data = self._request_json(method='POST', path='/v1/sessions/status', payload={'sessionId': session_id})
        return self._unwrap_named_object(data, 'session', 'status')

    def complete_session(self, session_id: str) -> dict[str, Any]:
        return self._request_json(method='POST', path='/v1/sessions/complete', payload={'sessionId': session_id})

    def get_launch_spec(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request_json(method='POST', path='/v1/launch-spec', payload=payload)

    def get_public_tcp_bridge_launch(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request_json(
            method='POST',
            path='/v1/tcp-bridge/launch',
            payload=payload,
            include_auth=False,
        )

    def exchange_oauth_token(self, *, token_url: str, form_payload: dict[str, Any]) -> dict[str, Any]:
        raw_payload = self._request_json(method='POST', url=token_url, form=form_payload, include_auth=False, expect_envelope=False)
        return self._unwrap_oauth_payload(raw_payload)

    def introspect_oauth_token(
        self,
        *,
        introspect_url: str,
        token: str,
        client_id: str | None = None,
        client_secret: str | None = None,
        token_type_hint: str | None = None,
    ) -> dict[str, Any]:
        form_payload: dict[str, Any] = {
            'token': token,
            'client_id': client_id,
            'client_secret': client_secret,
            'token_type_hint': token_type_hint,
        }
        raw_payload = self._request_json(method='POST', url=introspect_url, form=form_payload, include_auth=False, expect_envelope=False)
        return self._unwrap_oauth_payload(raw_payload)
