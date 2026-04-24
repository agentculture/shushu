from __future__ import annotations

import json
from datetime import date

import pytest

from shushu import store


@pytest.fixture(autouse=True)
def _tmp_store(monkeypatch, tmp_path):
    monkeypatch.setenv("SHUSHU_HOME", str(tmp_path / "shushu"))


def test_load_returns_empty_when_no_file():
    data = store.load()
    assert data.schema_version == 1
    assert data.secrets == []


def test_set_then_load_roundtrips():
    rec = store.set_secret(
        name="FOO",
        value="bar",
        hidden=False,
        source="localhost",
        purpose="test",
    )
    assert rec.name == "FOO"
    data = store.load()
    assert len(data.secrets) == 1
    assert data.secrets[0].name == "FOO"
    assert data.secrets[0].value == "bar"


def test_overwrite_silently_replaces_value():
    store.set_secret(name="FOO", value="v1", hidden=False, source="localhost", purpose="")
    store.set_secret(name="FOO", value="v2", hidden=False, source="localhost", purpose="")
    data = store.load()
    assert len(data.secrets) == 1
    assert data.secrets[0].value == "v2"


def test_overwrite_preserves_created_at_and_handed_over_by():
    first = store.set_secret(name="FOO", value="v1", hidden=False, source="localhost", purpose="")
    second = store.set_secret(name="FOO", value="v2", hidden=False, source="localhost", purpose="")
    assert first.created_at == second.created_at
    assert first.handed_over_by == second.handed_over_by


def test_set_rejects_invalid_name():
    with pytest.raises(store.ValidationError):
        store.set_secret(
            name="lowercase-bad",
            value="v",
            hidden=False,
            source="localhost",
            purpose="",
        )


def test_update_metadata_only():
    store.set_secret(name="FOO", value="v", hidden=False, source="localhost", purpose="orig")
    store.update_metadata(name="FOO", purpose="new")
    data = store.load()
    assert data.secrets[0].purpose == "new"
    assert data.secrets[0].value == "v"  # untouched


def test_update_metadata_rejects_immutable_fields():
    store.set_secret(name="FOO", value="v", hidden=False, source="localhost", purpose="")
    with pytest.raises(store.ValidationError):
        store.update_metadata(name="FOO", source="forbidden")  # type: ignore[arg-type]


def test_update_metadata_rejects_unknown_secret():
    with pytest.raises(store.NotFoundError):
        store.update_metadata(name="NOPE", purpose="x")


def test_get_value_raises_on_hidden():
    store.set_secret(name="SECRET", value="s", hidden=True, source="localhost", purpose="")
    with pytest.raises(store.HiddenError):
        store.get_value("SECRET")


def test_get_value_returns_visible():
    store.set_secret(name="VISIBLE", value="hello", hidden=False, source="localhost", purpose="")
    assert store.get_value("VISIBLE") == "hello"


def test_delete_removes_record():
    store.set_secret(name="FOO", value="v", hidden=False, source="localhost", purpose="")
    store.delete("FOO")
    assert store.load().secrets == []


def test_delete_missing_raises_not_found():
    with pytest.raises(store.NotFoundError):
        store.delete("NOPE")


def test_list_names_sorted():
    for n in ["BAZ", "FOO", "BAR"]:
        store.set_secret(name=n, value="v", hidden=False, source="localhost", purpose="")
    assert store.list_names() == ["BAR", "BAZ", "FOO"]


def test_schema_version_mismatch_raises():
    paths = store._paths()
    paths.dir.mkdir(parents=True, exist_ok=True)
    paths.file.write_text(json.dumps({"schema_version": 99, "secrets": []}))
    with pytest.raises(store.StateError) as exc:
        store.load()
    assert "schema_version" in str(exc.value)


def test_alert_at_parsed_and_stored():
    store.set_secret(
        name="FOO",
        value="v",
        hidden=False,
        source="localhost",
        purpose="",
        alert_at=date(2030, 1, 1),
    )
    rec = store.load().secrets[0]
    assert rec.alert_at == date(2030, 1, 1)


def test_set_secret_rejects_changing_source_on_overwrite():
    store.set_secret(name="FOO", value="v1", hidden=False, source="localhost", purpose="")
    with pytest.raises(store.ValidationError) as exc:
        store.set_secret(
            name="FOO", value="v2", hidden=False, source="https://elsewhere", purpose=""
        )
    assert "source is immutable" in str(exc.value)


def test_set_secret_rejects_changing_hidden_on_overwrite():
    store.set_secret(name="FOO", value="v1", hidden=False, source="localhost", purpose="")
    with pytest.raises(store.ValidationError) as exc:
        store.set_secret(name="FOO", value="v2", hidden=True, source="localhost", purpose="")
    assert "hidden is immutable" in str(exc.value)


def test_corrupt_json_raises_state_error():
    paths = store._paths()
    paths.dir.mkdir(parents=True, exist_ok=True)
    paths.file.write_text("{ this is not json")
    with pytest.raises(store.StateError) as exc:
        store.load()
    assert "JSON" in str(exc.value) or "json" in str(exc.value)


def test_schema_version_as_string_raises_state_error():
    paths = store._paths()
    paths.dir.mkdir(parents=True, exist_ok=True)
    paths.file.write_text(json.dumps({"schema_version": "1", "secrets": []}))
    with pytest.raises(store.StateError) as exc:
        store.load()
    assert "non-integer schema_version" in str(exc.value)


def test_set_secret_on_overwrite_with_empty_purpose_keeps_existing():
    """Documented falsy-merge: set_secret(purpose='') on overwrite keeps prior purpose."""
    store.set_secret(name="FOO", value="v1", hidden=False, source="localhost", purpose="orig")
    store.set_secret(name="FOO", value="v2", hidden=False, source="localhost", purpose="")
    rec = store.load().secrets[0]
    assert rec.purpose == "orig"


def test_update_metadata_empty_purpose_clears_existing():
    """update_metadata distinguishes None (leave alone) from "" (clear)."""
    store.set_secret(name="FOO", value="v", hidden=False, source="localhost", purpose="orig")
    store.update_metadata(name="FOO", purpose="")
    rec = store.load().secrets[0]
    assert rec.purpose == ""


def test_utf8_roundtrip():
    """Arbitrary UTF-8 in values must survive serialization (spec §4.3)."""
    store.set_secret(
        name="UNICODE", value="pa$$wörd-日本語-🔑", hidden=False, source="localhost", purpose=""
    )
    rec = store.load().secrets[0]
    assert rec.value == "pa$$wörd-日本語-🔑"
