#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1 && pwd)"
branch_name="${1:-$(git -C "$repo_root" branch --show-current 2>/dev/null || true)}"
baseline_branch="main"

if [[ -z "$branch_name" ]]; then
  printf "Could not determine branch name. Pass one explicitly.\n" >&2
  exit 1
fi

if [[ "$branch_name" == "$baseline_branch" ]]; then
  printf "Branch is %s. Pass a non-%s branch to compare against the active baseline.\n" "$baseline_branch" "$baseline_branch" >&2
  exit 1
fi

if [[ "$branch_name" == "original" ]]; then
  printf "Branch is original. The original artifact folders are read-only initialization archives.\n" >&2
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
  local baseline_value="$1"
  local branch_value="$2"
  awk -v baseline="$baseline_value" -v branch="$branch_value" 'BEGIN { printf "%+.4f", branch - baseline }'
}

percent_change() {
  local baseline_value="$1"
  local branch_value="$2"
  awk -v baseline="$baseline_value" -v branch="$branch_value" 'BEGIN {
    if (baseline == 0) {
      printf "n/a"
    } else {
      printf "%+.1f%%", ((branch - baseline) / baseline) * 100
    }
  }'
}

baseline_eval_dir="$repo_root/experiment_evaluations/$baseline_branch"
branch_eval_dir="$repo_root/experiment_evaluations/$branch_name"
baseline_bench_dir="$repo_root/experiment_benchmarks/$baseline_branch"
branch_bench_dir="$repo_root/experiment_benchmarks/$branch_name"

baseline_eval="$(latest_file "$baseline_eval_dir" 'trec_eval-*.txt')"
branch_eval="$(latest_file "$branch_eval_dir" 'trec_eval-*.txt')"
baseline_bench="$(latest_file "$baseline_bench_dir" 'benchmark-*.txt')"
branch_bench="$(latest_file "$branch_bench_dir" 'benchmark-*.txt')"

if [[ -z "$baseline_eval" || -z "$baseline_bench" ]]; then
  printf "Missing active baseline artifacts under %s. Refresh the %s baseline first by rerunning evaluation and benchmark on %s.\n" "$baseline_branch" "$baseline_branch" "$baseline_branch" >&2
  exit 1
fi

if [[ -z "$branch_eval" || -z "$branch_bench" ]]; then
  printf "Missing evaluation or benchmark artifacts for %s.\n" "$branch_name" >&2
  exit 1
fi

baseline_eval_topics="$(meta_value "$baseline_eval" topics)"
branch_eval_topics="$(meta_value "$branch_eval" topics)"
baseline_eval_qrels="$(meta_value "$baseline_eval" qrels)"
branch_eval_qrels="$(meta_value "$branch_eval" qrels)"

if [[ "$baseline_eval_topics" != "$branch_eval_topics" || "$baseline_eval_qrels" != "$branch_eval_qrels" ]]; then
  printf "Evaluation metadata mismatch between the %s baseline and %s.\n" "$baseline_branch" "$branch_name" >&2
  printf "%s topics: %s\nbranch topics: %s\n" "$baseline_branch" "$baseline_eval_topics" "$branch_eval_topics" >&2
  printf "%s qrels:  %s\nbranch qrels:  %s\n" "$baseline_branch" "$baseline_eval_qrels" "$branch_eval_qrels" >&2
  exit 1
fi

baseline_bench_topics="$(meta_value "$baseline_bench" topics)"
branch_bench_topics="$(meta_value "$branch_bench" topics)"
baseline_bench_smoke_topics="$(meta_value "$baseline_bench" smoke_topics)"
branch_bench_smoke_topics="$(meta_value "$branch_bench" smoke_topics)"
baseline_bench_iterations="$(meta_value "$baseline_bench" iterations)"
branch_bench_iterations="$(meta_value "$branch_bench" iterations)"

if [[ "$baseline_bench_topics" != "$branch_bench_topics" || "$baseline_bench_smoke_topics" != "$branch_bench_smoke_topics" || "$baseline_bench_iterations" != "$branch_bench_iterations" ]]; then
  printf "Benchmark metadata mismatch between the %s baseline and %s.\n" "$baseline_branch" "$branch_name" >&2
  printf "%s topics:         %s\nbranch topics:     %s\n" "$baseline_branch" "$baseline_bench_topics" "$branch_bench_topics" >&2
  printf "%s smoke topics:   %s\nbranch smoke topics: %s\n" "$baseline_branch" "$baseline_bench_smoke_topics" "$branch_bench_smoke_topics" >&2
  printf "%s iterations:     %s\nbranch iterations: %s\n" "$baseline_branch" "$baseline_bench_iterations" "$branch_bench_iterations" >&2
  exit 1
fi

baseline_eval_collection="$(meta_value "$baseline_eval" collection)"
branch_eval_collection="$(meta_value "$branch_eval" collection)"
baseline_bench_collection="$(meta_value "$baseline_bench" collection)"
branch_bench_collection="$(meta_value "$branch_bench" collection)"

baseline_map="$(eval_metric "$baseline_eval" map)"
branch_map="$(eval_metric "$branch_eval" map)"
baseline_rprec="$(eval_metric "$baseline_eval" Rprec)"
branch_rprec="$(eval_metric "$branch_eval" Rprec)"
baseline_p10="$(eval_metric "$baseline_eval" P_10)"
branch_p10="$(eval_metric "$branch_eval" P_10)"
baseline_bpref="$(eval_metric "$baseline_eval" bpref)"
branch_bpref="$(eval_metric "$branch_eval" bpref)"
baseline_rr="$(eval_metric "$baseline_eval" recip_rank)"
branch_rr="$(eval_metric "$branch_eval" recip_rank)"

baseline_index_median="$(bench_metric "$baseline_bench" index_median)"
branch_index_median="$(bench_metric "$branch_bench" index_median)"
baseline_search_smoke_median="$(bench_metric "$baseline_bench" search_smoke_median)"
branch_search_smoke_median="$(bench_metric "$branch_bench" search_smoke_median)"
baseline_search_topics_median="$(bench_metric "$baseline_bench" search_topics_median)"
branch_search_topics_median="$(bench_metric "$branch_bench" search_topics_median)"

printf "Comparing branch '%s' against %s\n\n" "$branch_name" "$baseline_branch"
printf "%s eval:  %s\n" "$baseline_branch" "$baseline_eval"
printf "branch eval: %s\n" "$branch_eval"
printf "%s bench: %s\n" "$baseline_branch" "$baseline_bench"
printf "branch bench: %s\n\n" "$branch_bench"

if [[ "$baseline_eval_collection" != "$branch_eval_collection" ]]; then
  printf "Note: evaluation collection paths differ.\n"
  printf "%s collection: %s\n" "$baseline_branch" "$baseline_eval_collection"
  printf "branch collection: %s\n\n" "$branch_eval_collection"
fi

if [[ "$baseline_bench_collection" != "$branch_bench_collection" ]]; then
  printf "Note: benchmark collection paths differ.\n"
  printf "%s collection: %s\n" "$baseline_branch" "$baseline_bench_collection"
  printf "branch collection: %s\n\n" "$branch_bench_collection"
fi

printf "%-22s %-10s %-10s %-10s\n" "metric" "$baseline_branch" "$branch_name" "delta"
printf "%-22s %-10s %-10s %-10s\n" "map" "$baseline_map" "$branch_map" "$(delta "$baseline_map" "$branch_map")"
printf "%-22s %-10s %-10s %-10s\n" "Rprec" "$baseline_rprec" "$branch_rprec" "$(delta "$baseline_rprec" "$branch_rprec")"
printf "%-22s %-10s %-10s %-10s\n" "P_10" "$baseline_p10" "$branch_p10" "$(delta "$baseline_p10" "$branch_p10")"
printf "%-22s %-10s %-10s %-10s\n" "bpref" "$baseline_bpref" "$branch_bpref" "$(delta "$baseline_bpref" "$branch_bpref")"
printf "%-22s %-10s %-10s %-10s\n" "recip_rank" "$baseline_rr" "$branch_rr" "$(delta "$baseline_rr" "$branch_rr")"

printf "\n%-22s %-10s %-10s %-10s\n" "benchmark" "$baseline_branch" "$branch_name" "change"
printf "%-22s %-10s %-10s %-10s\n" "index_median" "$baseline_index_median" "$branch_index_median" "$(percent_change "$baseline_index_median" "$branch_index_median")"
printf "%-22s %-10s %-10s %-10s\n" "search_smoke_median" "$baseline_search_smoke_median" "$branch_search_smoke_median" "$(percent_change "$baseline_search_smoke_median" "$branch_search_smoke_median")"
printf "%-22s %-10s %-10s %-10s\n" "search_topics_median" "$baseline_search_topics_median" "$branch_search_topics_median" "$(percent_change "$baseline_search_topics_median" "$branch_search_topics_median")"
