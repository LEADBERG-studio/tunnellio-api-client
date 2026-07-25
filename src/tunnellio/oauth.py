from __future__ import annotations

import base64
import hashlib
import json
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from .errors import ValidationError


@dataclass(slots=True)
class PkcePair:
    verifier: str
    challenge: str
    method: str = 'S256'

    def to_dict(self) -> dict[str, Any]:
        return {
            'verifier': self.verifier,
            'challenge': self.challenge,
            'method': self.method,
        }


@dataclass(slots=True)
class OAuthAuthorizeRequest:
    authorize_url: str
    client_id: str
    redirect_uri: str
    scope: str | None = None
    state: str | None = None
    audience: str | None = None
    code_challenge: str | None = None
    code_challenge_method: str = 'S256'
    response_type: str = 'code'
    extra_params: dict[str, Any] = field(default_factory=dict)

    def to_query_params(self) -> dict[str, Any]:
        params: dict[str, Any] = {
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'response_type': self.response_type,
        }
        if self.scope:
            params['scope'] = self.scope
        if self.state:
            params['state'] = self.state
        if self.audience:
            params['audience'] = self.audience
        if self.code_challenge:
            params['code_challenge'] = self.code_challenge
            params['code_challenge_method'] = self.code_challenge_method
        params.update(self.extra_params)
        return params


@dataclass(slots=True)
class OAuthTokenRecord:
    name: str
    client_id: str
    access_token: str
    token_type: str = 'Bearer'
    refresh_token: str | None = None
    scope: str | None = None
    expires_at: str | None = None
    obtained_at: str | None = None
    resource: str | None = None
    redirect_uri: str | None = None
    authorize_url: str | None = None
    token_url: str | None = None
    introspect_url: str | None = None
    discovery_url: str | None = None
    authorization_server: str | None = None
    client_secret: str | None = None
    domain_selector: str | None = None
    auth_mode: str | None = None
    connection_mode: str | None = None
    proxy_session_id: str | None = None

    @classmethod
    def from_token_response(
        cls,
        *,
        name: str,
        client_id: str,
        token_payload: dict[str, Any],
        client_secret: str | None = None,
        resource: str | None = None,
        redirect_uri: str | None = None,
        authorize_url: str | None = None,
        token_url: str | None = None,
        introspect_url: str | None = None,
        discovery_url: str | None = None,
        authorization_server: str | None = None,
        domain_selector: str | None = None,
        fallback_refresh_token: str | None = None,
    ) -> 'OAuthTokenRecord':
        access_token = _str_from_keys(token_payload, 'access_token', 'accessToken')
        if not access_token:
            raise ValidationError('OAuth token response did not contain an access token.', details={'response': token_payload})
        obtained = _iso_now()
        expires_in = _int_from_keys(token_payload, 'expires_in', 'expiresIn')
        expires_at = (
            (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat().replace('+00:00', 'Z')
            if expires_in is not None
            else None
        )
        return cls(
            name=name,
            client_id=client_id,
            client_secret=client_secret,
            access_token=access_token,
            token_type=_str_from_keys(token_payload, 'token_type', 'tokenType') or 'Bearer',
            refresh_token=_str_from_keys(token_payload, 'refresh_token', 'refreshToken') or fallback_refresh_token,
            scope=_str_from_keys(token_payload, 'scope', 'scopes'),
            expires_at=expires_at,
            obtained_at=obtained,
            resource=resource,
            redirect_uri=redirect_uri,
            authorize_url=authorize_url,
            token_url=token_url,
            introspect_url=introspect_url,
            discovery_url=discovery_url,
            authorization_server=authorization_server,
            domain_selector=domain_selector,
            auth_mode=_str_from_keys(token_payload, 'auth_mode', 'authMode'),
            connection_mode=_str_from_keys(token_payload, 'connection_mode', 'connectionMode'),
            proxy_session_id=_str_from_keys(token_payload, 'proxy_session_id', 'proxySessionId'),
        )

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> 'OAuthTokenRecord':
        access_token = payload.get('accessToken') or payload.get('access_token')
        client_id = payload.get('clientId') or payload.get('client_id')
        name = payload.get('name')
        if not isinstance(name, str) or not name:
            raise ValidationError('Saved OAuth token record is missing name.', details={'payload': payload})
        if not isinstance(client_id, str) or not client_id:
            raise ValidationError('Saved OAuth token record is missing clientId.', details={'payload': payload})
        if not isinstance(access_token, str) or not access_token:
            raise ValidationError('Saved OAuth token record is missing accessToken.', details={'payload': payload})
        return cls(
            name=name,
            client_id=client_id,
            access_token=access_token,
            token_type=str(payload.get('tokenType') or payload.get('token_type') or 'Bearer'),
            refresh_token=_str_or_none(payload.get('refreshToken') or payload.get('refresh_token')),
            scope=_str_or_none(payload.get('scope')),
            expires_at=_str_or_none(payload.get('expiresAt') or payload.get('expires_at')),
            obtained_at=_str_or_none(payload.get('obtainedAt') or payload.get('obtained_at')),
            resource=_str_or_none(payload.get('resource')),
            redirect_uri=_str_or_none(payload.get('redirectUri') or payload.get('redirect_uri')),
            authorize_url=_str_or_none(payload.get('authorizeUrl') or payload.get('authorize_url')),
            token_url=_str_or_none(payload.get('tokenUrl') or payload.get('token_url')),
            introspect_url=_str_or_none(payload.get('introspectUrl') or payload.get('introspect_url')),
            discovery_url=_str_or_none(payload.get('discoveryUrl') or payload.get('discovery_url')),
            authorization_server=_str_or_none(payload.get('authorizationServer') or payload.get('authorization_server')),
            client_secret=_str_or_none(payload.get('clientSecret') or payload.get('client_secret')),
            domain_selector=_str_or_none(payload.get('domainSelector') or payload.get('domain_selector')),
            auth_mode=_str_or_none(payload.get('authMode') or payload.get('auth_mode')),
            connection_mode=_str_or_none(payload.get('connectionMode') or payload.get('connection_mode')),
            proxy_session_id=_str_or_none(payload.get('proxySessionId') or payload.get('proxy_session_id')),
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            'name': self.name,
            'clientId': self.client_id,
            'accessToken': self.access_token,
            'tokenType': self.token_type,
        }
        for key, value in {
            'refreshToken': self.refresh_token,
            'scope': self.scope,
            'expiresAt': self.expires_at,
            'obtainedAt': self.obtained_at,
            'resource': self.resource,
            'redirectUri': self.redirect_uri,
            'authorizeUrl': self.authorize_url,
            'tokenUrl': self.token_url,
            'introspectUrl': self.introspect_url,
            'discoveryUrl': self.discovery_url,
            'authorizationServer': self.authorization_server,
            'clientSecret': self.client_secret,
            'domainSelector': self.domain_selector,
            'authMode': self.auth_mode,
            'connectionMode': self.connection_mode,
            'proxySessionId': self.proxy_session_id,
        }.items():
            if value is not None:
                payload[key] = value
        return payload

    def authorization_header(self) -> str:
        return f'{self.token_type} {self.access_token}'

    def is_expired(self, *, leeway_seconds: int = 60) -> bool:
        if not self.expires_at:
            return False
        expires_at = _parse_iso_datetime(self.expires_at)
        return datetime.now(timezone.utc) + timedelta(seconds=leeway_seconds) >= expires_at


def generate_pkce_verifier(length: int = 64) -> str:
    if length < 43 or length > 128:
        raise ValidationError('PKCE verifier length must be between 43 and 128.', details={'length': length})
    verifier = secrets.token_urlsafe(length)
    while len(verifier) < length:
        verifier += secrets.token_urlsafe(8)
    return verifier[:length]


def build_code_challenge(verifier: str) -> str:
    if not verifier:
        raise ValidationError('PKCE verifier is required.')
    digest = hashlib.sha256(verifier.encode('utf-8')).digest()
    return base64.urlsafe_b64encode(digest).decode('ascii').rstrip('=')


def generate_pkce_pair(length: int = 64) -> PkcePair:
    verifier = generate_pkce_verifier(length)
    return PkcePair(verifier=verifier, challenge=build_code_challenge(verifier))


def build_authorize_url(request: OAuthAuthorizeRequest) -> str:
    query = urlencode(request.to_query_params())
    separator = '&' if '?' in request.authorize_url else '?'
    return f'{request.authorize_url}{separator}{query}'


def build_token_storage_name(*, client_id: str, domain_slug: str | None = None) -> str:
    raw = '-'.join(part for part in [domain_slug, client_id[-8:]] if part)
    cleaned = ''.join(ch if ch.isalnum() or ch in {'-', '_'} else '-' for ch in raw)
    collapsed = '-'.join(part for part in cleaned.split('-') if part)
    return collapsed or f'oauth-{client_id[-8:]}'


def save_token_record(path: Path, record: OAuthTokenRecord) -> OAuthTokenRecord:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record.to_dict(), indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return record


def load_token_record(path: Path) -> OAuthTokenRecord:
    if not path.exists():
        raise ValidationError('OAuth token file was not found.', details={'path': str(path)})
    payload = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(payload, dict):
        raise ValidationError('OAuth token file must contain an object.', details={'path': str(path)})
    return OAuthTokenRecord.from_dict(payload)


def _str_or_none(value: Any) -> str | None:
    return None if value is None else str(value)


def _str_from_keys(payload: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = payload.get(key)
        if value is not None:
            return str(value)
    return None


def _int_from_keys(payload: dict[str, Any], *keys: str) -> int | None:
    for key in keys:
        value = payload.get(key)
        if value is not None:
            return int(value)
    return None


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def _parse_iso_datetime(value: str) -> datetime:
    cleaned = value.replace('Z', '+00:00')
    return datetime.fromisoformat(cleaned).astimezone(timezone.utc)


__all__ = [
    'OAuthAuthorizeRequest',
    'OAuthTokenRecord',
    'PkcePair',
    'build_authorize_url',
    'build_code_challenge',
    'build_token_storage_name',
    'generate_pkce_pair',
    'generate_pkce_verifier',
    'load_token_record',
    'save_token_record',
]
