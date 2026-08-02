from __future__ import annotations

import hashlib
import hmac
import json
import select
import socket
import threading
import time
import uuid
from typing import Any, Callable

CONTROL_PORT_DEFAULT = 7835
NETWORK_TIMEOUT = 3.0
MAX_FRAME_LENGTH = 256
FRAME_DELIMITER = b'\x00'


def _recv_frame(sock: socket.socket, *, timeout: float = NETWORK_TIMEOUT) -> dict[str, Any] | None:
    buf = bytearray()
    deadline = time.monotonic() + timeout if timeout > 0 else None
    while True:
        if deadline is not None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            sock.settimeout(remaining)
        try:
            chunk = sock.recv(1)
        except socket.timeout:
            return None
        if not chunk:
            return None
        if chunk == FRAME_DELIMITER:
            break
        buf.extend(chunk)
        if len(buf) > MAX_FRAME_LENGTH:
            return None
    if not buf:
        return None
    return json.loads(buf.decode('utf-8'))


def _send_frame(sock: socket.socket, message: dict[str, Any] | str) -> None:
    if isinstance(message, str):
        raw = message.encode('utf-8') + FRAME_DELIMITER
    else:
        raw = json.dumps(message, separators=(',', ':')).encode('utf-8') + FRAME_DELIMITER
    sock.sendall(raw)


def _compute_auth_tag(secret: str, challenge: uuid.UUID) -> str:
    hashed_secret = hashlib.sha256(secret.encode('utf-8')).digest()
    mac = hmac.new(hashed_secret, challenge.bytes, hashlib.sha256)
    return mac.hexdigest()


def _auth_handshake(sock: socket.socket, secret: str) -> bool:
    challenge_msg = _recv_frame(sock)
    if challenge_msg is None:
        return False
    challenge_str = challenge_msg.get('Challenge')
    if challenge_str is None:
        return False
    challenge = uuid.UUID(challenge_str)
    tag = _compute_auth_tag(secret, challenge)
    _send_frame(sock, {'Authenticate': tag})
    return True


def _connect(host: str, port: int, timeout: float = NETWORK_TIMEOUT) -> socket.socket:
    sock = socket.create_connection((host, port), timeout=timeout)
    sock.settimeout(None)
    return sock


def _bidirectional_copy(local_sock: socket.socket, remote_sock: socket.socket) -> None:
    sockets = [local_sock, remote_sock]
    try:
        while True:
            readable, _, _ = select.select(sockets, [], [], 1.0)
            if not readable:
                continue
            for sock in readable:
                data = sock.recv(65536)
                if not data:
                    return
                other = remote_sock if sock is local_sock else local_sock
                other.sendall(data)
    except (OSError, ConnectionError):
        pass
    finally:
        for s in sockets:
            try:
                s.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                s.close()
            except OSError:
                pass


class _ConnectionThread(threading.Thread):
    def __init__(self, conn_id: str, host: str, control_port: int, local_host: str, local_port: int, secret: str | None, logger: Callable[[str], None] | None = None, *, hello_template: dict[str, Any] | None = None, password: str | None = None):
        super().__init__(daemon=True)
        self._conn_id = conn_id
        self._host = host
        self._control_port = control_port
        self._local_host = local_host
        self._local_port = local_port
        self._secret = secret
        self._logger = logger
        self._hello_template = hello_template
        self._password = password

    def run(self) -> None:
        if self._logger:
            self._logger(f'Connection {self._conn_id}: handling')
        try:
            remote_sock = _connect(self._host, self._control_port)
            if self._secret:
                if not _auth_handshake(remote_sock, self._secret):
                    if self._logger:
                        self._logger(f'Connection {self._conn_id}: auth failed')
                    remote_sock.close()
                    return
            if self._hello_template is not None:
                accept_frame = dict(self._hello_template)
                accept_frame['type'] = 'accept'
                accept_frame['connectionId'] = self._conn_id
                if self._password:
                    accept_frame['password'] = self._password
                _send_frame(remote_sock, accept_frame)
            else:
                _send_frame(remote_sock, {'Accept': self._conn_id})
            local_sock = _connect(self._local_host, self._local_port)
            _bidirectional_copy(local_sock, remote_sock)
        except (OSError, ConnectionError) as exc:
            if self._logger:
                self._logger(f'Connection {self._conn_id}: error: {exc}')
        except Exception as exc:
            if self._logger:
                self._logger(f'Connection {self._conn_id}: unexpected error: {exc}')


class TcpBridgeProcess:
    _pid_counter = 0

    def __init__(
        self,
        *,
        host: str,
        control_port: int = CONTROL_PORT_DEFAULT,
        local_host: str = '127.0.0.1',
        local_port: int = 3000,
        requested_port: int = 0,
        secret: str | None = None,
        logger: Callable[[str], None] | None = None,
        hello_template: dict[str, Any] | None = None,
        password: str | None = None,
        password_required: bool = False,
        hostname: str | None = None,
    ):
        self._host = host
        self._control_port = control_port
        self._local_host = local_host
        self._local_port = local_port
        self._requested_port = requested_port
        self._secret = secret
        self._logger = logger
        self._hello_template = hello_template
        self._password = password
        self._password_required = password_required
        self._hostname = hostname
        self._control_sock: socket.socket | None = None
        self._remote_port: int | None = None
        self._returncode: int | None = None
        self._lock = threading.Lock()
        self._threads: list[_ConnectionThread] = []
        self._thread: threading.Thread | None = None
        TcpBridgeProcess._pid_counter += 1
        self._pid = -TcpBridgeProcess._pid_counter

    @property
    def pid(self) -> int:
        return self._pid

    @property
    def returncode(self) -> int | None:
        return self._returncode

    @property
    def remote_port(self) -> int | None:
        return self._remote_port

    def start(self) -> None:
        self._control_sock = _connect(self._host, self._control_port)
        if self._secret:
            if not _auth_handshake(self._control_sock, self._secret):
                raise RuntimeError('TCP bridge authentication failed')
        if self._hello_template is not None:
            hello_frame = dict(self._hello_template)
            if self._password:
                hello_frame['password'] = self._password
            _send_frame(self._control_sock, hello_frame)
        else:
            _send_frame(self._control_sock, {'Hello': self._requested_port})
        hello = _recv_frame(self._control_sock)
        if hello is None:
            raise RuntimeError('TCP bridge handshake failed: no response')
        if 'Error' in hello:
            raise RuntimeError(f'TCP bridge handshake failed: {hello["Error"]}')
        if self._hello_template is not None:
            remote_port = hello.get('port') or hello.get('publicPort')
            if remote_port is None and 'Hello' in hello:
                remote_port = hello['Hello']
            if remote_port is None:
                raise RuntimeError(f'TCP bridge handshake failed: {hello}')
            self._remote_port = int(remote_port)
        else:
            if 'Hello' not in hello:
                raise RuntimeError(f'TCP bridge handshake failed: {hello}')
            self._remote_port = int(hello['Hello'])
        if self._logger:
            self._logger(f'Bridge connected: {self._host}:{self._remote_port}')
        self._thread = threading.Thread(target=self._control_loop, daemon=True)
        self._thread.start()

    def _control_loop(self) -> None:
        assert self._control_sock is not None
        try:
            while True:
                msg = _recv_frame(self._control_sock, timeout=0.5)
                if msg is None:
                    break
                if self._hello_template is not None:
                    msg_type = msg.get('type')
                    if msg_type == 'connection':
                        conn_id = str(msg.get('connectionId') or msg.get('id') or '')
                        thread = _ConnectionThread(
                            conn_id=conn_id,
                            host=self._host,
                            control_port=self._control_port,
                            local_host=self._local_host,
                            local_port=self._local_port,
                            secret=self._secret,
                            logger=self._logger,
                            hello_template=self._hello_template,
                            password=self._password,
                        )
                        with self._lock:
                            self._threads.append(thread)
                        thread.start()
                    elif msg_type == 'heartbeat':
                        pass
                    elif msg_type == 'error' or 'Error' in msg:
                        err = msg.get('error') or msg.get('Error')
                        if self._logger:
                            self._logger(f'Bridge server error: {err}')
                        break
                else:
                    if 'Connection' in msg:
                        conn_id = msg['Connection']
                        thread = _ConnectionThread(
                            conn_id=conn_id,
                            host=self._host,
                            control_port=self._control_port,
                            local_host=self._local_host,
                            local_port=self._local_port,
                            secret=self._secret,
                            logger=self._logger,
                        )
                        with self._lock:
                            self._threads.append(thread)
                        thread.start()
                    elif 'Heartbeat' in msg or msg == 'Heartbeat':
                        pass
                    elif 'Error' in msg:
                        if self._logger:
                            self._logger(f'Bridge server error: {msg["Error"]}')
                        break
        except (OSError, ConnectionError):
            pass
        finally:
            with self._lock:
                self._returncode = 0

    def poll(self) -> int | None:
        if self._returncode is not None:
            return self._returncode
        if self._control_sock is not None:
            try:
                readable, _, _ = select.select([self._control_sock], [], [], 0.0)
                if readable:
                    data = self._control_sock.recv(1, socket.MSG_PEEK)
                    if not data:
                        with self._lock:
                            if self._returncode is None:
                                self._returncode = 0
            except (OSError, ConnectionError):
                with self._lock:
                    if self._returncode is None:
                        self._returncode = 0
        if self._thread is not None and not self._thread.is_alive():
            with self._lock:
                if self._returncode is None:
                    self._returncode = 0
        return self._returncode

    def terminate(self) -> None:
        self._close_control()

    def kill(self) -> None:
        self._close_control()

    def wait(self, timeout: float | None = None) -> int:
        if self._thread is not None:
            self._thread.join(timeout=timeout)
        if self._returncode is None:
            self._returncode = 0
        return self._returncode

    def _close_control(self) -> None:
        if self._control_sock is not None:
            try:
                self._control_sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                self._control_sock.close()
            except OSError:
                pass
            self._control_sock = None


def launch_bridge(
    *,
    host: str,
    control_port: int = CONTROL_PORT_DEFAULT,
    local_host: str = '127.0.0.1',
    local_port: int = 3000,
    requested_port: int = 0,
    secret: str | None = None,
    logger: Callable[[str], None] | None = None,
    hello_template: dict[str, Any] | None = None,
    password: str | None = None,
    password_required: bool = False,
    hostname: str | None = None,
) -> TcpBridgeProcess:
    process = TcpBridgeProcess(
        host=host,
        control_port=control_port,
        local_host=local_host,
        local_port=local_port,
        requested_port=requested_port,
        secret=secret,
        logger=logger,
        hello_template=hello_template,
        password=password,
        password_required=password_required,
        hostname=hostname,
    )
    process.start()
    return process


__all__ = ['TcpBridgeProcess', 'launch_bridge', 'CONTROL_PORT_DEFAULT']
