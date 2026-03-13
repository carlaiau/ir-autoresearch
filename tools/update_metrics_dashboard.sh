#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1 && pwd)"

if ! command -v python3 >/dev/null 2>&1; then
  printf "python3 is required but was not found on PATH\n" >&2
  exit 1
fi

metrics_dir="$repo_root/docs/metrics"
graphs_dir="$repo_root/docs/graphs"
tsv_file="$metrics_dir/branch-comparisons.tsv"
map_graph="$graphs_dir/map-vs-original.svg"
bench_graph="$graphs_dir/benchmark-vs-original.svg"

mkdir -p "$metrics_dir" "$graphs_dir"

printf "Exporting branch comparisons against the original baseline\n"
"$repo_root/tools/export_branch_comparisons.sh" > "$tsv_file"

printf "Rendering graphs\n"
python3 "$repo_root/tools/render_metrics_graphs.py" \
  --input "$tsv_file" \
  --map-output "$map_graph" \
  --bench-output "$bench_graph"

printf "Metrics TSV written to %s\n" "$tsv_file"
printf "MAP graph written to %s\n" "$map_graph"
printf "Benchmark graph written to %s\n" "$bench_graph"
