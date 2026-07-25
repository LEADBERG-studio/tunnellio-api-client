from __future__ import annotations


def _normalize_base_url(value: str) -> str:
    normalized = value.strip().rstrip('/')
    if not normalized:
        return ''
    if normalized.startswith('http://') or normalized.startswith('https://'):
        return normalized
    return 'https://' + normalized



def build_discovery_url(*, auth_domain: str | None = None, explicit_url: str | None = None) -> str | None:
    if explicit_url:
        return explicit_url.strip()
    if not auth_domain:
        return None

    value = _normalize_base_url(auth_domain)
    if not value:
        return None
    if value.endswith('/.well-known/oauth-authorization-server'):
        return value
    return value + '/.well-known/oauth-authorization-server'



def build_protected_resource_metadata_url(*, resource_url: str | None = None, explicit_url: str | None = None) -> str | None:
    if explicit_url:
        return explicit_url.strip()
    if not resource_url:
        return None

    value = _normalize_base_url(resource_url)
    if not value:
        return None
    if value.endswith('/.well-known/oauth-protected-resource'):
        return value
    return value + '/.well-known/oauth-protected-resource'


__all__ = ['build_discovery_url', 'build_protected_resource_metadata_url']
