from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .client import ApiClient
from .config import RuntimeConfig
from .discovery import build_discovery_url
from .errors import ApiError, InteractiveInputRequiredError, RequestedAuthModeMismatchError, ValidationError
from .models import (
    Capabilities,
    ConnectionProfile,
    DiscoveryMetadata,
    DomainSummary,
    KeySummary,
    Meta,
    PlanResult,
    SavedProfile,
    SessionSummary,
)


@dataclass(slots=True)
class PlanOptions:
    key_selector: str | None = None
    domain_selector: str | None = None
    local_host: str = '127.0.0.1'
    local_port: int = 3000
    public_key_path: str | None = None
    key_lifetime_days: int | None = None
    domain_lifetime_days: int | None = None
    note: str | None = None
    save_profile: bool = False
    mode: str = 'plan'
    requested_auth_mode: str | None = None
    connection_mode: str | None = None
    oauth_client_policy: str | None = None
    runtime_name: str | None = None
    use_discovery: bool = True
    session_strategy: str | None = None
    enable_pkce: bool = False


class Planner:
    def __init__(self, client: ApiClient, config: RuntimeConfig):
        self._client = client
        self._config = config

    def build_plan(self, options: PlanOptions) -> PlanResult:
        meta = Meta.from_api(self._client.fetch_meta())
        capabilities = Capabilities.from_api(self._client.fetch_capabilities())
        payload = self.build_launch_payload(options, capabilities)
        data = self._client.get_launch_spec(payload)

        key = KeySummary.from_api(data['key'])
        domain = DomainSummary.from_api(data['domain'])
        connection_profile = ConnectionProfile.from_api(data['connectionProfile'])
        session = SessionSummary.from_api(data['session']) if data.get('session') else None
        discovery = self._load_discovery(meta, connection_profile, options)
        session_open_payload = self.build_session_open_payload(options, key, domain, connection_profile, session)
        auth_contract = self.build_auth_contract(meta, connection_profile, session, discovery)
        runtime_contract = self.build_runtime_contract(options, connection_profile, session)
        self._validate_requested_auth_mode(options, auth_contract, domain)

        saved_profile = None
        if options.save_profile:
            saved_profile = self._save_profile(meta, key, domain, connection_profile, session)

        return PlanResult(
            mode=options.mode,
            meta=meta,
            key=key,
            domain=domain,
            connection_profile=connection_profile,
            session=session,
            saved_profile=saved_profile,
            capabilities=capabilities,
            discovery=discovery,
            session_open_payload=session_open_payload,
            auth=auth_contract,
            runtime=runtime_contract,
        )

    def build_launch_payload(self, options: PlanOptions, capabilities: Capabilities | None = None) -> dict[str, Any]:
        capabilities = capabilities or Capabilities.from_api(self._client.fetch_capabilities())
        if not options.domain_selector:
            raise InteractiveInputRequiredError(
                missing=['domainMode'],
                choices={'domainMode': ['existing', 'new', 'ephemeral_random']},
            )

        domain_mode, domain_value = _split_selector(
            options.domain_selector,
            label='domain',
            allow_bare_random=True,
        )
        local = {
            'host': options.local_host,
            'port': options.local_port,
        }
        root_payload: dict[str, Any] = {
            'local': local,
        }
        if options.requested_auth_mode:
            root_payload['requestedAuthMode'] = options.requested_auth_mode
        if options.connection_mode:
            root_payload['connectionMode'] = options.connection_mode
        if options.oauth_client_policy:
            root_payload['oauthClientPolicy'] = options.oauth_client_policy
        if options.runtime_name:
            root_payload['runtimeName'] = options.runtime_name
        if options.session_strategy:
            root_payload['sessionStrategy'] = options.session_strategy
        if options.enable_pkce:
            root_payload['enablePkce'] = True

        if domain_mode in {'random', 'ephemeral', 'ephemeral_random'}:
            if not capabilities.ephemeral.enabled or not capabilities.domains.supports_random_ephemeral:
                raise ValidationError('Random ephemeral domains are not available for this token.')
            key_payload = self._build_key_payload(options, capabilities, required=True)
            root_payload.update(
                {
                    'domainMode': 'ephemeral_random',
                    'domain': {'note': options.note or ''},
                    'key': key_payload,
                }
            )
            return root_payload

        if domain_mode == 'new':
            if not capabilities.domains.can_create:
                raise ValidationError('Creating persistent domains is not allowed for this token.')
            self._validate_domain_lifetime(options.domain_lifetime_days, capabilities)
            key_payload = self._build_key_payload(options, capabilities, required=True)
            root_payload.update(
                {
                    'domainMode': 'new',
                    'domain': {
                        'hostname': domain_value,
                        'requestedLifetimeDays': options.domain_lifetime_days,
                        'note': options.note or '',
                    },
                    'key': key_payload,
                }
            )
            return root_payload

        if domain_mode in {'existing', 'id', 'existing-id'}:
            domain = self._resolve_domain(domain_mode, domain_value)
            key_payload = None
            if domain.key_id is None:
                key_payload = self._build_key_payload(options, capabilities, required=True)
            root_payload.update(
                {
                    'domainMode': 'existing',
                    'domain': {'domainId': domain.id},
                    'key': key_payload,
                }
            )
            return root_payload

        raise ValidationError(
            f'Unsupported domain selector mode {domain_mode!r}.',
            details={'selector': options.domain_selector},
        )

    def build_session_open_payload(
        self,
        options: PlanOptions,
        key: KeySummary,
        domain: DomainSummary,
        connection_profile: ConnectionProfile,
        session: SessionSummary | None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            'runtimeName': options.runtime_name or domain.hostname,
            'keyId': key.id,
            'domainId': domain.id,
            'hostname': domain.hostname,
            'publicUrl': connection_profile.public_url,
            'local': {
                'host': connection_profile.local_host,
                'port': connection_profile.local_port,
            },
            'authMode': connection_profile.auth_mode or domain.auth_mode or options.requested_auth_mode,
            'connectionMode': connection_profile.connection_mode or domain.connection_mode or options.connection_mode,
        }
        if connection_profile.oauth_client_policy or options.oauth_client_policy:
            payload['oauthClientPolicy'] = connection_profile.oauth_client_policy or options.oauth_client_policy
        if options.session_strategy:
            payload['sessionStrategy'] = options.session_strategy
        if options.enable_pkce:
            payload['enablePkce'] = True
        if session is not None and session.resume_token:
            payload['resumeToken'] = session.resume_token
        return payload

    def build_auth_contract(
        self,
        meta: Meta,
        connection_profile: ConnectionProfile,
        session: SessionSummary | None,
        discovery: DiscoveryMetadata | None,
    ) -> dict[str, Any]:
        return {
            'authMode': connection_profile.auth_mode or (session.auth_mode if session else None),
            'connectionMode': connection_profile.connection_mode or (session.connection_mode if session else None),
            'authDomain': meta.auth_domain,
            'discoveryUrl': connection_profile.discovery_url or meta.oauth_authorization_server or build_discovery_url(auth_domain=meta.auth_domain),
            'authorizeUrl': connection_profile.authorize_url or (discovery.authorization_endpoint if discovery else None),
            'tokenUrl': connection_profile.token_url or (discovery.token_endpoint if discovery else None),
            'introspectUrl': connection_profile.introspect_url or (discovery.introspection_endpoint if discovery else None),
            'tokenVerification': connection_profile.token_verification or meta.oauth_token_verification,
            'oauthClientPolicy': connection_profile.oauth_client_policy,
        }

    def build_runtime_contract(
        self,
        options: PlanOptions,
        connection_profile: ConnectionProfile,
        session: SessionSummary | None,
    ) -> dict[str, Any]:
        return {
            'name': options.runtime_name,
            'publicUrl': connection_profile.public_url,
            'sessionId': session.id if session else None,
            'resumeToken': session.resume_token if session else None,
            'proxySessionId': session.proxy_session_id if session else None,
            'requestedAuthMode': options.requested_auth_mode,
            'connectionMode': connection_profile.connection_mode or options.connection_mode,
            'sessionStrategy': options.session_strategy,
            'useDiscovery': options.use_discovery,
            'enablePkce': options.enable_pkce,
        }

    def _validate_requested_auth_mode(
        self,
        options: PlanOptions,
        auth_contract: dict[str, Any],
        domain: DomainSummary,
    ) -> None:
        requested = options.requested_auth_mode
        actual = auth_contract.get('authMode')
        if not requested or not actual:
            return
        if actual == requested or actual == 'dual':
            return
        raise RequestedAuthModeMismatchError(
            requested=requested,
            actual=str(actual),
            details={
                'domainId': domain.id,
                'hostname': domain.hostname,
            },
        )

    def _load_discovery(
        self,
        meta: Meta,
        connection_profile: ConnectionProfile,
        options: PlanOptions,
    ) -> DiscoveryMetadata | None:
        if not options.use_discovery:
            return None
        discovery_url = (
            connection_profile.discovery_url
            or meta.oauth_authorization_server
            or build_discovery_url(auth_domain=meta.auth_domain)
        )
        if not discovery_url:
            return None
        try:
            payload = self._client.fetch_oauth_authorization_server(discovery_url=discovery_url)
        except ApiError:
            return None
        return DiscoveryMetadata.from_api(payload)

    def _build_key_payload(
        self,
        options: PlanOptions,
        capabilities: Capabilities,
        *,
        required: bool,
    ) -> dict[str, Any] | None:
        if not options.key_selector:
            if required:
                raise InteractiveInputRequiredError(
                    missing=['keySelection'],
                    choices={'keySelection': ['existing', 'register_public_key']},
                )
            return None

        key_mode, key_value = _split_selector(options.key_selector, label='key')
        if key_mode in {'existing', 'id', 'existing-id'}:
            key = self._resolve_key(key_mode, key_value)
            return {
                'mode': 'existing',
                'keyId': key.id,
            }

        if key_mode == 'new':
            if not capabilities.keys.can_create:
                raise ValidationError('Creating keys is not allowed for this token.')
            self._validate_key_lifetime(options.key_lifetime_days, capabilities)
            if not options.public_key_path:
                raise InteractiveInputRequiredError(missing=['publicKeyPath'])
            public_key = Path(options.public_key_path).expanduser().read_text(encoding='utf-8').strip()
            if not public_key:
                raise ValidationError('Public key file is empty.', details={'path': options.public_key_path})
            return {
                'mode': 'register_public_key',
                'name': key_value,
                'publicKey': public_key,
                'requestedLifetimeDays': options.key_lifetime_days,
            }

        raise ValidationError(
            f'Unsupported key selector mode {key_mode!r}.',
            details={'selector': options.key_selector},
        )

    def _resolve_key(self, mode: str, value: str) -> KeySummary:
        if mode in {'id', 'existing-id'}:
            return KeySummary.from_api(
                {
                    'id': int(value),
                    'name': f'key-{value}',
                    'fingerprint': '',
                    'createdAt': '',
                    'expiresAt': None,
                    'lastUsedAt': None,
                    'status': 'active',
                }
            )

        keys = [KeySummary.from_api(item) for item in self._client.list_keys()]
        for key in keys:
            if key.name == value:
                return key
        raise ValidationError(f"Key '{value}' was not found.")

    def _resolve_domain(self, mode: str, value: str) -> DomainSummary:
        domains = [DomainSummary.from_api(item) for item in self._client.list_domains()]
        if mode in {'id', 'existing-id'}:
            for domain in domains:
                if str(domain.id) == value:
                    return domain
            raise ValidationError(f"Domain id '{value}' was not found.")

        for domain in domains:
            if domain.hostname == value or domain.fqdn == value:
                return domain
        raise ValidationError(f"Domain '{value}' was not found.")

    def _validate_key_lifetime(self, lifetime_days: int | None, capabilities: Capabilities) -> None:
        if lifetime_days is None:
            return
        if lifetime_days < capabilities.keys.min_lifetime_days or lifetime_days > capabilities.keys.max_lifetime_days:
            raise ValidationError(
                'Key lifetime is outside the allowed range.',
                details={
                    'minLifetimeDays': capabilities.keys.min_lifetime_days,
                    'maxLifetimeDays': capabilities.keys.max_lifetime_days,
                    'requestedLifetimeDays': lifetime_days,
                },
            )

    def _validate_domain_lifetime(self, lifetime_days: int | None, capabilities: Capabilities) -> None:
        if lifetime_days is None:
            return
        if lifetime_days < capabilities.domains.min_lifetime_days or lifetime_days > capabilities.domains.max_lifetime_days:
            raise ValidationError(
                'Domain lifetime is outside the allowed range.',
                details={
                    'minLifetimeDays': capabilities.domains.min_lifetime_days,
                    'maxLifetimeDays': capabilities.domains.max_lifetime_days,
                    'requestedLifetimeDays': lifetime_days,
                },
            )

    def _save_profile(
        self,
        meta: Meta,
        key: KeySummary,
        domain: DomainSummary,
        connection_profile: ConnectionProfile,
        session: SessionSummary | None,
    ) -> SavedProfile:
        target_path = self._config.profiles_dir / f'{domain.hostname}.json'
        payload: dict[str, Any] = {
            'meta': meta.to_dict(),
            'key': key.to_dict(),
            'domain': domain.to_dict(),
            'connectionProfile': connection_profile.to_dict(),
        }
        if session is not None:
            payload['session'] = session.to_dict()
        temp_path = target_path.with_suffix(target_path.suffix + '.tmp')
        temp_path.write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')
        temp_path.replace(target_path)
        return SavedProfile(name=domain.hostname, path=str(target_path))



def _split_selector(selector: str, *, label: str, allow_bare_random: bool = False) -> tuple[str, str]:
    normalized = selector.strip()
    if allow_bare_random and normalized in {'random', 'ephemeral', 'ephemeral_random'}:
        return normalized, ''
    if ':' not in normalized:
        raise ValidationError(
            f'{label} selector must use the form <mode>:<value>.',
            details={'selector': selector},
        )
    mode, value = normalized.split(':', 1)
    mode = mode.strip()
    value = value.strip()
    if not mode or not value:
        raise ValidationError(f"Invalid {label} selector '{selector}'.")
    return mode, value


__all__ = ['PlanOptions', 'Planner', '_split_selector']
