# Repository Agent Guide

Explicit user instructions take precedence. Use the `gh` CLI for all GitHub
interaction; do not use the GitHub connector/plugin.

## Purpose and scope

This repository compares reranking methods on a fixed WSJ/TREC candidate set.
Stage 1 is lexical retrieval; stage 2 is reranking. For bounded maintenance or
documentation requests, complete the requested work without starting experiments.

Read before changes:

- `README.md`
- `program.md`
- `stage1/README.md`
- `reranking/README.md`
- `index/JASSjr_index.go`
- `search/JASSjr_search.go`
- `tools/eval_wsj.sh`
- `tools/benchmark_wsj.sh`

The repository uses shell smoke tests, not Bats. An actual WSJ experiment requires
an absolute path to the collection file; discover it locally or ask if unavailable.

## Fixed baseline

**MAP 0.2521 before all reranking** is the sole stage-1 baseline, saved in
`stage1/results/integrated-main-20260918/`. Use its exact candidate run, topics,
qrels and manifest hashes for every reranker experiment. The manifest records
BM25, query-expansion settings and `JASSJR_RERANK_DOCS=0`.

Main is the code integration branch, not a moving experimental baseline. New
lexical evaluation runs and changes to main do not replace the fixed baseline.
Any proposed replacement requires an explicit decision.

Previous JEV results have been discarded. Follow `reranking/jev.md` for the
pending top-100 JEV rerun, using a new empty cache for uncached time/cost evidence.
Do not claim any JEV effectiveness or performance result before that run completes.

The `original` evaluation/benchmark folders remain read-only initialization
history, not an approval baseline. The mixed branch dashboard is retired. Do not
use legacy exporters or branch-vs-main artifact comparisons for current approval.

## Collection integrity

WSJ is a single file containing repeated `<DOC>...</DOC>` records. DOCNO supplies
the retrieval document ID. Useful text includes headlines and may span multiple
fields; entities such as `&amp;` occur. Preserve document boundaries, exact DOCNO
association and the declared field/normalization policy when changing parsers.

## Git and experiment workflow

- Inspect local state and GitHub issues/PRs with gh before starting work.
- Use a fresh `codex/search-<tag>` branch for each distinct hypothesis.
- Never overwrite unrelated user changes, use destructive git commands or reuse
  rejected experiment branches for unrelated work.
- Do not merge into main without explicit user authorization.
- Create an issue for each experiment unless continuing an existing one. Use
  `Experiment: <specific idea>` and include hypothesis, files, acceptance criteria,
  retrieval metrics and timing/cost risks.
- Make the smallest change that tests the hypothesis. Keep the fixed stage-1 input.
- Run `./tests/smoke.sh`, relevant reranking contract tests and the actual paired
  evaluation. Use `bash tests/two_stage.sh` for stage-boundary changes.
- Record MAP, Rprec, P_10, bpref and recip_rank against the fixed baseline, candidate
  recall at K, per-topic changes, reranking/end-to-end time, cache state and cost.
- Preserve accepted and rejected experiment code plus final branch-local evidence.
  Commit and push experiment branches, including rejected attempts. Record results,
  rejection reasons and commit hashes on the issue; do not reset rejected history.
- Open PRs only for accepted experiments. Maintenance PRs describe their actual
  change and verification without inventing retrieval improvements.

For autonomous research explicitly requested by the user, continue with a new
hypothesis after completing the accepted/rejected path until stopped or blocked.
This does not authorize an experiment loop for ordinary documentation work.

## Effectiveness and performance

MAP is the headline metric. Compare rerankers using the same saved candidates,
query set and judgments. Record model/checkpoint, content coverage or truncation,
worker/batch settings, device and pricing assumptions. Tune on development data;
settings selected on evaluation topics are exploratory rather than held-out proof.

Report cached replay separately from uncached inference. Unknown time or cost is
not zero. Assess rerankers by measured effectiveness/time/cost tradeoffs, not MAP
alone. For a separately authorized lexical change, benchmark against a controlled
lexical baseline: <=5% median slowdown is acceptable; >5% to 15% needs a worthwhile
retrieval gain; >15% indexing or search slowdown is rejected by default.

## Artifacts and reporting

Current reports and their raw evidence belong in:

- `stage1/results/` — the fixed baseline and clearly labeled verification runs.
- `reranking/results/` — experiments identifying the fixed stage-1 manifest/run.

Preserve the canonical run, raw trec_eval, topics, qrels and manifest unchanged.
Commit final experiment evidence. Never commit WSJ article text, API secrets or
cache contents. Never modify/recommit original archive artifacts. Legacy
`experiment_evaluations/` and `experiment_benchmarks/` are not active comparisons.
Do not regenerate the retired README branch leaderboard.

PRs should include hypothesis (for experiments), change, metrics and deltas,
timing/cost scope, evidence links, validation and issue link where applicable.
Distinguish pending, failed and completed runs. At completion, report issues,
branches/PRs, accepted/rejected experiments, results versus stage 1 and blockers as
applicable to the task. Do not invent fresh results for documentation-only work.
