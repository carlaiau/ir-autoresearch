# Search Agent Program

This repository is for autonomous retrieval experiments on a compact search engine implementation. The agent's job is to improve end-to-end retrieval effectiveness on the WSJ/TREC setup while avoiding serious indexing and search-time regressions.

## Mission

Optimize the indexing and searching strategy in:

- `index/JASSjr_index.go`
- `search/JASSjr_search.go`

The system is judged primarily by `trec_eval` results on the shipped WSJ topics/qrels:

- `51-100.titles.txt`
- `51-100.qrels.txt`

Every accepted change must improve overall retrieval effectiveness, and must not introduce a serious regression in indexing or search latency.

## Setup

Before experimentation begins, do this once per run:

1. Choose a run tag based on the date and idea family.
2. Use `main` as the starting point for the next dedicated experiment branch:
   - Branch name format: `codex/search-<tag>`
3. Read the in-scope files:
   - `README.md`
   - `program.md`
   - `index/JASSjr_index.go`
   - `search/JASSjr_search.go`
   - `tools/smoke_eval.sh`
   - `tools/eval_wsj.sh`
   - `tools/benchmark.sh`
   - `tools/benchmark_wsj.sh`
   - `tools/update_metrics_dashboard.sh`
4. Confirm the WSJ collection file exists on disk.
5. Refresh the active baseline on `main` before starting a new research loop:
   - `git checkout main`
   - `git pull --ff-only`
6. Run a baseline smoke check:
   - `./tests/smoke.sh`
7. Run a baseline evaluation:
   - `./tools/eval_wsj.sh /absolute/path/to/wsj.xml`
8. Run a baseline benchmark pass:
   - `./tools/benchmark_wsj.sh /absolute/path/to/wsj.xml`
9. Note the latest evaluation report and benchmark report for `main`.
10. Create or refresh the experiment branch from the updated `main`.
11. Know how to compare an experiment branch against the active baseline on `main`:
   - `./tools/compare_branch_to_main.sh <branch>`

## Optimization Objective

Primary objective:

- Increase retrieval effectiveness, with `map` as the main headline metric.

Secondary objectives:

- Improve or preserve `Rprec`, `P_10`, `bpref`, and `recip_rank`.
- Avoid serious regressions in indexing time and search time.
- Prefer simpler changes when retrieval gains are similar.

## Acceptance Rules

A change is acceptable only if all of the following are true:

1. `./tests/smoke.sh` passes.
2. `./tools/eval_wsj.sh /absolute/path/to/wsj.xml` completes successfully.
3. Overall retrieval effectiveness improves relative to the latest compatible evaluation on `main`.
4. `./tools/benchmark_wsj.sh /absolute/path/to/wsj.xml` shows no serious regression relative to the latest compatible benchmark on `main`.

Use this benchmark policy:

- `<= 5%` median slowdown: acceptable.
- `> 5%` and `<= 15%` slowdown: acceptable only if the retrieval gain is clearly worthwhile and should be called out in the PR.
- `> 15%` median slowdown in indexing or search: reject by default.

When in doubt, reject performance-neutral complexity and reject quality gains that come with large latency regressions.

## Experiment Loop

Loop continuously until stopped:

1. Check out `main`, pull the latest remote changes, and refresh the `main` smoke/evaluation/benchmark artifacts.
2. Pick one retrieval idea.
3. Create or update the experiment branch from refreshed `main`.
4. Edit the indexer and/or searcher.
5. Run the lightweight smoke test:
   - `./tests/smoke.sh`
6. If smoke fails, fix or discard immediately.
7. Run full evaluation:
   - `./tools/eval_wsj.sh /absolute/path/to/wsj.xml`
8. Run benchmark guardrail:
   - `./tools/benchmark_wsj.sh /absolute/path/to/wsj.xml`
9. Compare the branch against the latest `main` artifacts:
   - `./tools/compare_branch_to_main.sh <branch>`
10. Refresh the committed dashboard assets:
   - `./tools/update_metrics_dashboard.sh`
11. If the change improves retrieval and respects benchmark guardrails:
   - commit it
   - keep the branch moving forward
   - update or open a PR
12. If the change does not improve retrieval or causes a serious regression:
   - discard it
   - return the branch to the last accepted commit

## Good Experiment Targets

Safe areas to explore:

- tokenization changes
- normalization rules
- stopword handling
- stemming or conflation
- document length handling
- BM25 parameter tuning
- query term weighting
- candidate ordering and tie-breaking
- vocabulary or postings layout changes that preserve end-to-end behavior

Avoid changes that only reshuffle code without a plausible retrieval or performance hypothesis.

## Artifact Policy

Artifacts are grouped by git branch automatically.

Evaluation reports go to:

- `experiment_evaluations/<branch>/`

Benchmark reports go to:

- `experiment_benchmarks/<branch>/`

The `experiment_evaluations/original/` and `experiment_benchmarks/original/` folders are immutable initialization archives. Do not write new artifacts into them and do not use them for active approval comparisons.

Do not commit generated evaluation or benchmark artifacts.

Do commit the PR dashboard assets after each accepted experiment:

- `docs/metrics/branch-comparisons.tsv`
- `docs/graphs/map-vs-main.svg`
- `docs/graphs/benchmark-vs-main.svg`

For long-run production graphing, export the `main` history with:

- `./tools/export_metrics_history.sh`

When graphing, use only rows from the real WSJ/TREC evaluation setup. Do not mix smoke or toy verification runs into production metric charts.

For the README dashboard, treat `main` as the active baseline and plot one point per non-main branch using:

- `./tools/export_branch_comparisons.sh`

## GitHub Workflow

Use the same high-level interaction model as the original autonomous research loop:

1. Work on a dedicated experiment branch.
2. Keep only accepted improvements on that branch.
3. Open or update a PR from the experiment branch into the base branch.
4. In the PR description, summarize:
   - the hypothesis
   - the code changes
   - the latest `trec_eval` headline metrics
   - the latest benchmark medians
   - the branch-vs-main comparison from `./tools/compare_branch_to_main.sh <branch>`
   - the updated README dashboard that shows the branch against the latest `main` baseline
   - any tradeoffs
5. Before opening or updating the PR, refresh:
   - `./tools/update_metrics_dashboard.sh`
6. Only merge PRs that improve overall search effectiveness and do not introduce a serious time regression.

If a PR does not clear both quality and performance guardrails, close or supersede it instead of merging.

## Reporting Format

For every accepted experiment, record:

- commit hash
- branch name
- evaluation report path
- benchmark report path
- key metric deltas:
  - `map`
  - `Rprec`
  - `P_10`
  - index median
  - search median
- one short description of the idea

## Operating Principle

This is not a binary-compatibility project. Internal index structure may evolve. The only things that matter are:

- the system still works end to end
- smoke checks stay green
- retrieval quality improves
- latency does not regress badly
