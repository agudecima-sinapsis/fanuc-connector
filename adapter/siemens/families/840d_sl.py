"""SINUMERIK 840D sl family pack — machine-builder DB90 (MA-64 / technicians).

Mode, status, program and CNC clock live in one STRING/DT window on DB90.
Alarm presence is still the portable LIS2 channel byte (DB21.DBB36); the
technicians did not give a DB90 alarm address.

S7 STRING[n] on the wire is n+2 bytes (max, length, then chars). Layout:

    DB90.DBX376.0  STRING[15]   mode
    DB90.DBX394.0  STRING[15]   status
    DB90.DBX412.0  STRING[160]  program   (162 bytes on the wire)
    DB90.DBX574.0  DATE_AND_TIME (8 bytes BCD)

412 + 162 = 574: the "162 bytes" quoted for the timestamp is the preceding
program STRING, not the DT size. DATE_AND_TIME is always 8 bytes.
"""

from datetime import datetime, timezone
from unicodedata import combining, normalize as u_normalize

BUILDER_DB = 90
WINDOW_START = 376
WINDOW_LEN = 206  # 574 + 8 - 376

MODE_REL, MODE_CAP = 0, 15
STATUS_REL, STATUS_CAP = 18, 15  # 394 - 376
PROGRAM_REL, PROGRAM_CAP = 36, 160  # 412 - 376
DT_REL, DT_LEN = 198, 8  # 574 - 376

CHAN_DB, CHAN_START, CHAN_LEN = 21, 32, 6  # DBB32..DBB37 of channel 1
ALARM_WITH_STOP_BIT, ALARM_CHANNEL_BIT = 7, 6  # DB21.DBB36

# Contract values pass through as-is after normalize.
MODE_MAP = {
    "AUTO": "AUTOMATIC",
    "AUTOMATIC": "AUTOMATIC",
    "AUTOMATIK": "AUTOMATIC",
    "AUTOMATICO": "AUTOMATIC",
    "MDI": "MANUAL_DATA_INPUT",
    "MDA": "MANUAL_DATA_INPUT",
    "MANUAL_DATA_INPUT": "MANUAL_DATA_INPUT",
    "MANUAL DATA INPUT": "MANUAL_DATA_INPUT",
    "JOG": "MANUAL",
    "MANUAL": "MANUAL",
    "HAND": "MANUAL",
    "EINRICHTEN": "MANUAL",
    "REPOS": "MANUAL",
    "REF": "MANUAL",
    "REFPOINT": "MANUAL",
    "TEACHIN": "MANUAL",
    "TEACH IN": "MANUAL",
    "AUTOMATIC MODE": "AUTOMATIC",
    "AUTO MODE": "AUTOMATIC",
    "MDI AUTO": "MANUAL_DATA_INPUT",
    "MDIAUTO": "MANUAL_DATA_INPUT",
}

EXECUTION_MAP = {
    "ACTIVE": "ACTIVE",
    "RUNNING": "ACTIVE",
    "RUN": "ACTIVE",
    "LAUFEND": "ACTIVE",
    "CYCLE": "ACTIVE",
    "IN CYCLE": "ACTIVE",
    "EXECUTING": "ACTIVE",
    "INTERRUPTED": "INTERRUPTED",
    "INTERRUPT": "INTERRUPTED",
    "HOLD": "INTERRUPTED",
    "FEEDHOLD": "INTERRUPTED",
    "FEED HOLD": "INTERRUPTED",
    "UNTERBROCHEN": "INTERRUPTED",
    "READY": "READY",
    "RESET": "READY",
    "IDLE": "READY",
    "PROGRAM_COMPLETED": "PROGRAM_COMPLETED",
    "COMPLETED": "PROGRAM_COMPLETED",
    "M30": "PROGRAM_COMPLETED",
    "M02": "PROGRAM_COMPLETED",
    "PROGRAM END": "PROGRAM_COMPLETED",
    "ENDED": "PROGRAM_COMPLETED",
    "PROGRAM_OPTIONAL_STOP": "PROGRAM_OPTIONAL_STOP",
    "OPTIONAL_STOP": "PROGRAM_OPTIONAL_STOP",
    "OPTIONAL STOP": "PROGRAM_OPTIONAL_STOP",
    "M00": "PROGRAM_OPTIONAL_STOP",
    "M01": "PROGRAM_OPTIONAL_STOP",
    "PROGRAM_STOPPED": "PROGRAM_STOPPED",
    "STOPPED": "PROGRAM_STOPPED",
    "STOP": "PROGRAM_STOPPED",
    "GESTOPPT": "PROGRAM_STOPPED",
    "WAITING": "STOPPED",
    "WAIT": "STOPPED",
    "WARTEND": "STOPPED",
    "ABORTED": "STOPPED",
    "ABGEBROCHEN": "STOPPED",
}


_last_logged_raw = None


def bit(byte_value, index):
    return bool((byte_value >> index) & 1)


def _normalize(text):
    """Uppercase, collapse space, strip accents so Automático → AUTOMATICO."""
    folded = u_normalize("NFKD", text or "")
    folded = "".join(ch for ch in folded if not combining(ch))
    return " ".join(folded.replace("_", " ").split()).upper()


def decode_s7_string(data, capacity):
    """Decode STRING[capacity] or fall back to CHAR[capacity]."""
    if not data:
        return ""
    if len(data) >= 2 and data[0] == capacity and data[1] <= capacity:
        n = min(data[1], len(data) - 2)
        return data[2 : 2 + n].decode("latin-1").rstrip("\x00 ").strip()
    return data[:capacity].decode("latin-1").rstrip("\x00 ").strip()


def _bcd(byte):
    return ((byte >> 4) * 10) + (byte & 0x0F)


def decode_s7_dt(data):
    """S7 DATE_AND_TIME (8 bytes BCD) → ISO-8601. CNC clock, labelled Z.

    Returns None when the 8 bytes are not a valid DT (zeros, garbage).
    """
    if data is None or len(data) < DT_LEN:
        return None
    year = _bcd(data[0])
    year += 1900 if year >= 90 else 2000
    month = _bcd(data[1])
    day = _bcd(data[2])
    hour = _bcd(data[3])
    minute = _bcd(data[4])
    second = _bcd(data[5])
    msec = _bcd(data[6]) * 10 + (data[7] >> 4)
    try:
        dt = datetime(
            year, month, day, hour, minute, second, msec * 1000, tzinfo=timezone.utc
        )
    except ValueError:
        return None
    return dt.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def map_mode(raw):
    key = _normalize(raw)
    if not key:
        return "UNAVAILABLE"
    mapped = MODE_MAP.get(key)
    if mapped:
        return mapped
    # Unknown PLC text: keep it visible in SHDR so we can extend the table.
    return raw.strip()


def map_execution(raw):
    key = _normalize(raw)
    if not key:
        return "STOPPED"
    return EXECUTION_MAP.get(key, raw.strip())


def resolve_alarms(chan):
    """DB21.DBB36 bits 6–7 → boolean Condition (no code/text)."""
    dbb36 = chan[4]
    return bit(dbb36, ALARM_WITH_STOP_BIT) or bit(dbb36, ALARM_CHANNEL_BIT)


def read_840d_sl(plc, cfg):
    """Read stable item names from the technician DB90 window.

    Returns mode, execution, program, alarm. Optional `timestamp` is the CNC
    DATE_AND_TIME; the adapter pops it for the SHDR line and does not change-gate
    on it (milliseconds would emit every poll).
    """
    del cfg  # pack owns addresses; env PROGRAM_DB is unused
    window = plc.db_read(BUILDER_DB, WINDOW_START, WINDOW_LEN)
    chan = plc.db_read(CHAN_DB, CHAN_START, CHAN_LEN)
    mode_slice = window[MODE_REL : MODE_REL + MODE_CAP + 2]
    status_slice = window[STATUS_REL : STATUS_REL + STATUS_CAP + 2]
    raw_mode = decode_s7_string(mode_slice, MODE_CAP)
    raw_status = decode_s7_string(status_slice, STATUS_CAP)
    raw_program = decode_s7_string(
        window[PROGRAM_REL : PROGRAM_REL + PROGRAM_CAP + 2], PROGRAM_CAP
    )
    global _last_logged_raw
    logged = (raw_mode, raw_status, raw_program)
    if logged != _last_logged_raw:
        print(
            f"DB90 raw mode={raw_mode!r} bytes={mode_slice.hex()} "
            f"status={raw_status!r} program={raw_program!r}",
            flush=True,
        )
        _last_logged_raw = logged
    sample = {
        "mode": map_mode(raw_mode),
        "execution": map_execution(raw_status),
        "program": raw_program,
        "alarm": resolve_alarms(chan),
    }
    plc_ts = decode_s7_dt(window[DT_REL : DT_REL + DT_LEN])
    if plc_ts:
        sample["timestamp"] = plc_ts
    return sample
