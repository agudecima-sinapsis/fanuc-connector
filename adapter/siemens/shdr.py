"""Minimal MTConnect SHDR TCP server (port 7878) with PING/PONG."""

import socket
import threading


CONDITION_KEYS = frozenset({"alarm"})
ITEM_ORDER = ("avail", "program", "mode", "execution", "alarm")


def alarm_level(value):
    if isinstance(value, str):
        return value
    return "FAULT" if value else "NORMAL"


def format_shdr(timestamp, sample):
    """One SHDR line. Omit `program` when the key is absent or None.

    Events: timestamp|key|value|...
    Condition (alarm last): |alarm|NORMAL|||| or |alarm|FAULT||||
    """
    parts = [timestamp]
    extras = [key for key in sample if key not in ITEM_ORDER]
    for key in list(ITEM_ORDER) + extras:
        if key not in sample:
            continue
        value = sample[key]
        if value is None:
            continue
        if key in CONDITION_KEYS:
            parts.extend([key, alarm_level(value), "", "", "", ""])
        else:
            parts.extend([key, str(value)])
    return "|".join(parts) + "\n"


class ShdrServer:
    """Accept SHDR clients, replay the last snapshot, answer `* PING`."""

    def __init__(self, host="0.0.0.0", port=7878):
        self.host = host
        self.port = port
        self._sock = None
        self._thread = None
        self._running = False
        self._clients = []
        self._lock = threading.Lock()
        self._last_line = None

    def start(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.host, self.port))
        sock.listen(8)
        sock.settimeout(0.5)
        self._sock = sock
        self.port = sock.getsockname()[1]
        self._running = True
        self._thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        with self._lock:
            clients = list(self._clients)
        for conn in clients:
            try:
                conn.close()
            except OSError:
                pass
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
        if self._thread is not None:
            self._thread.join(timeout=2)

    def emit(self, timestamp, sample):
        line = format_shdr(timestamp, sample)
        self.broadcast(line)

    def broadcast(self, line):
        payload = line.encode("utf-8")
        with self._lock:
            self._last_line = line
            clients = list(self._clients)
        stale = []
        for conn in clients:
            try:
                conn.sendall(payload)
            except OSError:
                stale.append(conn)
        if stale:
            with self._lock:
                self._clients = [c for c in self._clients if c not in stale]
            for conn in stale:
                try:
                    conn.close()
                except OSError:
                    pass

    def _accept_loop(self):
        while self._running:
            try:
                conn, _addr = self._sock.accept()
            except socket.timeout:
                continue
            except OSError:
                if self._running:
                    continue
                return
            conn.settimeout(0.5)
            with self._lock:
                self._clients.append(conn)
                last = self._last_line
            if last:
                try:
                    conn.sendall(last.encode("utf-8"))
                except OSError:
                    with self._lock:
                        if conn in self._clients:
                            self._clients.remove(conn)
                    try:
                        conn.close()
                    except OSError:
                        pass
                    continue
            threading.Thread(target=self._client_loop, args=(conn,), daemon=True).start()

    def _client_loop(self, conn):
        buf = b""
        try:
            while self._running:
                try:
                    chunk = conn.recv(1024)
                except socket.timeout:
                    continue
                except OSError:
                    break
                if not chunk:
                    break
                buf += chunk
                while b"\n" in buf:
                    raw, buf = buf.split(b"\n", 1)
                    line = raw.decode("utf-8", errors="replace").strip()
                    if line.startswith("* PING"):
                        try:
                            conn.sendall(b"* PONG\n")
                        except OSError:
                            return
        finally:
            with self._lock:
                if conn in self._clients:
                    self._clients.remove(conn)
            try:
                conn.close()
            except OSError:
                pass
