from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, List
import json
import random

# ---- Helpers ---------------------------------------------------------------

def clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))

def nrm_to_0_127(x: float) -> int:
    return int(round(clamp01(x) * 127))

# ---- Core objects ----------------------------------------------------------

@dataclass
class Osc:
    wave: str = "Plysaw II"
    pitch_semitones: int = 0          # [-24 .. +24]
    wt_position: float = 0.5          # 0..1
    intensity: float = 0.5            # 0..1
    amp: float = 0.8                  # 0..1
    formant: Optional[float] = None   # 0..1 if applicable

@dataclass
class Filter:
    ftype: str = "Daft"               # "Daft","Lowpass4","Bandpass",...
    cutoff: float = 0.5               # 0..1
    resonance: float = 0.15           # 0..1
    mix: float = 1.0                  # 0..1 (toward F1 vs F2 when used in MIX)

@dataclass
class Env:
    attack: float = 0.01
    decay: float = 0.2
    sustain: float = 0.7
    release: float = 0.25

@dataclass
class LFO:
    rate_hz: float = 2.0              # or map to host-sync fractions
    depth: float = 0.0                # 0..1
    shape: str = "triangle"

@dataclass
class FX:
    fx1_type: str = "DimensionExp"
    fx1_amt: float = 0.3
    fx1_size: float = 0.4
    fx2_type: str = "Reverb"
    fx2_amt: float = 0.25
    fx2_size: float = 0.5

@dataclass
class Global:
    quality: str = "Ultra"            # "Eco","High","Ultra"
    volume: float = 0.8               # 0..1
    bpm: float = 120.0                # metadata only

@dataclass
class MassivePatch:
    name: str = "Init from Python"
    osc1: Osc = Osc()
    osc2: Osc = Osc(wave="Math III", pitch_semitones=-12, wt_position=0.3, intensity=0.45, amp=0.7)
    osc3: Osc = Osc(wave="Squ-Sw I", pitch_semitones=-12, wt_position=0.35, intensity=0.5, amp=0.6, formant=0.4)
    filter1: Filter = Filter()
    filter2: Optional[Filter] = None
    env1_amp: Env = Env()
    env4_mod: Env = Env(attack=0.005, decay=0.15, sustain=0.4, release=0.15)
    lfo5: LFO = LFO(rate_hz=5.0, depth=0.0)
    lfo6: LFO = LFO(rate_hz=0.5, depth=0.0)
    fx: FX = FX()
    global_: Global = Global()

    # ---------- JSON IO ----------
    def to_json(self, path: str):
        with open(path, "w") as f:
            json.dump(asdict(self), f, indent=2)

    @staticmethod
    def from_json(path: str) -> "MassivePatch":
        with open(path, "r") as f:
            raw = json.load(f)
        def build(cls, d):  # tiny helper to map dict->dataclass
            return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
        return MassivePatch(
            name=raw.get("name","Patch"),
            osc1=build(Osc, raw["osc1"]),
            osc2=build(Osc, raw["osc2"]),
            osc3=build(Osc, raw["osc3"]),
            filter1=build(Filter, raw["filter1"]),
            filter2=(build(Filter, raw["filter2"]) if raw.get("filter2") else None),
            env1_amp=build(Env, raw["env1_amp"]),
            env4_mod=build(Env, raw["env4_mod"]),
            lfo5=build(LFO, raw["lfo5"]),
            lfo6=build(LFO, raw["lfo6"]),
            fx=build(FX, raw["fx"]),
            global_=build(Global, raw["global_"]),
        )

    # ---------- Simple randomizer w/ musical constraints ----------
    def randomize(self, seed: Optional[int]=None):
        rng = random.Random(seed)
        self.osc1.wave = rng.choice(["Plysaw II","Square-Saw I","Sin-Triangle","Groan II","Scrapyard"])
        self.osc2.wave = rng.choice(["Math III","Addict","Chrome","Carbon","Roughmath I"])
        self.osc3.wave = rng.choice(["Squ-Sw I","Formant","Digigrain II","Bell","Sine"])
        for o in [self.osc1, self.osc2, self.osc3]:
            o.pitch_semitones = rng.choice([0, -12, 7, -5, 12])
            o.wt_position = clamp01(rng.uniform(0.2, 0.8))
            o.intensity = clamp01(rng.uniform(0.3, 0.9))
            o.amp = clamp01(rng.uniform(0.4, 0.95))
        self.filter1.ftype = rng.choice(["Daft","Lowpass4","Bandpass","Scream"])
        self.filter1.cutoff = clamp01(rng.uniform(0.15, 0.85))
        self.filter1.resonance = clamp01(rng.uniform(0.05, 0.5))
        self.fx.fx1_type = rng.choice(["DimensionExp","Chorus","Phaser"])
        self.fx.fx2_type = rng.choice(["Reverb","Delay","Small Reverb"])
        return self

    # ---------- Map to 8 Macro values (0..127) ----------
    # You set these 8 macros up once in Massive (MIDI Learn) to control the linked params
    def to_macro_values(self) -> Dict[str, int]:
        """
        Example mapping:
        M1: Filter1 Cutoff
        M2: Filter1 Resonance
        M3: OSC1 WT Position
        M4: OSC2 WT Position
        M5: OSC Mix (use as you like)
        M6: Env1 Sustain
        M7: FX1 Amount
        M8: FX2 Amount
        """
        return {
            "M1_cutoff":    nrm_to_0_127(self.filter1.cutoff),
            "M2_res":       nrm_to_0_127(self.filter1.resonance),
            "M3_osc1_wt":   nrm_to_0_127(self.osc1.wt_position),
            "M4_osc2_wt":   nrm_to_0_127(self.osc2.wt_position),
            "M5_mix":       nrm_to_0_127(self.filter1.mix),
            "M6_env_sus":   nrm_to_0_127(self.env1_amp.sustain),
            "M7_fx1_amt":   nrm_to_0_127(self.fx.fx1_amt),
            "M8_fx2_amt":   nrm_to_0_127(self.fx.fx2_amt),
        }
