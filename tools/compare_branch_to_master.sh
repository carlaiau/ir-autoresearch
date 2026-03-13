#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1 && pwd)"
branch_name="${1:-$(git -C "$repo_root" branch --show-current 2>/dev/null || true)}"

if [[ -z "$branch_name" ]]; then
  printf "Could not determine branch name. Pass one explicitly.\n" >&2
  exit 1
fi

if [[ "$branch_name" == "master" ]]; then
  printf "Branch is master. Pass a non-master branch to compare against the original baseline.\n" >&2
  exit 1
fi

latest_file() {
  local dir="$1"
  local pattern="$2"
  find "$dir" -type f -name "$pattern" 2>/dev/null | sort | tail -n 1
}

meta_value() {
  local file="$1"
  local key="$2"
  awk -F': ' -v key="$key" '$1 == key { print $2; exit }' "$file"
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

delta() {
  local master_value="$1"
  local branch_value="$2"
  awk -v m="$master_value" -v b="$branch_value" 'BEGIN { printf "%+.4f", b - m }'
}

percent_change() {
  local master_value="$1"
  local branch_value="$2"
  awk -v m="$master_value" -v b="$branch_value" 'BEGIN {
    if (m == 0) {
      printf "n/a"
    } else {
      printf "%+.1f%%", ((b - m) / m) * 100
    }
  }'
}

master_eval_dir="$repo_root/experiment_evaluations/master"
branch_eval_dir="$repo_root/experiment_evaluations/$branch_name"
master_bench_dir="$repo_root/experiment_benchmarks/master"
branch_bench_dir="$repo_root/experiment_benchmarks/$branch_name"

master_eval="$(latest_file "$master_eval_dir" 'trec_eval-*.txt')"
branch_eval="$(latest_file "$branch_eval_dir" 'trec_eval-*.txt')"
master_bench="$(latest_file "$master_bench_dir" 'benchmark-*.txt')"
branch_bench="$(latest_file "$branch_bench_dir" 'benchmark-*.txt')"

if [[ -z "$master_eval" || -z "$branch_eval" ]]; then
  printf "Missing evaluation artifacts for master or %s.\n" "$branch_name" >&2
  exit 1
fi

if [[ -z "$master_bench" || -z "$branch_bench" ]]; then
  printf "Missing benchmark artifacts for master or %s.\n" "$branch_name" >&2
  exit 1
fi

master_eval_topics="$(meta_value "$master_eval" topics)"
branch_eval_topics="$(meta_value "$branch_eval" topics)"
master_eval_qrels="$(meta_value "$master_eval" qrels)"
branch_eval_qrels="$(meta_value "$branch_eval" qrels)"

if [[ "$master_eval_topics" != "$branch_eval_topics" || "$master_eval_qrels" != "$branch_eval_qrels" ]]; then
  printf "Evaluation metadata mismatch between original baseline and %s.\n" "$branch_name" >&2
  printf "original topics: %s\nbranch topics:   %s\n" "$master_eval_topics" "$branch_eval_topics" >&2
  printf "original qrels:  %s\nbranch qrels:   %s\n" "$master_eval_qrels" "$branch_eval_qrels" >&2
  exit 1
fi

master_bench_topics="$(meta_value "$master_bench" topics)"
branch_bench_topics="$(meta_value "$branch_bench" topics)"
master_bench_smoke_topics="$(meta_value "$master_bench" smoke_topics)"
branch_bench_smoke_topics="$(meta_value "$branch_bench" smoke_topics)"
master_bench_iterations="$(meta_value "$master_bench" iterations)"
branch_bench_iterations="$(meta_value "$branch_bench" iterations)"

if [[ "$master_bench_topics" != "$branch_bench_topics" || "$master_bench_smoke_topics" != "$branch_bench_smoke_topics" || "$master_bench_iterations" != "$branch_bench_iterations" ]]; then
  printf "Benchmark metadata mismatch between original baseline and %s.\n" "$branch_name" >&2
  printf "original topics:       %s\nbranch topics:         %s\n" "$master_bench_topics" "$branch_bench_topics" >&2
  printf "original smoke topics: %s\nbranch smoke topics:   %s\n" "$master_bench_smoke_topics" "$branch_bench_smoke_topics" >&2
  printf "original iterations:   %s\nbranch iterations:     %s\n" "$master_bench_iterations" "$branch_bench_iterations" >&2
  exit 1
fi

master_eval_collection="$(meta_value "$master_eval" collection)"
branch_eval_collection="$(meta_value "$branch_eval" collection)"
master_bench_collection="$(meta_value "$master_bench" collection)"
branch_bench_collection="$(meta_value "$branch_bench" collection)"

master_map="$(eval_metric "$master_eval" map)"
branch_map="$(eval_metric "$branch_eval" map)"
master_rprec="$(eval_metric "$master_eval" Rprec)"
branch_rprec="$(eval_metric "$branch_eval" Rprec)"
master_p10="$(eval_metric "$master_eval" P_10)"
branch_p10="$(eval_metric "$branch_eval" P_10)"
master_bpref="$(eval_metric "$master_eval" bpref)"
branch_bpref="$(eval_metric "$branch_eval" bpref)"
master_rr="$(eval_metric "$master_eval" recip_rank)"
branch_rr="$(eval_metric "$branch_eval" recip_rank)"

master_index_median="$(bench_metric "$master_bench" index_median)"
branch_index_median="$(bench_metric "$branch_bench" index_median)"
master_search_smoke_median="$(bench_metric "$master_bench" search_smoke_median)"
branch_search_smoke_median="$(bench_metric "$branch_bench" search_smoke_median)"
master_search_topics_median="$(bench_metric "$master_bench" search_topics_median)"
branch_search_topics_median="$(bench_metric "$branch_bench" search_topics_median)"

printf "Comparing branch '%s' against original\n\n" "$branch_name"
printf "original eval: %s\n" "$master_eval"
printf "branch eval:  %s\n" "$branch_eval"
printf "original bench: %s\n" "$master_bench"
printf "branch bench: %s\n\n" "$branch_bench"

if [[ "$master_eval_collection" != "$branch_eval_collection" ]]; then
  printf "Note: evaluation collection paths differ.\n"
  printf "original collection: %s\n" "$master_eval_collection"
  printf "branch collection: %s\n\n" "$branch_eval_collection"
fi

if [[ "$master_bench_collection" != "$branch_bench_collection" ]]; then
  printf "Note: benchmark collection paths differ.\n"
  printf "original collection: %s\n" "$master_bench_collection"
  printf "branch collection: %s\n\n" "$branch_bench_collection"
fi

printf "%-22s %-10s %-10s %-10s\n" "metric" "original" "$branch_name" "delta"
printf "%-22s %-10s %-10s %-10s\n" "map" "$master_map" "$branch_map" "$(delta "$master_map" "$branch_map")"
printf "%-22s %-10s %-10s %-10s\n" "Rprec" "$master_rprec" "$branch_rprec" "$(delta "$master_rprec" "$branch_rprec")"
printf "%-22s %-10s %-10s %-10s\n" "P_10" "$master_p10" "$branch_p10" "$(delta "$master_p10" "$branch_p10")"
printf "%-22s %-10s %-10s %-10s\n" "bpref" "$master_bpref" "$branch_bpref" "$(delta "$master_bpref" "$branch_bpref")"
printf "%-22s %-10s %-10s %-10s\n" "recip_rank" "$master_rr" "$branch_rr" "$(delta "$master_rr" "$branch_rr")"

printf "\n%-22s %-10s %-10s %-10s\n" "benchmark" "original" "$branch_name" "change"
printf "%-22s %-10s %-10s %-10s\n" "index_median" "$master_index_median" "$branch_index_median" "$(percent_change "$master_index_median" "$branch_index_median")"
printf "%-22s %-10s %-10s %-10s\n" "search_smoke_median" "$master_search_smoke_median" "$branch_search_smoke_median" "$(percent_change "$master_search_smoke_median" "$branch_search_smoke_median")"
printf "%-22s %-10s %-10s %-10s\n" "search_topics_median" "$master_search_topics_median" "$branch_search_topics_median" "$(percent_change "$master_search_topics_median" "$branch_search_topics_median")"
