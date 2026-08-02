import json
import socket
import threading
import time
import uuid

from tunnellio.bridge import (
    CONTROL_PORT_DEFAULT,
    TcpBridgeProcess,
    _bidirectional_copy,
    _compute_auth_tag,
    _recv_frame,
    _send_frame,
    launch_bridge,
)


class _FakeControlServer:
    """Minimal bore-protocol control server for testing."""

    def __init__(self, *, remote_port: int = 51000, secret: str | None = None):
        self._remote_port = remote_port
        self._secret = secret
        self._listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._listener.bind(('127.0.0.1', 0))
        self._listener.listen(5)
        self.host, self.port = self._listener.getsockname()
        self._stop = False
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self.hello_received = None
        self.accept_ids: list[str] = []

    def start(self):
        self._thread.start()
        return self

    def stop(self):
        self._stop = True
        try:
            self._listener.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self._listener.close()
        except OSError:
            pass

    def _serve(self):
        while not self._stop:
            try:
                conn, _ = self._listener.accept()
            except OSError:
                break
            threading.Thread(target=self._handle, args=(conn,), daemon=True).start()

    def _handle(self, conn: socket.socket):
        try:
            if self._secret:
                challenge = uuid.uuid4()
                _send_frame(conn, {'Challenge': str(challenge)})
                auth_msg = _recv_frame(conn)
                if auth_msg is None or 'Authenticate' not in auth_msg:
                    return
                expected = _compute_auth_tag(self._secret, challenge)
                if auth_msg['Authenticate'] != expected:
                    return
            hello_msg = _recv_frame(conn)
            if hello_msg is None or 'Hello' not in hello_msg:
                return
            self.hello_received = hello_msg['Hello']
            _send_frame(conn, {'Hello': self._remote_port})
            while not self._stop:
                msg = _recv_frame(conn, timeout=0.5)
                if msg is None:
                    break
                if 'Accept' in msg:
                    self.accept_ids.append(msg['Accept'])
        except (OSError, Exception):
            pass
        finally:
            try:
                conn.close()
            except OSError:
                pass


def test_send_and_recv_frame_roundtrip() -> None:
    a, b = socket.socketpair()
    try:
        _send_frame(a, {'Hello': 42})
        result = _recv_frame(b, timeout=1.0)
        assert result == {'Hello': 42}
    finally:
        a.close()
        b.close()


def test_auth_tag_computes_hmac_sha256() -> None:
    challenge = uuid.UUID('12345678-1234-1234-1234-123456789abc')
    tag = _compute_auth_tag('my_secret', challenge)
    assert isinstance(tag, str)
    assert len(tag) == 64
    tag2 = _compute_auth_tag('my_secret', challenge)
    assert tag == tag2
    tag3 = _compute_auth_tag('wrong', challenge)
    assert tag != tag3


def test_bidirectional_copy_transfers_data() -> None:
    local_a, local_b = socket.socketpair()
    remote_a, remote_b = socket.socketpair()
    local_a.sendall(b'hello from local')
    remote_a.sendall(b'hello from remote')
    t = threading.Thread(target=_bidirectional_copy, args=(local_b, remote_b), daemon=True)
    t.start()
    time.sleep(0.2)
    assert remote_a.recv(256) == b'hello from local'
    assert local_a.recv(256) == b'hello from remote'
    local_a.close()
    remote_a.close()
    t.join(timeout=2.0)


def test_launch_bridge_handshake_without_secret() -> None:
    server = _FakeControlServer(remote_port=51005).start()
    try:
        time.sleep(0.1)
        process = launch_bridge(
            host=server.host,
            control_port=server.port,
            local_host='127.0.0.1',
            local_port=9999,
            requested_port=51005,
        )
        time.sleep(0.3)
        assert process.remote_port == 51005
        assert server.hello_received == 51005
        process.terminate()
        process.wait(timeout=2.0)
    finally:
        server.stop()


def test_launch_bridge_handshake_with_secret() -> None:
    server = _FakeControlServer(remote_port=51006, secret='test_secret').start()
    try:
        time.sleep(0.1)
        process = launch_bridge(
            host=server.host,
            control_port=server.port,
            local_host='127.0.0.1',
            local_port=9999,
            requested_port=51006,
            secret='test_secret',
        )
        time.sleep(0.3)
        assert process.remote_port == 51006
        process.terminate()
        process.wait(timeout=2.0)
    finally:
        server.stop()
