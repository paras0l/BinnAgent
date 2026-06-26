#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
    PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
  else
    PYTHON_BIN="python3"
  fi
fi

usage() {
  cat <<'USAGE'
Run deterministic learner simulations.

Usage:
  ./scripts/run_learner_simulation.sh
  ./scripts/run_learner_simulation.sh --persona grade7_low_vocab --scenario smoke_learning_journey
  ./scripts/run_learner_simulation.sh --test

Options are passed through to scripts/run_learner_simulation.py.
Set PYTHON_BIN=/path/to/python to override the interpreter.
USAGE
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ "${1:-}" == "--test" ]]; then
  exec "$PYTHON_BIN" -m pytest tests/simulation -q
fi

exec "$PYTHON_BIN" scripts/run_learner_simulation.py "$@"
