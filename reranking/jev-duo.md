# Experiment 1: JEV duo with Noul

[Issue #72](https://github.com/carlaiau/ir-autoresearch/issues/72).
This experiment applies the original duoBERT **Sum** aggregation idea to JEV
Noul probabilities. It uses complete articles rather than duoBERT's truncated
BERT inputs; it is not a reproduction of the trained duoBERT checkpoint.

Completed: **rejected configuration**, MAP 0.3019 versus input 0.3055.
See the [measured outcome](results/jev-duo-noul-top20-20260918/summary.md).

## Fixed protocol

Start with the saved [whole-document JEV pointwise run](results/jev-full-documents-top100-20260918/results.md),
MAP **0.3055**, derived from the frozen lexical stage-1 MAP **0.2521** run.
For each of the 50 topics:

1. Select the first 20 documents from that pointwise ranking.
2. Compare every ordered pair, including both A/B and B/A orientations:
   20 × 19 = **380 requests per query**, **19,000 overall** before retries.
3. Send the query and two complete parsed articles to pinned **jev-1.13.0**.
   Ask Noul whether A provides more useful information relevant to the query
   than B. Equal or lesser usefulness belongs to the false criterion.
   No document ranks, prior scores, or relevance judgements are sent.
4. Score each document by summing its 19 outgoing Noul probabilities. Do not
   assume the reverse probability is the complement, or blend in pointwise scores.
5. Sort the top 20 by that sum, preserving pointwise order for ties. Preserve
   document order at ranks 21 onward. No indexing changes are required.

Eight requests can be in flight within each query. SDK retries are disabled;
explicit retries for transient errors are journaled, with at most three attempts
per comparison. A fresh pairwise cache prevents contamination by earlier runs.
Cache identity includes orientation, full payload, prompt, model and endpoint.

## Context and evidence

Never truncate silently. The preflight records serialized request character
sizes, not guessed tokenizer counts. If the provider rejects a complete pair,
the run fails and preserves partial evidence instead of changing the experiment.
Raw article content and cached responses remain local and ignored. Committed
score journals contain article hashes/lengths, probability, model, usage, timing
and request identity; the collection hash pins the source text.

Report MAP, Rprec, P_10, bpref and reciprocal rank against both pointwise and
lexical inputs. Also report paired AP changes, candidate recall@20, complete
ordered-pair coverage, and orientation diagnostics. Both directions scoring below
0.5 can indicate a tie; it is not automatically an error. All settings are
exploratory on these 50 topics, not held-out confirmation.

Record actual attempts, retries, cache hits, returned input/output tokens,
estimated API cost, total duo time and query p50/p95. Local compute cost is
unknown. A separate composed total adds saved pointwise time/cost and lexical
search time; it is not a freshly measured integrated benchmark. Failed-request
billing is unknown. Do not include unrelated prior failed passage experiments in
the composed pointwise→duo cost.

## Run

Use the same pinned environment as the pointwise experiment and provide
`TYPESAFE_API_KEY` via the environment or ignored `.env` files. For an isolated
worktree, `--env-root` may point to the existing checkout containing those files.

```bash
python reranking/jev_duo.py \
  --results-dir reranking/results/jev-duo-noul-top20-20260918 \
  --cache .cache/jev-duo-noul-top20-20260918 \
  --input-usd-per-million 0.042 --output-usd-per-million 0 \
  --pricing-source 'https://typesafe.ai/blog/introducing-system-one-models-and-jev; verified 2026-09-18'
```

Results directories must be new. `--cache-only` supports offline reproduction,
with its timing and new-request cost explicitly distinct from an uncached run.
Run `JEV_PYTHON=/path/to/python ./tests/jev_duo.sh` for offline contract checks.

Choice with more than two options is a separate future experiment.

References: [original duoBERT](https://arxiv.org/abs/1910.14424),
[Noul semantics](https://docs.typesafe.ai/primitives/noul),
[JEV models](https://docs.typesafe.ai/models).
