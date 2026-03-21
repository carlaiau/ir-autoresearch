#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1 && pwd)"
source "$repo_root/tools/load_env.sh"
key_source="$(load_repo_env_with_key_source "$repo_root")"
export JASSJR_OPENAI_KEY_SOURCE="$key_source"
branch_name="$(git -C "$repo_root" branch --show-current 2>/dev/null || true)"
branch_name="${branch_name:-detached-head}"

if [[ "$branch_name" == "original" ]]; then
  printf "Refusing to write benchmark artifacts for branch 'original'. The original artifact folders are read-only initialization archives.\n" >&2
  exit 1
fi

iters=5
topics_file="$repo_root/51-100.titles.txt"
smoke_topics_file="$repo_root/tests/fixtures/smoke_topics.txt"
workdir="$repo_root/wsj-benchmark/$branch_name"
output_dir="$repo_root/experiment_benchmarks/$branch_name"

usage() {
  cat <<EOF
Usage: $0 [-n iterations] [-t topics.txt] [-w workdir] <wsj-dir-or-file>

Run a small set of indexing/search benchmarks and write a timestamped report.
Artifacts are grouped by the current git branch:
  $branch_name

Options:
  -n <num>   Number of timed iterations per benchmark.
             Default: $iters
  -t <file>  Topics file for the main search benchmark.
             Default: $topics_file
  -w <dir>   Working directory for merged input, binaries, and index files.
             Default: $workdir
  -h         Show this help text.
EOF
}

emit_env_setting() {
  local name="$1"
  if [[ -n "${!name:-}" ]]; then
    printf "%s: %s\n" "$name" "${!name}"
  fi
}

emit_metadata_file() {
  local file="$1"
  [[ -f "$file" ]] || return 0
  cat "$file"
}

while getopts ":n:t:w:h" opt; do
  case "$opt" in
    n)
      iters="$OPTARG"
      ;;
    t)
      topics_file="$OPTARG"
      ;;
    w)
      workdir="$OPTARG"
      ;;
    h)
      usage
      exit 0
      ;;
    :)
      printf "Missing value for -%s\n\n" "$OPTARG" >&2
      usage >&2
      exit 1
      ;;
    \?)
      printf "Unknown option: -%s\n\n" "$OPTARG" >&2
      usage >&2
      exit 1
      ;;
  esac
done
shift "$((OPTIND - 1))"

if [[ $# -ne 1 ]]; then
  usage >&2
  exit 1
fi

input_path="$1"

if [[ ! -e "$input_path" ]]; then
  printf "Input path does not exist: %s\n" "$input_path" >&2
  exit 1
fi

if [[ ! -f "$topics_file" ]]; then
  printf "Topics file does not exist: %s\n" "$topics_file" >&2
  exit 1
fi

if [[ ! -f "$smoke_topics_file" ]]; then
  printf "Smoke topics file does not exist: %s\n" "$smoke_topics_file" >&2
  exit 1
fi

if ! command -v go >/dev/null 2>&1; then
  printf "go is required but was not found on PATH\n" >&2
  exit 1
fi

mkdir -p "$workdir"
mkdir -p "$output_dir"

workdir="$(cd "$workdir" >/dev/null 2>&1 && pwd)"
output_dir="$(cd "$output_dir" >/dev/null 2>&1 && pwd)"
topics_file="$(cd "$(dirname "$topics_file")" >/dev/null 2>&1 && pwd)/$(basename "$topics_file")"
smoke_topics_file="$(cd "$(dirname "$smoke_topics_file")" >/dev/null 2>&1 && pwd)/$(basename "$smoke_topics_file")"

if [[ "$input_path" != /* ]]; then
  input_path="$PWD/$input_path"
fi

merged_input="$workdir/wsj_all.xml"
index_bin="$workdir/jassjr-index"
search_bin="$workdir/jassjr-search"
timestamp="$(date '+%Y%m%d-%H%M%S')"
output_file="$output_dir/benchmark-$timestamp.txt"
smoke_metadata_file="$workdir/rerank-smoke-$timestamp.txt"
topics_metadata_file="$workdir/rerank-topics-$timestamp.txt"

if [[ -d "$input_path" ]]; then
  printf "Merging WSJ files from %s\n" "$input_path"
  find "$input_path" -type f | LC_ALL=C sort | while IFS= read -r file; do
    cat "$file"
    printf '\n'
  done > "$merged_input"
  collection_file="$merged_input"
else
  collection_file="$input_path"
fi

printf "Building Go binaries in %s\n" "$workdir"
go build -o "$index_bin" "$repo_root/index/JASSjr_index.go"
go build -o "$search_bin" "$repo_root/search/JASSjr_search.go"

rm -f \
  "$workdir/docids.bin" \
  "$workdir/forward.bin" \
  "$workdir/forward_offsets.bin" \
  "$workdir/lengths.bin" \
  "$workdir/postings.bin" \
  "$workdir/results.trec" \
  "$smoke_metadata_file" \
  "$topics_metadata_file" \
  "$workdir/vocab.bin"

index_output="$(
  cd "$workdir" &&
    "$repo_root/tools/benchmark.sh" "$iters" "$index_bin" "$collection_file"
)"

search_cmd=("$search_bin")
if [[ "${JASSJR_OPENAI_RERANK_MODE:-off}" != "off" ]]; then
  "$repo_root/tools/run_search_pipeline.sh" --workdir "$workdir" --metadata-file "$smoke_metadata_file" < "$smoke_topics_file" >/dev/null
  "$repo_root/tools/run_search_pipeline.sh" --workdir "$workdir" --metadata-file "$topics_metadata_file" < "$topics_file" >/dev/null
  search_cmd=("$repo_root/tools/run_search_pipeline.sh" "--workdir" "$workdir")
fi

search_smoke_output="$(
  cd "$workdir" &&
    "$repo_root/tools/benchmark.sh" "$iters" "${search_cmd[@]}" < "$smoke_topics_file"
)"

search_topics_output="$(
  cd "$workdir" &&
    "$repo_root/tools/benchmark.sh" "$iters" "${search_cmd[@]}" < "$topics_file"
)"

index_median="$(printf '%s\n' "$index_output" | awk '/^Median:/ {print $2}')"
search_smoke_median="$(printf '%s\n' "$search_smoke_output" | awk '/^Median:/ {print $2}')"
search_topics_median="$(printf '%s\n' "$search_topics_output" | awk '/^Median:/ {print $2}')"

{
  printf "branch: %s\n" "$branch_name"
  printf "timestamp: %s\n" "$timestamp"
  printf "collection: %s\n" "$collection_file"
  printf "topics: %s\n" "$topics_file"
  printf "smoke_topics: %s\n" "$smoke_topics_file"
  printf "iterations: %s\n\n" "$iters"
  emit_env_setting JASSJR_BM25_K1
  emit_env_setting JASSJR_BM25_B
  emit_env_setting JASSJR_FEEDBACK_DOCS
  emit_env_setting JASSJR_EXPANSION_TERMS
  emit_env_setting JASSJR_EXPANSION_WEIGHT
  emit_env_setting JASSJR_EXPANSION_MAX_QUERY_TERMS
  emit_env_setting JASSJR_RERANK_DOCS
  emit_env_setting JASSJR_RERANK_PASSAGE_WINDOW
  emit_env_setting JASSJR_RERANK_PASSAGE_WEIGHT
  emit_env_setting JASSJR_OPENAI_RERANK_MODE
  emit_env_setting JASSJR_OPENAI_MONO_MODEL
  emit_env_setting JASSJR_OPENAI_DUO_MODEL
  emit_env_setting JASSJR_OPENAI_MONO_DOCS
  emit_env_setting JASSJR_OPENAI_DUO_DOCS
  emit_env_setting JASSJR_OPENAI_DOC_WORDS
  emit_env_setting JASSJR_OPENAI_PROMPT_VERSION
  emit_env_setting JASSJR_OPENAI_CACHE_DIR
  if [[ -n "${JASSJR_BM25_K1:-}" || -n "${JASSJR_BM25_B:-}" || -n "${JASSJR_FEEDBACK_DOCS:-}" || -n "${JASSJR_EXPANSION_TERMS:-}" || -n "${JASSJR_EXPANSION_WEIGHT:-}" || -n "${JASSJR_EXPANSION_MAX_QUERY_TERMS:-}" || -n "${JASSJR_RERANK_DOCS:-}" || -n "${JASSJR_RERANK_PASSAGE_WINDOW:-}" || -n "${JASSJR_RERANK_PASSAGE_WEIGHT:-}" || -n "${JASSJR_OPENAI_RERANK_MODE:-}" || -n "${JASSJR_OPENAI_MONO_MODEL:-}" || -n "${JASSJR_OPENAI_DUO_MODEL:-}" || -n "${JASSJR_OPENAI_MONO_DOCS:-}" || -n "${JASSJR_OPENAI_DUO_DOCS:-}" || -n "${JASSJR_OPENAI_DOC_WORDS:-}" || -n "${JASSJR_OPENAI_PROMPT_VERSION:-}" || -n "${JASSJR_OPENAI_CACHE_DIR:-}" ]]; then
    printf "\n"
  fi
  emit_metadata_file "$topics_metadata_file"
  [[ -f "$topics_metadata_file" ]] && printf "\n"

  printf "index_median: %s\n" "$index_median"
  printf "search_smoke_median: %s\n" "$search_smoke_median"
  printf "search_topics_median: %s\n\n" "$search_topics_median"

  printf "[index]\n%s\n\n" "$index_output"
  printf "[search_smoke]\n%s\n\n" "$search_smoke_output"
  printf "[search_topics]\n%s\n" "$search_topics_output"
} | tee "$output_file"

printf "Benchmark summary written to %s\n" "$output_file"
