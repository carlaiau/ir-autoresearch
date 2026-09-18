# JEV duo with Noul: rejected configuration

[Issue #72](https://github.com/carlaiau/jev-reranking/issues/72) ·
[Protocol](../../jev-duo.md) · [Raw report](results.md) · [Audit](audit.txt)

The top-20 pairwise pass **does not improve** its pointwise input: MAP drops
from **0.3055 to 0.3019** (−0.0036, approximately −1.18%). It adds 837.984 seconds
and an estimated $2.305419 in successful-response API usage. Preserve this
configuration as a negative experiment; keep pointwise JEV as the stronger
measured result. No replacement of the frozen stage-1 baseline is proposed.

| Metric | Stage 1 | Pointwise JEV input | Pointwise → duo | Delta vs pointwise |
| --- | ---: | ---: | ---: | ---: |
| MAP | 0.2521 | 0.3055 | 0.3019 | −0.0036 |
| Rprec | 0.2989 | 0.3248 | 0.3237 | −0.0011 |
| P_10 | 0.4460 | 0.6340 | 0.6200 | −0.0140 |
| bpref | 0.3178 | 0.3533 | 0.3515 | −0.0018 |
| recip_rank | 0.6271 | 0.8063 | 0.8072 | +0.0009 |

Compared with the pointwise input, topic AP improves for 20 topics, declines for
20, and ties for 10 (using trec_eval's reported precision). Candidate recall@20
is 0.170098, unchanged by reordering those same documents. This is recall of all
known relevant documents in the top-20 pool, not precision@20.

## Calls, cost and time

| Measurement | Duo pass only | Pointwise + duo |
| --- | ---: | ---: |
| Successful scores | 19,000 | 24,000 |
| Actual API attempts | 19,010 | 24,010 |
| Failed attempts, subsequently recovered | 10 | 10 |
| Client-cache hits | 0 | 0 |
| Estimated successful-response API cost | $2.305419 | $2.633731 |
| Reranking wall time, all 50 topics | 837.984 s | 1,049.477 s |
| Search including saved lexical pass | — | 1,050.164 s |
| Query p50 | 15.050 s | Not measured |
| Query p95 | 19.070 s | Not measured |

Duo shared preparation: 3.539 seconds. Query percentiles exclude shared setup;
all timings include retries when they occur. Eight concurrent requests within
each query; single uncached run. The combined column adds the saved pointwise
run, so it is a composed estimate rather than a fresh end-to-end measurement.
It costs about 8.02× and takes about 4.96× the reranking time of pointwise alone,
while lowering MAP. No extra indexing or lexical retrieval run was performed.

Returned duo usage: **54,890,924 input tokens**, **456,000 output tokens**.
Pricing: $0.042 per million input tokens, output free, using the
[documented JEV rate](https://typesafe.ai/blog/introducing-system-one-models-and-jev).
Eight HTTP 529 errors and two timeouts recovered. Any charges for those failed
attempts are unknown; estimates are not invoices. Local compute remains unknown.
Earlier failed passage runs are unrelated and excluded from this cascade's cost.

## Evidence and limitations

All 19,000 ordered comparisons used pinned JEV 1.13.0 and two complete parsed
articles. No truncation or context-limit rejection occurred. The largest
serialized request was 42,546 characters. The audit verifies both orientations,
full-text and payload hashes, model version, Sum aggregation, stable ties,
unchanged document order below rank 20, source/run hashes and usage accounting.
See [score journal](scores.jsonl), [attempt journal](attempts.jsonl),
[document sums](document-scores.json), [paired topics](pointwise-paired.json),
and [manifest](manifest.json). No article content or credentials are committed.

Across 9,500 unordered pairs, **2,596 (27.33%)** have both orientations above 0.5;
421 (4.43%) have both below 0.5. Mean absolute deviation of p(A>B)+p(B>A) from
one is 0.157548. Mutual preference is a useful inconsistency diagnostic;
both-below-half can reflect ties under the false criterion. These observations
do not establish the cause of the quality regression. The primary ranking uses
unaltered outgoing sums, without post-result symmetrization or prompt tuning.

This rejects this particular full-document Noul prompt/depth/aggregation
configuration on these 50 topics. It does not establish that every JEV pairwise
method fails. Choice with more than two options remains a separate experiment.

Smoke tests, five duo contract/integration tests, five existing JEV comparison
checks, and the full-result audit passed. The implementation was clean at run
start, commit `ea27881f59daf13b7fb1604d1a1c681cd54a5f6a`; its source hashes
are in the manifest. Later commits add tests and reporting without changing
that runner. The read-only original archive is historical, not the baseline.
