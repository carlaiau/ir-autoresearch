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

seed_dense_vectors_from_existing_artifact() {
  local repo_root="$1"
  local target_workdir="$2"

  [[ "${JASSJR_SEMANTIC_MODE:-off}" == "off" ]] && return 0
  [[ -f "$target_workdir/dense-docs.f32" && -f "$target_workdir/dense-docs.meta.json" ]] && return 0
  [[ -f "$target_workdir/docids.bin" ]] || return 0

  local doc_count
  doc_count="$(wc -l < "$target_workdir/docids.bin" | tr -d '[:space:]')"
  local semantic_model="${JASSJR_SEMANTIC_MODEL:-text-embedding-3-small}"
  local semantic_dimensions="${JASSJR_SEMANTIC_DIMENSIONS:-512}"
  local semantic_doc_words="${JASSJR_SEMANTIC_DOC_WORDS:-220}"
  local semantic_batch_size="${JASSJR_SEMANTIC_BATCH_SIZE:-64}"
  local seed
  seed="$(
    python3 - "$repo_root" "$target_workdir" "$doc_count" "$semantic_model" "$semantic_dimensions" "$semantic_doc_words" "$semantic_batch_size" <<'PY'
import json
import os
import pathlib
import sys

repo_root = pathlib.Path(sys.argv[1]).resolve()
target_workdir = pathlib.Path(sys.argv[2]).resolve()
doc_count = int(sys.argv[3])
model = sys.argv[4]
dimensions = int(sys.argv[5])
doc_words = int(sys.argv[6])
batch_size = int(sys.argv[7])

matches = []
for meta_path in repo_root.rglob("dense-docs.meta.json"):
    try:
        meta = json.loads(meta_path.read_text())
    except Exception:
        continue

    vector_path = pathlib.Path(meta.get("vector_file", "")).expanduser()
    if not vector_path.is_absolute():
        vector_path = (meta_path.parent / vector_path).resolve()

    if pathlib.Path(vector_path).resolve() == (target_workdir / "dense-docs.f32").resolve():
        continue

    if (
        meta.get("status") != "complete"
        or meta.get("mode") != "openai"
        or meta.get("model") != model
        or int(meta.get("dimensions", -1)) != dimensions
        or int(meta.get("doc_words", -1)) != doc_words
        or int(meta.get("batch_size", -1)) != batch_size
        or int(meta.get("documents", -1)) != doc_count
        or not vector_path.is_file()
    ):
        continue

    matches.append((str(meta_path), str(vector_path)))

matches.sort()
if matches:
    print(matches[0][0])
    print(matches[0][1])
PY
  )"

  [[ -n "$seed" ]] || return 0

  local seed_meta
  local seed_vector
  seed_meta="$(printf '%s\n' "$seed" | sed -n '1p')"
  seed_vector="$(printf '%s\n' "$seed" | sed -n '2p')"
  [[ -n "$seed_meta" && -n "$seed_vector" ]] || return 0

  ln -sfn "$seed_vector" "$target_workdir/dense-docs.f32"
  ln -sfn "$seed_meta" "$target_workdir/dense-docs.meta.json"
  printf "Reusing dense vectors from %s\n" "$seed_meta"
}

workdir_lock_dir=""

release_workdir_lock() {
  if [[ -n "$workdir_lock_dir" && -d "$workdir_lock_dir" ]]; then
    rm -rf "$workdir_lock_dir"
  fi
}

acquire_workdir_lock() {
  local target_workdir="$1"
  local lock_dir="$target_workdir/.active-run.lock"
  local holder_pid=""
  if [[ -f "$lock_dir/pid" ]]; then
    holder_pid="$(cat "$lock_dir/pid" 2>/dev/null || true)"
  fi

  if [[ -n "$holder_pid" ]] && ! kill -0 "$holder_pid" 2>/dev/null; then
    rm -rf "$lock_dir"
  fi

  if ! mkdir "$lock_dir" 2>/dev/null; then
    printf "Another WSJ benchmark or evaluation is already using workdir %s\n" "$target_workdir" >&2
    if [[ -f "$lock_dir/info" ]]; then
      printf "Current lock holder:\n" >&2
      cat "$lock_dir/info" >&2
    fi
    exit 1
  fi

  printf "%s\n" "$$" > "$lock_dir/pid"
  {
    printf "pid: %s\n" "$$"
    printf "script: %s\n" "$0"
    printf "started_at: %s\n" "$(date '+%Y-%m-%d %H:%M:%S %z')"
  } > "$lock_dir/info"
  workdir_lock_dir="$lock_dir"
}

trap release_workdir_lock EXIT

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
acquire_workdir_lock "$workdir"

if [[ "$input_path" != /* ]]; then
  input_path="$PWD/$input_path"
fi

merged_input="$workdir/wsj_all.xml"
index_bin="$workdir/jassjr-index"
search_bin="$workdir/jassjr-search"
dense_search_bin="$workdir/jassjr-dense-search"
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
go build -o "$dense_search_bin" "$repo_root/tools/JASSjr_dense_search.go"

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

seed_dense_vectors_from_existing_artifact "$repo_root" "$workdir"

search_cmd=("$search_bin")
if [[ "${JASSJR_OPENAI_RERANK_MODE:-off}" != "off" || "${JASSJR_SEMANTIC_MODE:-off}" != "off" ]]; then
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
  emit_env_setting JASSJR_SEMANTIC_MODE
  emit_env_setting JASSJR_SEMANTIC_MODEL
  emit_env_setting JASSJR_SEMANTIC_DIMENSIONS
  emit_env_setting JASSJR_SEMANTIC_DOC_WORDS
  emit_env_setting JASSJR_SEMANTIC_BATCH_SIZE
  emit_env_setting JASSJR_SEMANTIC_TOPK
  emit_env_setting JASSJR_FUSION_RRF_K
  emit_env_setting JASSJR_FUSION_WEIGHT_BM25
  emit_env_setting JASSJR_FUSION_WEIGHT_RM3
  emit_env_setting JASSJR_FUSION_WEIGHT_DENSE
  emit_env_setting JASSJR_FUSION_BM25_TOPK
  emit_env_setting JASSJR_FUSION_RM3_TOPK
  emit_env_setting JASSJR_FUSION_DENSE_TOPK
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
  if [[ -n "${JASSJR_BM25_K1:-}" || -n "${JASSJR_BM25_B:-}" || -n "${JASSJR_FEEDBACK_DOCS:-}" || -n "${JASSJR_EXPANSION_TERMS:-}" || -n "${JASSJR_EXPANSION_WEIGHT:-}" || -n "${JASSJR_EXPANSION_MAX_QUERY_TERMS:-}" || -n "${JASSJR_SEMANTIC_MODE:-}" || -n "${JASSJR_SEMANTIC_MODEL:-}" || -n "${JASSJR_SEMANTIC_DIMENSIONS:-}" || -n "${JASSJR_SEMANTIC_DOC_WORDS:-}" || -n "${JASSJR_SEMANTIC_BATCH_SIZE:-}" || -n "${JASSJR_SEMANTIC_TOPK:-}" || -n "${JASSJR_FUSION_RRF_K:-}" || -n "${JASSJR_FUSION_WEIGHT_BM25:-}" || -n "${JASSJR_FUSION_WEIGHT_RM3:-}" || -n "${JASSJR_FUSION_WEIGHT_DENSE:-}" || -n "${JASSJR_FUSION_BM25_TOPK:-}" || -n "${JASSJR_FUSION_RM3_TOPK:-}" || -n "${JASSJR_FUSION_DENSE_TOPK:-}" || -n "${JASSJR_RERANK_DOCS:-}" || -n "${JASSJR_RERANK_PASSAGE_WINDOW:-}" || -n "${JASSJR_RERANK_PASSAGE_WEIGHT:-}" || -n "${JASSJR_OPENAI_RERANK_MODE:-}" || -n "${JASSJR_OPENAI_MONO_MODEL:-}" || -n "${JASSJR_OPENAI_DUO_MODEL:-}" || -n "${JASSJR_OPENAI_MONO_DOCS:-}" || -n "${JASSJR_OPENAI_DUO_DOCS:-}" || -n "${JASSJR_OPENAI_DOC_WORDS:-}" || -n "${JASSJR_OPENAI_PROMPT_VERSION:-}" || -n "${JASSJR_OPENAI_CACHE_DIR:-}" ]]; then
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
