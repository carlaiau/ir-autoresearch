#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1 && pwd)"

if ! command -v python3 >/dev/null 2>&1; then
  printf "python3 is required but was not found on PATH\n" >&2
  exit 1
fi

python3 "$repo_root/tools/export_branch_comparisons.py"
