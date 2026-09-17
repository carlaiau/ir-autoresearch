# Two-stage research program

Read AGENTS.md, stage1/README.md and reranking/README.md before experimenting.
The immediate objective is reranking research: improve effectiveness and quantify
the additional search time and cost on an unchanged candidate set.

## Stage 1: establish and freeze the input

Read the Go index/search sources and confirm the absolute WSJ collection path.
Refresh main in a clean checkout when establishing an approval baseline; preserve
unrelated working changes. Run smoke tests, `python3 stage1/run.py <WSJ>` and
`./tools/benchmark_wsj.sh <WSJ>`. Preserve the complete stage-1 result directory,
including results.md, raw trec_eval, run and data/configuration hashes. Document
BM25 and existing feedback as a single candidate-generation stage.

Freeze this input across a reranker comparison. Any lexical change requires a new
stage-1 baseline and a separate comparison cohort, not a silent replacement.

## Stage 2: reranking experiment loop

1. Inspect repo state and GitHub issues/PRs using gh CLI; avoid duplicate work.
2. Choose a concrete reranking hypothesis and create an experiment issue.
3. Work on a fresh codex/search-<tag> branch. Main is the code approval baseline;
   the frozen lexical run is the effectiveness baseline for the reranker.
4. Start with JEV pointwise scoring. Run `python3 reranking/run.py <stage1-dir>`
   with an explicit candidate depth and record configuration, model and cache mode.
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

Legacy experiment_evaluations/, experiment_benchmarks/ and docs/metrics/ are
historical records. Their exporters and README dashboard do not yet consume stage
manifests. Keep stage reports authoritative for new work; do not combine legacy
lexical timings with reranked effectiveness and label that an end-to-end benchmark.

This restructuring is a bounded maintenance task; it does not start an unbounded
experiment loop or authorize paid runs merely to validate the folder migration.
