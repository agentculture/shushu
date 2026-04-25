"""`shushu doctor` — store / permission / schema integrity."""

from __future__ import annotations

import stat as stat_

from shushu import alerts, fs, store
from shushu.cli._errors import EXIT_STATE
from shushu.cli._output import emit_result


def handle(args) -> int:
    json_mode = args.json
    if getattr(args, "all_users", False):
        return _handle_all_users(args)
    if getattr(args, "user", None):
        return _handle_admin_user(args)
    report = _run_self_checks()
    payload = {"checks": report, "summary": _summarize(report)}
    if json_mode:
        emit_result(payload, json_mode=True)
    else:
        for c in report:
            print(f"[{c['status']}] {c['name']}: {c['detail']}")
        s = payload["summary"]
        print(f"pass={s['pass']} warn={s['warn']} fail={s['fail']}")
    return 0 if payload["summary"]["fail"] == 0 else EXIT_STATE


def _handle_all_users(args) -> int:
    from shushu import admin

    json_mode = args.json

    def _row(info):
        paths = admin.store_paths_for(info)
        report = _run_checks_for_paths(paths)
        summary = _summarize(report)
        return {"user": info.name, "checks": report, "summary": summary}

    rows = admin.for_each_user(_row)
    if json_mode:
        emit_result({"users": rows}, json_mode=True)
    else:
        any_fail = False
        for row in rows:
            print(f"# {row['user']}")
            for c in row["checks"]:
                print(f"  [{c['status']}] {c['name']}: {c['detail']}")
            s = row["summary"]
            print(f"  pass={s['pass']} warn={s['warn']} fail={s['fail']}")
            if s["fail"] > 0:
                any_fail = True
    return 0 if not any_fail else EXIT_STATE


def _handle_admin_user(args) -> int:
    import os as _os

    from shushu import admin

    json_mode = args.json

    def _child() -> int:
        _os.environ.pop("SHUSHU_HOME", None)
        report = _run_self_checks()
        payload = {"checks": report, "summary": _summarize(report)}
        if json_mode:
            emit_result(payload, json_mode=True)
        else:
            for c in report:
                print(f"[{c['status']}] {c['name']}: {c['detail']}")
            s = payload["summary"]
            print(f"pass={s['pass']} warn={s['warn']} fail={s['fail']}")
        return 0 if payload["summary"]["fail"] == 0 else EXIT_STATE

    return admin.as_user(args.user, _child)


def _run_self_checks():
    paths = fs.user_store_paths()
    return _run_checks_for_paths(paths)


def _run_checks_for_paths(paths):
    """Run all store checks against the given StorePaths. Root-readable."""
    checks = [_check_store_dir(paths)]
    data, file_checks, fatal = _check_secrets_file_at(paths)
    checks.extend(file_checks)
    if fatal:
        return checks
    for record in data.secrets:
        checks.extend(_check_record(record))
    return checks


def _check_store_dir(paths):
    if not paths.dir.exists():
        return {"name": "store_dir", "status": "PASS", "detail": "no store yet (lazy init)"}
    try:
        mode = stat_.S_IMODE(paths.dir.stat().st_mode)
    except OSError as exc:
        return {
            "name": "store_dir",
            "status": "FAIL",
            "detail": f"could not stat {paths.dir}: {exc}",
        }
    if mode != 0o700:
        return {
            "name": "store_dir_mode",
            "status": "WARN",
            "detail": f"{paths.dir} mode {oct(mode)}; expected 0o700",
        }
    return {"name": "store_dir", "status": "PASS", "detail": str(paths.dir)}


def _check_secrets_file_at(paths):
    """Return (data, checks, fatal). `fatal=True` means stop further checks.

    Reads `paths.file` directly so root can inspect any user's store without
    forking. Uses `store.load()` for self-mode (correct lock path), and
    direct JSON parsing for foreign-user paths (root reads files directly).
    """
    import json as _json

    if not paths.file.exists():
        empty = store.StoreData(schema_version=store.SCHEMA_VERSION, secrets=[])
        return empty, [{"name": "schema_version", "status": "PASS", "detail": "empty store"}], False
    checks = []
    try:
        mode = stat_.S_IMODE(paths.file.stat().st_mode)
    except OSError as exc:
        checks.append(
            {
                "name": "secrets_file_mode",
                "status": "FAIL",
                "detail": f"could not stat {paths.file}: {exc}",
            }
        )
        return None, checks, True
    if mode == 0o600:
        checks.append(
            {"name": "secrets_file_mode", "status": "PASS", "detail": f"{paths.file} mode 0o600"}
        )
    else:
        checks.append(
            {
                "name": "secrets_file_mode",
                "status": "WARN",
                "detail": f"{paths.file} mode {oct(mode)}; expected 0o600",
            }
        )
    try:
        raw = _json.loads(paths.file.read_text(encoding="utf-8"))
        sv = raw.get("schema_version")
        if not isinstance(sv, int):
            raise store.StateError(
                f"secrets.json is missing or has non-integer schema_version (got {sv!r})"
            )
        if sv != store.SCHEMA_VERSION:
            raise store.StateError(
                f"store schema_version={sv} but this binary supports {store.SCHEMA_VERSION}"
            )
        secrets_raw = raw.get("secrets", [])
        if not isinstance(secrets_raw, list):
            raise store.StateError(
                f"secrets.json 'secrets' field must be a list (got {type(secrets_raw).__name__})"
            )
        data = _parse_store_data(raw)
    except (store.StateError, ValueError, KeyError, TypeError) as exc:
        checks.append({"name": "schema_version", "status": "FAIL", "detail": str(exc)})
        return None, checks, True
    except OSError as exc:
        checks.append(
            {
                "name": "schema_version",
                "status": "FAIL",
                "detail": f"could not read {paths.file}: {exc}",
            }
        )
        return None, checks, True
    checks.append({"name": "schema_version", "status": "PASS", "detail": f"v{data.schema_version}"})
    return data, checks, False


def _parse_store_data(raw: dict) -> store.StoreData:
    """Parse a JSON dict into StoreData without going through store.load().

    Lets root read any user's secrets.json directly (no fork, no lock) for
    the --all-users doctor path.
    """
    from shushu.store import _json_to_record  # type: ignore[attr-defined]

    secrets = [_json_to_record(d) for d in raw.get("secrets", [])]
    return store.StoreData(schema_version=store.SCHEMA_VERSION, secrets=secrets)


def _check_record(record):
    out = []
    if not record.purpose:
        out.append(
            {
                "name": "purpose",
                "status": "WARN",
                "detail": (
                    f"{record.name} has empty purpose;"
                    f" consider `shushu set {record.name} --purpose '...'`"
                ),
            }
        )
    if not record.rotation_howto:
        out.append(
            {
                "name": "rotation_howto",
                "status": "WARN",
                "detail": (
                    f"{record.name} has empty rotation_howto;"
                    f" consider `shushu set {record.name} --rotate-howto '...'`"
                ),
            }
        )
    state = alerts.classify(record.alert_at)
    if state == "expired":
        out.append(
            {
                "name": "alert_at",
                "status": "WARN",
                "detail": f"{record.name} alert_at={record.alert_at} is expired",
            }
        )
    elif state == "alerting":
        out.append(
            {
                "name": "alert_at",
                "status": "WARN",
                "detail": f"{record.name} alert_at={record.alert_at} is within 30 days",
            }
        )
    return out


def _summarize(checks):
    return {
        "pass": sum(1 for c in checks if c["status"] == "PASS"),
        "warn": sum(1 for c in checks if c["status"] == "WARN"),
        "fail": sum(1 for c in checks if c["status"] == "FAIL"),
    }
