import socket
import threading
import time

import pytest

from adapter import config_from_env, load_pack, parse_program_db, run_loop, split_pack_sample
from families import PACKS
from shdr import ShdrServer

from datetime import datetime, timezone
from importlib import import_module

from tests.test_840d_sl import FakePlc, build_window, _chan

sl = import_module("families.840d_sl")


def test_program_db_unset_is_none_not_99():
    assert parse_program_db(None) is None
    assert parse_program_db("") is None
    assert parse_program_db("  ") is None


def test_program_db_invalid_exits():
    with pytest.raises(SystemExit, match="block number"):
        parse_program_db("DB100")
    with pytest.raises(SystemExit, match="positive"):
        parse_program_db("0")


def test_config_never_defaults_db99_and_pack_reads_db90():
    cfg, pack = config_from_env(
        {
            "SIEMENS_FAMILY": "840d_sl",
            "IP_MACHINE": "192.0.2.10",
            "PLC_SLOT": "2",
        }
    )
    assert pack is PACKS["840d_sl"]
    assert cfg["PROGRAM_DB"] is None
    assert cfg["PROGRAM_DB"] != 99
    plc = FakePlc(window=build_window(program="MAIN.MPF"), chan=_chan())
    sample = pack(plc, cfg)
    assert sample["program"] == "MAIN.MPF"
    assert all(db != 99 for db, _start, _size in plc.reads)
    assert (90, 376, 206) in plc.reads


def test_unknown_family_refuses_before_shdr():
    with pytest.raises(SystemExit, match="Unknown SIEMENS_FAMILY"):
        load_pack("828d")
    with pytest.raises(SystemExit, match="Refusing to serve SHDR"):
        config_from_env({"SIEMENS_FAMILY": "828d", "IP_MACHINE": "192.0.2.10"})


def test_default_family_is_840d_sl():
    cfg, pack = config_from_env({"IP_MACHINE": "192.0.2.10"})
    assert cfg["SIEMENS_FAMILY"] == "840d_sl"
    assert pack is PACKS["840d_sl"]


def test_split_pack_sample_pops_timestamp():
    sample, ts = split_pack_sample(
        {"mode": "AUTOMATIC", "timestamp": "2026-09-03T20:15:04.561Z"}
    )
    assert ts == "2026-09-03T20:15:04.561Z"
    assert "timestamp" not in sample
    assert sample["mode"] == "AUTOMATIC"


def test_tcp_fake_pack_includes_program_uses_plc_timestamp():
    server = ShdrServer(host="127.0.0.1", port=0)
    server.start()
    running = {"on": True}
    plc = FakePlc(
        window=build_window(
            mode="AUTO",
            status="RUNNING",
            program="O99",
            dt=datetime(2026, 9, 3, 20, 15, 4, 561000, tzinfo=timezone.utc),
        ),
        chan=_chan(),
    )
    emitted = []

    class Capture:
        def emit(self, timestamp, sample):
            emitted.append((timestamp, sample))
            server.emit(timestamp, sample)

    def fake_pack(_plc, _cfg):
        sample = sl.read_840d_sl(_plc, _cfg)
        running["on"] = False
        return sample

    try:
        thread = threading.Thread(
            target=run_loop,
            kwargs={
                "pack": fake_pack,
                "cfg": {},
                "shdr": Capture(),
                "connect": lambda: plc,
                "close": lambda _plc: None,
                "running": lambda: running["on"],
                "sleep": lambda _s: None,
                "now": lambda: "DEVICE-NOW",
                "poll_interval": 0,
                "reconnect_s": 0,
            },
            daemon=True,
        )
        thread.start()
        deadline = time.time() + 2
        line = b""
        while time.time() < deadline:
            with server._lock:
                line = (server._last_line or "").encode("utf-8")
            if line:
                break
            time.sleep(0.02)
        thread.join(timeout=2)
        text = line.decode("utf-8")
        assert "avail|AVAILABLE" in text
        assert "mode|AUTOMATIC" in text
        assert "execution|ACTIVE" in text
        assert "program|O99" in text
        assert "timestamp" not in text
        assert emitted
        assert emitted[0][0] == "2026-09-03T20:15:04.561Z"
        with socket.create_connection(("127.0.0.1", server.port), timeout=2) as conn:
            conn.settimeout(2)
            replay = conn.recv(4096).decode("utf-8")
            assert "program|O99" in replay
            assert "mode|AUTOMATIC" in replay
    finally:
        running["on"] = False
        server.stop()


def test_timestamp_only_change_does_not_reemit():
    class Capture:
        def __init__(self):
            self.lines = []

        def emit(self, timestamp, sample):
            self.lines.append((timestamp, dict(sample)))

    samples = [
        {"mode": "AUTOMATIC", "execution": "ACTIVE", "program": "A", "alarm": False, "timestamp": "T1"},
        {"mode": "AUTOMATIC", "execution": "ACTIVE", "program": "A", "alarm": False, "timestamp": "T2"},
        {"mode": "MANUAL", "execution": "READY", "program": "A", "alarm": False, "timestamp": "T3"},
    ]
    idx = {"i": 0}
    running = {"on": True}

    def pack(_plc, _cfg):
        sample = samples[idx["i"]]
        idx["i"] += 1
        if idx["i"] >= len(samples):
            running["on"] = False
        return sample

    shdr = Capture()
    run_loop(
        pack=pack,
        cfg={},
        shdr=shdr,
        connect=lambda: object(),
        close=lambda _plc: None,
        running=lambda: running["on"] and idx["i"] <= len(samples),
        sleep=lambda _s: None,
        now=lambda: "NOW",
        poll_interval=0,
        reconnect_s=0,
    )
    modes = [sample["mode"] for _ts, sample in shdr.lines]
    assert modes.count("AUTOMATIC") == 1
    assert "MANUAL" in modes
