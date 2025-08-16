

from pathlib import Path
import pytest

from massive import midi as midi_mod


# ------------------------------ fakes ---------------------------------


class FakeMessage:
    def __init__(self, type: str, **kwargs):
        self.type = type
        self.kw = dict(kwargs)


class FakePort:
    def __init__(self, name: str, parent: "FakeMido"):
        self.name = name
        self.parent = parent

    def __enter__(self):
        self.parent.last_opened = self.name
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def send(self, msg):
        # Record the tuple (port_name, msg)
        self.parent.sent.append((self.name, msg))


class FakeMido:
    def __init__(self, names=None):
        self._names = list(names or [])
        self.sent = []
        self.last_opened = None

    # Behave like mido module functions/classes
    def get_output_names(self):
        return list(self._names)

    def open_output(self, name: str):
        return FakePort(name, self)

    def Message(self, *args, **kwargs):  # noqa: N802
        return FakeMessage(*args, **kwargs)


@pytest.fixture()
def fake_mido(monkeypatch):
    # Patch the midi module's `mido` reference with our fake
    fake = FakeMido(names=["IAC Driver Bus 1", "Massive", "Some Virtual Port"])
    monkeypatch.setattr(midi_mod, "mido", fake, raising=False)
    return fake


# ------------------------------ tests ---------------------------------


def test_port_listing_and_resolution(fake_mido):
    names = midi_mod.list_output_ports()
    assert "IAC Driver Bus 1" in names
    assert "Massive" in names

    # exact
    assert midi_mod.find_output_port("Massive") == "Massive"
    # case-insensitive exact
    assert midi_mod.find_output_port("massive") == "Massive"
    # substring
    assert midi_mod.find_output_port("Virtual") == "Some Virtual Port"
    # default guess prefers IAC
    assert midi_mod.default_output_port_guess() == "IAC Driver Bus 1"


def test_send_cc_and_batch(fake_mido):
    port = "IAC Driver Bus 1"

    # Single CC
    midi_mod.send_cc(74, 127, port_name=port, channel=1)
    assert len(fake_mido.sent) == 1
    p, msg = fake_mido.sent[-1]
    assert p == port
    assert msg.type == "control_change"
    assert msg.kw["control"] == 74
    assert msg.kw["value"] == 127
    assert msg.kw["channel"] == 1

    # Batch
    fake_mido.sent.clear()
    midi_mod.send_cc_batch([(1, -1), (2, 200)], port_name=port, channel=2, inter_message_ms=0)
    assert len(fake_mido.sent) == 2
    # values are clamped 0..127
    assert fake_mido.sent[0][1].kw["control"] == 1 and fake_mido.sent[0][1].kw["value"] == 0
    assert fake_mido.sent[1][1].kw["control"] == 2 and fake_mido.sent[1][1].kw["value"] == 127
    assert all(s[1].kw["channel"] == 2 for s in fake_mido.sent)


def test_load_cc_assignments_option_a_and_send_macros(tmp_path: Path, fake_mido):
    # Create YAML with simple cc array 21..28
    yaml_text = "cc: [21, 22, 23, 24, 25, 26, 27, 28]\n"
    cfg = tmp_path / "macro_map.yaml"
    cfg.write_text(yaml_text, encoding="utf-8")

    # load
    cc_map = midi_mod.load_cc_assignments(cfg)
    assert cc_map == [21, 22, 23, 24, 25, 26, 27, 28]

    # send macros with mapping
    vals = [0, 64, 127, 5, 6, 7, 8, 9]
    fake_mido.sent.clear()
    midi_mod.send_macros(vals, port_name="Massive", cc_map=cc_map, inter_message_ms=0)
    assert len(fake_mido.sent) == 8
    for i, (_, msg) in enumerate(fake_mido.sent):
        assert msg.kw["control"] == cc_map[i]
        # values are clamped 0..127 and integers
        assert 0 <= msg.kw["value"] <= 127
        assert isinstance(msg.kw["value"], int)


def test_load_cc_assignments_option_b_with_fill_defaults(tmp_path: Path, fake_mido):
    # Provide per-macro list with some missing -> fill defaults
    yaml_text = """
macros:
  - idx: 0
    cc: 10
  - idx: 3
    cc: 40
  - idx: 8      # invalid index; ignored (filled by defaults)
    cc: 99
"""
    cfg = tmp_path / "macro_map.yaml"
    cfg.write_text(yaml_text, encoding="utf-8")

    cc_map = midi_mod.load_cc_assignments(cfg)
    # slot 0 (macro 1) set to 10, slot 3 (macro 4) set to 40, others default to 1..8
    assert cc_map[0] == 10
    assert cc_map[3] == 40
    # ensure length and defaults
    assert len(cc_map) == 8
    for i in range(8):
        if i not in (0, 3):
            assert cc_map[i] == i + 1