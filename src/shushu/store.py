"""Per-user secrets store on disk. Single source of truth for secrets.json.

Responsibilities:
- Load/save JSON under the per-user store dir.
- Enforce schema_version and record-field validation.
- Enforce immutability: source / hidden / created_at / handed_over_by / name.
- Provide CRUD: set_secret, update_metadata, get_value, delete, list_names.
- Expose typed errors for the CLI layer to turn into ShushuError exit codes.

Does NOT know about sudo, argparse, or output formatting.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

from shushu import fs

SCHEMA_VERSION = 1
NAME_RE = re.compile(r"^[A-Z_][A-Z0-9_]{0,63}$")

# --- typed errors --------------------------------------------------------


class StoreError(Exception):
    """Base for store-level errors that the CLI translates to exit codes."""


class ValidationError(StoreError):
    """Input failed validation (bad name, bad date, immutable field)."""


class NotFoundError(StoreError):
    """Secret name not present in the store."""


class HiddenError(StoreError):
    """Attempt to read value of a hidden secret."""


class StateError(StoreError):
    """Store file corrupt / schema_version mismatch / unreadable."""


# --- dataclasses ---------------------------------------------------------


@dataclass(frozen=True)
class SecretRecord:
    name: str
    value: str
    hidden: bool
    source: str
    purpose: str
    rotation_howto: str
    alert_at: date | None
    handed_over_by: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class StoreData:
    schema_version: int
    secrets: list[SecretRecord] = field(default_factory=list)


# --- serialization -------------------------------------------------------


def _record_to_json(r: SecretRecord) -> dict[str, Any]:
    return {
        "name": r.name,
        "value": r.value,
        "hidden": r.hidden,
        "source": r.source,
        "purpose": r.purpose,
        "rotation_howto": r.rotation_howto,
        "alert_at": r.alert_at.isoformat() if r.alert_at else None,
        "handed_over_by": r.handed_over_by,
        "created_at": _dt_to_str(r.created_at),
        "updated_at": _dt_to_str(r.updated_at),
    }


def _json_to_record(d: dict[str, Any]) -> SecretRecord:
    return SecretRecord(
        name=d["name"],
        value=d["value"],
        hidden=bool(d["hidden"]),
        source=d["source"],
        purpose=d.get("purpose", ""),
        rotation_howto=d.get("rotation_howto", ""),
        alert_at=date.fromisoformat(d["alert_at"]) if d.get("alert_at") else None,
        handed_over_by=d.get("handed_over_by"),
        created_at=_str_to_dt(d["created_at"]),
        updated_at=_str_to_dt(d["updated_at"]),
    )


def _dt_to_str(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _str_to_dt(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


# --- load / save ---------------------------------------------------------


def _paths() -> fs.StorePaths:
    return fs.user_store_paths()


def load() -> StoreData:
    paths = _paths()
    if not paths.file.exists():
        return StoreData(schema_version=SCHEMA_VERSION, secrets=[])
    try:
        with fs.locked_read(paths):
            raw = json.loads(paths.file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StateError(f"secrets.json is not valid JSON: {exc}")
    sv = raw.get("schema_version")
    if sv != SCHEMA_VERSION:
        raise StateError(f"store schema_version={sv} but this binary supports {SCHEMA_VERSION}")
    try:
        secrets = [_json_to_record(d) for d in raw.get("secrets", [])]
    except (KeyError, ValueError) as exc:
        raise StateError(f"secrets.json contains malformed record: {exc}")
    return StoreData(schema_version=SCHEMA_VERSION, secrets=secrets)


def _save(data: StoreData) -> None:
    paths = _paths()
    with fs.locked_write(paths):
        payload = {
            "schema_version": data.schema_version,
            "secrets": [_record_to_json(r) for r in data.secrets],
        }
        fs.atomic_write_text(paths.file, json.dumps(payload, indent=2) + "\n")


# --- validation ----------------------------------------------------------


def _validate_name(name: str) -> None:
    if not NAME_RE.match(name):
        raise ValidationError(
            f"invalid name {name!r}; must match {NAME_RE.pattern} "
            "(uppercase + underscore + digits, starts with letter/_, ≤64 chars)"
        )


# --- mutations -----------------------------------------------------------

IMMUTABLE_FIELDS = ("source", "hidden", "created_at", "handed_over_by", "name")
MUTABLE_META_FIELDS = ("purpose", "rotation_howto", "alert_at")


def set_secret(
    *,
    name: str,
    value: str,
    hidden: bool,
    source: str,
    purpose: str,
    rotation_howto: str = "",
    alert_at: date | None = None,
    handed_over_by: str | None = None,
) -> SecretRecord:
    """Create or overwrite the named secret. Overwrite preserves
    created_at, source, hidden, handed_over_by (all immutable)."""
    _validate_name(name)
    data = load()
    existing = _find(data, name)
    now = _now_utc()
    if existing is None:
        rec = SecretRecord(
            name=name,
            value=value,
            hidden=hidden,
            source=source,
            purpose=purpose,
            rotation_howto=rotation_howto,
            alert_at=alert_at,
            handed_over_by=handed_over_by,
            created_at=now,
            updated_at=now,
        )
        new_secrets = [*data.secrets, rec]
    else:
        # Overwrite: value changes; immutables stay; mutables may change
        # if the caller passed new ones. For v1, set_secret-with-value
        # preserves all metadata unless new flags were explicitly given.
        # The CLI layer is responsible for not passing new source/hidden
        # on overwrite; store enforces the invariant via update_metadata.
        if existing.source != source:
            raise ValidationError("source is immutable post-create; delete and re-create to change")
        if existing.hidden != hidden:
            raise ValidationError("hidden is immutable post-create; delete and re-create to change")
        rec = SecretRecord(
            name=existing.name,
            value=value,
            hidden=existing.hidden,
            source=existing.source,
            purpose=purpose or existing.purpose,
            rotation_howto=rotation_howto or existing.rotation_howto,
            alert_at=alert_at if alert_at is not None else existing.alert_at,
            handed_over_by=existing.handed_over_by,
            created_at=existing.created_at,
            updated_at=now,
        )
        new_secrets = [r if r.name != name else rec for r in data.secrets]
    _save(StoreData(schema_version=SCHEMA_VERSION, secrets=new_secrets))
    return rec


def update_metadata(
    *,
    name: str,
    purpose: str | None = None,
    rotation_howto: str | None = None,
    alert_at: date | None = None,
    **forbidden: Any,
) -> SecretRecord:
    """Update only mutable metadata. Refuses attempts to touch immutables."""
    if forbidden:
        bad = next(iter(forbidden))
        raise ValidationError(
            f"{bad!r} is immutable post-create; " "delete and re-create to change it"
        )
    data = load()
    existing = _find(data, name)
    if existing is None:
        raise NotFoundError(f"no secret named {name}")
    rec = SecretRecord(
        name=existing.name,
        value=existing.value,
        hidden=existing.hidden,
        source=existing.source,
        purpose=purpose if purpose is not None else existing.purpose,
        rotation_howto=(rotation_howto if rotation_howto is not None else existing.rotation_howto),
        alert_at=alert_at if alert_at is not None else existing.alert_at,
        handed_over_by=existing.handed_over_by,
        created_at=existing.created_at,
        updated_at=_now_utc(),
    )
    new_secrets = [r if r.name != name else rec for r in data.secrets]
    _save(StoreData(schema_version=SCHEMA_VERSION, secrets=new_secrets))
    return rec


def get_value(name: str) -> str:
    data = load()
    rec = _find(data, name)
    if rec is None:
        raise NotFoundError(f"no secret named {name}")
    if rec.hidden:
        raise HiddenError(
            f"{name} is a hidden secret; use `shushu run --inject VAR={name} -- <cmd>`"
        )
    return rec.value


def get_record(name: str) -> SecretRecord:
    data = load()
    rec = _find(data, name)
    if rec is None:
        raise NotFoundError(f"no secret named {name}")
    return rec


def delete(name: str) -> None:
    data = load()
    rec = _find(data, name)
    if rec is None:
        raise NotFoundError(f"no secret named {name}")
    new_secrets = [r for r in data.secrets if r.name != name]
    _save(StoreData(schema_version=SCHEMA_VERSION, secrets=new_secrets))


def list_names() -> list[str]:
    return sorted(r.name for r in load().secrets)


def _find(data: StoreData, name: str) -> SecretRecord | None:
    for r in data.secrets:
        if r.name == name:
            return r
    return None
