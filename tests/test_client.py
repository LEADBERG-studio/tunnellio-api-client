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
        if kwargs.get('url'):
            return {'issuer': 'https://auth.example.com', 'introspection_endpoint': 'https://auth.example.com/introspect'}
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
