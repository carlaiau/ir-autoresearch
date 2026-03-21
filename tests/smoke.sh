#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1 && pwd)"

"$repo_root/tools/smoke_eval.sh" "$@"
"$repo_root/tests/openai_config.sh"
