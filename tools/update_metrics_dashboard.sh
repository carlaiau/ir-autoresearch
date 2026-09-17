#!/usr/bin/env bash
# The mixed branch dashboard is retired; do not restore obsolete comparisons.
set -euo pipefail
printf '%s\n' \
  'The legacy branch dashboard is retired.' \
  'Current baseline: stage1/results/integrated-main-20260918/results.md (MAP 0.2521).' \
  'Reranking status: reranking/results/README.md; JEV rerun pending.' \
  'Update the stage reports from matching baseline manifests instead.'
