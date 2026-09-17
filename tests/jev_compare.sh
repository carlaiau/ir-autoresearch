#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
"${JEV_PYTHON:-.venv-monobert/bin/python}" tests/jev_compare.py
