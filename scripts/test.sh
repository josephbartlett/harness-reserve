#!/usr/bin/env sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
export PYTHONPATH="$ROOT/src:$ROOT/tests${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONDONTWRITEBYTECODE=1
python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 20)'
python3 scripts/validate_scaffold.py
python3 -m unittest discover -s tests -v
