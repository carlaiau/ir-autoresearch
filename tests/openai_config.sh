#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1 && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

cat > "$tmpdir/.env" <<'EOF'
OPENAI_API_KEY=dotenv-value
JASSJR_OPENAI_RERANK_MODE=mono
EOF

unset OPENAI_API_KEY || true
unset JASSJR_OPENAI_RERANK_MODE || true
unset JASSJR_OPENAI_DUO_MODEL || true

source "$repo_root/tools/load_env.sh"
load_repo_env "$tmpdir"
[[ "${OPENAI_API_KEY:-}" == "dotenv-value" ]] || {
  printf "Expected load_repo_env to populate OPENAI_API_KEY from .env\n" >&2
  exit 1
}
[[ "${JASSJR_OPENAI_RERANK_MODE:-}" == "mono" ]] || {
  printf "Expected load_repo_env to populate JASSJR_OPENAI_RERANK_MODE from .env\n" >&2
  exit 1
}

export OPENAI_API_KEY="env-value"
export JASSJR_OPENAI_RERANK_MODE="mono"
config_output="$(python3 "$repo_root/tools/openai_rerank.py" --repo-root "$tmpdir" --check-config)"
grep -Fq "JASSJR_OPENAI_KEY_SOURCE: env" <<<"$config_output" || {
  printf "Expected exported OPENAI_API_KEY to win over .env\n" >&2
  exit 1
}

cat > "$tmpdir/.env" <<'EOF'
OPENAI_API_KEY=dotenv-other
JASSJR_OPENAI_RERANK_MODE=mono_duo
JASSJR_OPENAI_DUO_MODEL=gpt-5.1
EOF

unset JASSJR_OPENAI_RERANK_MODE || true
unset JASSJR_OPENAI_DUO_MODEL || true
if python3 "$repo_root/tools/openai_rerank.py" --repo-root "$tmpdir" --check-config >/dev/null 2>&1; then
  printf "Expected duo config with gpt-5.1 to be rejected\n" >&2
  exit 1
fi

rm -f "$tmpdir/.env"
unset OPENAI_API_KEY || true
unset JASSJR_OPENAI_RERANK_MODE || true
unset JASSJR_OPENAI_DUO_MODEL || true

export JASSJR_OPENAI_RERANK_MODE="mono"
if python3 "$repo_root/tools/openai_rerank.py" --repo-root "$tmpdir" --check-config >/dev/null 2>&1; then
  printf "Expected missing OPENAI_API_KEY to fail for enabled rerank mode\n" >&2
  exit 1
fi
unset JASSJR_OPENAI_RERANK_MODE || true

printf "OpenAI config checks passed\n"
