#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1 && pwd)"

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

percent_change() {
  local original_value="$1"
  local branch_value="$2"
  awk -v o="$original_value" -v b="$branch_value" 'BEGIN {
    if (o == 0) {
      printf ""
    } else {
      printf "%.4f", ((b - o) / o) * 100
    }
  }'
}

original_eval="$(latest_file "$repo_root/experiment_evaluations/master" 'trec_eval-*.txt')"
original_bench="$(latest_file "$repo_root/experiment_benchmarks/master" 'benchmark-*.txt')"

if [[ -z "$original_eval" || -z "$original_bench" ]]; then
  printf "Missing original baseline artifacts under master.\n" >&2
  exit 1
fi

original_collection="$(meta_value "$original_eval" collection)"
original_topics="$(meta_value "$original_eval" topics)"
original_qrels="$(meta_value "$original_eval" qrels)"
original_smoke_topics="$(meta_value "$original_bench" smoke_topics)"
original_iterations="$(meta_value "$original_bench" iterations)"

original_map="$(eval_metric "$original_eval" map)"
original_rprec="$(eval_metric "$original_eval" Rprec)"
original_p10="$(eval_metric "$original_eval" P_10)"
original_bpref="$(eval_metric "$original_eval" bpref)"
original_rr="$(eval_metric "$original_eval" recip_rank)"
original_index_median="$(bench_metric "$original_bench" index_median)"
original_search_smoke_median="$(bench_metric "$original_bench" search_smoke_median)"
original_search_topics_median="$(bench_metric "$original_bench" search_topics_median)"

printf "branch\tbranch_label\ttimestamp\tbaseline_branch\tcollection\ttopics\tqrels\tsmoke_topics\titerations\toriginal_map\tbranch_map\tmap_delta\toriginal_Rprec\tbranch_Rprec\tRprec_delta\toriginal_P_10\tbranch_P_10\tP_10_delta\toriginal_bpref\tbranch_bpref\tbpref_delta\toriginal_recip_rank\tbranch_recip_rank\trecip_rank_delta\toriginal_index_median\tbranch_index_median\tindex_change_pct\toriginal_search_smoke_median\tbranch_search_smoke_median\tsearch_smoke_change_pct\toriginal_search_topics_median\tbranch_search_topics_median\tsearch_topics_change_pct\teval_file\tbench_file\n"

find "$repo_root/experiment_evaluations" "$repo_root/experiment_benchmarks" -type f \( -name 'trec_eval-*.txt' -o -name 'benchmark-*.txt' \) 2>/dev/null \
  | while IFS= read -r file; do
      rel="${file#"$repo_root/experiment_evaluations/"}"
      rel="${rel#"$repo_root/experiment_benchmarks/"}"
      printf "%s\n" "${rel%/*}"
    done \
  | sort -u \
  | while IFS= read -r branch_name; do
      [[ -z "$branch_name" || "$branch_name" == "master" ]] && continue

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
        printf "Skipping %s: evaluation metadata does not match original baseline.\n" "$branch_name" >&2
        continue
      fi

      if [[ "$branch_bench_topics" != "$original_topics" || "$branch_smoke_topics" != "$original_smoke_topics" || "$branch_iterations" != "$original_iterations" ]]; then
        printf "Skipping %s: benchmark metadata does not match original baseline.\n" "$branch_name" >&2
        continue
      fi

      branch_collection="$(meta_value "$branch_eval" collection)"
      branch_map="$(eval_metric "$branch_eval" map)"
      branch_rprec="$(eval_metric "$branch_eval" Rprec)"
      branch_p10="$(eval_metric "$branch_eval" P_10)"
      branch_bpref="$(eval_metric "$branch_eval" bpref)"
      branch_rr="$(eval_metric "$branch_eval" recip_rank)"
      branch_index_median="$(bench_metric "$branch_bench" index_median)"
      branch_search_smoke_median="$(bench_metric "$branch_bench" search_smoke_median)"
      branch_search_topics_median="$(bench_metric "$branch_bench" search_topics_median)"
      branch_timestamp="$(
        printf "%s\n%s\n" "$(timestamp_from_file "$branch_eval")" "$(timestamp_from_file "$branch_bench")" | sort | tail -n 1
      )"
      branch_label="${branch_name#codex/}"

      printf "%s\t%s\t%s\toriginal\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%.4f\t%s\t%s\t%.4f\t%s\t%s\t%.4f\t%s\t%s\t%.4f\t%s\t%s\t%.4f\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" \
        "$branch_name" \
        "$branch_label" \
        "$branch_timestamp" \
        "$branch_collection" \
        "$branch_topics" \
        "$branch_qrels" \
        "$branch_smoke_topics" \
        "$branch_iterations" \
        "$original_map" \
        "$branch_map" \
        "$(awk -v o="$original_map" -v b="$branch_map" 'BEGIN { printf b - o }')" \
        "$original_rprec" \
        "$branch_rprec" \
        "$(awk -v o="$original_rprec" -v b="$branch_rprec" 'BEGIN { printf b - o }')" \
        "$original_p10" \
        "$branch_p10" \
        "$(awk -v o="$original_p10" -v b="$branch_p10" 'BEGIN { printf b - o }')" \
        "$original_bpref" \
        "$branch_bpref" \
        "$(awk -v o="$original_bpref" -v b="$branch_bpref" 'BEGIN { printf b - o }')" \
        "$original_rr" \
        "$branch_rr" \
        "$(awk -v o="$original_rr" -v b="$branch_rr" 'BEGIN { printf b - o }')" \
        "$original_index_median" \
        "$branch_index_median" \
        "$(percent_change "$original_index_median" "$branch_index_median")" \
        "$original_search_smoke_median" \
        "$branch_search_smoke_median" \
        "$(percent_change "$original_search_smoke_median" "$branch_search_smoke_median")" \
        "$original_search_topics_median" \
        "$branch_search_topics_median" \
        "$(percent_change "$original_search_topics_median" "$branch_search_topics_median")" \
        "$branch_eval" \
        "$branch_bench"
    done
