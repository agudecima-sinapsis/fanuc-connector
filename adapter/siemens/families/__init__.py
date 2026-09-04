"""Siemens CNC family packs. Slice 1 ships 840D sl only.

The pack module is `840d_sl.py` (digit-prefixed). Import it via importlib so
`SIEMENS_FAMILY=840d_sl` stays the config key without a renamed file.
"""

from importlib import import_module

_840d_sl = import_module(".840d_sl", __package__)
read_840d_sl = _840d_sl.read_840d_sl

PACKS = {
    "840d_sl": read_840d_sl,
}

__all__ = ["PACKS", "read_840d_sl"]
