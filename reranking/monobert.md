# Full-document monoBERT MaxP

Implementation: `monobert.py`. Tracking issue: [#66](https://github.com/carlaiau/ir-autoresearch/issues/66).

The stage-1 index and fixed MAP **0.2521** candidate run remain unchanged. This
reranker reads each shortlisted document in full and scores every overlapping
passage against the query. MaxP selects the highest passage score as the document
score. Only the selected prefix is reordered; the rest of the candidate run stays
in its existing order.

## Local model, not hosted inference

Use `castorini/monobert-large-msmarco`, pinned to revision
`0a97706f3827389da43b83348d5d18c9d53876fa`. Hugging Face supplies the model files;
PyTorch runs the model on this machine. Documents and queries are not uploaded to
an inference service. The model is loaded as a two-label relevance classifier;
missing/mismatched weights fail instead of silently initializing a new head.
Relevance is label 1 and scores are log-softmax probabilities, matching the
[upstream monoBERT implementation](https://github.com/castorini/pygaggle/blob/master/pygaggle/rerank/transformer.py).

This is BERT inference, not an instruction prompt sent to a chat model. Download
traffic is setup activity and is distinct from hosted inference calls. After
prefetch, `--local-files-only` requires all model files to be cached and prevents
Hugging Face downloads during the experiment. No score cache is used: every
passage is actually inferred on each run.

## Setup and run

From the repository root (Python 3.10+; tested with Python 3.13):

```sh
python3 -m venv .venv-monobert
.venv-monobert/bin/python -m pip install -r reranking/requirements-monobert.txt
.venv-monobert/bin/python reranking/prepare_monobert.py
.venv-monobert/bin/python reranking/monobert.py \
  --top-k 100 --batch-size 8 --local-files-only
```

The default input is the frozen `stage1/results/integrated-main-20260918/`.
Collection, topics, qrels and run hashes are checked before model loading.
`--collection` supports a relocated identical WSJ file. `--results-dir` must be a
new directory; by default results go under `reranking/results/<branch>/<run-id>/`.
The automatic device preference is CUDA, then Apple MPS, then CPU. Use
`--device cpu|mps|cuda` for controlled comparisons. All runs use float32.

## Full-document coverage

The collection reader joins by exact DOCNO, removes DOCNO and markup, decodes
entities and retains the other field contents, including headlines and multiple
TEXT blocks. It does not prefix-truncate articles. Tokenize each full candidate
document without adding special tokens or enabling truncation, then work directly
with those token IDs. Tokenization includes the pinned tokenizer's normal
uncasing/normalization; coverage is measured over its resulting token sequence.

The initial window size is 384 document tokens with 64-token overlap. The actual
capacity is the smaller of that size and the model's input limit minus the actual
query length and required special tokens. Reduce overlap if the remaining window
is smaller than 65 tokens. Queries are not silently truncated: a query leaving no
document budget fails. Every document's last partial window is included. There is
no maximum passage count and no passage selection/filtering step.

`passages.jsonl` records query ID, DOCNO, token start/end, score and newly covered
token count. The runner validates coverage intervals and verifies every original
document-token position was scored before writing a completed result. No article
text or token IDs are written to committed evidence. This guarantees coverage of
shortlisted documents, not retrieval of every document in the corpus or reasoning
across distant passages in one model pass.

## Calls, timing and cost

The generated **Calls, time and cost** table in `results.md` exposes the requested
measurements; detailed counters and scope are also in `manifest.json`.

| Measurement | Meaning |
| --- | --- |
| Query/document pairs | Number of candidate documents considered, summed over queries |
| Passage scoring calls | Individual query/passage examples successfully scored |
| Model forward calls | Actual successful batched model invocations; distinct from passage count |
| Attempted calls | Attempts retained in failure metadata, including a failed batch |
| Hosted inference API calls | Zero for this local implementation |
| Input tokens | All scored query/passage/special tokens, including overlap and repeated queries |
| Padded input tokens | Tokens allocated after each batch is padded; useful for compute comparisons |
| Model load | Model/tokenizer loading and device transfer; can include download if allowed |
| Extraction/tokenization | Separate setup times for complete document text and token sequences |
| Scoring | Per-query preparation, batched inference, aggregation and passage evidence writing |
| Inference | Synchronized model prediction, batch padding/transfers and score extraction |
| Reranking | Extraction, loading, tokenization, scoring and output generation |
| Query p50/p95 | Sequential per-query elapsed time after shared model/text/token setup |
| Composed end-to-end search | Saved stage-1 search time plus this run's reranking time |
| Run wall time | Validation through evaluation; excludes dependency installation, prior prefetch, interpreter startup and final report serialization |

Model calls are batched within each query, including across documents. With
batch size 8, 100 passage scores usually need 13 forward calls. Calls on different
queries are not merged into one batch. No automatic OOM retry or silent CPU
fallback changes the measurement; failures are explicit. CPU/GPU synchronization
is included so asynchronous dispatch is not mistaken for completed inference.

Hosted inference API cost is **$0**. Local compute cost is **unknown** until an
hourly rate is supplied. It is estimated from measured run wall time:

`estimated_compute_cost_usd = total_wall_seconds / 3600 × compute_usd_per_hour`

For example, append the following only if $1/hour is your documented assumption:

```sh
--compute-usd-per-hour 1 --pricing-source 'Assumed workstation rate, USD, YYYY-MM-DD'
```

The rate must be finite and non-negative, with a source/date or explicitly stated
internal assumption. The separate reranking-only estimate excludes verification
and trec_eval. Neither estimate is an invoice or measured electricity consumption.
Dependency installation, model prefetch and stage-1 compute are outside that cost
scope. Pre-download before an inference benchmark; keep setup time separate.

No hosted Hugging Face inference adapter is implemented. That would require a
separate provider/deployment, pricing and per-request usage accounting.

## Evidence and validation

Each completed run includes `results.md`, `manifest.json`, `run.trec`, aggregate
and per-topic trec_eval, passage coverage/scores, and `queries.json`. `progress.json`
tracks completed queries; failures get `failure.json` and no accepted result.

Run `bash tests/monobert.sh` for offline tests of tail relevance, overlap coverage,
query-budget handling, MaxP ordering, batch counts, cost arithmetic, immutable
baseline files and failure isolation. Synthetic tests validate behavior only;
actual WSJ results are required to claim a retrieval gain. Compare MAP, Rprec,
P_10, bpref and reciprocal rank on the fixed baseline. Full-document monoBERT and
24,000-character JEV have different content policies; report that difference.

## First WSJ measurement

[Full result](results/monobert-maxp-top100-20260918/results.md), top 100 candidates
for each of 50 topics: MAP **0.2693** versus **0.2521** (+0.0172, +6.8%).
All five headline metrics improved. This is an exploratory evaluation, with no
claim of held-out tuning or superiority to other methods. The subsequent
[JEV comparison](results/jev-comparison-20260918.md) is now complete; duoBERT remains
pending.

On an Apple M3 Pro with 36 GiB memory, MPS and float32, this run scored **19,593
passages in 2,475 model calls**. Reranking took **1,510.93 seconds** including shared
setup; query p50/p95 were **30.27 / 42.19 seconds** excluding shared setup. Hosted
inference API cost was **$0**, while local compute cost remains **unknown**, as
requested. No indexing changes or hosted inference requests were made.

The [validation report](results/monobert-maxp-top100-20260918/validation.md) records
coverage checks and paired AP changes. Quality improved at substantial added
latency; this is an experimental reranker, not an established cost/latency winner.
