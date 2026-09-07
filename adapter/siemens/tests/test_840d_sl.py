from datetime import datetime, timezone
from importlib import import_module

sl = import_module("families.840d_sl")


def _chan(*, dbb32=0, dbb33=0, dbb34=0, dbb35=0, dbb36=0, dbb37=0):
    return bytes([dbb32, dbb33, dbb34, dbb35, dbb36, dbb37])


def _bcd(n):
    return ((n // 10) << 4) | (n % 10)


def encode_s7_string(text, capacity):
    raw = text.encode("latin-1")[:capacity]
    return bytes([capacity, len(raw)]) + raw + bytes(capacity - len(raw))


def encode_s7_dt(dt):
    year = dt.year % 100
    msec = dt.microsecond // 1000
    return bytes(
        [
            _bcd(year),
            _bcd(dt.month),
            _bcd(dt.day),
            _bcd(dt.hour),
            _bcd(dt.minute),
            _bcd(dt.second),
            _bcd(msec // 10),
            ((msec % 10) << 4),
        ]
    )


def build_window(*, mode="AUTO", status="RUNNING", program="O1234", dt=None, pad=0):
    buf = bytearray(sl.WINDOW_LEN)
    buf[sl.MODE_REL : sl.MODE_REL + sl.MODE_CAP + 2] = encode_s7_string(mode, sl.MODE_CAP)
    buf[sl.STATUS_REL : sl.STATUS_REL + sl.STATUS_CAP + 2] = encode_s7_string(
        status, sl.STATUS_CAP
    )
    buf[sl.PROGRAM_REL : sl.PROGRAM_REL + sl.PROGRAM_CAP + 2] = encode_s7_string(
        program, sl.PROGRAM_CAP
    )
    if dt is not None:
        encoded = encode_s7_dt(dt)
        buf[sl.DT_REL : sl.DT_REL + sl.DT_LEN] = encoded
    if pad:
        buf[17] = pad
        buf[35] = pad
    return bytes(buf)


class FakePlc:
    def __init__(self, *, window=None, chan=None):
        self._window = window if window is not None else build_window()
        self._chan = bytes(chan if chan is not None else _chan())
        self.reads = []

    def db_read(self, db, start, size):
        self.reads.append((db, start, size))
        if db == sl.BUILDER_DB and start == sl.WINDOW_START:
            assert size == sl.WINDOW_LEN
            return self._window
        if db == sl.CHAN_DB and start == sl.CHAN_START:
            return self._chan
        raise AssertionError(f"unexpected db_read db={db} start={start} size={size}")


def test_window_offsets_match_technician_map():
    assert sl.WINDOW_START + sl.STATUS_REL == 394
    assert sl.WINDOW_START + sl.PROGRAM_REL == 412
    assert sl.WINDOW_START + sl.DT_REL == 574
    assert sl.PROGRAM_CAP + 2 == 162
    assert sl.WINDOW_START + sl.PROGRAM_REL + sl.PROGRAM_CAP + 2 == 574
    assert sl.WINDOW_LEN == 206


def test_auto_running_reads_db90_and_program():
    dt = datetime(2026, 9, 3, 20, 15, 4, 561000, tzinfo=timezone.utc)
    plc = FakePlc(
        window=build_window(mode="AUTO", status="RUNNING", program="MAIN.MPF", dt=dt),
        chan=_chan(),
    )
    sample = sl.read_840d_sl(plc, {})
    assert sample["mode"] == "AUTOMATIC"
    assert sample["execution"] == "ACTIVE"
    assert sample["program"] == "MAIN.MPF"
    assert sample["alarm"] is False
    assert sample["timestamp"] == "2026-09-03T20:15:04.561Z"
    assert (sl.BUILDER_DB, sl.WINDOW_START, sl.WINDOW_LEN) in plc.reads
    assert all(db != 99 for db, _start, _size in plc.reads)


def test_mdi_jog_and_empty_mode():
    assert sl.map_mode("MDI") == "MANUAL_DATA_INPUT"
    assert sl.map_mode("JOG") == "MANUAL"
    assert sl.map_mode("  auto  ") == "AUTOMATIC"
    assert sl.map_mode("") == "UNAVAILABLE"
    assert sl.map_mode("WEIRD") == "UNAVAILABLE"


def test_execution_synonyms():
    assert sl.map_execution("RUNNING") == "ACTIVE"
    assert sl.map_execution("RESET") == "READY"
    assert sl.map_execution("M30") == "PROGRAM_COMPLETED"
    assert sl.map_execution("M00") == "PROGRAM_OPTIONAL_STOP"
    assert sl.map_execution("STOPPED") == "PROGRAM_STOPPED"
    assert sl.map_execution("") == "STOPPED"
    assert sl.map_execution("Ciclo raro") == "Ciclo raro"


def test_char_array_fallback_when_not_s7_string():
    raw = b"AUTO           "
    assert sl.decode_s7_string(raw, 15) == "AUTO"


def test_s7_string_uses_length_byte():
    payload = bytes([15, 4]) + b"AUTO" + bytes(11)
    assert sl.decode_s7_string(payload, 15) == "AUTO"


def test_invalid_dt_omits_timestamp():
    plc = FakePlc(window=build_window(dt=None), chan=_chan())
    sample = sl.read_840d_sl(plc, {})
    assert "timestamp" not in sample


def test_alarm_bits_6_and_7_only():
    none = _chan()
    stop = _chan(dbb36=1 << sl.ALARM_WITH_STOP_BIT)
    channel = _chan(dbb36=1 << sl.ALARM_CHANNEL_BIT)
    other = _chan(dbb36=0b00011111)
    assert sl.resolve_alarms(none) is False
    assert sl.resolve_alarms(stop) is True
    assert sl.resolve_alarms(channel) is True
    assert sl.resolve_alarms(other) is False


def test_program_always_from_db90_never_db99():
    plc = FakePlc(window=build_window(program="JOB_44"), chan=_chan())
    sample = sl.read_840d_sl(plc, {"PROGRAM_DB": 99})
    assert sample["program"] == "JOB_44"
    assert all(db != 99 for db, _start, _size in plc.reads)
    assert (90, 376, 206) in plc.reads
