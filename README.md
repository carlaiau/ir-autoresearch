# Search Experiment Sandbox

This repository provides a compact sandbox for experimenting with a simple, understandable IR system. The aim is to enable an agent to iteratively optimize indexing and ranking strategies, evaluate each iteration with `trec_eval`, and preserve only the changes that improve overall retrieval effectiveness. Computational efficiency work is deferred for now; benchmark data is optional context when available, not part of the current approval gate.

## Current Results

<!-- README_METRICS_TABLE_START -->
Current accepted leader [`codex/search-openai-mono`](https://github.com/carlaiau/ir-autoresearch/tree/codex/search-openai-mono) improves `MAP` from `0.2080` on to `0.2485` (`+0.0405 (+19.5%)`). It also raises `P@5` from `0.4320` to `0.5240`.

| Branch | Issue | MAP | MAP Δ | P@5 | P@20 | R-prec | bpref | recall | Index (s) | Search (s) |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `original` | - | 0.2080 | baseline | 0.4320 | 0.3660 | 0.2563 | 0.2880 | 0.5634 | 9.89 | 0.42 |
| [`codex/search-bm25-rsj`](https://github.com/carlaiau/ir-autoresearch/tree/codex/search-bm25-rsj) | [#1](https://github.com/carlaiau/ir-autoresearch/issues/1) | 0.2349 | **+0.0269** | 0.4440 | 0.3910 | 0.2741 | 0.3036 | 0.5986 | 9.75 | 0.24 |
| [`codex/search-skip-metadata-fields`](https://github.com/carlaiau/ir-autoresearch/tree/codex/search-skip-metadata-fields) | [#6](https://github.com/carlaiau/ir-autoresearch/issues/6) | 0.2350 | **+0.0001** | 0.4480 | 0.3920 | 0.2758 | 0.3040 | 0.5986 | 9.71 | 0.23 |
| [`codex/search-headline-boost`](https://github.com/carlaiau/ir-autoresearch/tree/codex/search-headline-boost) | [#10](https://github.com/carlaiau/ir-autoresearch/issues/10) | 0.2355 | **+0.0005** | 0.4520 | 0.3910 | 0.2768 | 0.3046 | 0.6007 | 8.99 | 0.19 |
| [`codex/search-bm25-b-030`](https://github.com/carlaiau/ir-autoresearch/tree/codex/search-bm25-b-030) | [#14](https://github.com/carlaiau/ir-autoresearch/issues/14) | 0.2365 | **+0.0010** | 0.4600 | 0.3980 | 0.2801 | 0.3048 | 0.6016 | 8.83 | 0.20 |
| [`codex/search-prf`](https://github.com/carlaiau/ir-autoresearch/tree/codex/search-prf) | [#23](https://github.com/carlaiau/ir-autoresearch/issues/23) | 0.2396 | **+0.0031** | 0.4640 | 0.3960 | 0.2840 | 0.3071 | 0.6031 | 10.42 | 0.21 |
| [`codex/search-bm25-grid-search`](https://github.com/carlaiau/ir-autoresearch/tree/codex/search-bm25-grid-search) | [#25](https://github.com/carlaiau/ir-autoresearch/issues/25) | 0.2402 | **+0.0006** | 0.4680 | 0.3950 | 0.2826 | 0.3062 | 0.6029 | 10.61 | 0.22 |
| [`codex/search-rerank-span`](https://github.com/carlaiau/ir-autoresearch/tree/codex/search-rerank-span) | [#30](https://github.com/carlaiau/ir-autoresearch/issues/30) | 0.2410 | **+0.0008** | 0.4720 | 0.3950 | 0.2826 | 0.3065 | 0.6029 | 10.03 | 0.24 |
| [`codex/search-duobert-grid`](https://github.com/carlaiau/ir-autoresearch/tree/codex/search-duobert-grid) | [#30](https://github.com/carlaiau/ir-autoresearch/issues/30) | 0.2418 | **+0.0008** | 0.4600 | 0.4010 | 0.2836 | 0.3074 | 0.6029 | 11.95 | 0.26 |
| [`codex/search-openai-mono`](https://github.com/carlaiau/ir-autoresearch/tree/codex/search-openai-mono) | [#30](https://github.com/carlaiau/ir-autoresearch/issues/30) | 0.2485 | **+0.0067** | 0.5240 | 0.4080 | 0.2781 | 0.3086 | 0.6029 | 12.04 | 0.71 |

**Legend**
- `MAP`: Mean Average Precision. A single overall ranking-quality score across all queries; higher is better.
- `P@5` and `P@20`: How many of the top 5 or top 20 results are relevant. Higher means better early precision.
- `R-prec`: Precision after retrieving `R` results, where `R` is the number of relevant documents for that query. Higher is better.
- `bpref`: A relevance metric that is more tolerant of incomplete judgment sets. Higher is better.
- `recall` (`num_rel_ret / num_rel`): Fraction of all judged-relevant documents that were retrieved anywhere in the run. higher is better.
- `Index (s)`: Median wall-clock indexing time in seconds across benchmark runs; lower is better.
- `Search (s)`: Median wall-clock search time in seconds for the full topics file across benchmark runs; lower is better.

The `Index (s)` and `Search (s)` columns are currently informational only. New experiments do not need fresh benchmark runs to be accepted right now.
<!-- README_METRICS_TABLE_END -->

Generated files:

- `docs/metrics/branch-comparisons.tsv`
- `docs/metrics/branch-comparisons.md`

## Inspiration And Provenance

This project is inspired by two upstream efforts:

- [karpathy/autoresearch](https://github.com/karpathy/autoresearch), which frames software improvement as an autonomous experiment loop driven by branch-based iteration and measurable outcomes. That repository is MIT-licensed.
- [andrewtrotman/JASSjr](https://github.com/andrewtrotman/JASSjr), which provides the minimal BM25 search engine foundation and the teaching-oriented WSJ/TREC setup that this repository adapts. JASSjr is BSD-2-Clause licensed and this repo keeps that upstream attribution in derived source files and includes the BSD-2-Clause text in [LICENSE.txt](LICENSE.txt).

The goal here is to bring the autonomous experiment-management ideas from `autoresearch` into information retrieval, and to further test the hypothesis that an agent can improve any system as long as it has a measurable objective.

This project is licensed under the MIT License, except for JassJr related code which is included in this repository, which are licensed under their respective open-source licenses, please see THIRD_PARTY_NOTICES.txt for details.

## What This Repo Is For

- experimenting with indexing logic in `index/JASSjr_index.go`
- experimenting with ranking and query processing in `search/JASSjr_search.go`
- validating end-to-end behavior with a tiny smoke fixture
- evaluating real retrieval quality on the WSJ/TREC setup
- optionally benchmarking indexing and search time for future efficiency work

This repo is intentionally small so an automated agent can understand the full workflow and iterate quickly.

## Core Workflow

Use these commands in order:

```bash
git checkout main
git pull --ff-only
./tests/smoke.sh
./tools/eval_wsj.sh /absolute/path/to/your/wsj.xml
./tools/update_metrics_dashboard.sh
```

What they do:

- `./tests/smoke.sh`
  Runs a tiny fixture-based smoke evaluation to catch obvious breakage.
- `./tools/eval_wsj.sh`
  Builds the search engine, runs the TREC topics, and records a timestamped `trec_eval` summary.
- `./tools/benchmark_wsj.sh`
  Optional: runs a few indexing and search benchmarks and records timestamped timings for later efficiency work.
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
```

After that, create or update an experiment branch from the refreshed `main` baseline and require the branch to beat the newest `main` evaluation artifact before approving a PR. Benchmark artifacts can still be collected when desired, but they are not part of the current approval gate.

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
- benchmark medians over time for indexing and search, when benchmark artifacts exist

That TSV also includes enough metadata to filter or separate runs:

- `collection`, `topics`, and `qrels` for evaluation rows
- `collection`, `topics`, `smoke_topics`, and `iterations` for benchmark rows

That matters because you may occasionally record toy or verification runs alongside full WSJ/TREC runs. For production reporting, filter to the real WSJ collection and the standard `51-100` topics/qrels before comparing `map`, and only compare benchmark medians when benchmark artifacts are available.

## Success Criteria

A change is worth keeping only if:

- the smoke test still passes
- `trec_eval` improves overall retrieval effectiveness relative to the latest compatible evaluation on `main`

In practice, `map` is the main headline metric, but `Rprec`, `P_10`, `bpref`, and `recip_rank` should also be watched. Benchmark runs remain available for future efficiency work, but they are optional right now.

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
