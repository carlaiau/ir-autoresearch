#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1 && pwd)"
branch_name="${1:-main}"

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

rel_ret_ratio() {
  local num_rel_ret="$1"
  local num_rel="$2"
  awk -v num_rel_ret="$num_rel_ret" -v num_rel="$num_rel" 'BEGIN {
    if (num_rel == "" || num_rel == 0) {
      print ""
    } else {
      printf "%.4f", num_rel_ret / num_rel
    }
  }'
}

printf "branch\ttimestamp\tkind\trunid\tcollection\ttopics\tqrels\tsmoke_topics\titerations\tmap\tP_5\tP_10\tP_20\tRprec\tbpref\trecip_rank\tnum_rel_ret_over_num_rel\tindex_median\tsearch_smoke_median\tsearch_topics_median\tsource_file\n"

find "$repo_root/experiment_evaluations/$branch_name" -type f -name 'trec_eval-*.txt' 2>/dev/null | sort | while IFS= read -r file; do
  num_rel="$(eval_metric "$file" num_rel)"
  num_rel_ret="$(eval_metric "$file" num_rel_ret)"
  printf "%s\t%s\teval\t%s\t%s\t%s\t%s\t\t\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t\t\t\t%s\n" \
    "$branch_name" \
    "$(timestamp_from_file "$file")" \
    "$(eval_metric "$file" runid)" \
    "$(meta_value "$file" collection)" \
    "$(meta_value "$file" topics)" \
    "$(meta_value "$file" qrels)" \
    "$(eval_metric "$file" map)" \
    "$(eval_metric "$file" P_5)" \
    "$(eval_metric "$file" P_10)" \
    "$(eval_metric "$file" P_20)" \
    "$(eval_metric "$file" Rprec)" \
    "$(eval_metric "$file" bpref)" \
    "$(eval_metric "$file" recip_rank)" \
    "$(rel_ret_ratio "$num_rel_ret" "$num_rel")" \
    "$file"
done

find "$repo_root/experiment_benchmarks/$branch_name" -type f -name 'benchmark-*.txt' 2>/dev/null | sort | while IFS= read -r file; do
  printf "%s\t%s\tbenchmark\t\t%s\t%s\t\t%s\t%s\t\t\t\t\t\t\t\t%s\t%s\t%s\t%s\n" \
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
