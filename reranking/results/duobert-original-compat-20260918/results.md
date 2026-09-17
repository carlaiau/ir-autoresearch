# Original duoBERT local compatibility check

**Original-code execution passed. Pretrained inference remains unverified because
the published checkpoint could not be downloaded.** This is a synthetic runtime
check, not a WSJ reranking experiment or a model port.

Issue: [#71](https://github.com/carlaiau/ir-autoresearch/issues/71).
Branch: `codex/search-duobert-original-compat`.
Test date: 2026-09-18 Pacific/Auckland (logs use 2026-09-17 UTC).

## What ran

- Unmodified [castorini/duobert](https://github.com/castorini/duobert/tree/24c7a16f847bad4ad79a07efc58d04bce70ebc6c),
  revision `24c7a16f847bad4ad79a07efc58d04bce70ebc6c`.
- Original `run_duobert_msmarco.py`, including TFRecord loading, `BertModel`,
  pairwise classifier, CPU Estimator fallback, probability-sum aggregation and
  prediction-file writing. Upstream source was mounted read-only.
- TensorFlow 1.15.5, Python 3.6, Ubuntu 18.04 x86_64 container on Docker Desktop
  29.2.0, running on an Apple M3 Pro with 36 GiB unified memory, macOS 26.4.
  Docker's VM has approximately 7.65 GiB RAM. This is emulated Intel **CPU**
  execution, not native ARM, MPS, CUDA or TPU inference.
- Image `tensorflow/tensorflow:1.15.5-py3`, pinned digest
  `sha256:181ff142e73ed8efe350f49288c7b0f5681fde66534a76d8de4fc75d4e30d571`.
- Two ordered pairs, A/B and B/A, one synthetic query, batch size 2.
  Each example has seven synthetic token IDs, padded to length 512; segment IDs
  are 0, 1 and 2. No WSJ text or downloaded model weights were used.
- Both a tiny two-layer model and BERT-large dimensions completed successfully.
  The large configuration has 24 layers, hidden size 1024, 16 attention heads,
  intermediate size 4096, vocabulary 30522 and three token-type embeddings.
  See [configuration](large-config.json).

Both runs use **random weights** (`--init_checkpoint=`). These are execution
checks only; synthetic labels and apparent metrics in the upstream logs have no
retrieval meaning. Random initialization is not seeded, so document order may
vary. Success requires both documents to be ranked, not a particular winner.

## Evidence and limitations

| Check | Outcome | Evidence |
| --- | --- | --- |
| TensorFlow import and real tensor operation | Passed | [Runtime log](runtime.log) |
| Original tiny evaluator | Passed | [Log](original-eval.log), [predictions](tiny-predictions.tsv) |
| Original BERT-large evaluator | Passed | [Log](original-large-eval.log), [predictions](large-predictions.tsv) |
| Repository smoke tests | Passed | [Log](repo-smoke.log) |
| Saved reproduction script at BERT-large dimensions | Passed | [Log](reproduction.log) |
| Pretrained checkpoint inference | Blocked by download access | See below |

Saved logs have trailing whitespace removed. Checkpoint HTTP evidence is
[recorded separately](checkpoint-access.txt), with cookies omitted.

The first tiny run reached inference but failed when writing into a missing
output directory. The [failure log](missing-output-directory.log) is retained;
creating that directory fixed the setup without modifying upstream code.

The large run took **14.69 seconds wall time** for container startup, fixture
generation, model construction, random initialization, inference on two padded
pairs, aggregation and output. It excludes the image download and is neither
steady-state model latency nor a WSJ per-query benchmark. Environment settings:
`OMP_NUM_THREADS=4`, `TF_NUM_INTRAOP_THREADS=4`, `TF_NUM_INTEROP_THREADS=2`.
Only one timed run is reported. No hosted inference API was called; local compute
cost is unknown.

The authors' published 3.43 GB checkpoint is
`duobert-large-msmarco-pretrained-and-finetuned.zip`, with advertised MD5
`dcae7441103ae8241f16df743b75337b`. On this test date:

- The original Dropbox share redirected to a newer share URL, which returned
  HTML rather than the model archive.
- Both the legacy and redirected direct-download endpoints returned HTTP 404.
- The authors' Waterloo mirror raw-file URL redirected to `/users/sign_in`.

These access results do not prove the checkpoint is unavailable everywhere.
An accessible original checkpoint, with checksum verification, is needed before
claiming pretrained inference works. No replacement checkpoint or PyTorch port
was substituted. The original runtime does not establish Apple GPU support.

## Reproduce

Requires a running Docker Desktop capable of `linux/amd64` execution, Git, gh,
and host Python 3. The image and source downloads need network access; inference
runs with container networking disabled. Run from the repository root:

```sh
mkdir -p .cache/duobert-original
gh repo clone castorini/duobert .cache/duobert-original/upstream
git -C .cache/duobert-original/upstream checkout 24c7a16f847bad4ad79a07efc58d04bce70ebc6c
docker pull --platform linux/amd64 tensorflow/tensorflow@sha256:181ff142e73ed8efe350f49288c7b0f5681fde66534a76d8de4fc75d4e30d571
bash tools/verify_duobert_original.sh \
  "$PWD/.cache/duobert-original/upstream" \
  "$PWD/.cache/duobert-original/new-large-check" --large
```

Use a new work directory for each invocation. Omit `--large` for the tiny
configuration. The helper verifies upstream revision and cleanliness, generates
synthetic input, invokes the original evaluator and checks the two output ranks.
Code/models/runtime files stay under ignored `.cache/`; only the fixture helper,
reproduction script and text evidence are committed.

## Fixed retrieval baseline

Stage 1 remains MAP **0.2521**, with no indexing or candidate changes.
No MAP, Rprec, P_10, bpref, recip_rank, candidate recall, per-topic changes or
end-to-end WSJ timing was measured here. Full paired evaluation is outside this
compatibility check and awaits a functioning pretrained reranker.

- Fixed folder: `stage1/results/integrated-main-20260918/`.
- Candidate SHA-256: `d1f737713de16e857ba69988ee85f5d30fef2bc4f4d6004d4ff73e87c7c9045b`.
- Manifest SHA-256: `65228181d2984dee1bfb8c98717e769fb114ec03fc3d03183ee145c0511485c5`.

Conclusion: the original TensorFlow implementation can execute locally at
BERT-large dimensions in a CPU container. Acceptance is limited to code/runtime
compatibility; pretrained retrieval quality and useful throughput are pending.
