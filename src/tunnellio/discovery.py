from __future__ import annotations


def build_discovery_url(*, auth_domain: str | None = None, explicit_url: str | None = None) -> str | None:
    if explicit_url:
        return explicit_url.strip()
    if not auth_domain:
        return None

    value = auth_domain.strip().rstrip('/')
    if not value:
        return None
    if value.startswith('http://') or value.startswith('https://'):
        if value.endswith('/.well-known/oauth-authorization-server'):
            return value
        return value + '/.well-known/oauth-authorization-server'
    return 'https://' + value + '/.well-known/oauth-authorization-server'


__all__ = ['build_discovery_url']
