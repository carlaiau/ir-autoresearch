#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1 && pwd)"
printf "Deprecated: use ./tools/compare_branch_to_main.sh instead.\n" >&2
exec "$repo_root/tools/compare_branch_to_main.sh" "$@"
