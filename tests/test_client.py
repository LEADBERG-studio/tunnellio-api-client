import ssl

import tunnellio.client as client


class FakeTruststore:
    @staticmethod
    def SSLContext(protocol: int):
        return ssl.SSLContext(protocol)



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
