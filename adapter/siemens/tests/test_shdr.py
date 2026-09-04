import socket
import threading
import time

from shdr import ShdrServer, format_shdr


TS = "2026-01-01T00:00:00.000Z"


def test_format_auto_running_without_program():
    line = format_shdr(
        TS,
        {
            "avail": "AVAILABLE",
            "mode": "AUTOMATIC",
            "execution": "ACTIVE",
            "alarm": False,
        },
    )
    assert line.startswith(TS)
    assert "avail|AVAILABLE" in line
    assert "mode|AUTOMATIC" in line
    assert "execution|ACTIVE" in line
    assert "alarm|NORMAL||||" in line
    assert "program" not in line
    assert line.endswith("\n")


def test_format_includes_program_when_present():
    line = format_shdr(
        TS,
        {
            "avail": "AVAILABLE",
            "program": "O1234",
            "mode": "AUTOMATIC",
            "execution": "ACTIVE",
            "alarm": True,
        },
    )
    assert "program|O1234" in line
    assert "alarm|FAULT||||" in line


def test_format_omits_program_key_when_none():
    line = format_shdr(TS, {"mode": "AUTOMATIC", "program": None})
    assert "program" not in line


def test_tcp_ping_pong_and_snapshot():
    server = ShdrServer(host="127.0.0.1", port=0)
    server.start()
    try:
        server.emit(
            TS,
            {
                "avail": "AVAILABLE",
                "mode": "AUTOMATIC",
                "execution": "ACTIVE",
                "alarm": False,
            },
        )
        with socket.create_connection(("127.0.0.1", server.port), timeout=2) as conn:
            conn.settimeout(2)
            first = conn.recv(4096).decode("utf-8")
            assert "mode|AUTOMATIC" in first
            assert "program" not in first
            conn.sendall(b"* PING\n")
            pong = conn.recv(4096).decode("utf-8")
            assert pong.strip() == "* PONG"
    finally:
        server.stop()


def test_broadcast_reaches_connected_client():
    server = ShdrServer(host="127.0.0.1", port=0)
    server.start()
    received = []

    def _listen():
        with socket.create_connection(("127.0.0.1", server.port), timeout=2) as conn:
            conn.settimeout(2)
            received.append(conn.recv(4096))

    try:
        thread = threading.Thread(target=_listen, daemon=True)
        thread.start()
        deadline = time.time() + 2
        while time.time() < deadline:
            with server._lock:
                ready = bool(server._clients)
            if ready:
                break
            time.sleep(0.02)
        server.emit(TS, {"avail": "AVAILABLE", "mode": "MANUAL", "execution": "READY", "alarm": False})
        thread.join(timeout=2)
        assert received
        text = received[0].decode("utf-8")
        assert "mode|MANUAL" in text
        assert "execution|READY" in text
    finally:
        server.stop()
