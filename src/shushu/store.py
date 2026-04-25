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
    hidden_raw = d["hidden"]
    if not isinstance(hidden_raw, bool):
        # Strict check: bool(non-bool) silently coerces (e.g. bool("false") is
        # True), which would defeat the schema-enforced contract for hand-edited
        # or corrupt stores. Reject anything that isn't an actual JSON bool.
        raise StateError(
            f"secret {d.get('name', '?')!r} has non-boolean hidden "
            f"(got {type(hidden_raw).__name__})"
        )
    return SecretRecord(
        name=d["name"],
        value=d["value"],
        hidden=hidden_raw,
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
    # Literal 'Z' in the format string matches the letter, not a tz
    # designator — we attach UTC via replace(). Leaving strict format
    # (no microseconds) per the design spec's seconds-precision wire
    # format; improve the error message so hand-edits don't produce a
    # cryptic strptime traceback.
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise ValueError(
            f"non-canonical datetime {s!r}; expected seconds precision "
            f"(`YYYY-MM-DDTHH:MM:SSZ`, e.g. '2026-04-24T12:00:00Z')"
        ) from exc


def _now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


# --- load / save ---------------------------------------------------------


def _paths() -> fs.StorePaths:
    return fs.user_store_paths()


def _load_raw_unlocked() -> StoreData:
    """Read + parse secrets.json without acquiring a lock.

    Caller must already hold either LOCK_SH (for read-only paths like
    public `load()`) or LOCK_EX (for read-mutate-write cycles inside the
    `set_secret` / `update_metadata` / `delete` functions). The
    `_unlocked` suffix means "this function does not acquire a lock
    itself", not "the file is unlocked when this runs".
    """
    paths = _paths()
    if not paths.file.exists():
        return StoreData(schema_version=SCHEMA_VERSION, secrets=[])
    try:
        raw = json.loads(paths.file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StateError(f"secrets.json is not valid JSON: {exc}")
    sv = raw.get("schema_version")
    if not isinstance(sv, int):
        raise StateError(
            f"secrets.json is missing or has non-integer schema_version "
            f"(got {sv!r}); file may be corrupt or hand-edited"
        )
    if sv != SCHEMA_VERSION:
        raise StateError(
            f"store schema_version={sv} but this binary supports {SCHEMA_VERSION}; "
            "upgrade shushu or file a migration issue"
        )
    secrets_raw = raw.get("secrets", [])
    if not isinstance(secrets_raw, list):
        raise StateError(
            f"secrets.json 'secrets' field must be a list (got {type(secrets_raw).__name__})"
        )
    try:
        secrets = [_json_to_record(d) for d in secrets_raw]
    except (KeyError, ValueError, TypeError) as exc:
        raise StateError(f"secrets.json contains malformed record: {exc}")
    return StoreData(schema_version=SCHEMA_VERSION, secrets=secrets)


def _save_unlocked(data: StoreData) -> None:
    """Write secrets.json atomically without acquiring a lock. Only safe
    to call from within a `locked_write()` context."""
    paths = _paths()
    payload = {
        "schema_version": data.schema_version,
        "secrets": [_record_to_json(r) for r in data.secrets],
    }
    fs.atomic_write_text(paths.file, json.dumps(payload, indent=2) + "\n")


def load() -> StoreData:
    """Public read path. Acquires shared lock; safe for concurrent readers.

    The existence check happens inside `_load_raw_unlocked()`, under the
    lock, to avoid a TOCTOU where a concurrent writer creates the file
    after we check `exists()` but before we read.
    """
    paths = _paths()
    with fs.locked_read(paths):
        return _load_raw_unlocked()


def _save(data: StoreData) -> None:
    """Public write path (currently unused — mutations use locked_write
    blocks directly so they can load + mutate + save under a single
    LOCK_EX). Kept for any future single-shot-write use case."""
    paths = _paths()
    with fs.locked_write(paths):
        _save_unlocked(data)


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
# These tuples are exported for CLI-layer consumers (Task 13+) to list
# mutable fields in `shushu explain` / `shushu doctor` output and enforce
# flag-level immutability checks before calling into the store. Not
# consumed inside this module.


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
    """Create or overwrite the named secret.

    Overwrite preserves immutables (`created_at`, `source`, `hidden`,
    `handed_over_by`). For mutable metadata (`purpose`, `rotation_howto`,
    `alert_at`), overwrite falls through falsy/None args to the existing
    record — passing `purpose=""` will NOT clear a prior non-empty
    purpose via this method. Use `update_metadata(purpose="")` when you
    need to explicitly clear a mutable field (None means "leave alone",
    "" means "set to empty").
    """
    _validate_name(name)
    paths = _paths()
    with fs.locked_write(paths):
        data = _load_raw_unlocked()
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
            if existing.source != source:
                raise ValidationError(
                    "source is immutable post-create; delete and re-create to change"
                )
            if existing.hidden != hidden:
                raise ValidationError(
                    "hidden is immutable post-create; delete and re-create to change"
                )
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
        _save_unlocked(StoreData(schema_version=SCHEMA_VERSION, secrets=new_secrets))
        return rec


def update_metadata(
    *,
    name: str,
    purpose: str | None = None,
    rotation_howto: str | None = None,
    alert_at: date | None = None,
    **forbidden: Any,
) -> SecretRecord:
    """Update only mutable metadata. Refuses attempts to touch immutables.

    Distinguishes `None` (leave field alone) from `""` (set to empty) for
    string fields. For `alert_at`, `None` also means "leave alone" —
    clearing once set is a v2 concern; use `delete` + re-create.
    """
    if forbidden:
        bad = next(iter(forbidden))
        raise ValidationError(
            f"{bad!r} is immutable post-create; " "delete and re-create to change it"
        )
    paths = _paths()
    with fs.locked_write(paths):
        data = _load_raw_unlocked()
        existing = _find(data, name)
        if existing is None:
            raise NotFoundError(f"no secret named {name}")
        rec = SecretRecord(
            name=existing.name,
            value=existing.value,
            hidden=existing.hidden,
            source=existing.source,
            purpose=purpose if purpose is not None else existing.purpose,
            rotation_howto=(
                rotation_howto if rotation_howto is not None else existing.rotation_howto
            ),
            alert_at=alert_at if alert_at is not None else existing.alert_at,
            handed_over_by=existing.handed_over_by,
            created_at=existing.created_at,
            updated_at=_now_utc(),
        )
        new_secrets = [r if r.name != name else rec for r in data.secrets]
        _save_unlocked(StoreData(schema_version=SCHEMA_VERSION, secrets=new_secrets))
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
    paths = _paths()
    with fs.locked_write(paths):
        data = _load_raw_unlocked()
        rec = _find(data, name)
        if rec is None:
            raise NotFoundError(f"no secret named {name}")
        new_secrets = [r for r in data.secrets if r.name != name]
        _save_unlocked(StoreData(schema_version=SCHEMA_VERSION, secrets=new_secrets))


def list_names() -> list[str]:
    return sorted(r.name for r in load().secrets)


def _find(data: StoreData, name: str) -> SecretRecord | None:
    for r in data.secrets:
        if r.name == name:
            return r
    return None
