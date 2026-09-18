#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
"${PYTHON:-$root/.venv-monobert/bin/python}" "$root/tests/msmarco.py"
