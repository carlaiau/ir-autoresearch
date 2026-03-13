#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1 && pwd)"
branch_name="${1:-master}"

timestamp_from_file() {
  basename "$1" | sed -E 's/^[^-]+-([0-9]{8}-[0-9]{6})\.txt$/\1/'
}

eval_metric() {
  local file="$1"
  local metric="$2"
  awk -v metric="$metric" '$1 == metric && $2 == "all" { print $3; exit }' "$file"
}

bench_metric() {
  local file="$1"
  local key="$2"
  awk -F': ' -v key="$key" '$1 == key { print $2; exit }' "$file"
}

meta_value() {
  local file="$1"
  local key="$2"
  awk -F': ' -v key="$key" '$1 == key { print $2; exit }' "$file"
}

printf "branch\ttimestamp\tkind\trunid\tcollection\ttopics\tqrels\tsmoke_topics\titerations\tmap\tRprec\tP_10\tbpref\trecip_rank\tindex_median\tsearch_smoke_median\tsearch_topics_median\tsource_file\n"

find "$repo_root/experiment_evaluations/$branch_name" -type f -name 'trec_eval-*.txt' 2>/dev/null | sort | while IFS= read -r file; do
  printf "%s\t%s\teval\t%s\t%s\t%s\t%s\t\t\t%s\t%s\t%s\t%s\t%s\t\t\t\t%s\n" \
    "$branch_name" \
    "$(timestamp_from_file "$file")" \
    "$(eval_metric "$file" runid)" \
    "$(meta_value "$file" collection)" \
    "$(meta_value "$file" topics)" \
    "$(meta_value "$file" qrels)" \
    "$(eval_metric "$file" map)" \
    "$(eval_metric "$file" Rprec)" \
    "$(eval_metric "$file" P_10)" \
    "$(eval_metric "$file" bpref)" \
    "$(eval_metric "$file" recip_rank)" \
    "$file"
done

find "$repo_root/experiment_benchmarks/$branch_name" -type f -name 'benchmark-*.txt' 2>/dev/null | sort | while IFS= read -r file; do
  printf "%s\t%s\tbenchmark\t\t%s\t%s\t\t%s\t%s\t\t\t\t\t\t%s\t%s\t%s\t%s\n" \
    "$branch_name" \
    "$(timestamp_from_file "$file")" \
    "$(meta_value "$file" collection)" \
    "$(meta_value "$file" topics)" \
    "$(meta_value "$file" smoke_topics)" \
    "$(meta_value "$file" iterations)" \
    "$(bench_metric "$file" index_median)" \
    "$(bench_metric "$file" search_smoke_median)" \
    "$(bench_metric "$file" search_topics_median)" \
    "$file"
done
