from tunnellio.oauth import OAuthAuthorizeRequest, build_authorize_url, build_code_challenge, generate_pkce_pair



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
