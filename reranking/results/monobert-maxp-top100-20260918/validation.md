# WSJ monoBERT validation

The first full-document MaxP run improved MAP from **0.2521 to 0.2693** (+6.8%).
The stage-1 index, saved candidates, topics and qrels were unchanged. This is one
exploratory measurement, not a repeated latency benchmark or a held-out claim.

## Configuration and timing

- Apple M3 Pro, 36 GiB RAM, macOS 26.4, Apple GPU via MPS, float32.
- Pinned 335,143,938-parameter `castorini/monobert-large-msmarco` checkpoint;
  model/library revisions are in [manifest.json](manifest.json).
- Top 100 per query; 384 document tokens per passage, overlap 64; batch size 8.
- Model prefetched before inference (119.932 s download/setup, excluded from run).
  Dependency installation was also excluded and was not timed.
- No warm-up phase, score cache, hosted inference, retries or device fallback.
- Reranking: 1,510.927 s; run wall time through evaluation: 1,511.404 s.
- Per-query p50: 30.269 s; p95: 42.189 s, excluding shared extraction/model load/tokenization.
- Composed search time: saved stage-1 0.687 s + reranking = 1,511.614 s.
- Hosted inference calls/cost: 0 / $0. Local compute cost is unknown by user choice.

## Independent checks against saved evidence

After completion, a separate audit read every [passage record](passages.jsonl)
and checked token intervals, no gaps, the final document tail, finite scores and
model input sizes no greater than 512. It reconstructed MaxP ordering directly
from saved scores and checked every final run row against that ordering and the
untouched stage-1 tail. It verified the source run/data hashes against the frozen
baseline and recomputed batch counts per query.

All checks passed: **5,000 query/document pairs**, **4,596 unique documents**,
**19,593 passage scores**, **2,475 successful model calls** (attempted counts match),
and **5,782,119 of 5,782,119 document-token positions covered** across query pairs.
The source hash in the manifest matches the evaluated implementation. The run was
made before committing the implementation, so its provenance correctly records
`dirty: true` and the parent commit, together with exact implementation hashes.

## Paired effectiveness

| Metric | Stage 1 | monoBERT | Delta |
| --- | ---: | ---: | ---: |
| MAP | 0.2521 | 0.2693 | +0.0172 |
| Rprec | 0.2989 | 0.3149 | +0.0160 |
| P_10 | 0.4460 | 0.4960 | +0.0500 |
| bpref | 0.3178 | 0.3368 | +0.0190 |
| recip_rank | 0.6271 | 0.6715 | +0.0444 |

AP improved for **35** topics, worsened for **14**, and tied for **1**, using
rounded per-topic trec_eval values. Mean candidate recall at 100 is **0.3121**;
reordering this candidate set cannot change its recall. Full-run recall is also
unchanged because the run retains every candidate.

[Paired analysis](paired-analysis.json), [baseline per-topic evaluation](stage1-trec_eval-per-topic.txt),
[reranked per-topic evaluation](trec_eval-per-topic.txt), and [query timings](queries.json).
The retrieval gain comes with substantial added latency. No comparison winner is
claimed while local cost is unknown and JEV/duoBERT measurements are pending.

## Implementation checks

Passed: `bash tests/monobert.sh` (six offline tests), `./tests/smoke.sh`,
`bash tests/two_stage.sh`, dependency `pip check`, Python compilation and
`git diff --check`. Tests cover tail relevance, window coverage, query budgets,
tie order, batching/cost arithmetic, immutable input hashes and failure handling.
No retriever code changed; the frozen stage-1 artifacts remain the comparison
baseline. Historical `original` artifacts were not modified.
