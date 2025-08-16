

from __future__ import annotations

"""
Musically-constrained random preset generators.

Public API:
    generate_from_recipe(recipe_path) -> list[dict]
      - Reads a YAML file with one or more generator entries and returns a list
        of patch dictionaries (ready to be written by io_json.save_batch).

YAML schema (flexible):
----------------------
# Either top-level list ...
- type: lead
  count: 32
  name_prefix: "LD"
  seed: 1234
  key: "C minor"
  tempo: 140
  overrides:
    filter.cutoff: [0.4, 0.9]     # range -> uniform
    env1.attack: 0.01             # constant
# ...or object with "generators"
generators:
  - type: bass
    count: 24
    name_prefix: "BS"
"""

from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Tuple, Union
import math
import random

try:
    import yaml
except Exception:
    yaml = None  # type: ignore

PathLike = Union[str, Path]

__all__ = ["generate_from_recipe"]

# ----------------------------- small utils ---------------------------------


def _rng(seed: Optional[Union[int, str]]) -> random.Random:
    if seed is None:
        return random.Random()
    if isinstance(seed, int):
        return random.Random(seed)
    # stable hash for strings
    h = 1469598103934665603
    for ch in str(seed):
        h ^= ord(ch)
        h *= 1099511628211
        h &= (1 << 64) - 1
    return random.Random(h)


def _clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x


def _set_dotted(target: MutableMapping[str, Any], dotted: str, value: Any) -> None:
    cur: MutableMapping[str, Any] = target
    parts = [p for p in str(dotted).split(".") if p]
    for p in parts[:-1]:
        if p not in cur or not isinstance(cur[p], dict):
            cur[p] = {}
        cur = cur[p]  # type: ignore[assignment]
    cur[parts[-1]] = value


def _apply_overrides(patch: Dict[str, Any], overrides: Mapping[str, Any], rng: random.Random) -> None:
    for path, spec in overrides.items():
        if isinstance(spec, (list, tuple)) and len(spec) == 2:
            lo, hi = float(spec[0]), float(spec[1])
            _set_dotted(patch, path, float(rng.uniform(lo, hi)))
        else:
            _set_dotted(patch, path, spec)


def _choose_wave(rng: random.Random, kind: str | None = None) -> str:
    if kind == "harmonic":
        choices = ["saw", "square", "wavetable", "triangle"]
        weights = [0.5, 0.3, 0.15, 0.05]
    elif kind == "soft":
        choices = ["sine", "triangle", "saw", "square"]
        weights = [0.5, 0.3, 0.15, 0.05]
    else:
        choices = ["saw", "square", "sine", "triangle", "wavetable", "noise"]
        weights = [0.45, 0.25, 0.1, 0.08, 0.07, 0.05]
    x = rng.random()
    acc = 0.0
    for c, w in zip(choices, weights):
        acc += w
        if x <= acc:
            return c
    return choices[-1]


# ---------------------------- base template --------------------------------


def _base_patch(name: str, tag: str, key: Optional[str], tempo: Optional[float]) -> Dict[str, Any]:
    return {
        "version": 1,
        "name": name,
        "osc": [
            {"wave": "saw", "wt_pos": 0.5, "transpose": 0, "detune": 0.0, "amp": 0.8},
            {"wave": "square", "wt_pos": 0.5, "transpose": 0, "detune": 0.0, "amp": 0.7},
            {"wave": "sine", "wt_pos": 0.0, "transpose": 0, "detune": 0.0, "amp": 0.0},
        ],
        "mix": {"osc_balance": 0.5, "noise": 0.0},
        "filter": {"type": "lowpass4", "cutoff": 0.5, "res": 0.2, "drive": 0.0, "mix": 1.0},
        "env1": {"attack": 0.01, "decay": 0.15, "sustain": 0.8, "release": 0.15},  # amp
        "env2": {"attack": 0.02, "decay": 0.25, "sustain": 0.4, "release": 0.2},   # mod
        "lfo1": {"rate": 0.2, "shape": "sine", "amount": 0.0, "tempo_sync": False},
        "fx": {
            "reverb": {"mix": 0.1, "size": 0.5},
            "delay": {"mix": 0.1, "time": 0.3, "feedback": 0.2, "sync": False},
            "chorus": {"mix": 0.0, "rate": 0.2, "depth": 0.2},
        },
        "mod": {
            "env2_to_cutoff": 0.0,
            "lfo1_to_pitch": 0.0,
            "lfo1_to_amp": 0.0,
        },
        "meta": {"tags": [tag], "key": key, "tempo": tempo},
    }


# --------------------------- generator flavors -----------------------------


def _gen_lead(rng: random.Random, name: str, key: Optional[str], tempo: Optional[float]) -> Dict[str, Any]:
    p = _base_patch(name, "lead", key, tempo)
    # bright, quick, a bit of glide in feel (sim via filter + short env)
    p["osc"][0]["wave"] = _choose_wave(rng, "harmonic")
    p["osc"][1]["wave"] = _choose_wave(rng, "harmonic")
    p["osc"][0]["detune"] = round(rng.uniform(0.01, 0.08), 4)
    p["osc"][1]["detune"] = round(rng.uniform(0.01, 0.12), 4)
    p["osc"][2]["amp"] = 0.0
    p["filter"]["cutoff"] = round(_clamp01(rng.uniform(0.55, 0.95)), 4)
    p["filter"]["res"] = round(rng.uniform(0.05, 0.25), 4)
    p["env1"].update({"attack": round(rng.uniform(0.001, 0.02), 4), "decay": round(rng.uniform(0.1, 0.25), 4), "sustain": round(rng.uniform(0.6, 0.9), 4), "release": round(rng.uniform(0.05, 0.2), 4)})
    p["env2"].update({"attack": 0.0, "decay": round(rng.uniform(0.05, 0.25), 4), "sustain": round(rng.uniform(0.0, 0.2), 4), "release": round(rng.uniform(0.05, 0.2), 4)})
    p["mod"]["env2_to_cutoff"] = round(rng.uniform(0.2, 0.7), 4)
    p["fx"]["reverb"]["mix"] = round(rng.uniform(0.05, 0.2), 4)
    p["fx"]["delay"]["mix"] = round(rng.uniform(0.05, 0.25), 4)
    p["lfo1"]["amount"] = round(rng.uniform(0.0, 0.25), 4)
    return p


def _gen_bass(rng: random.Random, name: str, key: Optional[str], tempo: Optional[float]) -> Dict[str, Any]:
    p = _base_patch(name, "bass", key, tempo)
    p["osc"][0]["wave"] = _choose_wave(rng, "harmonic")
    p["osc"][1]["wave"] = _choose_wave(rng, "harmonic")
    p["osc"][0]["transpose"] = -12 if rng.random() < 0.8 else 0
    p["osc"][1]["transpose"] = -12 if rng.random() < 0.5 else 0
    p["osc"][0]["detune"] = round(rng.uniform(0.0, 0.03), 4)
    p["osc"][1]["detune"] = round(rng.uniform(0.0, 0.05), 4)
    p["filter"]["cutoff"] = round(_clamp01(rng.uniform(0.15, 0.45)), 4)
    p["filter"]["res"] = round(rng.uniform(0.1, 0.35), 4)
    p["filter"]["drive"] = round(rng.uniform(0.0, 0.4), 4)
    p["env1"].update({"attack": round(rng.uniform(0.001, 0.01), 4), "decay": round(rng.uniform(0.05, 0.18), 4), "sustain": round(rng.uniform(0.6, 0.95), 4), "release": round(rng.uniform(0.04, 0.12), 4)})
    p["env2"].update({"attack": 0.0, "decay": round(rng.uniform(0.05, 0.2), 4), "sustain": round(rng.uniform(0.0, 0.2), 4), "release": round(rng.uniform(0.05, 0.15), 4)})
    p["mod"]["env2_to_cutoff"] = round(rng.uniform(0.3, 0.9), 4)
    p["fx"]["reverb"]["mix"] = 0.0
    p["fx"]["delay"]["mix"] = 0.0
    p["lfo1"]["amount"] = round(rng.uniform(0.0, 0.15), 4)
    return p


def _gen_pad(rng: random.Random, name: str, key: Optional[str], tempo: Optional[float]) -> Dict[str, Any]:
    p = _base_patch(name, "pad", key, tempo)
    for i in (0, 1):
        p["osc"][i]["wave"] = _choose_wave(rng, "soft")
        p["osc"][i]["detune"] = round(rng.uniform(0.02, 0.12), 4)
    p["osc"][2]["wave"] = "sine"
    p["osc"][2]["amp"] = round(rng.uniform(0.1, 0.4), 4)
    p["filter"]["type"] = "lowpass2"
    p["filter"]["cutoff"] = round(_clamp01(rng.uniform(0.25, 0.6)), 4)
    p["filter"]["res"] = round(rng.uniform(0.05, 0.2), 4)
    p["env1"].update({"attack": round(rng.uniform(0.2, 1.2), 4), "decay": round(rng.uniform(0.5, 1.5), 4), "sustain": round(rng.uniform(0.6, 0.95), 4), "release": round(rng.uniform(0.8, 2.5), 4)})
    p["env2"].update({"attack": round(rng.uniform(0.1, 0.5), 4), "decay": round(rng.uniform(0.6, 1.8), 4), "sustain": round(rng.uniform(0.5, 0.9), 4), "release": round(rng.uniform(0.8, 2.0), 4)})
    p["mod"]["env2_to_cutoff"] = round(rng.uniform(0.1, 0.5), 4)
    p["fx"]["reverb"]["mix"] = round(rng.uniform(0.2, 0.6), 4)
    p["fx"]["reverb"]["size"] = round(rng.uniform(0.5, 0.9), 4)
    p["fx"]["chorus"]["mix"] = round(rng.uniform(0.15, 0.5), 4)
    p["fx"]["delay"]["mix"] = round(rng.uniform(0.05, 0.25), 4)
    p["lfo1"]["amount"] = round(rng.uniform(0.0, 0.35), 4)
    p["lfo1"]["rate"] = round(rng.uniform(0.05, 0.35), 4)
    return p


def _gen_pluck(rng: random.Random, name: str, key: Optional[str], tempo: Optional[float]) -> Dict[str, Any]:
    p = _base_patch(name, "pluck", key, tempo)
    p["osc"][0]["wave"] = _choose_wave(rng, None)
    p["osc"][1]["wave"] = _choose_wave(rng, None)
    p["osc"][0]["detune"] = round(rng.uniform(0.0, 0.05), 4)
    p["osc"][1]["detune"] = round(rng.uniform(0.0, 0.08), 4)
    p["env1"].update({"attack": round(rng.uniform(0.001, 0.01), 4), "decay": round(rng.uniform(0.05, 0.25), 4), "sustain": round(rng.uniform(0.0, 0.25), 4), "release": round(rng.uniform(0.05, 0.2), 4)})
    p["env2"].update({"attack": 0.0, "decay": round(rng.uniform(0.05, 0.2), 4), "sustain": 0.0, "release": round(rng.uniform(0.02, 0.15), 4)})
    p["filter"]["cutoff"] = round(_clamp01(rng.uniform(0.35, 0.85)), 4)
    p["mod"]["env2_to_cutoff"] = round(rng.uniform(0.3, 0.9), 4)
    p["fx"]["reverb"]["mix"] = round(rng.uniform(0.05, 0.25), 4)
    p["fx"]["delay"]["mix"] = round(rng.uniform(0.1, 0.35), 4)
    return p


_GENERATORS = {
    "lead": _gen_lead,
    "bass": _gen_bass,
    "pad": _gen_pad,
    "pluck": _gen_pluck,
}


# ---------------------------- public entrypoint -----------------------------


def _normalize_entries(raw: Any) -> List[Mapping[str, Any]]:
    if isinstance(raw, list):
        return [e for e in raw if isinstance(e, Mapping)]
    if isinstance(raw, Mapping) and isinstance(raw.get("generators"), list):
        return [e for e in raw["generators"] if isinstance(e, Mapping)]
    return []


def generate_from_recipe(recipe_path: PathLike) -> List[Dict[str, Any]]:
    """
    Build a list of patches from a YAML recipe.
    """
    if yaml is None:
        raise RuntimeError("PyYAML is required to read the generators.yaml")

    p = Path(recipe_path)
    if not p.exists():
        raise FileNotFoundError(f"Recipe not found: {p}")

    with p.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or []

    entries = _normalize_entries(raw)
    if not entries:
        # allow a degenerate one-off default
        entries = [{"type": "lead", "count": 1, "name_prefix": "LD"}]

    patches: List[Dict[str, Any]] = []
    for entry in entries:
        kind = str(entry.get("type", "lead")).lower()
        count = int(entry.get("count", 1))
        name_prefix = str(entry.get("name_prefix", kind.upper()))
        key = entry.get("key")
        tempo = entry.get("tempo")
        overrides = entry.get("overrides") or {}
        seed = entry.get("seed")

        rng = _rng(seed)

        gen = _GENERATORS.get(kind)
        if gen is None:
            gen = _gen_lead  # fallback

        for i in range(1, max(1, count) + 1):
            name = f"{name_prefix}_{i:04d}"
            patch = gen(rng, name, key, tempo)
            if isinstance(overrides, Mapping) and overrides:
                _apply_overrides(patch, overrides, rng)
            patches.append(patch)

    return patches