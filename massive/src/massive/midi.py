from __future__ import annotations

"""
MIDI utilities for Massive Automator.

- Port discovery & opening (mido/rtmidi)
- CC sending utilities
- Macro CC dispatch that pairs with configs/macro_map.yaml

Expected YAML shapes we understand for CC mapping:

Option A (simple):
------------------
cc:
  - 1
  - 2
  - 3
  - 4
  - 5
  - 6
  - 7
  - 8

Option B (per-macro inside macros list):
----------------------------------------
macros:
  - idx: 1
    cc: 1
    # ... other macro mapping fields used by macros.py
  - idx: 2
    cc: 2
  # ...

If neither form is present, defaults to CC 1..8.
"""

from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple, Union
import logging
import time

try:
    import mido
except Exception as e:  # pragma: no cover
    mido = None  # type: ignore[assignment]
    _IMPORT_ERROR = e
else:
    _IMPORT_ERROR = None

try:
    import yaml
except Exception:
    yaml = None  # type: ignore


PathLike = Union[str, Path]
log = logging.getLogger(__name__)

__all__ = [
    "list_output_ports",
    "find_output_port",
    "open_output",
    "default_output_port_guess",
    "send_cc",
    "send_cc_batch",
    "send_macros",
    "load_cc_assignments",
]


# --------------------------------------------------------------------------- #
# Port discovery
# --------------------------------------------------------------------------- #


def _require_mido() -> None:
    if mido is None:  # pragma: no cover
        raise ImportError(
            "mido (and a backend like python-rtmidi) is required for MIDI I/O. "
            f"Original import error: {_IMPORT_ERROR!r}"
        )


def list_output_ports() -> List[str]:
    """
    Return a list of available MIDI output port names.
    """
    _require_mido()
    return list(mido.get_output_names())


def find_output_port(
    query: str,
    *,
    case_insensitive: bool = True,
    substring: bool = True,
) -> Optional[str]:
    """
    Resolve a user-provided port name/substring to an actual port name.
    Preference order: exact match -> case-insensitive exact -> substring.

    Returns the resolved port name or None if not found.
    """
    _require_mido()
    ports = list_output_ports()
    if not ports:
        return None

    # 1) Exact
    if query in ports:
        return query

    # 2) Case-insensitive exact
    if case_insensitive:
        for p in ports:
            if p.lower() == query.lower():
                return p

    # 3) Substring
    if substring:
        q = query.lower() if case_insensitive else query
        for p in ports:
            if (p.lower() if case_insensitive else p).find(q) >= 0:
                return p
    return None


def default_output_port_guess() -> Optional[str]:
    """
    Heuristics to pick a likely port for NI Massive / IAC on macOS.
    Prefers an IAC bus, then anything containing 'Massive' or 'Virtual'.
    """
    _require_mido()
    candidates = list_output_ports()
    if not candidates:
        return None

    pri = [
        lambda n: "IAC" in n,
        lambda n: "Massive" in n,
        lambda n: "Virtual" in n,
        lambda n: True,  # fallback: first available
    ]
    for pred in pri:
        sel = [n for n in candidates if pred(n)]
        if sel:
            return sel[0]
    return candidates[0]


def open_output(port_name: str):
    """
    Open and return a mido output port context manager (must be closed by caller).
    """
    _require_mido()
    return mido.open_output(port_name)


# --------------------------------------------------------------------------- #
# CC sending
# --------------------------------------------------------------------------- #


def _clamp7(v: int) -> int:
    return max(0, min(127, int(v)))


def send_cc(
    cc: int,
    value: int,
    port_name: str,
    *,
    channel: int = 0,
) -> None:
    """
    Send a single Control Change to a given port.
    """
    _require_mido()
    msg = mido.Message("control_change", control=int(cc), value=_clamp7(value), channel=int(channel))
    with open_output(port_name) as port:
        port.send(msg)


def send_cc_batch(
    pairs: Iterable[Tuple[int, int]],
    port_name: str,
    *,
    channel: int = 0,
    inter_message_ms: float = 2.0,
) -> None:
    """
    Send a batch of (cc, value) tuples to the port with small spacing.
    """
    _require_mido()
    with open_output(port_name) as port:
        for cc, value in pairs:
            msg = mido.Message("control_change", control=int(cc), value=_clamp7(value), channel=int(channel))
            port.send(msg)
            if inter_message_ms > 0:
                time.sleep(inter_message_ms / 1000.0)


# --------------------------------------------------------------------------- #
# Macro dispatch (pairs values with CC assignments from YAML)
# --------------------------------------------------------------------------- #


def load_cc_assignments(path: PathLike = "configs/macro_map.yaml") -> List[int]:
    """
    Load CC assignments for the 8 macros from YAML.

    Returns a list of 8 integers (CC numbers). If not found/invalid, defaults to [1..8].
    """
    # Default fallback
    default = list(range(1, 9))

    try:
        if yaml is None:
            return default
        p = Path(path)
        if not p.exists():
            return default

        with p.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        # Option A
        cc = data.get("cc")
        if isinstance(cc, list) and len(cc) >= 8:
            nums = [int(x) for x in cc[:8]]
            return nums

        # Option B: macros list with per-entry idx+cc
        macros = data.get("macros")
        if isinstance(macros, list):
            arr: List[Optional[int]] = [None] * 8
            for entry in macros:
                if not isinstance(entry, dict):
                    continue
                idx = entry.get("idx")
                cc_num = entry.get("cc")
                if isinstance(idx, int) and isinstance(cc_num, int):
                    if 1 <= idx <= 8:
                        arr[idx - 1] = cc_num
                    elif 0 <= idx <= 7:
                        arr[idx] = cc_num
            # Fill any missing with defaults 1..8
            out: List[int] = []
            for i in range(8):
                out.append(int(arr[i]) if isinstance(arr[i], int) else i + 1)
            return out

        return default
    except Exception:  # pragma: no cover
        return default


def send_macros(
    values: Sequence[int],
    port_name: str,
    *,
    channel: int = 0,
    cc_map: Optional[Sequence[int]] = None,
    inter_message_ms: float = 2.0,
) -> None:
    """
    Send up to 8 macro values as CC messages.

    Args:
        values: sequence of ints in [0..127]; only the first 8 are used.
        port_name: exact or discovered port name to open.
        channel: MIDI channel (0-15).
        cc_map: optional sequence of CC numbers (length>=8). If None, loads from YAML.
        inter_message_ms: delay between messages to avoid flooding synth UIs.
    """
    _require_mido()
    if cc_map is None:
        cc_map = load_cc_assignments()

    # Normalize
    cc_used = list(cc_map[:8]) if len(cc_map) >= 8 else list(range(1, 9))
    vals = list(values[:8]) + [0] * (8 - min(8, len(values)))

    pairs = [(int(cc_used[i]), _clamp7(vals[i])) for i in range(8)]
    send_cc_batch(
        pairs,
        port_name,
        channel=channel,
        inter_message_ms=inter_message_ms,
    )