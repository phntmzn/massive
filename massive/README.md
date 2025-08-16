

# Massive Automator

Batch-generate **Massive-style presets**, validate JSON patch files, and push MIDI macros to control your synth.

## Features

- 🎹 Define patch templates in JSON (oscillators, filters, envelopes, LFOs, FX, global)
- 🎲 Randomize musically constrained leads, basses, pads, and plucks
- 🎛 Map to 8 macros via `configs/macro_map.yaml`
- 📤 Export batches of presets with `configs/generators.yaml`
- 🎚 Send macro/CC data live to Massive via IAC bus (macOS) or any MIDI port
- ✅ Validate patches against schema before sending

## Installation

```bash
git clone https://github.com/yourname/massive-automator
cd massive-automator
make install
```

This sets up a `.venv` with all dependencies installed.

## Usage

Run the CLI with:

```bash
massive --help
```

### Example commands

List MIDI ports:

```bash
massive list-ports
```

Generate 50 bass presets:

```bash
massive generate configs/generators.yaml --type bass --count 50
```

Send macro values from a patch:

```bash
massive send-macros presets/template_bass.json
```

Validate a patch JSON:

```bash
massive validate-patch presets/template_lead.json
```

## Project Layout

```
massive-automator/
├─ pyproject.toml
├─ README.md
├─ .gitignore
├─ Makefile
├─ configs/
│  ├─ macro_map.yaml
│  └─ generators.yaml
├─ presets/
│  ├─ template_lead.json
│  ├─ template_bass.json
│  └─ exported/
├─ scripts/
│  └─ setup_iac_macos.sh
├─ src/
│  └─ massive_automator/
│     ├─ schema.py
│     ├─ randomizers.py
│     ├─ validate.py
│     ├─ midi.py
│     ├─ macros.py
│     ├─ io_json.py
│     └─ cli.py
└─ tests/
```

## Development

- Run tests with `make test`
- Lint and type-check with `make lint`

Contributions welcome!