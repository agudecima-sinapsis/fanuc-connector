"""SINUMERIK 840D sl / LIS2 family pack (DB11 / DB21).

Bit map copied from scritps/ingests/dmgmori/s7_dmgmori.py. Do not import that
file — MQTT ingest would leak into the adapter process.

Signal addresses: SINUMERIK 840D sl Parameter Manual "Lists (Book 2)",
6FC5397-3CP40-5BA3, sections 4.7.2 (DB11) and 4.11 (DB21-DB30).
"""

MODE_DB, MODE_START, MODE_LEN = 11, 6, 1  # DBB6 active operating mode
CHAN_DB, CHAN_START, CHAN_LEN = 21, 32, 6  # DBB32..DBB37 of channel 1

MODE_AUTO_BIT, MODE_MDI_BIT, MODE_JOG_BIT = 0, 1, 2  # DB11.DBB6
PROG_RUNNING_BIT, PROG_STOPPED_BIT, PROG_INTERRUPTED_BIT = 0, 2, 3
CHAN_RESET_BIT = 7
M02_M30_BIT = 5  # DB21.DBB33, program end
M00_M01_BIT = 5  # DB21.DBB32, optional stop
ALARM_WITH_STOP_BIT, ALARM_CHANNEL_BIT = 7, 6  # DB21.DBB36


def bit(byte_value, index):
    return bool((byte_value >> index) & 1)


def read_s7_string(plc, db, offset, capacity):
    """Read a Siemens STRING: byte 0 is capacity, byte 1 is the current length."""
    data = plc.db_read(db, offset, capacity + 2)
    return data[2 : 2 + min(data[1], capacity)].decode("latin-1")


def resolve_mode(dbb6):
    """DB11.DBB6 -> CONTROLLER_MODE string."""
    if bit(dbb6, MODE_AUTO_BIT):
        return "AUTOMATIC"
    if bit(dbb6, MODE_MDI_BIT):
        return "MANUAL_DATA_INPUT"
    if bit(dbb6, MODE_JOG_BIT):
        return "MANUAL"
    return "UNAVAILABLE"


def resolve_status_original(chan):
    """DB21.DBB35 -> raw channel/program state, before M-function refinement.

    `chan` is the 6-byte window starting at DBB32, so chan[i] is DBB(32+i).
    """
    dbb35 = chan[3]
    if bit(dbb35, PROG_RUNNING_BIT):
        return "ACTIVE"
    if bit(dbb35, PROG_INTERRUPTED_BIT):
        return "INTERRUPTED"
    # Channel reset is checked BEFORE the remaining program-state bits: at NC
    # reset the program reads as aborted, but the machine is idle and ready,
    # not stopped mid-job.
    if bit(dbb35, CHAN_RESET_BIT):
        return "READY"
    return "STOPPED"


def refine_status(chan, status_original):
    """Disambiguate a stopped program using the M-function bits.

    Gate on the Stopped BIT, not on the mapped string: Waiting and Aborted also
    map to STOPPED, and refining them would let an abort with a latched DBB33.5
    publish PROGRAM_COMPLETED.
    """
    if not bit(chan[3], PROG_STOPPED_BIT):
        return status_original
    if bit(chan[1], M02_M30_BIT):  # DBB33.5
        return "PROGRAM_COMPLETED"
    if bit(chan[0], M00_M01_BIT):  # DBB32.5
        return "PROGRAM_OPTIONAL_STOP"
    return "PROGRAM_STOPPED"


def resolve_alarms(chan):
    """DB21.DBB36 bits 6–7 -> boolean Condition (no code/text)."""
    dbb36 = chan[4]
    return bit(dbb36, ALARM_WITH_STOP_BIT) or bit(dbb36, ALARM_CHANNEL_BIT)


def read_840d_sl(plc, cfg):
    """Read stable item names from an 840D sl PLC.

    Returns dict keys: mode, execution, alarm (bool). Includes program only
    when cfg['PROGRAM_DB'] is a proven integer. Never defaults that block.
    """
    mode_byte = plc.db_read(MODE_DB, MODE_START, MODE_LEN)[0]
    chan = plc.db_read(CHAN_DB, CHAN_START, CHAN_LEN)
    status_original = resolve_status_original(chan)
    sample = {
        "mode": resolve_mode(mode_byte),
        "execution": refine_status(chan, status_original),
        "alarm": resolve_alarms(chan),
    }
    program_db = cfg.get("PROGRAM_DB")
    if program_db is not None:
        sample["program"] = read_s7_string(
            plc,
            program_db,
            cfg.get("PROGRAM_OFFSET", 0),
            cfg.get("PROGRAM_CAPACITY", 64),
        )
    return sample
