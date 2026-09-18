# Two-stage research program

The [MS MARCO / TREC DL 2019 pointwise benchmark](reranking/msmarco.md), issue #73,
is an explicitly authorized additional dataset. It uses frozen supplied passage
candidates and a monoBERT reference, with nDCG@10 as its primary metric. Keep its
artifacts and conclusions separate from WSJ. The current scope excludes pairwise
JEV and new context-window strategies; those are follow-up work.

Read AGENTS.md, stage1/README.md and reranking/README.md before experimenting.
The immediate objective is reranking research: improve effectiveness and quantify
the additional search time and cost on an unchanged candidate set.

## Stage 1: establish and freeze the input

The stage-1 baseline is fixed at **MAP 0.2521 before all reranking**, saved under
`stage1/results/integrated-main-20260918/`. Use its exact candidates, topics, qrels
and hashes for every reranker experiment. The raw trec_eval and configuration are
already saved; no new stage-1 run is needed before the JEV rerun.

Lexical verification runs do not replace the baseline. Changes to main do not
replace it either. Propose any baseline replacement explicitly.

## Stage 2: reranking experiment loop

1. Inspect repo state and GitHub issues/PRs using gh CLI; avoid duplicate work.
2. Choose a concrete reranking hypothesis and create an experiment issue.
3. Work on a fresh codex/search-<tag> branch. Main is the code approval baseline;
   the frozen lexical run is the effectiveness baseline for the reranker.
4. Compare JEV on identical monoBERT passages (MaxP) and complete uncapped
   documents at top-k 100 with separate fresh caches. Follow
   `reranking/jev-comparison.md`. These two user-requested experiments may share
   one branch. Previous JEV results have been discarded.
5. Run smoke and reranking contract tests. Compare MAP, Rprec, P_10, bpref and
   reciprocal rank against the exact stage-1 run. Record candidate recall at K,
   per-topic changes, reranking and composed end-to-end time, and cost.
6. Repeat timing runs under controlled cache, hardware, concurrency and warm-up
   conditions. Unknown dollar cost is not zero. Use verified model-specific rates.
7. Compare monoBERT and duoBERT only when adapters exist and their measurements
   share the same data/candidates and explicit content/batching policies.
8. Preserve accepted and rejected experiment code and final result artifacts.
   Commit/push experiment branches and document results on the issue. Open PRs
   only for accepted experiments; never reset rejected history or merge without
   explicit user instruction. Follow AGENTS.md's issue and PR requirements.

For lexical changes retain the AGENTS.md performance guardrails (over 15% median
slowdown is rejected by default). For stage 2, explicitly assess the measured
quality/latency/cost tradeoff; a neural reranker cannot be approved from MAP alone
when time or cost is unknown. Selecting depths on the evaluation topics is
exploratory evidence, not held-out validation.

## Artifact policy

New result Markdown files live separately in stage1/results/ and
reranking/results/, alongside their raw outputs and manifests. Commit final
branch-local evidence for accepted and rejected experiments. Never include WSJ
article text, secrets or API cache contents. Do not refresh or overwrite original
archive folders. Do not commit refreshed main artifacts unless requested.

The mixed legacy branch dashboard is retired. Report only the fixed stage-1
baseline and rerankers actually evaluated on its exact candidates. Do not
regenerate the legacy leaderboard. Original artifacts remain read-only history.

Full-document monoBERT MaxP is implemented and its first uncached WSJ run is
saved under `reranking/results/monobert-maxp-top100-20260918/`: MAP 0.2693,
1,510.93 seconds of added reranking time. Local compute cost remains unknown by
user choice. This supports an experimental implementation, not a cost/latency
winner or a production recommendation. The JEV passage-MaxP and complete-document
runs are now complete; see `reranking/results/jev-comparison-20260918.md` for their
paired effectiveness, timing, cost and preserved failed-attempt evidence.
