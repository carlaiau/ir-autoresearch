#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1 && pwd)"
branch_name="$(git -C "$repo_root" branch --show-current 2>/dev/null || true)"
branch_name="${branch_name:-detached-head}"

if [[ "$branch_name" == "original" ]]; then
  printf "Refusing to write evaluation artifacts for branch 'original'. The original artifact folders are read-only initialization archives.\n" >&2
  exit 1
fi

default_k1_csv="0.6,0.7,0.8,0.9,1.0,1.1,1.2,1.3,1.4"
default_b_csv="0.0,0.1,0.2,0.3,0.4,0.5,0.6"
topics_file="$repo_root/51-100.titles.txt"
qrels_file="$repo_root/51-100.qrels.txt"
workdir="$repo_root/wsj-grid-search/$branch_name"
output_dir="$repo_root/experiment_evaluations/$branch_name"
output_file=""
k1_csv="$default_k1_csv"
b_csv="$default_b_csv"

usage() {
  cat <<EOF
Usage: $0 [-k k1_values] [-b b_values] [-t topics.txt] [-q qrels.txt] [-w workdir] [-o output.tsv] <wsj-dir-or-file>

Build the index once, then sweep BM25 k1/b parameter combinations for the current branch.
Artifacts are grouped by the current git branch:
  $branch_name

Options:
  -k <csv>   Comma-separated BM25 k1 values.
             Default: $default_k1_csv
  -b <csv>   Comma-separated BM25 b values.
             Default: $default_b_csv
  -t <file>  Topics file to feed into the searcher.
             Default: $topics_file
  -q <file>  Qrels file for trec_eval.
             Default: $qrels_file
  -w <dir>   Working directory for binaries and index files.
             Default: $workdir
  -o <file>  Output TSV path.
             Default: <experiment_evaluations/$branch_name>/bm25-grid-<timestamp>.tsv
  -h         Show this help text.
EOF
}

metric_value() {
  local file="$1"
  local metric="$2"
  awk -v metric="$metric" '$1 == metric && $2 == "all" { print $3; exit }' "$file"
}

while getopts ":k:b:t:q:w:o:h" opt; do
  case "$opt" in
    k)
      k1_csv="$OPTARG"
      ;;
    b)
      b_csv="$OPTARG"
      ;;
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
      output_file="$OPTARG"
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
mkdir -p "$output_dir"

workdir="$(cd "$workdir" >/dev/null 2>&1 && pwd)"
output_dir="$(cd "$output_dir" >/dev/null 2>&1 && pwd)"
topics_file="$(cd "$(dirname "$topics_file")" >/dev/null 2>&1 && pwd)/$(basename "$topics_file")"
qrels_file="$(cd "$(dirname "$qrels_file")" >/dev/null 2>&1 && pwd)/$(basename "$qrels_file")"

if [[ -z "$output_file" ]]; then
  timestamp="$(date '+%Y%m%d-%H%M%S')"
  output_file="$output_dir/bm25-grid-$timestamp.tsv"
elif [[ "$output_file" != /* ]]; then
  output_file="$PWD/$output_file"
fi

if [[ "$input_path" != /* ]]; then
  input_path="$PWD/$input_path"
fi

index_bin="$workdir/jassjr-index"
search_bin="$workdir/jassjr-search"
results_file="$workdir/results.trec"
summary_file="$workdir/trec_eval.txt"

if [[ -d "$input_path" ]]; then
  merged_input="$workdir/wsj_all.xml"
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
  "$workdir/forward.bin" \
  "$workdir/forward_offsets.bin" \
  "$workdir/lengths.bin" \
  "$workdir/postings.bin" \
  "$workdir/results.bin" \
  "$workdir/stdout.bin" \
  "$workdir/vocab.bin" \
  "$results_file" \
  "$summary_file"

(
  cd "$workdir" || exit 1
  "$index_bin" "$collection_file"
)

IFS=',' read -r -a k1_values <<< "$k1_csv"
IFS=',' read -r -a b_values <<< "$b_csv"

printf "k1\tb\tmap\tRprec\tP_10\tbpref\trecip_rank\n" > "$output_file"

for k1 in "${k1_values[@]}"; do
  for b in "${b_values[@]}"; do
    printf "Evaluating k1=%s b=%s\n" "$k1" "$b"
    (
      cd "$workdir" || exit 1
      JASSJR_BM25_K1="$k1" JASSJR_BM25_B="$b" "$search_bin" < "$topics_file" > "$results_file"
    )
    trec_eval -c -M1000 "$qrels_file" "$results_file" > "$summary_file"

    map="$(metric_value "$summary_file" map)"
    rprec="$(metric_value "$summary_file" Rprec)"
    p10="$(metric_value "$summary_file" P_10)"
    bpref="$(metric_value "$summary_file" bpref)"
    recip_rank="$(metric_value "$summary_file" recip_rank)"

    printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\n" \
      "$k1" \
      "$b" \
      "$map" \
      "$rprec" \
      "$p10" \
      "$bpref" \
      "$recip_rank" >> "$output_file"
  done
done

best_row="$(tail -n +2 "$output_file" | sort -t $'\t' -k3,3gr -k4,4gr -k5,5gr | head -n 1)"

printf "Grid search written to %s\n" "$output_file"
printf "Best combination: %s\n" "$best_row"
