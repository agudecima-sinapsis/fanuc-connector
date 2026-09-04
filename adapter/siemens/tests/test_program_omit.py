import socket
import threading
import time

import pytest

from adapter import config_from_env, load_pack, parse_program_db, run_loop
from families import PACKS
from shdr import ShdrServer

from tests.test_840d_sl import FakePlc, _chan
from importlib import import_module

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


def test_config_omits_program_and_never_defaults_db99():
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
    plc = FakePlc(mode=1 << sl.MODE_AUTO_BIT, chan=_chan(dbb35=1 << sl.PROG_RUNNING_BIT))
    sample = pack(plc, cfg)
    assert "program" not in sample
    assert all(db != 99 for db, _start, _size in plc.reads)


def test_unknown_family_refuses_before_shdr():
    with pytest.raises(SystemExit, match="Unknown SIEMENS_FAMILY"):
        load_pack("828d")
    with pytest.raises(SystemExit, match="Refusing to serve SHDR"):
        config_from_env({"SIEMENS_FAMILY": "828d", "IP_MACHINE": "192.0.2.10"})


def test_default_family_is_840d_sl():
    cfg, pack = config_from_env({"IP_MACHINE": "192.0.2.10"})
    assert cfg["SIEMENS_FAMILY"] == "840d_sl"
    assert pack is PACKS["840d_sl"]


def test_tcp_fake_pack_omits_program_key():
    server = ShdrServer(host="127.0.0.1", port=0)
    server.start()
    running = {"on": True}
    plc = FakePlc(mode=1 << sl.MODE_AUTO_BIT, chan=_chan(dbb35=1 << sl.PROG_RUNNING_BIT))

    def fake_pack(_plc, cfg):
        assert cfg["PROGRAM_DB"] is None
        sample = sl.read_840d_sl(_plc, cfg)
        running["on"] = False
        return sample

    try:
        thread = threading.Thread(
            target=run_loop,
            kwargs={
                "pack": fake_pack,
                "cfg": {"PROGRAM_DB": None},
                "shdr": server,
                "connect": lambda: plc,
                "close": lambda _plc: None,
                "running": lambda: running["on"],
                "sleep": lambda _s: None,
                "now": lambda: "2026-01-01T00:00:00.000Z",
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
        assert "program" not in text
        with socket.create_connection(("127.0.0.1", server.port), timeout=2) as conn:
            conn.settimeout(2)
            replay = conn.recv(4096).decode("utf-8")
            assert "program" not in replay
            assert "mode|AUTOMATIC" in replay
    finally:
        running["on"] = False
        server.stop()
