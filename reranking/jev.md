# JEV experiment: rerun on the fixed stage-1 baseline

Status: **pending rerun**. No JEV effectiveness, latency or cost result is accepted
yet. Previous evaluations have been discarded and must not be cited as evidence
for this experiment.

## Fixed input

Use `stage1/results/integrated-main-20260918/`, the sole baseline with
**MAP 0.2521 before all reranking**. Its candidate-run SHA-256 is
`d1f737713de16e857ba69988ee85f5d30fef2bc4f4d6004d4ff73e87c7c9045b`.
Use its saved topics and qrels; do not regenerate candidates or substitute a
combined fusion/API-pipeline run.

## Hypothesis and method

JEV pointwise relevance scoring improves the order of the top 100 candidates
per query relative to stage 1. Keep the existing relevance question, 24,000-character
article policy and eight workers fixed for this rerun; record truncation counts.
This is the existing JEV method, not the proposed full-document monoBERT method.
Use the requested model and actual returned model IDs in the report. A mutable
model alias is not sufficient provenance on its own.

```sh
python3 reranking/run.py stage1/results/integrated-main-20260918 \
  --top-k 100 --workers 8 --max-chars 24000 \
  --cache wsj-eval/jev-stage1-02521-fresh
```

Use the Python environment containing `tools/requirements-jev.txt` and configure
TYPESAFE_API_KEY. The first timing/cost run must use a new empty cache directory;
if this named cache already exists, choose another fresh name. Preserve its
responses afterward for cache-only reproducibility checks. Do not reuse an old
JEV cache to represent a fresh uncached experiment.

## Required evidence

Save the reranked run, raw trec_eval, paired MAP/Rprec/P_10/bpref/recip_rank deltas,
per-topic changes and candidate recall at K. Report reranking batch time and
end-to-end search time separately, with repeated uncached measurements where
budget permits. Record model, concurrency, content policy, cache hits, API calls,
input/output tokens and truncation counts.

Supply model-specific input/output USD rates and a dated pricing source to
estimate spend; missing prices remain unknown. Report cache-only timing separately
from uncached inference. Results belong in a new `reranking/results/` directory
and must reference the fixed baseline's run and manifest hashes.

Only after this rerun completes should the repository show JEV metrics or discuss
its effectiveness/time/cost tradeoff against the baseline. This documentation
update does not claim that the rerun has already happened.
