"""Обрыв управляющего канала переживается, а не завершает мост."""

import json
import socket
import threading
import time

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from tunnellio.bridge import TcpBridgeProcess


def _recv_frame(sock):
    buf = bytearray()
    while True:
        chunk = sock.recv(1)
        if not chunk:
            return None
        if chunk == b'\x00':
            break
        buf.extend(chunk)
    return json.loads(buf.decode('utf-8'))


def _send_frame(sock, payload):
    sock.sendall(json.dumps(payload).encode('utf-8') + b'\x00')


class _Server:
    """Принимает hello, отвечает, затем рвёт связь. Считает рукопожатия."""

    def __init__(self, drops=1):
        self._listener = socket.socket()
        self._listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._listener.bind(('127.0.0.1', 0))
        self._listener.listen(8)
        self.port = self._listener.getsockname()[1]
        self.handshakes = []
        self._drops = drops
        self._stop = False
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self):
        while not self._stop:
            try:
                conn, _ = self._listener.accept()
            except OSError:
                return
            try:
                frame = _recv_frame(conn)
                if frame is None:
                    conn.close()
                    continue
                self.handshakes.append(frame)
                _send_frame(conn, {'type': 'hello', 'hostname': frame.get('hostname'), 'port': 443})
                if len(self.handshakes) <= self._drops:
                    # Обрыв сразу после успешного рукопожатия: ровно то, что
                    # делает забывчивый роутер или перезапуск сервера.
                    conn.close()
                    continue
                while not self._stop:
                    time.sleep(0.05)
            except OSError:
                pass
            finally:
                try:
                    conn.close()
                except OSError:
                    pass

    def close(self):
        self._stop = True
        try:
            self._listener.close()
        except OSError:
            pass


def test_bridge_reconnects_after_control_channel_drop():
    server = _Server(drops=1)
    process = TcpBridgeProcess(
        host='127.0.0.1',
        control_port=server.port,
        local_host='127.0.0.1',
        local_port=1,
        hello_template={'type': 'hello', 'hostname': 'probe'},
    )
    try:
        process.start()
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and len(server.handshakes) < 2:
            time.sleep(0.1)

        assert len(server.handshakes) >= 2, 'мост не переподключился после обрыва'
        # Имя должно остаться тем же: адрес не меняется между попытками.
        assert {frame.get('hostname') for frame in server.handshakes} == {'probe'}
        # И самое важное: процесс всё это время считался живым, иначе надзор
        # сверху убил бы его и поднял заново с нуля.
        assert process.poll() is None
    finally:
        process.terminate()
        server.close()


def test_terminate_stops_reconnecting():
    server = _Server(drops=99)
    process = TcpBridgeProcess(
        host='127.0.0.1',
        control_port=server.port,
        local_host='127.0.0.1',
        local_port=1,
        hello_template={'type': 'hello', 'hostname': 'probe'},
    )
    try:
        process.start()
        time.sleep(0.5)
        process.terminate()
        assert process.wait(timeout=10) == 0
        seen = len(server.handshakes)
        time.sleep(1.5)
        assert len(server.handshakes) == seen, 'после terminate попытки продолжились'
    finally:
        server.close()
