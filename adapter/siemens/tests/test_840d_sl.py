from importlib import import_module

sl = import_module("families.840d_sl")


def _chan(*, dbb32=0, dbb33=0, dbb34=0, dbb35=0, dbb36=0, dbb37=0):
    return bytes([dbb32, dbb33, dbb34, dbb35, dbb36, dbb37])


class FakePlc:
    def __init__(self, *, mode=0, chan=None, strings=None):
        self._mode = bytes([mode])
        self._chan = bytes(chan if chan is not None else _chan())
        self._strings = strings or {}
        self.reads = []

    def db_read(self, db, start, size):
        self.reads.append((db, start, size))
        if db == sl.MODE_DB and start == sl.MODE_START:
            return self._mode
        if db == sl.CHAN_DB and start == sl.CHAN_START:
            return self._chan
        key = (db, start)
        if key in self._strings:
            text = self._strings[key]
            payload = text.encode("latin-1")
            cap = size - 2
            return bytes([cap, min(len(payload), cap)]) + payload[:cap]
        raise AssertionError(f"unexpected db_read db={db} start={start} size={size}")


def test_auto_running_mode_execution_alarm():
    mode_byte = 1 << sl.MODE_AUTO_BIT
    chan = _chan(dbb35=1 << sl.PROG_RUNNING_BIT)
    assert sl.resolve_mode(mode_byte) == "AUTOMATIC"
    assert sl.refine_status(chan, sl.resolve_status_original(chan)) == "ACTIVE"
    assert sl.resolve_alarms(chan) is False

    plc = FakePlc(mode=mode_byte, chan=chan)
    sample = sl.read_840d_sl(plc, {"PROGRAM_DB": None})
    assert sample == {
        "mode": "AUTOMATIC",
        "execution": "ACTIVE",
        "alarm": False,
    }
    assert "program" not in sample
    assert all(db != 99 for db, _start, _size in plc.reads)


def test_mdi_and_jog():
    assert sl.resolve_mode(1 << sl.MODE_MDI_BIT) == "MANUAL_DATA_INPUT"
    assert sl.resolve_mode(1 << sl.MODE_JOG_BIT) == "MANUAL"
    assert sl.resolve_mode(0) == "UNAVAILABLE"


def test_execution_program_end_and_stops():
    completed = _chan(dbb33=1 << sl.M02_M30_BIT, dbb35=1 << sl.PROG_STOPPED_BIT)
    optional = _chan(dbb32=1 << sl.M00_M01_BIT, dbb35=1 << sl.PROG_STOPPED_BIT)
    stopped = _chan(dbb35=1 << sl.PROG_STOPPED_BIT)
    interrupted = _chan(dbb35=1 << sl.PROG_INTERRUPTED_BIT)
    ready = _chan(dbb35=1 << sl.CHAN_RESET_BIT)
    assert sl.refine_status(completed, sl.resolve_status_original(completed)) == "PROGRAM_COMPLETED"
    assert sl.refine_status(optional, sl.resolve_status_original(optional)) == "PROGRAM_OPTIONAL_STOP"
    assert sl.refine_status(stopped, sl.resolve_status_original(stopped)) == "PROGRAM_STOPPED"
    assert sl.resolve_status_original(interrupted) == "INTERRUPTED"
    assert sl.resolve_status_original(ready) == "READY"


def test_alarm_bits_6_and_7_only():
    none = _chan()
    stop = _chan(dbb36=1 << sl.ALARM_WITH_STOP_BIT)
    channel = _chan(dbb36=1 << sl.ALARM_CHANNEL_BIT)
    other = _chan(dbb36=0b00011111)
    assert sl.resolve_alarms(none) is False
    assert sl.resolve_alarms(stop) is True
    assert sl.resolve_alarms(channel) is True
    assert sl.resolve_alarms(other) is False


def test_program_read_only_when_cfg_sets_block():
    plc = FakePlc(
        mode=1 << sl.MODE_AUTO_BIT,
        chan=_chan(dbb35=1 << sl.PROG_RUNNING_BIT),
        strings={(100, 0): "O1234"},
    )
    sample = sl.read_840d_sl(
        plc,
        {"PROGRAM_DB": 100, "PROGRAM_OFFSET": 0, "PROGRAM_CAPACITY": 64},
    )
    assert sample["program"] == "O1234"
    assert (100, 0, 66) in plc.reads
    assert all(db != 99 for db, _start, _size in plc.reads)


def test_abort_with_latched_m02_is_not_completed():
    """Waiting/Aborted map to STOPPED; only the Stopped bit is refined."""
    aborted = _chan(dbb33=1 << sl.M02_M30_BIT, dbb35=0)
    assert sl.resolve_status_original(aborted) == "STOPPED"
    assert sl.refine_status(aborted, "STOPPED") == "STOPPED"
