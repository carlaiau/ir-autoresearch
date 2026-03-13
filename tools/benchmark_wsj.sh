#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1 && pwd)"
branch_name="$(git -C "$repo_root" branch --show-current 2>/dev/null || true)"
branch_name="${branch_name:-detached-head}"

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
  "$workdir/lengths.bin" \
  "$workdir/postings.bin" \
  "$workdir/results.trec" \
  "$workdir/vocab.bin"

index_output="$(
  cd "$workdir" &&
    "$repo_root/tools/benchmark.sh" "$iters" "$index_bin" "$collection_file"
)"

search_smoke_output="$(
  cd "$workdir" &&
    "$repo_root/tools/benchmark.sh" "$iters" "$search_bin" < "$smoke_topics_file"
)"

search_topics_output="$(
  cd "$workdir" &&
    "$repo_root/tools/benchmark.sh" "$iters" "$search_bin" < "$topics_file"
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

  printf "index_median: %s\n" "$index_median"
  printf "search_smoke_median: %s\n" "$search_smoke_median"
  printf "search_topics_median: %s\n\n" "$search_topics_median"

  printf "[index]\n%s\n\n" "$index_output"
  printf "[search_smoke]\n%s\n\n" "$search_smoke_output"
  printf "[search_topics]\n%s\n" "$search_topics_output"
} | tee "$output_file"

printf "Benchmark summary written to %s\n" "$output_file"
