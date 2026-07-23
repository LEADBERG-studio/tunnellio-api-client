from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class Meta:
    api_version: str
    server_version: str
    site_domain: str
    api_domain: str
    api_base_url: str
    tunnel_domain: str
    ssh_host: str
    ssh_port: int
    ssh_user: str
    install_sh_url: str
    install_ps1_url: str

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> 'Meta':
        return cls(
            api_version=str(payload['apiVersion']),
            server_version=str(payload['serverVersion']),
            site_domain=str(payload['siteDomain']),
            api_domain=str(payload['apiDomain']),
            api_base_url=str(payload['apiBaseUrl']),
            tunnel_domain=str(payload['tunnelDomain']),
            ssh_host=str(payload['sshHost']),
            ssh_port=int(payload['sshPort']),
            ssh_user=str(payload['sshUser']),
            install_sh_url=str(payload['installShUrl']),
            install_ps1_url=str(payload['installPs1Url']),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            'apiVersion': self.api_version,
            'serverVersion': self.server_version,
            'siteDomain': self.site_domain,
            'apiDomain': self.api_domain,
            'apiBaseUrl': self.api_base_url,
            'tunnelDomain': self.tunnel_domain,
            'sshHost': self.ssh_host,
            'sshPort': self.ssh_port,
            'sshUser': self.ssh_user,
            'installShUrl': self.install_sh_url,
            'installPs1Url': self.install_ps1_url,
        }


@dataclass(slots=True)
class KeyCapabilities:
    max_count: int
    can_create: bool
    can_delete: bool
    min_lifetime_days: int
    max_lifetime_days: int
    default_lifetime_days: int | None

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> 'KeyCapabilities':
        return cls(
            max_count=int(payload['maxCount']),
            can_create=bool(payload['canCreate']),
            can_delete=bool(payload['canDelete']),
            min_lifetime_days=int(payload['minLifetimeDays']),
            max_lifetime_days=int(payload['maxLifetimeDays']),
            default_lifetime_days=payload.get('defaultLifetimeDays'),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            'maxCount': self.max_count,
            'canCreate': self.can_create,
            'canDelete': self.can_delete,
            'minLifetimeDays': self.min_lifetime_days,
            'maxLifetimeDays': self.max_lifetime_days,
            'defaultLifetimeDays': self.default_lifetime_days,
        }


@dataclass(slots=True)
class DomainCapabilities:
    can_create: bool
    can_delete: bool
    supports_random_ephemeral: bool
    min_lifetime_days: int
    max_lifetime_days: int
    default_lifetime_days: int | None

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> 'DomainCapabilities':
        return cls(
            can_create=bool(payload['canCreate']),
            can_delete=bool(payload['canDelete']),
            supports_random_ephemeral=bool(payload['supportsRandomEphemeral']),
            min_lifetime_days=int(payload['minLifetimeDays']),
            max_lifetime_days=int(payload['maxLifetimeDays']),
            default_lifetime_days=payload.get('defaultLifetimeDays'),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            'canCreate': self.can_create,
            'canDelete': self.can_delete,
            'supportsRandomEphemeral': self.supports_random_ephemeral,
            'minLifetimeDays': self.min_lifetime_days,
            'maxLifetimeDays': self.max_lifetime_days,
            'defaultLifetimeDays': self.default_lifetime_days,
        }


@dataclass(slots=True)
class EphemeralCapabilities:
    enabled: bool
    delete_on_disconnect: bool
    fallback_lifetime_hours: int

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> 'EphemeralCapabilities':
        return cls(
            enabled=bool(payload['enabled']),
            delete_on_disconnect=bool(payload['deleteOnDisconnect']),
            fallback_lifetime_hours=int(payload['fallbackLifetimeHours']),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            'enabled': self.enabled,
            'deleteOnDisconnect': self.delete_on_disconnect,
            'fallbackLifetimeHours': self.fallback_lifetime_hours,
        }


@dataclass(slots=True)
class Capabilities:
    keys: KeyCapabilities
    domains: DomainCapabilities
    ephemeral: EphemeralCapabilities

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> 'Capabilities':
        return cls(
            keys=KeyCapabilities.from_api(payload['keys']),
            domains=DomainCapabilities.from_api(payload['domains']),
            ephemeral=EphemeralCapabilities.from_api(payload['ephemeral']),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            'keys': self.keys.to_dict(),
            'domains': self.domains.to_dict(),
            'ephemeral': self.ephemeral.to_dict(),
        }


@dataclass(slots=True)
class KeySummary:
    id: int
    name: str
    fingerprint: str
    created_at: str
    expires_at: str | None
    last_used_at: str | None
    status: str
    domain_count: int | None = None

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> 'KeySummary':
        return cls(
            id=int(payload['id']),
            name=str(payload['name']),
            fingerprint=str(payload['fingerprint']),
            created_at=str(payload['createdAt']),
            expires_at=payload.get('expiresAt'),
            last_used_at=payload.get('lastUsedAt'),
            status=str(payload['status']),
            domain_count=(int(payload['domainCount']) if payload.get('domainCount') is not None else None),
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            'id': self.id,
            'name': self.name,
            'fingerprint': self.fingerprint,
            'createdAt': self.created_at,
            'expiresAt': self.expires_at,
            'lastUsedAt': self.last_used_at,
            'status': self.status,
        }
        if self.domain_count is not None:
            payload['domainCount'] = self.domain_count
        return payload


@dataclass(slots=True)
class DomainSummary:
    id: int
    hostname: str
    fqdn: str
    public_url: str
    key_id: int | None
    local_port: int
    note: str
    created_at: str
    expires_at: str | None
    last_used_at: str | None
    mode: str
    status: str
    key_name: str | None = None
    fingerprint: str | None = None

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> 'DomainSummary':
        return cls(
            id=int(payload['id']),
            hostname=str(payload['hostname']),
            fqdn=str(payload['fqdn']),
            public_url=str(payload['publicUrl']),
            key_id=(int(payload['keyId']) if payload.get('keyId') is not None else None),
            local_port=int(payload['localPort']),
            note=str(payload.get('note', '')),
            created_at=str(payload['createdAt']),
            expires_at=payload.get('expiresAt'),
            last_used_at=payload.get('lastUsedAt'),
            mode=str(payload['mode']),
            status=str(payload['status']),
            key_name=payload.get('keyName'),
            fingerprint=payload.get('fingerprint'),
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            'id': self.id,
            'hostname': self.hostname,
            'fqdn': self.fqdn,
            'publicUrl': self.public_url,
            'keyId': self.key_id,
            'localPort': self.local_port,
            'note': self.note,
            'createdAt': self.created_at,
            'expiresAt': self.expires_at,
            'lastUsedAt': self.last_used_at,
            'mode': self.mode,
            'status': self.status,
        }
        if self.key_name is not None:
            payload['keyName'] = self.key_name
        if self.fingerprint is not None:
            payload['fingerprint'] = self.fingerprint
        return payload


@dataclass(slots=True)
class SessionSummary:
    id: str
    hostname: str
    status: str
    delete_on_disconnect: bool
    created_at: str
    completed_at: str | None

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> 'SessionSummary':
        return cls(
            id=str(payload['id']),
            hostname=str(payload['hostname']),
            status=str(payload['status']),
            delete_on_disconnect=bool(payload['deleteOnDisconnect']),
            created_at=str(payload['createdAt']),
            completed_at=payload.get('completedAt'),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            'id': self.id,
            'hostname': self.hostname,
            'status': self.status,
            'deleteOnDisconnect': self.delete_on_disconnect,
            'createdAt': self.created_at,
            'completedAt': self.completed_at,
        }


@dataclass(slots=True)
class ConnectionProfile:
    ssh_host: str
    ssh_port: int
    ssh_user: str
    remote_hostname: str
    local_host: str
    local_port: int
    public_url: str
    ssh_command: str
    ssh_args: list[str]
    ssh_config_snippet: str

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> 'ConnectionProfile':
        return cls(
            ssh_host=str(payload['sshHost']),
            ssh_port=int(payload['sshPort']),
            ssh_user=str(payload['sshUser']),
            remote_hostname=str(payload['remoteHostname']),
            local_host=str(payload['localHost']),
            local_port=int(payload['localPort']),
            public_url=str(payload['publicUrl']),
            ssh_command=str(payload['sshCommand']),
            ssh_args=[str(item) for item in payload.get('sshArgs', [])],
            ssh_config_snippet=str(payload['sshConfigSnippet']),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            'sshHost': self.ssh_host,
            'sshPort': self.ssh_port,
            'sshUser': self.ssh_user,
            'remoteHostname': self.remote_hostname,
            'localHost': self.local_host,
            'localPort': self.local_port,
            'publicUrl': self.public_url,
            'sshCommand': self.ssh_command,
            'sshArgs': self.ssh_args,
            'sshConfigSnippet': self.ssh_config_snippet,
        }


@dataclass(slots=True)
class SavedProfile:
    name: str
    path: str

    def to_dict(self) -> dict[str, Any]:
        return {
            'name': self.name,
            'path': self.path,
        }


@dataclass(slots=True)
class PlanResult:
    mode: str
    meta: Meta
    key: KeySummary
    domain: DomainSummary
    connection_profile: ConnectionProfile
    session: SessionSummary | None = None
    saved_profile: SavedProfile | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            'ok': True,
            'mode': self.mode,
            'meta': self.meta.to_dict(),
            'key': self.key.to_dict(),
            'domain': self.domain.to_dict(),
            'connectionProfile': self.connection_profile.to_dict(),
            'launch': {
                'command': self.connection_profile.ssh_command,
                'args': self.connection_profile.ssh_args,
            },
        }
        if self.session is not None:
            payload['session'] = self.session.to_dict()
        if self.saved_profile is not None:
            payload['savedProfile'] = self.saved_profile.to_dict()
        return payload
