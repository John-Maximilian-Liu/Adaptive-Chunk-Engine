"""Stable ID generation using UUIDv7-compatible layout."""
from __future__ import annotations

import os
import time
import uuid
from typing import Optional


def new_id() -> str:
    try:
        return str(uuid.uuid7())  # type: ignore[attr-defined]
    except AttributeError:
        ts_ms = int(time.time() * 1000)
        rand = os.urandom(10)
        b = bytearray(16)
        b[0:6] = ts_ms.to_bytes(6, "big")
        b[6] = (rand[0] & 0x0F) | 0x70
        b[7] = rand[1]
        b[8] = (rand[2] & 0x3F) | 0x80
        b[9:16] = rand[3:10]
        return str(uuid.UUID(bytes=bytes(b)))


def ensure_id(value: Optional[str] = None) -> str:
    return value or new_id()
