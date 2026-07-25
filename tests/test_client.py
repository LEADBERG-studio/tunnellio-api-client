import ssl
from pathlib import Path

import tunnellio.client as client
from tunnellio.config import load_runtime_config


class FakeTruststore:
    @staticmethod
    def SSLContext(protocol: int):
        return ssl.SSLContext(protocol)


class FakeApiClient(client.ApiClient):
    def __init__(self):
        config = load_runtime_config(token='tok', base_url='https://api.tunnellio.ru', state_dir='test-artifacts/test-client', insecure_tls=True, require_token=False)
        super().__init__(config)
        self.calls = []

    def _request_json(self, **kwargs):  # type: ignore[override]
        self.calls.append(kwargs)
        url = kwargs.get('url')
        if isinstance(url, str) and url.endswith('/.well-known/oauth-protected-resource'):
            return {
                'resource': 'https://mcp.example.com',
                'authorization_servers': ['https://auth.example.com'],
                'scopes_supported': ['mcp.read', 'mcp.write'],
                'bearer_methods_supported': ['header'],
            }
        if kwargs.get('url') and kwargs.get('method') == 'POST' and kwargs.get('payload'):
            return {
                'ok': True,
                'data': {
                    'authorizationCode': 'code_123',
                    'redirectUri': kwargs['payload'].get('redirectUri'),
                },
            }
        if kwargs.get('url') and kwargs.get('method') == 'POST' and kwargs.get('form'):
            if 'token' in kwargs['form']:
                return {'ok': True, 'data': {'active': True}}
            return {
                'ok': True,
                'data': {
                    'accessToken': 'access_123',
                    'refreshToken': 'refresh_123',
                    'tokenType': 'Bearer',
                    'expiresIn': 3600,
                },
            }
        if kwargs.get('url'):
            return {
                'issuer': 'https://auth.example.com',
                'introspection_endpoint': 'https://auth.example.com/introspect',
                'service_documentation': 'https://auth.example.com/docs',
                'token_endpoint_auth_methods_supported': ['none'],
                'token_verification_methods_supported': ['introspection'],
            }
        if kwargs.get('path') == '/v1/sessions/open':
            return {'session': {'id': 'sess_123', 'status': 'active'}}
        return {'session': {'id': 'sess_123', 'status': 'active'}}



def test_build_ssl_context_insecure() -> None:
    ctx, backend = client.build_ssl_context(insecure_tls=True, platform='win32')
    assert isinstance(ctx, ssl.SSLContext)
    assert backend == 'insecure'



def test_build_ssl_context_windows_uses_truststore_when_available() -> None:
    original_loader = client._load_truststore_module
    try:
        client._load_truststore_module = lambda: FakeTruststore
        ctx, backend = client.build_ssl_context(insecure_tls=False, platform='win32')
    finally:
        client._load_truststore_module = original_loader
    assert isinstance(ctx, ssl.SSLContext)
    assert backend == 'windows-truststore'



def test_build_ssl_context_windows_falls_back_when_missing() -> None:
    original_loader = client._load_truststore_module
    try:
        client._load_truststore_module = lambda: None
        ctx, backend = client.build_ssl_context(insecure_tls=False, platform='win32')
    finally:
        client._load_truststore_module = original_loader
    assert isinstance(ctx, ssl.SSLContext)
    assert backend == 'openssl-default-missing-truststore'



def test_fetch_oauth_authorization_server_uses_discovery_url() -> None:
    api = FakeApiClient()
    payload = api.fetch_oauth_authorization_server(auth_domain='auth.example.com')
    assert payload['issuer'] == 'https://auth.example.com'
    assert api.calls[0]['method'] == 'GET'
    assert api.calls[0]['include_auth'] is False
    assert api.calls[0]['url'] == 'https://auth.example.com/.well-known/oauth-authorization-server'




def test_fetch_oauth_protected_resource_uses_resource_url() -> None:
    api = FakeApiClient()
    payload = api.fetch_oauth_protected_resource(resource_url='https://mcp.example.com')
    assert payload['resource'] == 'https://mcp.example.com'
    assert api.calls[0]['method'] == 'GET'
    assert api.calls[0]['include_auth'] is False
    assert api.calls[0]['url'] == 'https://mcp.example.com/.well-known/oauth-protected-resource'


def test_authorize_oauth_code_uses_post_json() -> None:
    api = FakeApiClient()
    payload = api.authorize_oauth_code(
        authorize_url='https://auth.example.com/oauth/authorize',
        payload={'domainId': 1, 'redirectUri': 'http://localhost:3333/callback', 'clientId': 'client-1'},
    )
    assert payload['authorizationCode'] == 'code_123'
    assert api.calls[0]['method'] == 'POST'
    assert api.calls[0]['include_auth'] is False



def test_exchange_oauth_token_unwraps_enveloped_response() -> None:
    api = FakeApiClient()
    payload = api.exchange_oauth_token(
        token_url='https://auth.example.com/oauth/token',
        form_payload={'grant_type': 'authorization_code', 'clientId': 'client-1', 'code': 'code_123'},
    )
    assert payload['accessToken'] == 'access_123'
    assert api.calls[0]['form']['grant_type'] == 'authorization_code'



def test_introspect_oauth_token_unwraps_enveloped_response() -> None:
    api = FakeApiClient()
    payload = api.introspect_oauth_token(
        introspect_url='https://auth.example.com/oauth/introspect',
        token='access_123',
        client_id='client-1',
    )
    assert payload['active'] is True
    assert api.calls[0]['form']['token'] == 'access_123'



def test_open_session_unwraps_session_payload() -> None:
    api = FakeApiClient()
    payload = api.open_session({'runtimeName': 'prod-api'})
    assert payload['id'] == 'sess_123'
    assert api.calls[0]['path'] == '/v1/sessions/open'


def test_heartbeat_session_includes_resume_token() -> None:
    api = FakeApiClient()
    api.heartbeat_session(session_id='sess_123', resume_token='rsm_123', payload={'runtimeName': 'prod-api'})
    assert api.calls[0]['path'] == '/v1/sessions/heartbeat'
    assert api.calls[0]['payload']['resumeToken'] == 'rsm_123'


def test_close_session_includes_resume_token() -> None:
    api = FakeApiClient()
    api.close_session(session_id='sess_123', resume_token='rsm_123', reason='done')
    assert api.calls[0]['path'] == '/v1/sessions/close'
    assert api.calls[0]['payload']['resumeToken'] == 'rsm_123'
