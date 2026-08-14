"""Обрыв в дороге: соединение выглядит живым, но не ведёт никуда.

Это не то же самое, что закрытое соединение. При обрыве до клиента не доходит
ни FIN, ни RST: сокет открыт, запись в него не ошибка (байты уходят в буфер
ядра), и по молчанию канала спокойный вечер неотличим от оборванного провода.

Раньше клиент верил молчанию: туннель считался живым и не вёл никуда, а
узнавалось это первым потерянным запросом, то есть от пользователя. Сервер
отвечает на каждый стук, поэтому тишина дольше срока - это приговор.
"""

import json
import socket
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from tunnellio import bridge as bridge_module
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


class _MuteServer:
    """Здоровается и замолкает навсегда, не закрывая соединение.

    Ровно так выглядит мост за оборванным проводом: сокет открыт, ответов нет.
    """

    def __init__(self, *, answer_heartbeats=False):
        self._listener = socket.socket()
        self._listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._listener.bind(('127.0.0.1', 0))
        self._listener.listen(8)
        self.port = self._listener.getsockname()[1]
        self.handshakes = []
        self.heartbeats = 0
        self._answer = answer_heartbeats
        self._stop = False
        self._sockets = []
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self):
        while not self._stop:
            try:
                conn, _ = self._listener.accept()
            except OSError:
                return
            self._sockets.append(conn)
            threading.Thread(target=self._session, args=(conn,), daemon=True).start()

    def _session(self, conn):
        try:
            frame = _recv_frame(conn)
            if frame is None:
                return
            self.handshakes.append(frame)
            _send_frame(conn, {'type': 'hello', 'hostname': frame.get('hostname'), 'port': 443})
            while not self._stop:
                message = _recv_frame(conn)
                if message is None:
                    return
                if str(message.get('type') or '') == 'heartbeat':
                    self.heartbeats += 1
                    if self._answer:
                        _send_frame(conn, {'type': 'heartbeat'})
        except OSError:
            pass

    def close(self):
        self._stop = True
        for sock in self._sockets:
            try:
                sock.close()
            except OSError:
                pass
        try:
            self._listener.close()
        except OSError:
            pass


def test_a_silent_line_is_treated_as_dead_and_the_bridge_reconnects(monkeypatch):
    # Сроки на время теста короткие: суть проверки в поведении, а не в ожидании.
    monkeypatch.setattr(bridge_module, 'SILENCE_LIMIT', 1.5)
    monkeypatch.setattr(bridge_module, 'HEARTBEAT_INTERVAL', 0.2)

    server = _MuteServer(answer_heartbeats=False)
    process = TcpBridgeProcess(
        host='127.0.0.1',
        control_port=server.port,
        local_host='127.0.0.1',
        local_port=1,
        hello_template={'type': 'hello', 'hostname': 'probe'},
    )
    try:
        process.start()
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and len(server.handshakes) < 2:
            time.sleep(0.1)

        # Сокет всё это время был открыт, и раньше клиент считал такой туннель
        # рабочим до первого потерянного запроса.
        assert len(server.handshakes) >= 2, 'клиент поверил молчанию и не переподключился'
        assert server.heartbeats >= 1, 'клиент не стучал, значит и ответа не ждал'
        # И процесс живой: надзор сверху не должен поднимать мост с нуля, пока
        # он справляется сам.
        assert process.poll() is None
    finally:
        process.terminate()
        server.close()


def test_an_answering_server_keeps_the_session(monkeypatch):
    """Отвечающий мост переподключений не вызывает: срок считается от ответа."""
    monkeypatch.setattr(bridge_module, 'SILENCE_LIMIT', 1.5)
    monkeypatch.setattr(bridge_module, 'HEARTBEAT_INTERVAL', 0.2)

    server = _MuteServer(answer_heartbeats=True)
    process = TcpBridgeProcess(
        host='127.0.0.1',
        control_port=server.port,
        local_host='127.0.0.1',
        local_port=1,
        hello_template={'type': 'hello', 'hostname': 'probe'},
    )
    try:
        process.start()
        time.sleep(4)
        assert len(server.handshakes) == 1, 'мост переподключился на живом канале'
        assert server.heartbeats >= 3
        assert process.poll() is None
    finally:
        process.terminate()
        server.close()


def test_a_refused_local_port_does_not_leave_the_visitor_hanging():
    """Своя программа не ответила - соединение с мостом закрывается сразу.

    Иначе оно висит у сервера в ожидании, и посетитель ждёт своего таймаута
    вместо честного отказа.
    """
    closed = threading.Event()

    listener = socket.socket()
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(('127.0.0.1', 0))
    listener.listen(4)
    port = listener.getsockname()[1]

    def serve():
        conn, _ = listener.accept()
        try:
            _recv_frame(conn)  # кадр accept
            # Ждём, пока клиент закроет соединение: recv вернёт пустоту.
            if not conn.recv(1):
                closed.set()
        except OSError:
            closed.set()
        finally:
            conn.close()

    threading.Thread(target=serve, daemon=True).start()

    thread = bridge_module._ConnectionThread(
        conn_id='c-1',
        host='127.0.0.1',
        control_port=port,
        local_host='127.0.0.1',
        # Порт 9 закрыт почти всегда: своя программа "не поднялась".
        local_port=9,
        secret=None,
        hello_template={'type': 'hello', 'hostname': 'probe'},
    )
    thread.start()
    thread.join(timeout=10)

    try:
        assert closed.wait(timeout=5), 'клиент оставил соединение с мостом висеть'
    finally:
        listener.close()
