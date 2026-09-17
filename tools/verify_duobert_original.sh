#!/usr/bin/env bash
# Original source smoke check, with synthetic inputs and RANDOM weights.
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
upstream="${1:?Usage: bash tools/verify_duobert_original.sh /absolute/upstream /absolute/new-workdir [--large]}"
work="${2:?Supply a new work directory}"
size="${3:-}"
revision=24c7a16f847bad4ad79a07efc58d04bce70ebc6c
image=tensorflow/tensorflow@sha256:181ff142e73ed8efe350f49288c7b0f5681fde66534a76d8de4fc75d4e30d571
[[ "$upstream" = /* && "$work" = /* ]] || { echo 'Use absolute paths' >&2; exit 1; }
[[ -z "$size" || "$size" = --large ]] || { echo 'Only --large is supported' >&2; exit 1; }
[[ "$(git -C "$upstream" rev-parse HEAD)" = "$revision" ]] || { echo 'Wrong upstream revision' >&2; exit 1; }
[[ -z "$(git -C "$upstream" status --porcelain)" ]] || { echo 'Upstream must be unchanged' >&2; exit 1; }
[[ ! -e "$work" ]] || { echo 'Work directory must be new; prevents cached/resumed output' >&2; exit 1; }
mkdir -p "$work/output"
docker run --rm --platform linux/amd64 --network none \
  -e OMP_NUM_THREADS=4 -e TF_NUM_INTRAOP_THREADS=4 -e TF_NUM_INTEROP_THREADS=2 \
  -v "$upstream:/upstream:ro" \
  -v "$repo_root/reranking/duobert_original_fixture.py:/fixture.py:ro" \
  -v "$work:/work" -w /upstream "$image" bash -c '
    set -euo pipefail
    python /fixture.py /work/data "$1"
    python run_duobert_msmarco.py \
      --data_dir=/work/data --bert_config_file=/work/data/bert_config.json \
      --output_dir=/work/output --init_checkpoint= --max_seq_length=512 \
      --do_train=False --do_eval=True --eval_batch_size=2 \
      --num_eval_docs=2 --use_tpu=False
  ' bash "$size" > "$work/execution.log" 2>&1
python3 - "$work/output/msmarco_predictions_dev.tsv" <<'PY'
import sys
from pathlib import Path
rows = [line.split('\t') for line in Path(sys.argv[1]).read_text().splitlines()]
assert len(rows) == 2, rows
assert {row[0] for row in rows} == {'synthetic-query'}, rows
assert {row[1] for row in rows} == {'A', 'B'}, rows
assert [row[2] for row in rows] == ['1', '2'], rows
print('PASS: unchanged original evaluator ranked both synthetic documents; random weights only.')
PY
printf 'Log: %s/execution.log\n' "$work"
