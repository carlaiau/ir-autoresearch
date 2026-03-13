#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1 && pwd)"

if ! command -v python3 >/dev/null 2>&1; then
  printf "python3 is required but was not found on PATH\n" >&2
  exit 1
fi

if ! command -v gh >/dev/null 2>&1; then
  printf "gh is required but was not found on PATH\n" >&2
  exit 1
fi

metrics_dir="$repo_root/docs/metrics"
tsv_file="$metrics_dir/branch-comparisons.tsv"
table_file="$metrics_dir/branch-comparisons.md"
readme_file="$repo_root/README.md"

mkdir -p "$metrics_dir"

printf "Exporting README branch metrics\n"
"$repo_root/tools/export_branch_comparisons.sh" > "$tsv_file"

printf "Refreshing README metrics table\n"
python3 "$repo_root/tools/render_metrics_table.py" \
  --input "$tsv_file" \
  --output "$table_file" \
  --readme "$readme_file"

printf "Metrics TSV written to %s\n" "$tsv_file"
printf "Metrics table written to %s\n" "$table_file"
printf "README metrics table refreshed in %s\n" "$readme_file"
