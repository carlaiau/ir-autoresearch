# Stage 2: reranking research

Compare rerankers on the **fixed stage-1 MAP 0.2521 baseline, before all
reranking**. Stage 2 reads its saved candidates and writes separate reports under
`reranking/results/`. Indexing and the frozen lexical run are unchanged.

## Implementations and results

| Method | Scoring unit and document score | MAP |
| --- | --- | ---: |
| [monoBERT MaxP](monobert.md) | Query + each passage; maximum passage score | 0.2693 |
| [JEV passage MaxP](jev-comparison.md) | Query + each identical monoBERT window; maximum Noul score | 0.3053 |
| [JEV complete document](jev-comparison.md) | Query + entire parsed article; one Noul score | 0.3055 |
| duoBERT | Query + document pair; pair selection/aggregation still to implement | Planned |

See the [paired JEV comparison](results/jev-comparison-20260918.md) for all five
metrics, calls, latency, API cost, coverage audits and failed-attempt spend.
Completed JEV runs use served model JEV 1.13.0, top 100 and eight concurrent calls
per query. The passage run scored all 19,593 monoBERT windows; the complete-document
run scored 5,000 query/document pairs without a character cap. Local compute
cost remains unknown by user choice.

## Reproduce JEV

Follow the [run commands](jev-comparison.md#run) for `jev_compare.py`. Install the
pinned SDK and configure `TYPESAFE_API_KEY` in the environment or ignored `.env` /
`.env.local`. Use separate fresh caches for uncached comparisons. The runner
verifies the fixed input hashes and every saved monoBERT passage boundary before
making requests. Raw response caches remain local and ignored.

JEV uses TypeSafe System One with the existing Noul relevance question: whether
the candidate article provides substantive information relevant to the query.
Noul yields a score in [0,1]. The pointwise decision is made independently for
each passage or document; it is not a monoBERT checkpoint or architecture.
Qrels are used only for evaluation and are never sent to the API.

The older `jev.py` / `run.py` interfaces retain their historical 24,000-character
cap and default K=200. They were not used for the new experiments. The current
comparison runner takes K=100 from the saved monoBERT manifest and applies no
content cap. See [JEV history](jev.md).

## Comparison contract

Freeze the stage-1 run/data hashes, topics, qrels and candidate depth. Retain all
candidates and untouched tails; stable ties preserve stage-1 ordering. Reranking
cannot change recall of that candidate set. Report MAP, Rprec, P_10, bpref and
reciprocal rank, paired per-topic changes and candidate recall at K.

Match content policies where possible and record differences. For JEV passages,
text is decoded from the original BERT token slices; whole-document inputs retain
the original parsed text. Different tokenizers and normalization are explicit
comparison limitations. Retain exact model versions and payload/coverage hashes.

Report successful scores, actual API attempts, failures, cache hits, returned
usage, estimated costs and assumptions. Unknown cost is not zero. Client-cache
replay is a reproducibility check, never uncached performance. Include failed
attempts in total experiment spend and distinguish estimates from invoices.

Measure shared setup, total reranking, and per-query p50/p95 separately. Composed
search time adds the saved lexical time and reranking time; it is not a fresh
integrated benchmark. State concurrency, batching, hardware, network and warm-up
scope. The present results are single uncached runs, not repeated benchmark
medians; hosted JEV and local Apple-GPU BERT are different execution environments.

Treat settings selected on topics 51–100 as exploratory, not held-out proof.
Assess measured quality/time/cost tradeoffs; do not apply lexical-only slowdown
thresholds to neural rerankers or declare a universal winner from one metric.
The [monoBERT/duoBERT paper](https://arxiv.org/abs/1910.14424) motivates comparisons
across depth and latency. A mono→duo cascade belongs within stage 2; report its
component and combined time/cost, pair selection, orientation and aggregation.
