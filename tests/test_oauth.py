from pathlib import Path

from tunnellio.errors import ValidationError
from tunnellio.oauth import (
    OAuthAuthorizeRequest,
    OAuthTokenRecord,
    build_authorize_url,
    build_code_challenge,
    build_token_storage_name,
    generate_pkce_pair,
    load_token_record,
    save_token_record,
)



def test_generate_pkce_pair() -> None:
    pair = generate_pkce_pair()
    assert len(pair.verifier) >= 43
    assert pair.challenge == build_code_challenge(pair.verifier)
    assert pair.method == 'S256'



def test_build_authorize_url() -> None:
    request = OAuthAuthorizeRequest(
        authorize_url='https://auth.example.com/authorize',
        client_id='client-1',
        redirect_uri='http://127.0.0.1/callback',
        scope='openid profile',
        state='xyz',
        code_challenge='challenge',
    )
    url = build_authorize_url(request)
    assert 'client_id=client-1' in url
    assert 'redirect_uri=http%3A%2F%2F127.0.0.1%2Fcallback' in url
    assert 'code_challenge=challenge' in url



def test_token_record_from_response_and_roundtrip(tmp_path: Path) -> None:
    record = OAuthTokenRecord.from_token_response(
        name='demo-token',
        client_id='client-1',
        client_secret=None,
        token_payload={
            'accessToken': 'access-123',
            'refreshToken': 'refresh-123',
            'tokenType': 'Bearer',
            'scope': 'proxy.connect proxy.inspect',
            'expiresIn': 3600,
            'authMode': 'dual',
            'connectionMode': 'dual',
        },
        token_url='https://auth.example.com/token',
        introspect_url='https://auth.example.com/introspect',
    )
    assert record.access_token == 'access-123'
    assert record.refresh_token == 'refresh-123'
    assert record.authorization_header() == 'Bearer access-123'
    assert record.is_expired(leeway_seconds=0) is False

    path = tmp_path / 'token.json'
    save_token_record(path, record)
    loaded = load_token_record(path)
    assert loaded.client_id == 'client-1'
    assert loaded.access_token == 'access-123'
    assert loaded.refresh_token == 'refresh-123'



def test_token_record_requires_access_token() -> None:
    try:
        OAuthTokenRecord.from_token_response(name='bad', client_id='client-1', token_payload={})
    except ValidationError as exc:
        assert exc.code == 'validation_error'
    else:
        raise AssertionError('ValidationError was not raised')





def test_refresh_roundtrip_preserves_refresh_token_when_server_omits_it() -> None:
    record = OAuthTokenRecord.from_token_response(
        name='demo-token',
        client_id='client-1',
        token_payload={
            'accessToken': 'access-456',
            'tokenType': 'Bearer',
            'scope': 'proxy.connect proxy.inspect',
            'expiresIn': 3600,
        },
        fallback_refresh_token='refresh-keep',
    )
    assert record.refresh_token == 'refresh-keep'


def test_build_token_storage_name() -> None:
    assert build_token_storage_name(client_id='ocl_12345678', domain_slug='demo') == 'demo-12345678'
