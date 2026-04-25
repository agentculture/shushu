#!/usr/bin/env bash
# Run shushu's pytest suite with optional parallelism, coverage, and
# tmp-artifact cleanup.
#
# Usage: bash test.sh [OPTIONS] [PYTEST_ARGS...]
#
# Options:
#   --parallel,    -p   Run with -n auto (pytest-xdist)
#   --coverage,    -c   Enable coverage reporting
#   --ci                Full CI mode: parallel + coverage + xml report + verbose
#   --quick,       -q   Quiet output, no coverage
#   --clean,       -k   Clean /tmp/shushu-tests/ AFTER the run, regardless of outcome
#                       (default: pytest's tmp_path_retention_policy=failed keeps the
#                        last 3 failed-test trees for inspection)
#   --clean-only        Don't run anything — just wipe /tmp/shushu-tests/ and exit
#   --clean-smoke NAME  Don't run anything — wipe /tmp/shushu-tests/smoke-NAME/ and exit.
#                       Spares manual `rm -rf` calls in shell smoke flows.
#   --smoke-home NAME   Don't run anything — print /tmp/shushu-tests/smoke-NAME and exit.
#                       Use as: SHUSHU_HOME="$(bash test.sh --smoke-home task22)" uv run shushu ...
#
# Extra args are passed through to pytest (e.g. -x, -k "pattern").
#
# pyproject.toml already pins --basetemp=/tmp/shushu-tests so EVERY tmp_path
# allocation is rooted there. Cleanup is one wrapper invocation away — never
# write a direct `rm -rf` against /tmp/shushu-tests/* from a shell.

set -euo pipefail

ROOT="/tmp/shushu-tests"
PARALLEL=""
COVERAGE=""
CI_MODE=""
QUIET=""
CLEAN=""
CLEAN_ONLY=""
CLEAN_SMOKE=""
SMOKE_HOME=""
EXTRA_ARGS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --parallel|-p)    PARALLEL=1; shift ;;
        --coverage|-c)    COVERAGE=1; shift ;;
        --ci)             CI_MODE=1; shift ;;
        --quick|-q)       QUIET=1; shift ;;
        --clean|-k)       CLEAN=1; shift ;;
        --clean-only)     CLEAN_ONLY=1; shift ;;
        --clean-smoke)
            if [[ $# -lt 2 || -z "${2-}" ]]; then
                echo "[run-tests] error: --clean-smoke requires a NAME argument" >&2
                exit 2
            fi
            CLEAN_SMOKE="$2"; shift 2 ;;
        --smoke-home)
            if [[ $# -lt 2 || -z "${2-}" ]]; then
                echo "[run-tests] error: --smoke-home requires a NAME argument" >&2
                exit 2
            fi
            SMOKE_HOME="$2"; shift 2 ;;
        --help|-h)
            sed -n '2,/^$/p' "$0" | sed 's/^# \?//'
            exit 0 ;;
        *)                EXTRA_ARGS+=("$1"); shift ;;
    esac
done

cleanup() {
    if [[ -d "$ROOT" ]]; then
        rm -rf "$ROOT"
        echo "[run-tests] cleaned $ROOT"
    fi
    return 0
}

clean_smoke_namespace() {
    local name="$1"
    # Defensive: refuse names that try to escape the smoke namespace.
    case "$name" in
        ""|*/*|..|.|*$'\n'*)
            echo "[run-tests] invalid smoke name: $name" >&2
            return 2 ;;
        *) ;;  # accepted name; fall through
    esac
    local target="$ROOT/smoke-$name"
    if [[ -d "$target" ]]; then
        rm -rf "$target"
        echo "[run-tests] cleaned $target"
    fi
    return 0
}

if [[ -n "$SMOKE_HOME" ]]; then
    case "$SMOKE_HOME" in
        ""|*/*|..|.|*$'\n'*)
            echo "[run-tests] invalid smoke name: $SMOKE_HOME" >&2
            exit 2 ;;
        *) ;;  # accepted name; fall through
    esac
    echo "$ROOT/smoke-$SMOKE_HOME"
    exit 0
fi

if [[ -n "$CLEAN_SMOKE" ]]; then
    clean_smoke_namespace "$CLEAN_SMOKE"
    exit 0
fi

if [[ -n "$CLEAN_ONLY" ]]; then
    cleanup
    exit 0
fi

# Pre-run: only clean if --clean was passed. Otherwise leave any
# pre-existing failed-test artifacts in place — pytest's retention
# policy will prune to the last 3 once the run starts.
if [[ -n "$CLEAN" ]]; then
    cleanup
fi

CMD=(uv run pytest)
if [[ -n "$CI_MODE" ]]; then
    CMD+=(-n auto --cov=shushu --cov-report=xml:coverage.xml --cov-report=term -v)
elif [[ -n "$QUIET" ]]; then
    CMD+=(-q)
    [[ -n "$PARALLEL" ]] && CMD+=(-n auto)
else
    [[ -n "$PARALLEL" ]] && CMD+=(-n auto)
    [[ -n "$COVERAGE" ]] && CMD+=(--cov=shushu --cov-report=term)
    CMD+=(-v)
fi
CMD+=("${EXTRA_ARGS[@]}")

echo "[run-tests] running: ${CMD[*]}"
set +e
"${CMD[@]}"
RC=$?
set -e

# Post-run: --clean wipes everything regardless of outcome.
# Without --clean, pytest already deleted passing-test artifacts; only
# the most recent failed runs remain, which is what you want for
# debugging. Don't touch them.
if [[ -n "$CLEAN" ]]; then
    cleanup
fi

exit "$RC"
