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
                'supportedConnectionModes': ['cloud_proxy'],
                'defaultConnectionMode': 'cloud_proxy',
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
    assert payload['runtime']['name'] == 'prod-api'
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
