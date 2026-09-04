"""Siemens S7 → SHDR adapter. Family packs vary S7 paths; item names stay stable."""

import os
import signal
import sys
import time
from datetime import datetime, timezone

from dotenv import load_dotenv

from families import PACKS
from shdr import ShdrServer

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PLC_RACK = 0

_running = True


def handle_shutdown(_signum, _frame):
    global _running
    _running = False


def utc_timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def load_pack(family):
    pack = PACKS.get(family)
    if pack is None:
        known = ", ".join(sorted(PACKS)) or "(none)"
        raise SystemExit(
            f"Unknown SIEMENS_FAMILY={family!r}. Shipped packs: {known}. "
            "Refusing to serve SHDR."
        )
    return pack


def parse_program_db(raw):
    """Unset/empty → None (omit SHDR program). Invalid → SystemExit. Never defaults to 99."""
    if raw is None or str(raw).strip() == "":
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise SystemExit(
            f"PROGRAM_DB must be a block number, got {raw!r} (e.g. 100, not 'DB100')."
        )
    if value <= 0:
        raise SystemExit(f"PROGRAM_DB must be a positive block number, got {value}.")
    return value


def config_from_env(env=None):
    env = os.environ if env is None else env
    family = env.get("SIEMENS_FAMILY") or "840d_sl"
    pack = load_pack(family)
    ip_machine = (env.get("IP_MACHINE") or "").strip()
    if not ip_machine:
        raise SystemExit("IP_MACHINE is not set.")
    cfg = {
        "SIEMENS_FAMILY": family,
        "IP_MACHINE": ip_machine,
        "PLC_RACK": PLC_RACK,
        "PLC_SLOT": int(env.get("PLC_SLOT") or "2"),
        "PROGRAM_DB": parse_program_db(env.get("PROGRAM_DB")),
        "PROGRAM_OFFSET": int(env.get("PROGRAM_OFFSET") or "0"),
        "PROGRAM_CAPACITY": int(env.get("PROGRAM_CAPACITY") or "64"),
        "POLL_INTERVAL_S": float(env.get("POLL_INTERVAL_S") or "0.5"),
        "SHDR_HOST": env.get("SHDR_HOST") or "0.0.0.0",
        "SHDR_PORT": int(env.get("SHDR_PORT") or "7878"),
        "RECONNECT_S": float(env.get("RECONNECT_S") or "5"),
    }
    return cfg, pack


def connect_plc(ip, rack, slot):
    import snap7

    plc = snap7.client.Client()
    print(f"Connecting to PLC at {ip}:102 (rack={rack}, slot={slot})...", flush=True)
    plc.connect(ip, rack, slot)
    print("Connected to PLC", flush=True)
    return plc


def close_plc(plc):
    if plc is None:
        return
    try:
        plc.disconnect()
    except Exception:
        pass
    try:
        plc.destroy()
    except Exception:
        pass


def run_loop(
    *,
    pack,
    cfg,
    shdr,
    connect,
    close,
    running,
    sleep,
    now,
    poll_interval,
    reconnect_s=5,
):
    """Poll the pack and emit change-gated SHDR. On PLC loss emit avail|UNAVAILABLE."""
    plc = None
    last = None
    while running():
        if plc is None:
            try:
                plc = connect()
            except Exception as exc:
                print(f"PLC connect failed: {exc}", flush=True)
                sleep(reconnect_s)
                continue
            try:
                fresh = pack(plc, cfg)
            except Exception as exc:
                print(f"PLC read failed on connect, reconnecting: {exc}", flush=True)
                shdr.emit(now(), {"avail": "UNAVAILABLE"})
                close(plc)
                plc = None
                sleep(reconnect_s)
                continue
            shdr.emit(now(), {"avail": "AVAILABLE", **fresh})
            last = dict(fresh)
            sleep(poll_interval)
            continue

        try:
            fresh = pack(plc, cfg)
        except Exception as exc:
            print(f"PLC read failed, reconnecting: {exc}", flush=True)
            shdr.emit(now(), {"avail": "UNAVAILABLE"})
            close(plc)
            plc = None
            last = None
            sleep(reconnect_s)
            continue

        if fresh != last:
            shdr.emit(now(), {"avail": "AVAILABLE", **fresh})
            last = dict(fresh)
        sleep(poll_interval)


def run(env=None, shdr=None):
    cfg, pack = config_from_env(env)
    server = shdr or ShdrServer(host=cfg["SHDR_HOST"], port=cfg["SHDR_PORT"])
    server.start()
    print(f"SHDR listening on {cfg['SHDR_HOST']}:{server.port}", flush=True)
    try:
        run_loop(
            pack=pack,
            cfg=cfg,
            shdr=server,
            connect=lambda: connect_plc(cfg["IP_MACHINE"], cfg["PLC_RACK"], cfg["PLC_SLOT"]),
            close=close_plc,
            running=lambda: _running,
            sleep=time.sleep,
            now=utc_timestamp,
            poll_interval=cfg["POLL_INTERVAL_S"],
            reconnect_s=cfg["RECONNECT_S"],
        )
    finally:
        server.stop()


def main():
    load_dotenv(os.getenv("FF_ENV_FILE", os.path.join(SCRIPT_DIR, "adapter.env")))
    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)
    run()


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:
        print(f"Critical error: {exc}", flush=True)
        sys.exit(1)
