

from __future__ import annotations
"""
Typed schema for a Massive-style patch.

We use Pydantic v2 models with strict bounds and `extra='forbid'` so accidental
keys are caught during validation.

Public bits:
- `Patch` (the full model)
- `coerce_patch(data: dict) -> dict`  -> validated + normalized dict
- `validate_patch(data: dict) -> None` -> raises `pydantic.ValidationError` on bad input
"""

from typing import List, Optional, Literal, Annotated, Dict, Any
from pydantic import BaseModel, Field, ConfigDict, ValidationError

# ---- common constrained types ---------------------------------------------

Float01 = Annotated[float, Field(ge=0.0, le=1.0)]
NonNeg = Annotated[float, Field(ge=0.0)]
MidiCCVal = Annotated[int, Field(ge=0, le=127)]

WaveName = Literal["saw", "square", "sine", "triangle", "wavetable", "noise"]
FilterType = Literal["lowpass4", "lowpass2", "bandpass", "highpass4", "highpass2"]
LFOShape = Literal["sine", "triangle", "square", "saw", "random"]

# ---- leaf components -------------------------------------------------------


class Osc(BaseModel):
    model_config = ConfigDict(extra="forbid")

    wave: WaveName = "saw"
    wt_pos: Float01 = 0.5
    transpose: int = 0  # semitones; keep range modest but not enforced here
    detune: float = 0.0  # +/- semitones fraction
    amp: Float01 = 0.8


class Mix(BaseModel):
    model_config = ConfigDict(extra="forbid")

    osc_balance: Float01 = 0.5  # 0..1 (osc1..osc2), osc3 is gated by its amp
    noise: Float01 = 0.0


class Filter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: FilterType = "lowpass4"
    cutoff: Float01 = 0.5
    res: Float01 = 0.2
    drive: Float01 = 0.0
    mix: Float01 = 1.0


class Envelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attack: NonNeg = 0.01
    decay: NonNeg = 0.15
    sustain: Float01 = 0.8
    release: NonNeg = 0.15


class LFO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rate: NonNeg = 0.2           # Hz if not tempo-synced
    shape: LFOShape = "sine"
    amount: Float01 = 0.0        # modulation depth 0..1
    tempo_sync: bool = False     # if True, 'rate' may be a musical value interpreted elsewhere


class FXReverb(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mix: Float01 = 0.1
    size: Float01 = 0.5


class FXDelay(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mix: Float01 = 0.1
    time: NonNeg = 0.3           # seconds if not synced
    feedback: Float01 = 0.2
    sync: bool = False


class FXChorus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mix: Float01 = 0.0
    rate: NonNeg = 0.2
    depth: Float01 = 0.2


class FX(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reverb: FXReverb = FXReverb()
    delay: FXDelay = FXDelay()
    chorus: FXChorus = FXChorus()


class Mod(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Simple named mod slots. Keep them 0..1 for normalized depth.
    env2_to_cutoff: Float01 = 0.0
    lfo1_to_pitch: Float01 = 0.0
    lfo1_to_amp: Float01 = 0.0


class Meta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tags: List[str] = []
    key: Optional[str] = None
    tempo: Optional[NonNeg] = None


# ---- root model ------------------------------------------------------------


class Patch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = 1
    name: str

    # Three oscillator slots to align with our generators
    osc: List[Osc] = Field(default_factory=lambda: [Osc(), Osc(), Osc()])

    mix: Mix = Mix()
    filter: Filter = Filter()
    env1: Envelope = Envelope()  # amplitude env
    env2: Envelope = Envelope()  # modulation env
    lfo1: LFO = LFO()
    fx: FX = FX()
    mod: Mod = Mod()
    meta: Meta = Meta()

    def to_dict(self) -> Dict[str, Any]:
        """Return a plain Python dict suitable for JSON serialization."""
        return self.model_dump(mode="python")


# ---- helpers ---------------------------------------------------------------


def coerce_patch(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and normalize an incoming dict, returning a clean dict.
    Raises pydantic.ValidationError on invalid inputs.
    """
    model = Patch.model_validate(data)
    return model.model_dump(mode="python")


def validate_patch(data: Dict[str, Any]) -> None:
    """
    Validate patch in-place; raises ValidationError if invalid.
    (Convenience wrapper for callers that only need to assert validity.)
    """
    Patch.model_validate(data)