

import json
from pathlib import Path

import pytest

from massive.macros import map_to_macros, resolve_path, load_macro_map


# ------------------------- fixtures & helpers -------------------------

@pytest.fixture()
def simple_patch():
    # Minimal patch structure used by tests; values match our generators/schema style
    return {
        "name": "TEST",
        "env1": {"attack": 0.01, "decay": 0.15, "sustain": 0.8, "release": 0.15},
        "env2": {"attack": 0.02, "decay": 0.25, "sustain": 0.4, "release": 0.2},
        "filter": {"type": "lowpass4", "cutoff": 0.5, "res": 0.2, "drive": 0.0, "mix": 1.0},
        "osc": [
            {"wave": "saw", "wt_pos": 0.5, "transpose": 0, "detune": 0.0, "amp": 0.8},
            {"wave": "square", "wt_pos": 0.5, "transpose": 0, "detune": 0.0, "amp": 0.7},
            {"wave": "sine", "wt_pos": 0.0, "transpose": 0, "detune": 0.0, "amp": 0.0},
        ],
        "meta": {"tags": ["unit"], "key": None, "tempo": None},
    }


def _write_yaml(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


# ------------------------------- resolve_path -------------------------------

def test_resolve_path_basic(simple_patch):
    assert resolve_path(simple_patch, "env1.attack") == pytest.approx(0.01)
    assert resolve_path(simple_patch, "filter.cutoff") == pytest.approx(0.5)
    assert resolve_path(simple_patch, "osc.0.amp") == pytest.approx(0.8)
    assert resolve_path(simple_patch, "osc[1].wt_pos") == pytest.approx(0.5)
    assert resolve_path(simple_patch, "osc[2].amp") == pytest.approx(0.0)


def test_resolve_path_missing_returns_default(simple_patch):
    assert resolve_path(simple_patch, "does.not.exist", default=0.42) == pytest.approx(0.42)
    # wrong type -> default
    tmp = {"x": {"y": "not-a-number"}}
    assert resolve_path(tmp, "x.y", default=0.1) == pytest.approx(0.1)


# ------------------------------ load_macro_map ------------------------------

def test_load_macro_map_missing_file_returns_empty(tmp_path: Path):
    cfg = load_macro_map(tmp_path / "nope.yaml")
    assert isinstance(cfg, dict)
    assert cfg.get("macros") == []


# -------------------------------- map_to_macros -----------------------------

def test_map_to_macros_constant_and_path(tmp_path: Path, simple_patch):
    # Macro 1 from path, Macro 2 constant, the rest should be zero-filled
    yaml_text = """
macros:
  - idx: 1
    source:
      path: "filter.cutoff"
      default: 0.0
    mapping:
      in: [0.0, 1.0]
      out: [0, 127]
  - idx: 2
    source:
      constant: 0.25
    mapping:
      in: [0.0, 1.0]
      out: [0, 127]
"""
    cfg_path = _write_yaml(tmp_path / "macro_map.yaml", yaml_text)
    vals = map_to_macros(simple_patch, macro_map_path=cfg_path)
    assert len(vals) == 8
    # cutoff 0.5 -> ~64
    assert vals[0] in (63, 64)
    # constant 0.25 -> ~32
    assert vals[1] in (31, 32)
    # remaining slots default to 0
    assert vals[2:] == [0, 0, 0, 0, 0, 0]


def test_map_to_macros_expr_pow_invert_clamp(tmp_path: Path, simple_patch):
    yaml_text = """
macros:
  - idx: 1
    source:
      expr: "0.7*a + 0.3*b"
      vars:
        a: "filter.cutoff"
        b: "env2.decay"
      default: 0.0
    mapping:
      in: [0.0, 1.0]
      out: [0, 127]
      curve: "pow:2.0"
      invert: true
      clamp: true
"""
    # filter.cutoff=0.5, env2.decay=0.25 -> mix=0.7*0.5 + 0.3*0.25 = 0.425
    # pow(2): 0.425^2 ≈ 0.1806; invert -> 0.8194; map to 0..127 ≈ 104
    cfg_path = _write_yaml(tmp_path / "macro_map.yaml", yaml_text)
    vals = map_to_macros(simple_patch, macro_map_path=cfg_path)
    assert 100 <= vals[0] <= 108  # allow rounding wiggle
    assert vals[1:] == [0, 0, 0, 0, 0, 0, 0]


def test_map_to_macros_indexing_and_defaults(tmp_path: Path, simple_patch):
    yaml_text = """
macros:
  - idx: 0      # zero-based index allowed -> goes to slot 0
    source:
      constant: 1.0
    mapping:
      in: [0.0, 1.0]
      out: [0, 127]
  - idx: 9      # invalid -> should fall back to first empty slot (slot 1)
    source:
      constant: 0.0
    mapping:
      in: [0.0, 1.0]
      out: [0, 127]
"""
    cfg_path = _write_yaml(tmp_path / "macro_map.yaml", yaml_text)
    vals = map_to_macros(simple_patch, macro_map_path=cfg_path)
    assert vals[0] == 127  # first macro set to full
    assert vals[1] == 0    # second placed into next empty slot
    assert vals[2:] == [0, 0, 0, 0, 0, 0]


def test_map_to_macros_bad_yaml_graceful(tmp_path: Path, simple_patch):
    # Non-list macros should be ignored -> fall back to zeros
    cfg_path = _write_yaml(tmp_path / "macro_map.yaml", "macros: not-a-list\n")
    vals = map_to_macros(simple_patch, macro_map_path=cfg_path)
    assert vals == [0, 0, 0, 0, 0, 0, 0, 0]