#!/usr/bin/env bash
# Compatibility entry point: evaluation now always freezes stage 1.
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1 && pwd)"
exec python3 "$repo_root/stage1/run.py" "$@"
