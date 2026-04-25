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
#   --clean-only        Don't run anything — just rm -rf /tmp/shushu-tests/ and exit
#
# Extra args are passed through to pytest (e.g. -x, -k "pattern").
#
# pyproject.toml already pins --basetemp=/tmp/shushu-tests so EVERY tmp_path
# allocation is rooted there. Cleanup is a single rm -rf away.

set -euo pipefail

ROOT="/tmp/shushu-tests"
PARALLEL=""
COVERAGE=""
CI_MODE=""
QUIET=""
CLEAN=""
CLEAN_ONLY=""
EXTRA_ARGS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --parallel|-p)  PARALLEL=1; shift ;;
        --coverage|-c)  COVERAGE=1; shift ;;
        --ci)           CI_MODE=1; shift ;;
        --quick|-q)     QUIET=1; shift ;;
        --clean|-k)     CLEAN=1; shift ;;
        --clean-only)   CLEAN_ONLY=1; shift ;;
        --help|-h)
            sed -n '2,/^$/p' "$0" | sed 's/^# \?//'
            exit 0 ;;
        *)              EXTRA_ARGS+=("$1"); shift ;;
    esac
done

cleanup() {
    if [[ -d "$ROOT" ]]; then
        rm -rf "$ROOT"
        echo "[run-tests] cleaned $ROOT"
    fi
}

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
