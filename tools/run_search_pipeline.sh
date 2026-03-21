#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1 && pwd)"
workdir=""
metadata_file=""

usage() {
  cat <<EOF
Usage: $0 --workdir <dir> [--metadata-file <file>]

Read topics from stdin, run the lexical searcher, and optionally apply
OpenAI-backed reranking before writing the final TREC run to stdout.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --workdir)
      workdir="$2"
      shift 2
      ;;
    --metadata-file)
      metadata_file="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf "Unknown argument: %s\n" "$1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -z "$workdir" ]]; then
  usage >&2
  exit 1
fi

workdir="$(cd "$workdir" >/dev/null 2>&1 && pwd)"
source "$repo_root/tools/load_env.sh"
key_source="$(load_repo_env_with_key_source "$repo_root")"
export JASSJR_OPENAI_KEY_SOURCE="$key_source"

topics_stdin_file="$(mktemp "$workdir/topics-stdin.XXXXXX.txt")"
raw_results_file="$(mktemp "$workdir/results-raw.XXXXXX.trec")"
trap 'rm -f "$topics_stdin_file" "$raw_results_file"' EXIT
cat > "$topics_stdin_file"

search_env=()
if [[ "${JASSJR_OPENAI_RERANK_MODE:-off}" != "off" ]]; then
  search_env+=("JASSJR_RERANK_DOCS=0")
fi

(
  cd "$workdir" || exit 1
  if [[ ${#search_env[@]} -gt 0 ]]; then
    env "${search_env[@]}" ./jassjr-search < "$topics_stdin_file" > "$raw_results_file"
  else
    ./jassjr-search < "$topics_stdin_file" > "$raw_results_file"
  fi
)

if [[ "${JASSJR_OPENAI_RERANK_MODE:-off}" == "off" ]]; then
  if [[ -n "$metadata_file" ]]; then
    cat > "$metadata_file" <<EOF
JASSJR_OPENAI_RERANK_MODE: off
JASSJR_OPENAI_KEY_SOURCE: $key_source
EOF
  fi
  cat "$raw_results_file"
  exit 0
fi

python_args=(
  "$repo_root/tools/openai_rerank.py"
  --repo-root "$repo_root"
  --workdir "$workdir"
  --topics-file "$topics_stdin_file"
  --run-file "$raw_results_file"
)
if [[ -n "$metadata_file" ]]; then
  python_args+=(--metadata-file "$metadata_file")
fi

python3 "${python_args[@]}"
