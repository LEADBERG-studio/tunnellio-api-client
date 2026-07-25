from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass, field
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


__all__ = [
    'OAuthAuthorizeRequest',
    'PkcePair',
    'build_authorize_url',
    'build_code_challenge',
    'generate_pkce_pair',
    'generate_pkce_verifier',
]
