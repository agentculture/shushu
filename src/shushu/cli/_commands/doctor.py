"""`shushu doctor` — store / permission / schema integrity."""

from __future__ import annotations

import stat as stat_

from shushu import alerts, fs, store
from shushu.cli._errors import EXIT_STATE, ShushuError
from shushu.cli._output import emit_result


def handle(args) -> int:
    json_mode = args.json
    # Admin variants (--user / --all-users) are wired in Task 26.
    if getattr(args, "user", None) or getattr(args, "all_users", False):
        raise ShushuError(
            66,
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
    checks = []

    # 1. store dir
    if not paths.dir.exists():
        checks.append({"name": "store_dir", "status": "PASS", "detail": "no store yet (lazy init)"})
    else:
        mode = stat_.S_IMODE(paths.dir.stat().st_mode)
        if mode != 0o700:
            checks.append(
                {
                    "name": "store_dir_mode",
                    "status": "WARN",
                    "detail": f"{paths.dir} mode {oct(mode)}; expected 0o700",
                }
            )
        else:
            checks.append({"name": "store_dir", "status": "PASS", "detail": str(paths.dir)})

    # 2. file + schema
    if paths.file.exists():
        mode = stat_.S_IMODE(paths.file.stat().st_mode)
        if mode != 0o600:
            checks.append(
                {
                    "name": "secrets_file_mode",
                    "status": "WARN",
                    "detail": f"{paths.file} mode {oct(mode)}; expected 0o600",
                }
            )
        try:
            data = store.load()
            checks.append(
                {"name": "schema_version", "status": "PASS", "detail": f"v{data.schema_version}"}
            )
        except store.StateError as exc:
            checks.append({"name": "schema_version", "status": "FAIL", "detail": str(exc)})
            return checks
    else:
        data = store.StoreData(schema_version=1, secrets=[])
        checks.append({"name": "schema_version", "status": "PASS", "detail": "empty store"})

    # 3. per-record checks
    for r in data.secrets:
        if not r.purpose:
            detail = f"{r.name} has empty purpose; consider `shushu set {r.name} --purpose '...'`"
            checks.append({"name": "purpose", "status": "WARN", "detail": detail})
        if not r.rotation_howto:
            detail = (
                f"{r.name} has empty rotation_howto;"
                f" consider `shushu set {r.name} --rotate-howto '...'`"
            )
            checks.append({"name": "rotation_howto", "status": "WARN", "detail": detail})
        state = alerts.classify(r.alert_at)
        if state == "expired":
            checks.append(
                {
                    "name": "alert_at",
                    "status": "WARN",
                    "detail": f"{r.name} alert_at={r.alert_at} is expired",
                }
            )
        elif state == "alerting":
            checks.append(
                {
                    "name": "alert_at",
                    "status": "WARN",
                    "detail": f"{r.name} alert_at={r.alert_at} is within 30 days",
                }
            )
    return checks


def _summarize(checks):
    return {
        "pass": sum(1 for c in checks if c["status"] == "PASS"),
        "warn": sum(1 for c in checks if c["status"] == "WARN"),
        "fail": sum(1 for c in checks if c["status"] == "FAIL"),
    }
