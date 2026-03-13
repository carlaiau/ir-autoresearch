# Search Experiment Sandbox

This repository is a compact experimentation sandbox for a JASSjr-style search engine. The goal is to let an agent iteratively improve indexing and ranking strategy, evaluate the result with `trec_eval`, and keep changes only when they improve overall retrieval effectiveness without causing serious performance regressions.

## Inspiration And Provenance

This project is inspired by two upstream efforts:

- [karpathy/autoresearch](https://github.com/karpathy/autoresearch), which frames software improvement as an autonomous experiment loop driven by branch-based iteration and measurable outcomes. That repository is MIT-licensed.
- [andrewtrotman/JASSjr](https://github.com/andrewtrotman/JASSjr), which provides the minimal BM25 search engine foundation and the teaching-oriented WSJ/TREC setup that this repository adapts. JASSjr is BSD-2-Clause licensed and this repo keeps that upstream attribution in derived source files and includes the BSD-2-Clause text in [LICENSE.txt](LICENSE.txt).

The intent here is not to erase those upstream influences, but to combine them: autonomous experiment management from `autoresearch`, applied to search-engine tuning on top of a JASSjr-derived codebase.

## What This Repo Is For

- experimenting with indexing logic in `index/JASSjr_index.go`
- experimenting with ranking and query processing in `search/JASSjr_search.go`
- validating end-to-end behavior with a tiny smoke fixture
- evaluating real retrieval quality on the WSJ/TREC setup
- benchmarking indexing and search time so quality gains do not come with unacceptable slowdowns

This repo is intentionally small so an automated agent can understand the full workflow and iterate quickly.

## Core Workflow

Use these commands in order:

```bash
git checkout main
git pull --ff-only
./tests/smoke.sh
./tools/eval_wsj.sh /absolute/path/to/your/wsj.xml
./tools/benchmark_wsj.sh /absolute/path/to/your/wsj.xml
./tools/update_metrics_dashboard.sh
```

What they do:

- `./tests/smoke.sh`
  Runs a tiny fixture-based smoke evaluation to catch obvious breakage.
- `./tools/eval_wsj.sh`
  Builds the search engine, runs the TREC topics, and records a timestamped `trec_eval` summary.
- `./tools/benchmark_wsj.sh`
  Runs a few indexing and search benchmarks and records timestamped timings.
- `./tools/update_metrics_dashboard.sh`
  Exports the README branch metrics and refreshes the metrics table embedded in this README.
- `./tools/compare_branch_to_main.sh <branch>`
  Compares the latest evaluation and benchmark artifacts for a branch against the active baseline on `main`.
- `./tools/export_metrics_history.sh [branch]`
  Exports a TSV time series from saved artifacts so MAP and benchmark medians can be reviewed over time.
- `./tools/export_branch_comparisons.sh`
  Exports the latest compatible artifact from every non-main branch as a branch-vs-main comparison TSV.

## Artifact Layout

Artifacts are grouped by the current git branch.

Evaluation summaries are written to:

- `experiment_evaluations/<branch>/`

Benchmark summaries are written to:

- `experiment_benchmarks/<branch>/`

This makes it easy to compare experiments branch by branch while keeping raw outputs out of git history. The `experiment_evaluations/original/` and `experiment_benchmarks/original/` folders are immutable initialization archives and must never be refreshed or overwritten.

Each new research loop should begin by refreshing the active baseline on `main`:

```bash
git checkout main
git pull --ff-only
./tests/smoke.sh
./tools/eval_wsj.sh /absolute/path/to/your/wsj.xml
./tools/benchmark_wsj.sh /absolute/path/to/your/wsj.xml
```

After that, create or update an experiment branch from the refreshed `main` baseline and require the branch to beat the newest `main` evaluation and benchmark artifacts before approving a PR.

To compare a branch against the current production baseline:

```bash
./tools/compare_branch_to_main.sh codex/search-my-idea
```

To export a history TSV for the production branch:

```bash
./tools/export_metrics_history.sh > main-metrics.tsv
```

To refresh the committed dashboard assets:

```bash
./tools/update_metrics_dashboard.sh
```

The raw history export from `tools/export_metrics_history.sh` is designed for simple analysis of:

- retrieval effectiveness over time, especially `map`
- benchmark medians over time for indexing and search

That TSV also includes enough metadata to filter or separate runs:

- `collection`, `topics`, and `qrels` for evaluation rows
- `collection`, `topics`, `smoke_topics`, and `iterations` for benchmark rows

That matters because you may occasionally record toy or verification runs alongside full WSJ/TREC runs. For production reporting, filter to the real WSJ collection and the standard `51-100` topics/qrels before comparing `map` or the benchmark medians.

## Metrics Dashboard

The README metrics table is a generated experiment log. It starts with the immutable `original` row, then lists each non-main experiment branch with compatible evaluation and benchmark artifacts, whether that branch was ultimately accepted or rejected. The `Status` and `Issue` columns are pulled from the GitHub issue/PR workflow, and `MAP Δ vs previous` compares each row against the immediately preceding row in the table. `main` is intentionally excluded from the README table, even though PR approval still compares candidate branches against the latest `main` artifacts.

Generated files:

- `docs/metrics/branch-comparisons.tsv`
- `docs/metrics/branch-comparisons.md`

<!-- README_METRICS_TABLE_START -->
| Branch | Status | Issue | MAP | MAP Δ vs previous | Index median | Search topics median | Updated |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| `original` | baseline | - | 0.2080 | baseline | 9.89 | 0.42 | 2026-03-13 14:28 |
| `codex/search-bm25-rsj` | accepted | [#1](https://github.com/carlaiau/ir-autoresearch/issues/1) | 0.2349 | **+0.0269** | 9.75 | 0.24 | 2026-03-13 15:19 |
| `codex/search-skip-metadata-fields` | accepted | [#6](https://github.com/carlaiau/ir-autoresearch/issues/6) | 0.2350 | **+0.0001** | 9.71 | 0.23 | 2026-03-13 16:18 |
| `codex/search-headline-boost` | accepted | [#10](https://github.com/carlaiau/ir-autoresearch/issues/10) | 0.2355 | **+0.0005** | 8.99 | 0.19 | 2026-03-13 17:06 |
| `codex/search-bm25-b-030` | accepted | [#14](https://github.com/carlaiau/ir-autoresearch/issues/14) | 0.2365 | **+0.0010** | 8.83 | 0.20 | 2026-03-13 20:44 |
| `codex/search-prf` | accepted | [#23](https://github.com/carlaiau/ir-autoresearch/issues/23) | 0.2396 | **+0.0031** | 10.42 | 0.21 | 2026-03-13 22:39 |
<!-- README_METRICS_TABLE_END -->

## Success Criteria

A change is worth keeping only if:

- the smoke test still passes
- `trec_eval` improves overall retrieval effectiveness relative to the latest compatible evaluation on `main`
- indexing and search benchmarks do not show a serious regression relative to the latest compatible benchmark on `main`

In practice, `map` is the main headline metric, but `Rprec`, `P_10`, `bpref`, and `recip_rank` should also be watched.

## Repository Structure

- `index/`
  Index construction logic.
- `search/`
  Query evaluation and ranking logic.
- `tests/fixtures/`
  Tiny smoke-test collection and toy qrels/topics.
- `tools/smoke_eval.sh`
  Lightweight shell-based smoke evaluation.
- `tools/eval_wsj.sh`
  Full WSJ/TREC evaluation with timestamped reports.
- `tools/benchmark.sh`
  Generic timing helper used by benchmark scripts.
- `tools/benchmark_wsj.sh`
  Branch-aware indexing and search benchmark runner.
- `tools/update_metrics_dashboard.sh`
  Refreshes the committed metrics TSV, generated Markdown table, and README metrics section.
- `tools/compare_branch_to_main.sh`
  Branch-vs-main artifact comparison helper.
- `tools/export_metrics_history.sh`
  TSV exporter for long-run metric history and reporting.
- `tools/export_branch_comparisons.sh`
  TSV exporter for the README branch metrics table.
- `tools/render_metrics_table.py`
  Markdown table renderer for the committed README metrics section.
- `program.md`
  The agent operating plan for autonomous search experiments.
