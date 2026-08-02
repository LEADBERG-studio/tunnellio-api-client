from pathlib import Path

from tunnellio.models import Capabilities
from tunnellio.planner import PlanOptions, Planner, _split_selector
from tunnellio.errors import InteractiveInputRequiredError, RequestedAuthModeMismatchError, ValidationError


class DummyClient:
    def fetch_meta(self):
        return {
            'apiVersion': '1',
            'serverVersion': '2',
            'siteDomain': 'tunnellio.ru',
            'apiDomain': 'api.tunnellio.ru',
            'apiBaseUrl': 'https://api.tunnellio.ru',
            'tunnelDomain': 'tunnellio.site',
            'sshHost': 'ssh.tunnellio.site',
            'sshPort': 22,
            'sshUser': 'tunnel',
            'installShUrl': 'https://example/install.sh',
            'installPs1Url': 'https://example/install.ps1',
            'authDomain': 'auth.example.com',
            'oauthAuthorizationServer': 'https://auth.example.com/.well-known/oauth-authorization-server',
            'oauthTokenVerification': 'introspection',
        }

    def fetch_capabilities(self):
        return {
            'keys': {
                'maxCount': 10,
                'canCreate': True,
                'canDelete': True,
                'minLifetimeDays': 1,
                'maxLifetimeDays': 365,
                'defaultLifetimeDays': 30,
            },
            'domains': {
                'canCreate': True,
                'canDelete': True,
                'supportsRandomEphemeral': True,
                'minLifetimeDays': 1,
                'maxLifetimeDays': 365,
                'defaultLifetimeDays': 30,
                'supportedAuthModes': ['legacy', 'oauth', 'dual'],
                'supportedConnectionModes': ['cloud_proxy', 'tcp_bridge', 'auto'],
                'defaultConnectionMode': 'cloud_proxy',
                'supportsKeylessTcpBridge': True,
                'tcpBridge': {
                    'enabled': True,
                    'protocol': 'bore',
                    'host': 'tunnel.example.net',
                    'controlPort': 7835,
                    'publicBaseDomain': 'tunnel.example.net',
                    'portRange': {'min': 51000, 'max': 51999},
                    'supportsPreconfiguredSubdomains': True,
                    'supportsGeneratedSubdomains': True,
                    'requiresSshKey': False,
                    'authRequired': False,
                },
                'oauthProxy': {
                    'enabled': True,
                    'allowTemporaryUrl': True,
                    'defaultClientPolicy': 'shared',
                    'dynamicClientRegistration': True,
                    'accessTokenTtlSeconds': 3600,
                    'refreshTokenTtlSeconds': 86400,
                },
            },
            'ephemeral': {
                'enabled': True,
                'deleteOnDisconnect': True,
                'fallbackLifetimeHours': 24,
            },
        }

    def list_keys(self):
        return [
            {
                'id': 1,
                'name': 'work',
                'fingerprint': 'SHA256:test',
                'createdAt': '2026-07-22T18:20:00+00:00',
                'expiresAt': None,
                'lastUsedAt': None,
                'status': 'active',
            }
        ]

    def list_domains(self):
        return [
            {
                'id': 2,
                'hostname': 'demo',
                'fqdn': 'demo.tunnellio.site',
                'publicUrl': 'https://demo.tunnellio.site',
                'keyId': None,
                'localPort': 3000,
                'note': '',
                'createdAt': '2026-07-22T18:25:00+00:00',
                'expiresAt': None,
                'lastUsedAt': None,
                'mode': 'persistent',
                'status': 'active',
                'authMode': 'oauth',
                'connectionMode': 'cloud_proxy',
            }
        ]

    def get_launch_spec(self, payload):
        return {
            'key': self.list_keys()[0],
            'domain': self.list_domains()[0],
            'connectionProfile': {
                'sshHost': 'ssh.tunnellio.site',
                'sshPort': 22,
                'sshUser': 'tunnel',
                'remoteHostname': 'demo',
                'localHost': '127.0.0.1',
                'localPort': 4040,
                'publicUrl': 'https://demo.tunnellio.site',
                'sshCommand': 'ssh ...',
                'sshArgs': ['ssh', '-N'],
                'sshConfigSnippet': 'Host demo',
                'authMode': 'oauth',
                'connectionMode': 'cloud_proxy',
                'oauthClientPolicy': 'shared',
                'discoveryUrl': 'https://auth.example.com/.well-known/oauth-authorization-server',
                'authorizeUrl': 'https://auth.example.com/authorize',
                'tokenUrl': 'https://auth.example.com/token',
                'introspectUrl': 'https://auth.example.com/introspect',
                'tokenVerification': 'introspection',
            },
            'session': {
                'id': 'sess_123',
                'hostname': 'demo',
                'status': 'active',
                'deleteOnDisconnect': True,
                'createdAt': '2026-07-22T18:25:00+00:00',
                'resumeToken': 'resume_123',
                'authMode': 'oauth',
                'connectionMode': 'cloud_proxy',
                'proxySessionId': 'proxy_123',
            },
        }

    def fetch_oauth_authorization_server(self, **kwargs):
        return {
            'issuer': 'https://auth.example.com',
            'authorization_endpoint': 'https://auth.example.com/authorize',
            'token_endpoint': 'https://auth.example.com/token',
            'introspection_endpoint': 'https://auth.example.com/introspect',
            'code_challenge_methods_supported': ['S256'],
            'scopes_supported': ['mcp.read', 'mcp.write'],
            'token_endpoint_auth_methods_supported': ['none'],
            'introspection_endpoint_auth_methods_supported': ['client_secret_post'],
        }

    def fetch_oauth_protected_resource(self, **kwargs):
        if kwargs.get('resource_metadata_url') == 'https://demo.tunnellio.site/.well-known/oauth-protected-resource':
            return {}
        return {
            'resource': 'https://auth.example.com',
            'authorization_servers': ['https://auth.example.com'],
            'scopes_supported': ['mcp.read', 'mcp.write'],
            'bearer_methods_supported': ['header'],
        }


class TcpBridgeDummyClient(DummyClient):
    """Client that returns a tcp_bridge connection profile without a key."""

    def get_launch_spec(self, payload):
        return {
            'domain': {
                'id': 3,
                'hostname': 'demo-app',
                'fqdn': 'demo-app.tunnellio.site',
                'publicUrl': 'https://demo-app.tunnellio.site',
                'keyId': None,
                'localPort': 3000,
                'note': '',
                'createdAt': '2026-07-22T18:25:00+00:00',
                'expiresAt': None,
                'lastUsedAt': None,
                'mode': 'persistent',
                'status': 'active',
                'authMode': 'legacy',
                'connectionMode': 'tcp_bridge',
            },
            'connectionProfile': {
                'connectionMode': 'tcp_bridge',
                'requiresSshKey': False,
                'publicUrl': 'https://demo-app.tunnellio.site',
                'localHost': '127.0.0.1',
                'localPort': 3000,
                'remoteHostname': 'demo-app',
                'tcpBridge': {
                    'enabled': True,
                    'protocol': 'bore',
                    'authRequired': False,
                    'requiresSshKey': False,
                    'host': 'tunnel.example.net',
                    'controlPort': 7835,
                    'publicPort': 51000,
                    'publicBaseDomain': 'tunnel.example.net',
                    'hostname': 'demo-app',
                    'publicUrl': 'https://demo-app.tunnellio.site',
                    'localHost': '127.0.0.1',
                    'localPort': 3000,
                    'preconfiguredSubdomain': True,
                    'generatedSubdomain': False,
                    'token': None,
                    'command': 'tunnellio-bridge connect --host tunnel.example.net --control-port 7835 --hostname demo-app --local-host 127.0.0.1 --local-port 3000',
                    'args': ['tunnellio-bridge', 'connect', '--host', 'tunnel.example.net', '--control-port', '7835', '--hostname', 'demo-app', '--local-host', '127.0.0.1', '--local-port', '3000'],
                },
            },
            'session': {
                'id': 'sess_tcp_456',
                'hostname': 'demo-app',
                'status': 'active',
                'deleteOnDisconnect': False,
                'createdAt': '2026-07-22T18:25:00+00:00',
                'resumeToken': 'resume_tcp_456',
                'connectionMode': 'tcp_bridge',
            },
        }


class KeylessBridgeDummyClient(DummyClient):
    """Client that simulates the public /v1/tcp-bridge/launch endpoint (no token, no key)."""

    def get_public_tcp_bridge_launch(self, payload):
        hostname = payload.get('hostname', 'gen-abc123')
        return {
            'connectionProfile': {
                'connectionMode': 'tcp_bridge',
                'requiresSshKey': False,
                'requiresApiToken': False,
                'publicUrl': f'https://{hostname}.tunnellio.site',
                'localHost': payload.get('localHost', '127.0.0.1'),
                'localPort': payload.get('localPort', 3000),
                'tcpBridge': {
                    'enabled': True,
                    'protocol': 'bore',
                    'authRequired': False,
                    'requiresSshKey': False,
                    'requiresApiToken': False,
                    'host': 'tunnel.example.net',
                    'controlPort': 7835,
                    'publicPort': 51001,
                    'publicBaseDomain': 'tunnel.example.net',
                    'hostname': hostname,
                    'publicUrl': f'https://{hostname}.tunnellio.site',
                    'localHost': payload.get('localHost', '127.0.0.1'),
                    'localPort': payload.get('localPort', 3000),
                    'preconfiguredSubdomain': True,
                    'generatedSubdomain': False,
                    'token': None,
                    'command': f'tunnellio-bridge connect --host tunnel.example.net --control-port 7835 --hostname {hostname} --local-host 127.0.0.1 --local-port 3000',
                    'args': ['tunnellio-bridge', 'connect', '--host', 'tunnel.example.net', '--control-port', '7835', '--hostname', hostname, '--local-host', '127.0.0.1', '--local-port', '3000'],
                },
            },
        }


class DummyConfig:
    profiles_dir = Path('.')



def test_split_selector() -> None:
    assert _split_selector('existing:work', label='key') == ('existing', 'work')



def test_split_selector_rejects_invalid_value() -> None:
    try:
        _split_selector('existing', label='key')
    except ValidationError as exc:
        assert 'selector' in exc.details
    else:
        raise AssertionError('ValidationError was not raised')



def test_build_launch_payload_for_new_domain() -> None:
    planner = Planner(DummyClient(), DummyConfig())
    capabilities = Capabilities.from_api(DummyClient().fetch_capabilities())
    options = PlanOptions(
        key_selector='existing:work',
        domain_selector='new:demo-app',
        local_host='127.0.0.1',
        local_port=4040,
        domain_lifetime_days=30,
        note='test',
        requested_auth_mode='oauth',
        connection_mode='cloud_proxy',
        oauth_client_policy='shared',
    )
    payload = planner.build_launch_payload(options, capabilities)
    assert payload['domainMode'] == 'new'
    assert payload['domain']['hostname'] == 'demo-app'
    assert payload['key']['mode'] == 'existing'
    assert payload['key']['keyId'] == 1
    assert payload['local']['port'] == 4040
    assert payload['requestedAuthMode'] == 'oauth'
    assert payload['connectionMode'] == 'cloud_proxy'



def test_existing_unbound_domain_requires_key() -> None:
    planner = Planner(DummyClient(), DummyConfig())
    capabilities = Capabilities.from_api(DummyClient().fetch_capabilities())
    options = PlanOptions(domain_selector='existing:demo')
    try:
        planner.build_launch_payload(options, capabilities)
    except InteractiveInputRequiredError as exc:
        assert 'missing' in exc.details
    else:
        raise AssertionError('InteractiveInputRequiredError was not raised')



def test_build_plan_returns_session_and_auth_contracts() -> None:
    planner = Planner(DummyClient(), DummyConfig())
    result = planner.build_plan(
        PlanOptions(
            key_selector='existing:work',
            domain_selector='existing:demo',
            local_port=4040,
            requested_auth_mode='oauth',
            connection_mode='cloud_proxy',
            oauth_client_policy='shared',
            runtime_name='prod-api',
            enable_pkce=True,
        )
    )
    payload = result.to_dict()
    assert payload['session']['resumeToken'] == 'resume_123'
    assert payload['auth']['tokenVerification'] == 'introspection'
    assert payload['auth']['protectedResourceMetadataUrl'] == 'https://auth.example.com/.well-known/oauth-protected-resource'
    assert payload['auth']['authorizationServers'] == ['https://auth.example.com']
    assert payload['auth']['scopesSupported'] == ['mcp.read', 'mcp.write']
    assert payload['auth']['tokenEndpointAuthMethodsSupported'] == ['none']
    assert payload['auth']['bearerMethodsSupported'] == ['header']
    assert payload['runtime']['name'] == 'prod-api'
    assert payload['protectedResource']['resource'] == 'https://auth.example.com'
    assert payload['sessionOpenPayload']['enablePkce'] is True


def test_build_plan_rejects_requested_auth_mode_mismatch() -> None:
    planner = Planner(DummyClient(), DummyConfig())
    try:
        planner.build_plan(
            PlanOptions(
                key_selector='existing:work',
                domain_selector='existing:demo',
                requested_auth_mode='legacy',
            )
        )
    except RequestedAuthModeMismatchError as exc:
        assert exc.details['requestedAuthMode'] == 'legacy'
        assert exc.details['actualAuthMode'] == 'oauth'
    else:
        raise AssertionError('RequestedAuthModeMismatchError was not raised')


def test_tcp_bridge_new_domain_omits_key_payload() -> None:
    planner = Planner(DummyClient(), DummyConfig())
    capabilities = Capabilities.from_api(DummyClient().fetch_capabilities())
    options = PlanOptions(
        domain_selector='new:demo-bridge',
        local_host='127.0.0.1',
        local_port=3000,
        connection_mode='tcp_bridge',
    )
    payload = planner.build_launch_payload(options, capabilities)
    assert payload['connectionMode'] == 'tcp_bridge'
    assert payload['domain']['connectionMode'] == 'tcp_bridge'
    assert payload['key'] is None


def test_tcp_bridge_build_plan_returns_keyless_profile() -> None:
    planner = Planner(TcpBridgeDummyClient(), DummyConfig())
    result = planner.build_plan(
        PlanOptions(
            domain_selector='new:demo-app',
            local_port=3000,
            connection_mode='tcp_bridge',
        )
    )
    assert result.key is None
    assert result.connection_profile.is_tcp_bridge is True
    assert result.connection_profile.is_keyless is True
    assert result.connection_profile.effective_transport == 'tcp_bridge'
    assert result.connection_profile.tcp_bridge is not None
    assert result.connection_profile.tcp_bridge.public_port == 51000
    assert result.connection_profile.effective_args[0] == 'tunnellio-bridge'
    payload = result.to_dict()
    assert 'key' not in payload
    assert payload['launch']['transport'] == 'tcp_bridge'
    assert payload['launch']['args'][0] == 'tunnellio-bridge'


def test_tcp_bridge_session_open_payload_omits_key_id_when_keyless() -> None:
    planner = Planner(TcpBridgeDummyClient(), DummyConfig())
    result = planner.build_plan(
        PlanOptions(
            domain_selector='new:demo-app',
            local_port=3000,
            connection_mode='tcp_bridge',
        )
    )
    assert 'keyId' not in result.session_open_payload
    assert result.session_open_payload['connectionMode'] == 'tcp_bridge'


def test_keyless_bridge_plan_calls_public_endpoint() -> None:
    planner = Planner(KeylessBridgeDummyClient(), DummyConfig())
    result = planner.build_keyless_bridge_plan(
        PlanOptions(
            domain_selector='new:my-bridge',
            local_port=3000,
            mode='bridge',
        )
    )
    assert result.meta is None
    assert result.key is None
    assert result.capabilities is None
    assert result.connection_profile.is_tcp_bridge is True
    assert result.connection_profile.is_keyless is True
    assert result.connection_profile.is_tokenless is True
    assert result.connection_profile.effective_args[0] == 'tunnellio-bridge'
    payload = result.to_dict()
    assert 'meta' not in payload
    assert 'key' not in payload
    assert payload['launch']['transport'] == 'tcp_bridge'


def test_keyless_bridge_plan_with_generated_subdomain() -> None:
    planner = Planner(KeylessBridgeDummyClient(), DummyConfig())
    result = planner.build_keyless_bridge_plan(
        PlanOptions(
            local_port=8080,
            mode='bridge',
        )
    )
    assert result.connection_profile.is_tokenless is True
    assert result.connection_profile.public_url is not None
    assert result.connection_profile.tcp_bridge is not None
    assert result.connection_profile.tcp_bridge.public_port == 51001
