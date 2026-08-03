from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any



def _str_or_none(value: Any) -> str | None:
    return None if value is None else str(value)



def _int_or_none(value: Any) -> int | None:
    return None if value is None else int(value)



def _bool_or_none(value: Any) -> bool | None:
    return None if value is None else bool(value)



def _list_of_strings(value: Any) -> list[str]:
    if value is None:
        return []
    return [str(item) for item in value]


@dataclass(slots=True)
class DiscoveryMetadata:
    issuer: str | None = None
    authorization_endpoint: str | None = None
    token_endpoint: str | None = None
    introspection_endpoint: str | None = None
    revocation_endpoint: str | None = None
    registration_endpoint: str | None = None
    jwks_uri: str | None = None
    service_documentation: str | None = None
    code_challenge_methods_supported: list[str] = field(default_factory=list)
    grant_types_supported: list[str] = field(default_factory=list)
    response_types_supported: list[str] = field(default_factory=list)
    scopes_supported: list[str] = field(default_factory=list)
    token_endpoint_auth_methods_supported: list[str] = field(default_factory=list)
    introspection_endpoint_auth_methods_supported: list[str] = field(default_factory=list)
    token_verification_methods_supported: list[str] = field(default_factory=list)

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> 'DiscoveryMetadata':
        return cls(
            issuer=_str_or_none(payload.get('issuer')),
            authorization_endpoint=_str_or_none(payload.get('authorization_endpoint')),
            token_endpoint=_str_or_none(payload.get('token_endpoint')),
            introspection_endpoint=_str_or_none(payload.get('introspection_endpoint')),
            revocation_endpoint=_str_or_none(payload.get('revocation_endpoint')),
            registration_endpoint=_str_or_none(payload.get('registration_endpoint')),
            jwks_uri=_str_or_none(payload.get('jwks_uri')),
            service_documentation=_str_or_none(payload.get('service_documentation')),
            code_challenge_methods_supported=_list_of_strings(payload.get('code_challenge_methods_supported')),
            grant_types_supported=_list_of_strings(payload.get('grant_types_supported')),
            response_types_supported=_list_of_strings(payload.get('response_types_supported')),
            scopes_supported=_list_of_strings(payload.get('scopes_supported')),
            token_endpoint_auth_methods_supported=_list_of_strings(payload.get('token_endpoint_auth_methods_supported')),
            introspection_endpoint_auth_methods_supported=_list_of_strings(payload.get('introspection_endpoint_auth_methods_supported')),
            token_verification_methods_supported=_list_of_strings(payload.get('token_verification_methods_supported')),
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        for key, value in {
            'issuer': self.issuer,
            'authorization_endpoint': self.authorization_endpoint,
            'token_endpoint': self.token_endpoint,
            'introspection_endpoint': self.introspection_endpoint,
            'revocation_endpoint': self.revocation_endpoint,
            'registration_endpoint': self.registration_endpoint,
            'jwks_uri': self.jwks_uri,
            'service_documentation': self.service_documentation,
            'code_challenge_methods_supported': self.code_challenge_methods_supported,
            'grant_types_supported': self.grant_types_supported,
            'response_types_supported': self.response_types_supported,
            'scopes_supported': self.scopes_supported,
            'token_endpoint_auth_methods_supported': self.token_endpoint_auth_methods_supported,
            'introspection_endpoint_auth_methods_supported': self.introspection_endpoint_auth_methods_supported,
            'token_verification_methods_supported': self.token_verification_methods_supported,
        }.items():
            if value is None or value == []:
                continue
            payload[key] = value
        return payload


@dataclass(slots=True)
class ProtectedResourceMetadata:
    resource: str | None = None
    authorization_servers: list[str] = field(default_factory=list)
    scopes_supported: list[str] = field(default_factory=list)
    bearer_methods_supported: list[str] = field(default_factory=list)
    resource_documentation: str | None = None

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> 'ProtectedResourceMetadata':
        return cls(
            resource=_str_or_none(payload.get('resource')),
            authorization_servers=_list_of_strings(payload.get('authorization_servers')),
            scopes_supported=_list_of_strings(payload.get('scopes_supported')),
            bearer_methods_supported=_list_of_strings(payload.get('bearer_methods_supported')),
            resource_documentation=_str_or_none(payload.get('resource_documentation')),
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        for key, value in {
            'resource': self.resource,
            'authorization_servers': self.authorization_servers,
            'scopes_supported': self.scopes_supported,
            'bearer_methods_supported': self.bearer_methods_supported,
            'resource_documentation': self.resource_documentation,
        }.items():
            if value is None or value == []:
                continue
            payload[key] = value
        return payload


@dataclass(slots=True)
class TcpBridgeMeta:
    enabled: bool = False
    protocol: str | None = None
    host: str | None = None
    control_port: int | None = None
    public_base_domain: str | None = None
    requires_ssh_key: bool | None = None
    auth_required: bool | None = None

    @classmethod
    def from_api(cls, payload: dict[str, Any] | None) -> 'TcpBridgeMeta | None':
        if not payload:
            return None
        return cls(
            enabled=bool(payload.get('enabled', False)),
            protocol=_str_or_none(payload.get('protocol')),
            host=_str_or_none(payload.get('host')),
            control_port=_int_or_none(payload.get('controlPort')),
            public_base_domain=_str_or_none(payload.get('publicBaseDomain')),
            requires_ssh_key=_bool_or_none(payload.get('requiresSshKey')),
            auth_required=_bool_or_none(payload.get('authRequired')),
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {'enabled': self.enabled}
        if self.protocol is not None:
            payload['protocol'] = self.protocol
        if self.host is not None:
            payload['host'] = self.host
        if self.control_port is not None:
            payload['controlPort'] = self.control_port
        if self.public_base_domain is not None:
            payload['publicBaseDomain'] = self.public_base_domain
        if self.requires_ssh_key is not None:
            payload['requiresSshKey'] = self.requires_ssh_key
        if self.auth_required is not None:
            payload['authRequired'] = self.auth_required
        return payload


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
    auth_domain: str | None = None
    auth_base_url: str | None = None
    default_connection_mode: str | None = None
    oauth_authorization_server: str | None = None
    oauth_issuer: str | None = None
    oauth_proxy_enabled: bool | None = None
    oauth_token_verification: str | None = None
    tcp_bridge: TcpBridgeMeta | None = None

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
            auth_domain=_str_or_none(payload.get('authDomain')),
            auth_base_url=_str_or_none(payload.get('authBaseUrl')),
            default_connection_mode=_str_or_none(payload.get('defaultConnectionMode')),
            oauth_authorization_server=_str_or_none(payload.get('oauthAuthorizationServer')),
            oauth_issuer=_str_or_none(payload.get('oauthIssuer')),
            oauth_proxy_enabled=_bool_or_none(payload.get('oauthProxyEnabled')),
            oauth_token_verification=_str_or_none(payload.get('oauthTokenVerification')),
            tcp_bridge=TcpBridgeMeta.from_api(payload.get('tcpBridge')),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = {
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
        if self.auth_domain is not None:
            payload['authDomain'] = self.auth_domain
        if self.auth_base_url is not None:
            payload['authBaseUrl'] = self.auth_base_url
        if self.default_connection_mode is not None:
            payload['defaultConnectionMode'] = self.default_connection_mode
        if self.oauth_authorization_server is not None:
            payload['oauthAuthorizationServer'] = self.oauth_authorization_server
        if self.oauth_issuer is not None:
            payload['oauthIssuer'] = self.oauth_issuer
        if self.oauth_proxy_enabled is not None:
            payload['oauthProxyEnabled'] = self.oauth_proxy_enabled
        if self.oauth_token_verification is not None:
            payload['oauthTokenVerification'] = self.oauth_token_verification
        if self.tcp_bridge is not None:
            payload['tcpBridge'] = self.tcp_bridge.to_dict()
        return payload


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
            default_lifetime_days=_int_or_none(payload.get('defaultLifetimeDays')),
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
class OAuthProxyCapabilities:
    enabled: bool = False
    allow_temporary_url: bool | None = None
    auth_base_url: str | None = None
    auth_domain: str | None = None
    default_client_policy: str | None = None
    discovery_url: str | None = None
    dynamic_client_registration: bool | None = None
    issuer: str | None = None
    access_token_ttl_seconds: int | None = None
    refresh_token_ttl_seconds: int | None = None
    token_verification: str | None = None

    @classmethod
    def from_api(cls, payload: dict[str, Any] | None) -> 'OAuthProxyCapabilities':
        payload = payload or {}
        return cls(
            enabled=bool(payload.get('enabled', False)),
            allow_temporary_url=_bool_or_none(payload.get('allowTemporaryUrl')),
            auth_base_url=_str_or_none(payload.get('authBaseUrl')),
            auth_domain=_str_or_none(payload.get('authDomain')),
            default_client_policy=_str_or_none(payload.get('defaultClientPolicy')),
            discovery_url=_str_or_none(payload.get('discoveryUrl')),
            dynamic_client_registration=_bool_or_none(payload.get('dynamicClientRegistration')),
            issuer=_str_or_none(payload.get('issuer')),
            access_token_ttl_seconds=_int_or_none(payload.get('accessTokenTtlSeconds')),
            refresh_token_ttl_seconds=_int_or_none(payload.get('refreshTokenTtlSeconds')),
            token_verification=_str_or_none(payload.get('tokenVerification')),
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {'enabled': self.enabled}
        if self.allow_temporary_url is not None:
            payload['allowTemporaryUrl'] = self.allow_temporary_url
        if self.auth_base_url is not None:
            payload['authBaseUrl'] = self.auth_base_url
        if self.auth_domain is not None:
            payload['authDomain'] = self.auth_domain
        if self.default_client_policy is not None:
            payload['defaultClientPolicy'] = self.default_client_policy
        if self.discovery_url is not None:
            payload['discoveryUrl'] = self.discovery_url
        if self.dynamic_client_registration is not None:
            payload['dynamicClientRegistration'] = self.dynamic_client_registration
        if self.issuer is not None:
            payload['issuer'] = self.issuer
        if self.access_token_ttl_seconds is not None:
            payload['accessTokenTtlSeconds'] = self.access_token_ttl_seconds
        if self.refresh_token_ttl_seconds is not None:
            payload['refreshTokenTtlSeconds'] = self.refresh_token_ttl_seconds
        if self.token_verification is not None:
            payload['tokenVerification'] = self.token_verification
        return payload


@dataclass(slots=True)
class TcpBridgePortRange:
    min_port: int | None = None
    max_port: int | None = None

    @classmethod
    def from_api(cls, payload: dict[str, Any] | None) -> 'TcpBridgePortRange | None':
        if not payload:
            return None
        return cls(
            min_port=_int_or_none(payload.get('min')),
            max_port=_int_or_none(payload.get('max')),
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if self.min_port is not None:
            payload['min'] = self.min_port
        if self.max_port is not None:
            payload['max'] = self.max_port
        return payload


@dataclass(slots=True)
class TcpBridgeCapabilities:
    enabled: bool = False
    protocol: str | None = None
    host: str | None = None
    control_port: int | None = None
    public_base_domain: str | None = None
    port_range: TcpBridgePortRange | None = None
    supports_preconfigured_subdomains: bool | None = None
    supports_generated_subdomains: bool | None = None
    requires_ssh_key: bool | None = None
    auth_required: bool | None = None

    @classmethod
    def from_api(cls, payload: dict[str, Any] | None) -> 'TcpBridgeCapabilities | None':
        if not payload:
            return None
        return cls(
            enabled=bool(payload.get('enabled', False)),
            protocol=_str_or_none(payload.get('protocol')),
            host=_str_or_none(payload.get('host')),
            control_port=_int_or_none(payload.get('controlPort')),
            public_base_domain=_str_or_none(payload.get('publicBaseDomain')),
            port_range=TcpBridgePortRange.from_api(payload.get('portRange')),
            supports_preconfigured_subdomains=_bool_or_none(payload.get('supportsPreconfiguredSubdomains')),
            supports_generated_subdomains=_bool_or_none(payload.get('supportsGeneratedSubdomains')),
            requires_ssh_key=_bool_or_none(payload.get('requiresSshKey')),
            auth_required=_bool_or_none(payload.get('authRequired')),
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {'enabled': self.enabled}
        if self.protocol is not None:
            payload['protocol'] = self.protocol
        if self.host is not None:
            payload['host'] = self.host
        if self.control_port is not None:
            payload['controlPort'] = self.control_port
        if self.public_base_domain is not None:
            payload['publicBaseDomain'] = self.public_base_domain
        if self.port_range is not None:
            payload['portRange'] = self.port_range.to_dict()
        if self.supports_preconfigured_subdomains is not None:
            payload['supportsPreconfiguredSubdomains'] = self.supports_preconfigured_subdomains
        if self.supports_generated_subdomains is not None:
            payload['supportsGeneratedSubdomains'] = self.supports_generated_subdomains
        if self.requires_ssh_key is not None:
            payload['requiresSshKey'] = self.requires_ssh_key
        if self.auth_required is not None:
            payload['authRequired'] = self.auth_required
        return payload


@dataclass(slots=True)
class DomainCapabilities:
    can_create: bool
    can_delete: bool
    supports_random_ephemeral: bool
    min_lifetime_days: int
    max_lifetime_days: int
    default_lifetime_days: int | None
    supported_auth_modes: list[str] = field(default_factory=list)
    supported_connection_modes: list[str] = field(default_factory=list)
    default_connection_mode: str | None = None
    oauth_proxy: OAuthProxyCapabilities = field(default_factory=OAuthProxyCapabilities)
    supports_keyless_tcp_bridge: bool | None = None
    tcp_bridge: TcpBridgeCapabilities | None = None

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> 'DomainCapabilities':
        return cls(
            can_create=bool(payload['canCreate']),
            can_delete=bool(payload['canDelete']),
            supports_random_ephemeral=bool(payload['supportsRandomEphemeral']),
            min_lifetime_days=int(payload['minLifetimeDays']),
            max_lifetime_days=int(payload['maxLifetimeDays']),
            default_lifetime_days=_int_or_none(payload.get('defaultLifetimeDays')),
            supported_auth_modes=_list_of_strings(payload.get('supportedAuthModes')),
            supported_connection_modes=_list_of_strings(payload.get('supportedConnectionModes')),
            default_connection_mode=_str_or_none(payload.get('defaultConnectionMode')),
            oauth_proxy=OAuthProxyCapabilities.from_api(payload.get('oauthProxy')),
            supports_keyless_tcp_bridge=_bool_or_none(payload.get('supportsKeylessTcpBridge')),
            tcp_bridge=TcpBridgeCapabilities.from_api(payload.get('tcpBridge')),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = {
            'canCreate': self.can_create,
            'canDelete': self.can_delete,
            'supportsRandomEphemeral': self.supports_random_ephemeral,
            'minLifetimeDays': self.min_lifetime_days,
            'maxLifetimeDays': self.max_lifetime_days,
            'defaultLifetimeDays': self.default_lifetime_days,
        }
        if self.supported_auth_modes:
            payload['supportedAuthModes'] = self.supported_auth_modes
        if self.supported_connection_modes:
            payload['supportedConnectionModes'] = self.supported_connection_modes
        if self.default_connection_mode is not None:
            payload['defaultConnectionMode'] = self.default_connection_mode
        if self.oauth_proxy:
            payload['oauthProxy'] = self.oauth_proxy.to_dict()
        if self.supports_keyless_tcp_bridge is not None:
            payload['supportsKeylessTcpBridge'] = self.supports_keyless_tcp_bridge
        if self.tcp_bridge is not None:
            payload['tcpBridge'] = self.tcp_bridge.to_dict()
        return payload


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
    oauth_proxy: OAuthProxyCapabilities = field(default_factory=OAuthProxyCapabilities)
    known: bool = True

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> 'Capabilities':
        return cls(
            keys=KeyCapabilities.from_api(payload['keys']),
            domains=DomainCapabilities.from_api(payload['domains']),
            ephemeral=EphemeralCapabilities.from_api(payload['ephemeral']),
            oauth_proxy=OAuthProxyCapabilities.from_api(payload.get('oauthProxy')),
        )

    @classmethod
    def unknown(cls) -> 'Capabilities':
        """Placeholder used when the server declines to describe capabilities.

        Some plans do not expose ``/v1/capabilities``. Refusing to launch in
        that case would be wrong: the server is the source of truth and will
        reject anything it does not allow. So the client stops second-guessing
        and lets the request through, with ``known`` marking the values as
        placeholders rather than facts.
        """
        return cls(
            keys=KeyCapabilities(
                max_count=0,
                can_create=True,
                can_delete=True,
                min_lifetime_days=0,
                max_lifetime_days=36500,
                default_lifetime_days=None,
            ),
            domains=DomainCapabilities(
                can_create=True,
                can_delete=True,
                supports_random_ephemeral=True,
                min_lifetime_days=0,
                max_lifetime_days=36500,
                default_lifetime_days=None,
            ),
            ephemeral=EphemeralCapabilities(
                enabled=True,
                delete_on_disconnect=True,
                fallback_lifetime_hours=24,
            ),
            known=False,
        )

    def to_dict(self) -> dict[str, Any]:
        payload = {
            'keys': self.keys.to_dict(),
            'domains': self.domains.to_dict(),
            'ephemeral': self.ephemeral.to_dict(),
        }
        if self.oauth_proxy:
            payload['oauthProxy'] = self.oauth_proxy.to_dict()
        if not self.known:
            payload['known'] = False
        return payload


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
            expires_at=_str_or_none(payload.get('expiresAt')),
            last_used_at=_str_or_none(payload.get('lastUsedAt')),
            status=str(payload['status']),
            domain_count=_int_or_none(payload.get('domainCount')),
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
    auth_mode: str | None = None
    stable_url_required: bool | None = None
    oauth_client_policy: str | None = None
    connection_mode: str | None = None
    route_state: str | None = None
    last_heartbeat_at: str | None = None
    tcp_bridge_password: str | None = None

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> 'DomainSummary':
        return cls(
            id=int(payload['id']),
            hostname=str(payload['hostname']),
            fqdn=str(payload['fqdn']),
            public_url=str(payload['publicUrl']),
            key_id=_int_or_none(payload.get('keyId')),
            local_port=int(payload['localPort']),
            note=str(payload.get('note', '')),
            created_at=str(payload['createdAt']),
            expires_at=_str_or_none(payload.get('expiresAt')),
            last_used_at=_str_or_none(payload.get('lastUsedAt')),
            mode=str(payload['mode']),
            status=str(payload['status']),
            key_name=_str_or_none(payload.get('keyName')),
            fingerprint=_str_or_none(payload.get('fingerprint')),
            auth_mode=_str_or_none(payload.get('authMode')),
            stable_url_required=_bool_or_none(payload.get('stableUrlRequired')),
            oauth_client_policy=_str_or_none(payload.get('oauthClientPolicy')),
            connection_mode=_str_or_none(payload.get('connectionMode')),
            route_state=_str_or_none(payload.get('routeState')),
            last_heartbeat_at=_str_or_none(payload.get('lastHeartbeatAt')),
            tcp_bridge_password=_str_or_none(payload.get('tcpBridgePassword')),
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
        for key, value in {
            'keyName': self.key_name,
            'fingerprint': self.fingerprint,
            'authMode': self.auth_mode,
            'stableUrlRequired': self.stable_url_required,
            'oauthClientPolicy': self.oauth_client_policy,
            'connectionMode': self.connection_mode,
            'routeState': self.route_state,
            'lastHeartbeatAt': self.last_heartbeat_at,
            'tcpBridgePassword': self.tcp_bridge_password,
        }.items():
            if value is not None:
                payload[key] = value
        return payload


@dataclass(slots=True)
class SessionSummary:
    id: str
    hostname: str
    status: str
    delete_on_disconnect: bool
    created_at: str
    completed_at: str | None
    resume_token: str | None = None
    route_state: str | None = None
    last_heartbeat_at: str | None = None
    auth_mode: str | None = None
    connection_mode: str | None = None
    proxy_session_id: str | None = None
    public_url: str | None = None

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> 'SessionSummary':
        return cls(
            id=str(payload['id']),
            hostname=str(payload.get('hostname', '')),
            status=str(payload.get('status', 'unknown')),
            delete_on_disconnect=bool(payload.get('deleteOnDisconnect', False)),
            created_at=str(payload.get('createdAt', '')),
            completed_at=_str_or_none(payload.get('completedAt')),
            resume_token=_str_or_none(payload.get('resumeToken')),
            route_state=_str_or_none(payload.get('routeState')),
            last_heartbeat_at=_str_or_none(payload.get('lastHeartbeatAt')),
            auth_mode=_str_or_none(payload.get('authMode')),
            connection_mode=_str_or_none(payload.get('connectionMode')),
            proxy_session_id=_str_or_none(payload.get('proxySessionId')),
            public_url=_str_or_none(payload.get('publicUrl')),
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            'id': self.id,
            'hostname': self.hostname,
            'status': self.status,
            'deleteOnDisconnect': self.delete_on_disconnect,
            'createdAt': self.created_at,
            'completedAt': self.completed_at,
        }
        for key, value in {
            'resumeToken': self.resume_token,
            'routeState': self.route_state,
            'lastHeartbeatAt': self.last_heartbeat_at,
            'authMode': self.auth_mode,
            'connectionMode': self.connection_mode,
            'proxySessionId': self.proxy_session_id,
            'publicUrl': self.public_url,
        }.items():
            if value is not None:
                payload[key] = value
        return payload


@dataclass(slots=True)
class TcpBridgeClientProtocol:
    hello: dict[str, Any] | None = None

    @classmethod
    def from_api(cls, payload: dict[str, Any] | None) -> 'TcpBridgeClientProtocol | None':
        if not payload:
            return None
        hello = payload.get('hello')
        return cls(hello=dict(hello) if isinstance(hello, dict) else None)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if self.hello is not None:
            payload['hello'] = self.hello
        return payload


@dataclass(slots=True)
class TcpBridgeProfile:
    enabled: bool = False
    protocol: str | None = None
    auth_required: bool | None = None
    requires_ssh_key: bool | None = None
    requires_api_token: bool | None = None
    password_required: bool | None = None
    host: str | None = None
    control_port: int | None = None
    public_port: int | None = None
    public_base_domain: str | None = None
    hostname: str | None = None
    public_url: str | None = None
    local_host: str | None = None
    local_port: int | None = None
    preconfigured_subdomain: bool | None = None
    generated_subdomain: bool | None = None
    token: str | None = None
    command: str | None = None
    args: list[str] = field(default_factory=list)
    client_protocol: TcpBridgeClientProtocol | None = None

    @classmethod
    def from_api(cls, payload: dict[str, Any] | None) -> 'TcpBridgeProfile | None':
        if not payload:
            return None
        return cls(
            enabled=bool(payload.get('enabled', False)),
            protocol=_str_or_none(payload.get('protocol')),
            auth_required=_bool_or_none(payload.get('authRequired')),
            requires_ssh_key=_bool_or_none(payload.get('requiresSshKey')),
            requires_api_token=_bool_or_none(payload.get('requiresApiToken')),
            password_required=_bool_or_none(payload.get('passwordRequired')),
            host=_str_or_none(payload.get('host')),
            control_port=_int_or_none(payload.get('controlPort')),
            public_port=_int_or_none(payload.get('publicPort')),
            public_base_domain=_str_or_none(payload.get('publicBaseDomain')),
            hostname=_str_or_none(payload.get('hostname')),
            public_url=_str_or_none(payload.get('publicUrl')),
            local_host=_str_or_none(payload.get('localHost')),
            local_port=_int_or_none(payload.get('localPort')),
            preconfigured_subdomain=_bool_or_none(payload.get('preconfiguredSubdomain')),
            generated_subdomain=_bool_or_none(payload.get('generatedSubdomain')),
            token=_str_or_none(payload.get('token')),
            command=_str_or_none(payload.get('command')),
            args=_list_of_strings(payload.get('args')),
            client_protocol=TcpBridgeClientProtocol.from_api(payload.get('clientProtocol')),
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {'enabled': self.enabled}
        if self.protocol is not None:
            payload['protocol'] = self.protocol
        if self.auth_required is not None:
            payload['authRequired'] = self.auth_required
        if self.requires_ssh_key is not None:
            payload['requiresSshKey'] = self.requires_ssh_key
        if self.requires_api_token is not None:
            payload['requiresApiToken'] = self.requires_api_token
        if self.password_required is not None:
            payload['passwordRequired'] = self.password_required
        if self.host is not None:
            payload['host'] = self.host
        if self.control_port is not None:
            payload['controlPort'] = self.control_port
        if self.public_port is not None:
            payload['publicPort'] = self.public_port
        if self.public_base_domain is not None:
            payload['publicBaseDomain'] = self.public_base_domain
        if self.hostname is not None:
            payload['hostname'] = self.hostname
        if self.public_url is not None:
            payload['publicUrl'] = self.public_url
        if self.local_host is not None:
            payload['localHost'] = self.local_host
        if self.local_port is not None:
            payload['localPort'] = self.local_port
        if self.preconfigured_subdomain is not None:
            payload['preconfiguredSubdomain'] = self.preconfigured_subdomain
        if self.generated_subdomain is not None:
            payload['generatedSubdomain'] = self.generated_subdomain
        if self.token is not None:
            payload['token'] = self.token
        if self.command is not None:
            payload['command'] = self.command
        if self.args:
            payload['args'] = self.args
        if self.client_protocol is not None:
            payload['clientProtocol'] = self.client_protocol.to_dict()
        return payload


@dataclass(slots=True)
class ConnectionProfile:
    ssh_host: str | None = None
    ssh_port: int | None = None
    ssh_user: str | None = None
    remote_hostname: str | None = None
    local_host: str | None = None
    local_port: int | None = None
    public_url: str | None = None
    ssh_command: str | None = None
    ssh_args: list[str] = field(default_factory=list)
    ssh_config_snippet: str | None = None
    auth_mode: str | None = None
    connection_mode: str | None = None
    oauth_client_policy: str | None = None
    discovery_url: str | None = None
    authorize_url: str | None = None
    token_url: str | None = None
    introspect_url: str | None = None
    token_verification: str | None = None
    requires_ssh_key: bool | None = None
    requires_api_token: bool | None = None
    tcp_bridge: TcpBridgeProfile | None = None

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> 'ConnectionProfile':
        return cls(
            ssh_host=_str_or_none(payload.get('sshHost')),
            ssh_port=_int_or_none(payload.get('sshPort')),
            ssh_user=_str_or_none(payload.get('sshUser')),
            remote_hostname=_str_or_none(payload.get('remoteHostname')),
            local_host=_str_or_none(payload.get('localHost')),
            local_port=_int_or_none(payload.get('localPort')),
            public_url=_str_or_none(payload.get('publicUrl')),
            ssh_command=_str_or_none(payload.get('sshCommand')),
            ssh_args=[str(item) for item in payload.get('sshArgs', [])],
            ssh_config_snippet=_str_or_none(payload.get('sshConfigSnippet')),
            auth_mode=_str_or_none(payload.get('authMode')),
            connection_mode=_str_or_none(payload.get('connectionMode')),
            oauth_client_policy=_str_or_none(payload.get('oauthClientPolicy')),
            discovery_url=_str_or_none(payload.get('discoveryUrl')),
            authorize_url=_str_or_none(payload.get('authorizeUrl')),
            token_url=_str_or_none(payload.get('tokenUrl')),
            introspect_url=_str_or_none(payload.get('introspectUrl')),
            token_verification=_str_or_none(payload.get('tokenVerification')),
            requires_ssh_key=_bool_or_none(payload.get('requiresSshKey')),
            requires_api_token=_bool_or_none(payload.get('requiresApiToken')),
            tcp_bridge=TcpBridgeProfile.from_api(payload.get('tcpBridge')),
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        for key, value in {
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
            'authMode': self.auth_mode,
            'connectionMode': self.connection_mode,
            'oauthClientPolicy': self.oauth_client_policy,
            'discoveryUrl': self.discovery_url,
            'authorizeUrl': self.authorize_url,
            'tokenUrl': self.token_url,
            'introspectUrl': self.introspect_url,
            'tokenVerification': self.token_verification,
            'requiresSshKey': self.requires_ssh_key,
            'requiresApiToken': self.requires_api_token,
        }.items():
            if value is None or value == []:
                continue
            payload[key] = value
        if self.tcp_bridge is not None:
            payload['tcpBridge'] = self.tcp_bridge.to_dict()
        return payload

    @property
    def effective_command(self) -> str:
        if self.tcp_bridge and self.tcp_bridge.enabled:
            return self.tcp_bridge.command or ''
        return self.ssh_command or ''

    @property
    def effective_args(self) -> list[str]:
        if self.tcp_bridge and self.tcp_bridge.enabled:
            return self.tcp_bridge.args
        return self.ssh_args

    @property
    def effective_transport(self) -> str:
        if self.connection_mode == 'tcp_bridge' and self.tcp_bridge and self.tcp_bridge.enabled:
            return 'tcp_bridge'
        return 'ssh'

    @property
    def is_tcp_bridge(self) -> bool:
        return self.connection_mode == 'tcp_bridge' and self.tcp_bridge is not None and self.tcp_bridge.enabled

    @property
    def is_keyless(self) -> bool:
        if self.requires_ssh_key is False:
            return True
        if self.tcp_bridge and self.tcp_bridge.requires_ssh_key is False:
            return True
        return False

    @property
    def is_tokenless(self) -> bool:
        if self.requires_api_token is False:
            return True
        if self.tcp_bridge and self.tcp_bridge.requires_api_token is False:
            return True
        return False


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
    meta: Meta | None
    key: KeySummary | None
    domain: DomainSummary | None
    connection_profile: ConnectionProfile
    session: SessionSummary | None = None
    saved_profile: SavedProfile | None = None
    capabilities: Capabilities | None = None
    discovery: DiscoveryMetadata | None = None
    protected_resource: ProtectedResourceMetadata | None = None
    session_open_payload: dict[str, Any] | None = None
    auth: dict[str, Any] | None = None
    runtime: dict[str, Any] | None = None
    degraded: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            'ok': True,
            'mode': self.mode,
            'connectionProfile': self.connection_profile.to_dict(),
            'launch': {
                'command': self.connection_profile.effective_command,
                'args': self.connection_profile.effective_args,
                'transport': self.connection_profile.effective_transport,
            },
        }
        if self.meta is not None:
            payload['meta'] = self.meta.to_dict()
        if self.domain is not None:
            payload['domain'] = self.domain.to_dict()
        if self.key is not None:
            payload['key'] = self.key.to_dict()
        if self.capabilities is not None:
            payload['capabilities'] = self.capabilities.to_dict()
        if self.discovery is not None:
            payload['discovery'] = self.discovery.to_dict()
        if self.protected_resource is not None:
            payload['protectedResource'] = self.protected_resource.to_dict()
        if self.session_open_payload is not None:
            payload['sessionOpenPayload'] = self.session_open_payload
        if self.auth is not None:
            payload['auth'] = self.auth
        if self.runtime is not None:
            payload['runtime'] = self.runtime
        if self.session is not None:
            payload['session'] = self.session.to_dict()
        if self.saved_profile is not None:
            payload['savedProfile'] = self.saved_profile.to_dict()
        if self.degraded:
            payload['degraded'] = list(self.degraded)
        return payload
