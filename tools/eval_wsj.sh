#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1 && pwd)"
branch_name="$(git -C "$repo_root" branch --show-current 2>/dev/null || true)"
branch_name="${branch_name:-detached-head}"

topics_file="$repo_root/51-100.titles.txt"
qrels_file="$repo_root/51-100.qrels.txt"
workdir="$repo_root/wsj-eval/$branch_name"
eval_output_dir="$repo_root/experiment_evaluations/$branch_name"
results_file=""

usage() {
  cat <<EOF
Usage: $0 [-t topics.txt] [-q qrels.txt] [-w workdir] [-o results.trec] <wsj-dir-or-file>

Build the index, run the bundled topics, and evaluate with trec_eval.
Artifacts are grouped by the current git branch:
  $branch_name
The trec_eval summary is written to a timestamped file in:
  $eval_output_dir

Options:
  -t <file>  Topics file to feed into the searcher.
             Default: $topics_file
  -q <file>  Qrels file for trec_eval.
             Default: $qrels_file
  -w <dir>   Working directory for merged input, binaries, and index files.
             Default: $workdir
  -o <file>  Output run file path.
             Default: <workdir>/results.trec
  -h         Show this help text.

Examples:
  $0 /path/to/wsj
  $0 -w /tmp/wsj-eval /path/to/wsj
  $0 -t my.topics -q my.qrels /path/to/wsj_all.xml
EOF
}

while getopts ":t:q:w:o:h" opt; do
  case "$opt" in
    t)
      topics_file="$OPTARG"
      ;;
    q)
      qrels_file="$OPTARG"
      ;;
    w)
      workdir="$OPTARG"
      ;;
    o)
      results_file="$OPTARG"
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

if [[ ! -f "$qrels_file" ]]; then
  printf "Qrels file does not exist: %s\n" "$qrels_file" >&2
  exit 1
fi

if ! command -v go >/dev/null 2>&1; then
  printf "go is required but was not found on PATH\n" >&2
  exit 1
fi

if ! command -v trec_eval >/dev/null 2>&1; then
  printf "trec_eval is required but was not found on PATH\n" >&2
  exit 1
fi

mkdir -p "$workdir"
mkdir -p "$eval_output_dir"

workdir="$(cd "$workdir" >/dev/null 2>&1 && pwd)"
eval_output_dir="$(cd "$eval_output_dir" >/dev/null 2>&1 && pwd)"
topics_file="$(cd "$(dirname "$topics_file")" >/dev/null 2>&1 && pwd)/$(basename "$topics_file")"
qrels_file="$(cd "$(dirname "$qrels_file")" >/dev/null 2>&1 && pwd)/$(basename "$qrels_file")"

if [[ -z "$results_file" ]]; then
  results_file="$workdir/results.trec"
elif [[ "$results_file" != /* ]]; then
  results_file="$PWD/$results_file"
fi

if [[ "$input_path" != /* ]]; then
  input_path="$PWD/$input_path"
fi

merged_input="$workdir/wsj_all.xml"
index_bin="$workdir/jassjr-index"
search_bin="$workdir/jassjr-search"
timestamp="$(date '+%Y%m%d-%H%M%S')"
eval_output_file="$eval_output_dir/trec_eval-$timestamp.txt"

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

printf "Indexing %s\n" "$collection_file"
rm -f \
  "$workdir/docids.bin" \
  "$workdir/lengths.bin" \
  "$workdir/postings.bin" \
  "$workdir/results.bin" \
  "$workdir/stdout.bin" \
  "$workdir/vocab.bin" \
  "$results_file"

(
  cd "$workdir" || exit 1
  "$index_bin" "$collection_file"

  printf "Running topics from %s\n" "$topics_file"
  "$search_bin" < "$topics_file" > "$results_file"
)

printf "Run file written to %s\n" "$results_file"
printf "Evaluating with trec_eval against %s\n" "$qrels_file"
summary="$(
  trec_eval -c -M1000 "$qrels_file" "$results_file"
)"
printf "%s\n" "$summary"
{
  printf "branch: %s\n" "$branch_name"
  printf "timestamp: %s\n" "$timestamp"
  printf "collection: %s\n" "$collection_file"
  printf "topics: %s\n" "$topics_file"
  printf "qrels: %s\n\n" "$qrels_file"
  printf "%s\n" "$summary"
} > "$eval_output_file"
printf "Summary written to %s\n" "$eval_output_file"
