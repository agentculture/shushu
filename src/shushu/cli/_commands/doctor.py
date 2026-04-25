"""`shushu doctor` — store / permission / schema integrity."""

from __future__ import annotations

import stat as stat_

from shushu import alerts, fs, store
from shushu.cli._errors import EXIT_STATE, EXIT_USER_ERROR, ShushuError
from shushu.cli._output import emit_result


def handle(args) -> int:
    json_mode = args.json
    # Admin variants (--user / --all-users) are wired in Task 26.
    if getattr(args, "user", None) or getattr(args, "all_users", False):
        raise ShushuError(
            EXIT_USER_ERROR,
            "doctor --user / --all-users not yet implemented",
            "coming in Task 26",
        )
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


def _run_self_checks():
    paths = fs.user_store_paths()
    checks = [_check_store_dir(paths)]
    data, file_checks, fatal = _check_secrets_file(paths)
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


def _check_secrets_file(paths):
    """Return (data, checks, fatal). `fatal=True` means stop further checks."""
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
        data = store.load()
    except store.StateError as exc:
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
