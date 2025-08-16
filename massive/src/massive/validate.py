from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple, Union

from pydantic import ValidationError

from .schema import Patch
from .io_json import read_json

PathLike = Union[str, Path]

__all__ = [
    "validate_patch",
    "coerce_patch",
    "validate_file",
    "validate_many",
    "json_schema",
]


def validate_patch(data: Dict[str, Any]) -> None:
    """Raise ValidationError if patch is invalid."""
    Patch.model_validate(data)


def coerce_patch(data: Dict[str, Any]) -> Dict[str, Any]:
    """Return a validated + normalized patch dict."""
    return Patch.model_validate(data).model_dump(mode="python")


def validate_file(path: PathLike) -> None:
    """Validate a single JSON file."""
    data = read_json(path)
    validate_patch(data)


def validate_many(items: Iterable[PathLike]) -> List[Tuple[Path, bool, str]]:
    """Validate many JSON files, returning (path, ok, error_string)."""
    results: List[Tuple[Path, bool, str]] = []
    for it in items:
        p = Path(it)
        try:
            validate_file(p)
            results.append((p, True, ""))
        except ValidationError as e:
            results.append((p, False, str(e)))
    return results


def json_schema() -> Dict[str, Any]:
    """Return the JSON Schema for Patch."""
    return Patch.model_json_schema()