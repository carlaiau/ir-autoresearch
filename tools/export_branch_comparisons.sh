#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1 && pwd)"
baseline_branch="main"

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
  local baseline_value="$1"
  local branch_value="$2"
  awk -v baseline="$baseline_value" -v branch="$branch_value" 'BEGIN {
    if (baseline == 0) {
      printf ""
    } else {
      printf "%.4f", ((branch - baseline) / baseline) * 100
    }
  }'
}

baseline_eval="$(latest_file "$repo_root/experiment_evaluations/$baseline_branch" 'trec_eval-*.txt')"
baseline_bench="$(latest_file "$repo_root/experiment_benchmarks/$baseline_branch" 'benchmark-*.txt')"

if [[ -z "$baseline_eval" || -z "$baseline_bench" ]]; then
  printf "Missing active baseline artifacts under %s. Refresh the %s baseline first.\n" "$baseline_branch" "$baseline_branch" >&2
  exit 1
fi

baseline_topics="$(meta_value "$baseline_eval" topics)"
baseline_qrels="$(meta_value "$baseline_eval" qrels)"
baseline_smoke_topics="$(meta_value "$baseline_bench" smoke_topics)"
baseline_iterations="$(meta_value "$baseline_bench" iterations)"

baseline_map="$(eval_metric "$baseline_eval" map)"
baseline_rprec="$(eval_metric "$baseline_eval" Rprec)"
baseline_p10="$(eval_metric "$baseline_eval" P_10)"
baseline_bpref="$(eval_metric "$baseline_eval" bpref)"
baseline_rr="$(eval_metric "$baseline_eval" recip_rank)"
baseline_index_median="$(bench_metric "$baseline_bench" index_median)"
baseline_search_smoke_median="$(bench_metric "$baseline_bench" search_smoke_median)"
baseline_search_topics_median="$(bench_metric "$baseline_bench" search_topics_median)"

printf "branch\tbranch_label\ttimestamp\tbaseline_branch\tcollection\ttopics\tqrels\tsmoke_topics\titerations\tbaseline_map\tbranch_map\tmap_delta\tbaseline_Rprec\tbranch_Rprec\tRprec_delta\tbaseline_P_10\tbranch_P_10\tP_10_delta\tbaseline_bpref\tbranch_bpref\tbpref_delta\tbaseline_recip_rank\tbranch_recip_rank\trecip_rank_delta\tbaseline_index_median\tbranch_index_median\tindex_change_pct\tbaseline_search_smoke_median\tbranch_search_smoke_median\tsearch_smoke_change_pct\tbaseline_search_topics_median\tbranch_search_topics_median\tsearch_topics_change_pct\teval_file\tbench_file\n"

find "$repo_root/experiment_evaluations" "$repo_root/experiment_benchmarks" -type f \( -name 'trec_eval-*.txt' -o -name 'benchmark-*.txt' \) 2>/dev/null \
  | while IFS= read -r file; do
      rel="${file#"$repo_root/experiment_evaluations/"}"
      rel="${rel#"$repo_root/experiment_benchmarks/"}"
      printf "%s\n" "${rel%/*}"
    done \
  | sort -u \
  | while IFS= read -r branch_name; do
      [[ -z "$branch_name" || "$branch_name" == "$baseline_branch" || "$branch_name" == "original" ]] && continue

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

      if [[ "$branch_topics" != "$baseline_topics" || "$branch_qrels" != "$baseline_qrels" ]]; then
        printf "Skipping %s: evaluation metadata does not match the %s baseline.\n" "$branch_name" "$baseline_branch" >&2
        continue
      fi

      if [[ "$branch_bench_topics" != "$baseline_topics" || "$branch_smoke_topics" != "$baseline_smoke_topics" || "$branch_iterations" != "$baseline_iterations" ]]; then
        printf "Skipping %s: benchmark metadata does not match the %s baseline.\n" "$branch_name" "$baseline_branch" >&2
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

      printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%.4f\t%s\t%s\t%.4f\t%s\t%s\t%.4f\t%s\t%s\t%.4f\t%s\t%s\t%.4f\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" \
        "$branch_name" \
        "$branch_label" \
        "$branch_timestamp" \
        "$baseline_branch" \
        "$branch_collection" \
        "$branch_topics" \
        "$branch_qrels" \
        "$branch_smoke_topics" \
        "$branch_iterations" \
        "$baseline_map" \
        "$branch_map" \
        "$(awk -v baseline="$baseline_map" -v branch="$branch_map" 'BEGIN { printf branch - baseline }')" \
        "$baseline_rprec" \
        "$branch_rprec" \
        "$(awk -v baseline="$baseline_rprec" -v branch="$branch_rprec" 'BEGIN { printf branch - baseline }')" \
        "$baseline_p10" \
        "$branch_p10" \
        "$(awk -v baseline="$baseline_p10" -v branch="$branch_p10" 'BEGIN { printf branch - baseline }')" \
        "$baseline_bpref" \
        "$branch_bpref" \
        "$(awk -v baseline="$baseline_bpref" -v branch="$branch_bpref" 'BEGIN { printf branch - baseline }')" \
        "$baseline_rr" \
        "$branch_rr" \
        "$(awk -v baseline="$baseline_rr" -v branch="$branch_rr" 'BEGIN { printf branch - baseline }')" \
        "$baseline_index_median" \
        "$branch_index_median" \
        "$(percent_change "$baseline_index_median" "$branch_index_median")" \
        "$baseline_search_smoke_median" \
        "$branch_search_smoke_median" \
        "$(percent_change "$baseline_search_smoke_median" "$branch_search_smoke_median")" \
        "$baseline_search_topics_median" \
        "$branch_search_topics_median" \
        "$(percent_change "$baseline_search_topics_median" "$branch_search_topics_median")" \
        "$branch_eval" \
        "$branch_bench"
    done
