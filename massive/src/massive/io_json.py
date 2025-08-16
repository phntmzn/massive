

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, List, Dict, Any, Union, Optional
from uuid import uuid4
from datetime import datetime

PathLike = Union[str, Path]

__all__ = [
    "load_patch",
    "save_patch",
    "load_batch",
    "save_batch",
    "read_json",
    "write_json",
]


# ---- core JSON I/O ---------------------------------------------------------


def read_json(path: PathLike) -> Any:
    """Read JSON with UTF-8 and return python object."""
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(obj: Any, path: PathLike, pretty: bool = True) -> Path:
    """Write JSON with UTF-8. Returns the written Path."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if pretty:
        text = json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=False)
        text += "\n"
        with p.open("w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    else:
        with p.open("w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
    return p


# ---- patch-level helpers ---------------------------------------------------


def load_patch(path: PathLike) -> Dict[str, Any]:
    """
    Load a single Massive patch JSON and return a dict.
    """
    data = read_json(path)
    if not isinstance(data, dict):
        raise TypeError(f"Patch at {path} must be a JSON object.")
    return data


def save_patch(
    patch: Dict[str, Any],
    path: PathLike,
    *,
    pretty: bool = True,
) -> Path:
    """
    Save a single Massive patch JSON. Returns the written path.
    """
    return write_json(patch, path, pretty=pretty)


# ---- batch utilities -------------------------------------------------------


def _infer_name(patch: Dict[str, Any], default_prefix: str, idx: int) -> str:
    """
    Choose a filename stem for a patch.
    Priority:
      1) patch['name']
      2) patch['meta']['name']
      3) f"{default_prefix}_{idx:04d}"
    """
    if isinstance(patch.get("name"), str) and patch["name"].strip():
        return sanitize_filename(patch["name"])
    meta = patch.get("meta")
    if isinstance(meta, dict) and isinstance(meta.get("name"), str) and meta["name"].strip():
        return sanitize_filename(meta["name"])
    return f"{default_prefix}_{idx:04d}"


def sanitize_filename(stem: str) -> str:
    bad = '<>:"/\\|?*'
    cleaned = "".join("_" if c in bad else c for c in stem).strip()
    return cleaned or f"patch_{uuid4().hex[:8]}"


def load_batch(paths_or_dir: PathLike) -> List[Dict[str, Any]]:
    """
    Load all JSON patches from a directory or a list of paths.
    """
    if isinstance(paths_or_dir, (str, Path)):
        p = Path(paths_or_dir)
        if p.is_dir():
            files = sorted(p.glob("*.json"))
        else:
            files = [p]
    else:
        files = [Path(x) for x in paths_or_dir]  # type: ignore[arg-type]

    patches: List[Dict[str, Any]] = []
    for fp in files:
        if fp.suffix.lower() != ".json":
            continue
        patches.append(load_patch(fp))
    return patches


def save_batch(
    patches: Iterable[Dict[str, Any]],
    out_dir: PathLike,
    *,
    default_prefix: str = "patch",
    pretty: bool = True,
    overwrite: bool = False,
) -> List[Path]:
    """
    Save an iterable of patch dicts into a directory.
    Returns the list of written Paths.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    written: List[Path] = []
    timestamp = datetime.now().strftime("%Y%m%d")
    for i, patch in enumerate(patches, start=1):
        stem = _infer_name(patch, default_prefix, i)
        candidate = out / f"{stem}.json"

        if candidate.exists() and not overwrite:
            # ensure uniqueness while keeping stem readable
            candidate = out / f"{stem}.{timestamp}.{uuid4().hex[:6]}.json"

        written.append(save_patch(patch, candidate, pretty=pretty))
    return written