massive_patch = {
    "oscillators": {
        "osc1": {
            "wave": "Sin-Tri",
            "mode": "Spectrum",
            "pitch": 24.00,
            "wt_position": 0.0,
            "intensity": 0.0,
            "amp": 1.0
        },
        "osc2": {
            "wave": "Sin-Tri",
            "mode": "Spectrum",
            "pitch": 31.00,
            "wt_position": 0.0,
            "intensity": 0.0,
            "amp": 1.0
        },
        "osc3": {
            "wave": "Squ-Swl",
            "mode": "Spectrum",
            "pitch": 0.0,
            "wt_position": 0.0,
            "intensity": 0.0,
            "amp": 1.0
        }
    },
    "modulation_osc": {
        "pitch": 0.0,
        "mod_modes": {
            "ring_mod": None,
            "phase": None,
            "position": None,
            "filter_fm": None
        }
    },
    "noise": {
        "type": "White",
        "color": 0.5,
        "amp": 0.5
    },
    "filters": {
        "filter1": {
            "type": "Lowpass4",
            "cutoff": 0.5,
            "resonance": 0.5
        },
        "filter2": {
            "type": "Highpass4",
            "cutoff": 0.5,
            "resonance": 0.5
        }
    },
    "fx": {
        "fx1": {
            "type": "Tube",
            "drywet": 0.5,
            "drive": 0.5
        },
        "fx2": {
            "type": "Reverb",
            "drywet": 0.5,
            "size": 0.5
        }
    },
    "envelopes": {
        "env1": {"attack": 0.01, "decay": 0.20, "sustain": 0.70, "release": 0.30},
        "env2": {"attack": 0.05, "decay": 0.25, "sustain": 0.60, "release": 0.40},
        "env3": {"attack": 0.10, "decay": 0.30, "sustain": 0.50, "release": 0.50},
        "env4": {"attack": 0.20, "decay": 0.35, "sustain": 0.40, "release": 0.60},
    },
    "lfos": {
        "lfo5": {"rate": 0.25, "curve": "sine", "amp": 1.0, "sync": True},
        "lfo6": {"rate": 0.50, "curve": "triangle", "amp": 0.8, "sync": True},
        "lfo7": {"rate": 0.75, "curve": "square", "amp": 0.6, "sync": False},
        "lfo8": {"rate": 1.00, "curve": "saw", "amp": 0.4, "sync": False},
    },
    "routing": {
        "filter_mix": 0.5,
        "amp_pan": 0.0
    },
    "macro_controls": {
        "1": "Delay",
        "2": "LPF",
        "3": "HPF",
        "4": "Res",
        "5": "Tube",
        "6": "Drive",
        "7": "Verb",
        "8": "Size"
    }
}