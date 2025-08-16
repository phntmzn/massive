

import pytest
from pydantic import ValidationError

from massive.validate import coerce_patch, validate_patch, json_schema


def test_minimal_patch_coerces_defaults():
    # Only name is required; everything else should be filled with defaults.
    data_in = {"name": "UnitTest"}
    data = coerce_patch(data_in)
    assert data["name"] == "UnitTest"
    # three oscillators with sane defaults
    assert "osc" in data and isinstance(data["osc"], list) and len(data["osc"]) == 3
    # filter block exists and is normalized to [0,1] bounds
    assert "filter" in data and 0.0 <= data["filter"]["cutoff"] <= 1.0
    # meta exists with expected keys
    assert "meta" in data and {"tags", "key", "tempo"} <= set(data["meta"].keys())


def test_reject_extra_root_key():
    bad = {"name": "X", "oops": 123}
    with pytest.raises(ValidationError):
        validate_patch(bad)


def test_bounds_enforced_filter_and_env():
    # cutoff > 1.0 should fail
    bad_cutoff = {"name": "Bad", "filter": {"cutoff": 1.5}}
    with pytest.raises(ValidationError):
        validate_patch(bad_cutoff)

    # negative release should fail
    bad_release = {"name": "Bad2", "env1": {"release": -0.1}}
    with pytest.raises(ValidationError):
        validate_patch(bad_release)


def test_nested_extra_keys_forbidden():
    # extra key inside env1 should raise
    bad = {"name": "Bad3", "env1": {"attack": 0.01, "weird": 123}}
    with pytest.raises(ValidationError):
        validate_patch(bad)


def test_string_numbers_are_coerced():
    # Strings that represent numbers should be coerced into floats
    ok = {
        "name": "Coerce",
        "filter": {"cutoff": "0.75", "res": "0.2", "drive": "0.0", "mix": "1.0"},
        "env1": {"attack": "0.02", "decay": "0.1", "sustain": "0.8", "release": "0.2"},
    }
    out = coerce_patch(ok)
    assert isinstance(out["filter"]["cutoff"], float)
    assert out["filter"]["cutoff"] == pytest.approx(0.75)
    assert out["env1"]["attack"] == pytest.approx(0.02)


def test_json_schema_contains_expected_fields():
    schema = json_schema()
    assert "properties" in schema
    props = schema["properties"]
    assert "name" in props
    assert "osc" in props
    assert "filter" in props