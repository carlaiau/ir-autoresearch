#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1 && pwd)"
archive_branch="original"

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

timestamp_from_file() {
  basename "$1" | sed -E 's/^[^-]+-([0-9]{8}-[0-9]{6})\.txt$/\1/'
}

latest_timestamp() {
  local eval_file="$1"
  local bench_file="$2"
  printf "%s\n%s\n" "$(timestamp_from_file "$eval_file")" "$(timestamp_from_file "$bench_file")" | sort | tail -n 1
}

percent_change() {
  local original_value="$1"
  local branch_value="$2"
  awk -v original="$original_value" -v branch="$branch_value" 'BEGIN {
    if (original == 0) {
      printf ""
    } else {
      printf "%.4f", ((branch - original) / original) * 100
    }
  }'
}

original_eval="$(latest_file "$repo_root/experiment_evaluations/$archive_branch" 'trec_eval-*.txt')"
original_bench="$(latest_file "$repo_root/experiment_benchmarks/$archive_branch" 'benchmark-*.txt')"

if [[ -z "$original_eval" || -z "$original_bench" ]]; then
  printf "Missing original archive artifacts under %s. The README table requires the original evaluation and benchmark reports.\n" "$archive_branch" >&2
  exit 1
fi

original_topics="$(meta_value "$original_eval" topics)"
original_qrels="$(meta_value "$original_eval" qrels)"
original_smoke_topics="$(meta_value "$original_bench" smoke_topics)"
original_iterations="$(meta_value "$original_bench" iterations)"

original_map="$(eval_metric "$original_eval" map)"
original_index_median="$(bench_metric "$original_bench" index_median)"
original_search_topics_median="$(bench_metric "$original_bench" search_topics_median)"
original_timestamp="$(latest_timestamp "$original_eval" "$original_bench")"

printf "branch\tbranch_label\ttimestamp\trow_kind\tmap\tmap_delta_vs_original\tindex_median\tindex_change_pct_vs_original\tsearch_topics_median\tsearch_topics_change_pct_vs_original\teval_file\tbench_file\n"
printf "%s\t%s\t%s\t%s\t%s\t%.4f\t%s\t%.4f\t%s\t%.4f\t%s\t%s\n" \
  "$archive_branch" \
  "$archive_branch" \
  "$original_timestamp" \
  "$archive_branch" \
  "$original_map" \
  0 \
  "$original_index_median" \
  0 \
  "$original_search_topics_median" \
  0 \
  "$original_eval" \
  "$original_bench"

branch_rows="$(
  find "$repo_root/experiment_evaluations" "$repo_root/experiment_benchmarks" -type f \( -name 'trec_eval-*.txt' -o -name 'benchmark-*.txt' \) 2>/dev/null \
    | while IFS= read -r file; do
        rel="${file#"$repo_root/experiment_evaluations/"}"
        rel="${rel#"$repo_root/experiment_benchmarks/"}"
        printf "%s\n" "${rel%/*}"
      done \
    | sort -u \
    | while IFS= read -r branch_name; do
        [[ -z "$branch_name" || "$branch_name" == "main" || "$branch_name" == "$archive_branch" ]] && continue

        branch_eval="$(latest_file "$repo_root/experiment_evaluations/$branch_name" 'trec_eval-*.txt')"
        branch_bench="$(latest_file "$repo_root/experiment_benchmarks/$branch_name" 'benchmark-*.txt')"

        if [[ -z "$branch_eval" || -z "$branch_bench" ]]; then
          printf "Skipping %s: missing evaluation or benchmark artifact.\n" "$branch_name" >&2
          continue
        fi

        branch_topics="$(meta_value "$branch_eval" topics)"
        branch_qrels="$(meta_value "$branch_eval" qrels)"
        branch_bench_topics="$(meta_value "$branch_bench" topics)"
        branch_smoke_topics="$(meta_value "$branch_bench" smoke_topics)"
        branch_iterations="$(meta_value "$branch_bench" iterations)"

        if [[ "$branch_topics" != "$original_topics" || "$branch_qrels" != "$original_qrels" ]]; then
          printf "Skipping %s: evaluation metadata does not match the original archive.\n" "$branch_name" >&2
          continue
        fi

        if [[ "$branch_bench_topics" != "$original_topics" || "$branch_smoke_topics" != "$original_smoke_topics" || "$branch_iterations" != "$original_iterations" ]]; then
          printf "Skipping %s: benchmark metadata does not match the original archive.\n" "$branch_name" >&2
          continue
        fi

        branch_map="$(eval_metric "$branch_eval" map)"
        branch_index_median="$(bench_metric "$branch_bench" index_median)"
        branch_search_topics_median="$(bench_metric "$branch_bench" search_topics_median)"
        branch_timestamp="$(latest_timestamp "$branch_eval" "$branch_bench")"

        printf "%s\t%s\t%s\t%s\t%s\t%.4f\t%s\t%s\t%s\t%s\t%s\t%s\n" \
          "$branch_name" \
          "${branch_name#codex/}" \
          "$branch_timestamp" \
          "branch" \
          "$branch_map" \
          "$(awk -v original="$original_map" -v branch="$branch_map" 'BEGIN { printf branch - original }')" \
          "$branch_index_median" \
          "$(percent_change "$original_index_median" "$branch_index_median")" \
          "$branch_search_topics_median" \
          "$(percent_change "$original_search_topics_median" "$branch_search_topics_median")" \
          "$branch_eval" \
          "$branch_bench"
      done \
    | sort -t "$(printf '\t')" -k3,3
)"

if [[ -n "$branch_rows" ]]; then
  printf "%s\n" "$branch_rows"
fi
