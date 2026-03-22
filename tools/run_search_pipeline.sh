#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1 && pwd)"
workdir=""
metadata_file=""

usage() {
  cat <<EOF
Usage: $0 --workdir <dir> [--metadata-file <file>]

Read topics from stdin, run the lexical searcher, and optionally apply
tri-source fusion and OpenAI-backed reranking before writing the final
TREC run to stdout.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --workdir)
      workdir="$2"
      shift 2
      ;;
    --metadata-file)
      metadata_file="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf "Unknown argument: %s\n" "$1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -z "$workdir" ]]; then
  usage >&2
  exit 1
fi

workdir="$(cd "$workdir" >/dev/null 2>&1 && pwd)"
source "$repo_root/tools/load_env.sh"
key_source="$(load_repo_env_with_key_source "$repo_root")"
export JASSJR_OPENAI_KEY_SOURCE="$key_source"

pipeline_tmpdir="$(mktemp -d "$workdir/pipeline-run.XXXXXX")"
topics_stdin_file="$pipeline_tmpdir/topics-stdin.txt"
raw_results_file="$pipeline_tmpdir/results-raw.trec"
bm25_results_file="$pipeline_tmpdir/results-bm25.trec"
rm3_results_file="$pipeline_tmpdir/results-rm3.trec"
rm3_expansion_results_file="$pipeline_tmpdir/results-rm3-expansion.trec"
dense_results_file="$pipeline_tmpdir/results-dense.trec"
rewrite_topics_file="$pipeline_tmpdir/topics-rewrite.txt"
rewrite_results_file="$pipeline_tmpdir/results-rewrite.trec"
final_results_file="$pipeline_tmpdir/results-final.trec"
dense_build_metadata_file="$pipeline_tmpdir/semantic-build.txt"
dense_query_metadata_file="$pipeline_tmpdir/semantic-query.txt"
rewrite_metadata_file="$pipeline_tmpdir/query-rewrite.txt"
fusion_bm25_rm3_metadata_file="$pipeline_tmpdir/fusion-bm25-rm3.txt"
fusion_bm25_rm3_expansion_metadata_file="$pipeline_tmpdir/fusion-bm25-rm3-expansion.txt"
fusion_bm25_rm3_expansion_rewrite_metadata_file="$pipeline_tmpdir/fusion-bm25-rm3-expansion-rewrite.txt"
fusion_bm25_dense_metadata_file="$pipeline_tmpdir/fusion-bm25-dense.txt"
fusion_tri_source_metadata_file="$pipeline_tmpdir/fusion-tri-source.txt"
fusion_tri_source_expansion_metadata_file="$pipeline_tmpdir/fusion-tri-source-expansion.txt"
fusion_tri_source_expansion_rewrite_metadata_file="$pipeline_tmpdir/fusion-tri-source-expansion-rewrite.txt"
rerank_metadata_file="$pipeline_tmpdir/rerank.txt"
pipeline_metadata_file="$pipeline_tmpdir/pipeline.txt"
trap 'rm -rf "$pipeline_tmpdir"' EXIT
cat > "$topics_stdin_file"

openai_mode="${JASSJR_OPENAI_RERANK_MODE:-off}"
semantic_mode="${JASSJR_SEMANTIC_MODE:-off}"
query_rewrite_mode="${JASSJR_OPENAI_QUERY_REWRITE_MODE:-off}"
rrf_k="${JASSJR_FUSION_RRF_K:-60}"
fusion_weight_bm25="${JASSJR_FUSION_WEIGHT_BM25:-0.05}"
fusion_weight_rm3="${JASSJR_FUSION_WEIGHT_RM3:-0.55}"
fusion_weight_rm3_expansion="${JASSJR_FUSION_WEIGHT_RM3_EXPANSION:-0.10}"
fusion_weight_query_rewrite="${JASSJR_FUSION_WEIGHT_QUERY_REWRITE:-0.08}"
fusion_weight_dense="${JASSJR_FUSION_WEIGHT_DENSE:-0.40}"
fusion_topk_bm25="${JASSJR_FUSION_BM25_TOPK:-250}"
fusion_topk_rm3="${JASSJR_FUSION_RM3_TOPK:-250}"
fusion_topk_rm3_expansion="${JASSJR_FUSION_RM3_EXPANSION_TOPK:-250}"
fusion_topk_query_rewrite="${JASSJR_FUSION_QUERY_REWRITE_TOPK:-150}"
fusion_topk_dense="${JASSJR_FUSION_DENSE_TOPK:-250}"

run_sparse_topics() {
  local topics_file="$1"
  local output_file="$2"
  shift 2
  (
    cd "$workdir" || exit 1
    env JASSJR_RERANK_DOCS=0 "$@" ./jassjr-search < "$topics_file" > "$output_file"
  )
}

run_sparse() {
  local output_file="$1"
  shift
  run_sparse_topics "$topics_stdin_file" "$output_file" "$@"
}

append_metadata() {
  local file="$1"
  [[ -f "$file" ]] || return 0
  cat "$file" >> "$pipeline_metadata_file"
  printf "\n" >> "$pipeline_metadata_file"
}

write_off_metadata() {
  cat >> "$pipeline_metadata_file" <<EOF
JASSJR_OPENAI_RERANK_MODE: off
JASSJR_OPENAI_KEY_SOURCE: $key_source
EOF
}

(
  cd "$workdir" || exit 1
  if [[ "$semantic_mode" == "off" && "$openai_mode" == "off" && "$query_rewrite_mode" == "off" ]]; then
    ./jassjr-search < "$topics_stdin_file" > "$raw_results_file"
  else
    env JASSJR_RERANK_DOCS=0 ./jassjr-search < "$topics_stdin_file" > "$raw_results_file"
  fi
)

if [[ "$semantic_mode" == "off" && "$query_rewrite_mode" == "off" ]]; then
  output_file="$raw_results_file"
  if [[ "$openai_mode" == "off" ]]; then
    write_off_metadata
  else
    python_args=(
      "$repo_root/tools/openai_rerank.py"
      --repo-root "$repo_root"
      --workdir "$workdir"
      --topics-file "$topics_stdin_file"
      --run-file "$raw_results_file"
      --output-file "$final_results_file"
      --metadata-file "$rerank_metadata_file"
    )
    python3 "${python_args[@]}"
    output_file="$final_results_file"
    append_metadata "$rerank_metadata_file"
  fi

  if [[ -n "$metadata_file" ]]; then
    cp "$pipeline_metadata_file" "$metadata_file"
  fi
  cat "$output_file"
  exit 0
fi

ablation_dir="$workdir/ablation-runs"
mkdir -p "$ablation_dir"
bm25_only_output="$ablation_dir/bm25-only.trec"
bm25_rm3_output="$ablation_dir/bm25-rm3-fusion.trec"
bm25_rm3_expansion_output="$ablation_dir/bm25-rm3-expansion-fusion.trec"
bm25_rm3_expansion_rewrite_output="$ablation_dir/bm25-rm3-rm3exp-rewrite-fusion.trec"
bm25_dense_output="$ablation_dir/bm25-dense-fusion.trec"
tri_source_output="$ablation_dir/bm25-rm3-dense-fusion.trec"
tri_source_expansion_output="$ablation_dir/bm25-rm3-rm3exp-dense-fusion.trec"
tri_source_expansion_rewrite_output="$ablation_dir/bm25-rm3-rm3exp-rewrite-dense-fusion.trec"

run_sparse "$bm25_results_file" JASSJR_FEEDBACK_DOCS=0 JASSJR_EXPANSION_TERMS=0 JASSJR_EXPANSION_WEIGHT=0
cp "$bm25_results_file" "$bm25_only_output"
run_sparse "$rm3_results_file"
run_sparse "$rm3_expansion_results_file" JASSJR_EXPANSION_ONLY=1

rewrite_enabled=0
if [[ "$query_rewrite_mode" != "off" ]]; then
  python3 "$repo_root/tools/openai_query_rewrite.py" \
    --repo-root "$repo_root" \
    --workdir "$workdir" \
    --topics-file "$topics_stdin_file" \
    --output-file "$rewrite_topics_file" \
    --metadata-file "$rewrite_metadata_file"
  if [[ -s "$rewrite_topics_file" ]]; then
    run_sparse_topics "$rewrite_topics_file" "$rewrite_results_file" JASSJR_FEEDBACK_DOCS=0 JASSJR_EXPANSION_TERMS=0 JASSJR_EXPANSION_WEIGHT=0
    rewrite_enabled=1
  fi
fi

if [[ "$semantic_mode" != "off" ]]; then
  python3 "$repo_root/tools/build_dense_vectors.py" \
    --repo-root "$repo_root" \
    --workdir "$workdir" \
    --metadata-file "$dense_build_metadata_file" >&2

  (
    cd "$workdir" || exit 1
    ./jassjr-dense-search --repo-root "$repo_root" --metadata-file "$dense_query_metadata_file" < "$topics_stdin_file" > "$dense_results_file"
  )
fi

python3 "$repo_root/tools/fuse_runs.py" \
  --output "$bm25_rm3_output" \
  --metadata-file "$fusion_bm25_rm3_metadata_file" \
  --rrf-k "$rrf_k" \
  --source bm25 "$bm25_results_file" "$fusion_weight_bm25" "$fusion_topk_bm25" \
  --source rm3 "$rm3_results_file" "$fusion_weight_rm3" "$fusion_topk_rm3"

python3 "$repo_root/tools/fuse_runs.py" \
  --output "$bm25_rm3_expansion_output" \
  --metadata-file "$fusion_bm25_rm3_expansion_metadata_file" \
  --rrf-k "$rrf_k" \
  --source bm25 "$bm25_results_file" "$fusion_weight_bm25" "$fusion_topk_bm25" \
  --source rm3 "$rm3_results_file" "$fusion_weight_rm3" "$fusion_topk_rm3" \
  --source rm3exp "$rm3_expansion_results_file" "$fusion_weight_rm3_expansion" "$fusion_topk_rm3_expansion"

if [[ "$rewrite_enabled" -eq 1 ]]; then
  python3 "$repo_root/tools/fuse_runs.py" \
    --output "$bm25_rm3_expansion_rewrite_output" \
    --metadata-file "$fusion_bm25_rm3_expansion_rewrite_metadata_file" \
    --rrf-k "$rrf_k" \
    --source bm25 "$bm25_results_file" "$fusion_weight_bm25" "$fusion_topk_bm25" \
    --source rm3 "$rm3_results_file" "$fusion_weight_rm3" "$fusion_topk_rm3" \
    --source rm3exp "$rm3_expansion_results_file" "$fusion_weight_rm3_expansion" "$fusion_topk_rm3_expansion" \
    --source rewrite "$rewrite_results_file" "$fusion_weight_query_rewrite" "$fusion_topk_query_rewrite"
fi

if [[ "$semantic_mode" != "off" ]]; then
  python3 "$repo_root/tools/fuse_runs.py" \
    --output "$bm25_dense_output" \
    --metadata-file "$fusion_bm25_dense_metadata_file" \
    --rrf-k "$rrf_k" \
    --source bm25 "$bm25_results_file" "$fusion_weight_bm25" "$fusion_topk_bm25" \
    --source dense "$dense_results_file" "$fusion_weight_dense" "$fusion_topk_dense"

  python3 "$repo_root/tools/fuse_runs.py" \
    --output "$tri_source_output" \
    --metadata-file "$fusion_tri_source_metadata_file" \
    --rrf-k "$rrf_k" \
    --source bm25 "$bm25_results_file" "$fusion_weight_bm25" "$fusion_topk_bm25" \
    --source rm3 "$rm3_results_file" "$fusion_weight_rm3" "$fusion_topk_rm3" \
    --source dense "$dense_results_file" "$fusion_weight_dense" "$fusion_topk_dense"

  python3 "$repo_root/tools/fuse_runs.py" \
    --output "$tri_source_expansion_output" \
    --metadata-file "$fusion_tri_source_expansion_metadata_file" \
    --rrf-k "$rrf_k" \
    --source bm25 "$bm25_results_file" "$fusion_weight_bm25" "$fusion_topk_bm25" \
    --source rm3 "$rm3_results_file" "$fusion_weight_rm3" "$fusion_topk_rm3" \
    --source rm3exp "$rm3_expansion_results_file" "$fusion_weight_rm3_expansion" "$fusion_topk_rm3_expansion" \
    --source dense "$dense_results_file" "$fusion_weight_dense" "$fusion_topk_dense"

  if [[ "$rewrite_enabled" -eq 1 ]]; then
    python3 "$repo_root/tools/fuse_runs.py" \
      --output "$tri_source_expansion_rewrite_output" \
      --metadata-file "$fusion_tri_source_expansion_rewrite_metadata_file" \
      --rrf-k "$rrf_k" \
      --source bm25 "$bm25_results_file" "$fusion_weight_bm25" "$fusion_topk_bm25" \
      --source rm3 "$rm3_results_file" "$fusion_weight_rm3" "$fusion_topk_rm3" \
      --source rm3exp "$rm3_expansion_results_file" "$fusion_weight_rm3_expansion" "$fusion_topk_rm3_expansion" \
      --source rewrite "$rewrite_results_file" "$fusion_weight_query_rewrite" "$fusion_topk_query_rewrite" \
      --source dense "$dense_results_file" "$fusion_weight_dense" "$fusion_topk_dense"
  fi
fi

{
  cat <<EOF
JASSJR_ABLATION_BM25_ONLY: $bm25_only_output
JASSJR_ABLATION_BM25_RM3_FUSION: $bm25_rm3_output
JASSJR_ABLATION_BM25_RM3_EXPANSION_FUSION: $bm25_rm3_expansion_output
EOF
  if [[ "$rewrite_enabled" -eq 1 ]]; then
    printf 'JASSJR_ABLATION_BM25_RM3_RM3EXP_REWRITE_FUSION: %s\n' "$bm25_rm3_expansion_rewrite_output"
  fi
  if [[ "$semantic_mode" != "off" ]]; then
    printf 'JASSJR_ABLATION_BM25_DENSE_FUSION: %s\n' "$bm25_dense_output"
    printf 'JASSJR_ABLATION_BM25_RM3_DENSE_FUSION: %s\n' "$tri_source_output"
    printf 'JASSJR_ABLATION_BM25_RM3_RM3EXP_DENSE_FUSION: %s\n' "$tri_source_expansion_output"
    if [[ "$rewrite_enabled" -eq 1 ]]; then
      printf 'JASSJR_ABLATION_BM25_RM3_RM3EXP_REWRITE_DENSE_FUSION: %s\n' "$tri_source_expansion_rewrite_output"
    fi
  fi
} > "$pipeline_metadata_file"

append_metadata "$rewrite_metadata_file"
append_metadata "$dense_build_metadata_file"
append_metadata "$dense_query_metadata_file"
append_metadata "$fusion_bm25_rm3_metadata_file"
append_metadata "$fusion_bm25_rm3_expansion_metadata_file"
append_metadata "$fusion_bm25_rm3_expansion_rewrite_metadata_file"
append_metadata "$fusion_bm25_dense_metadata_file"
append_metadata "$fusion_tri_source_metadata_file"
append_metadata "$fusion_tri_source_expansion_metadata_file"
append_metadata "$fusion_tri_source_expansion_rewrite_metadata_file"

candidate_output="$bm25_rm3_expansion_output"
if [[ "$rewrite_enabled" -eq 1 ]]; then
  candidate_output="$bm25_rm3_expansion_rewrite_output"
fi
if [[ "$semantic_mode" != "off" ]]; then
  candidate_output="$tri_source_expansion_output"
  if [[ "$rewrite_enabled" -eq 1 ]]; then
    candidate_output="$tri_source_expansion_rewrite_output"
  fi
fi

if [[ "$openai_mode" == "off" ]]; then
  write_off_metadata
  cat "$candidate_output" > "$final_results_file"
else
  python3 "$repo_root/tools/openai_rerank.py" \
    --repo-root "$repo_root" \
    --workdir "$workdir" \
    --topics-file "$topics_stdin_file" \
    --run-file "$candidate_output" \
    --output-file "$final_results_file" \
    --metadata-file "$rerank_metadata_file"
  append_metadata "$rerank_metadata_file"
fi

if [[ -n "$metadata_file" ]]; then
  cp "$pipeline_metadata_file" "$metadata_file"
fi
cat "$final_results_file"
