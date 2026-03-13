# Repository Agent Guide

If explicit user instructions conflict with this file, follow the user. Otherwise, treat this file as the default operating contract for autonomous work in this repository.

## Purpose

This repository is an autonomous experimentation sandbox for a compact JASSjr-derived search engine.

The goal is to improve end-to-end retrieval effectiveness on the WSJ/TREC setup while avoiding serious regressions in indexing and query latency.

This is not a binary-compatibility project. Internal index structure may evolve if end-to-end behavior improves.

## Read First

Before making changes, read these files:

- `README.md`
- `program.md`
- `index/JASSjr_index.go`
- `search/JASSjr_search.go`
- `tools/eval_wsj.sh`
- `tools/benchmark_wsj.sh`
- `tools/compare_branch_to_master.sh`
- `tools/update_metrics_dashboard.sh`

This repository uses shell smoke tests, not Bats.

## Required Input

The agent needs an absolute path to the WSJ collection file.

If the WSJ path is not supplied by the user and cannot be discovered locally with confidence, stop and ask for it.

## WSJ Collection Format

The WSJ collection is a single file containing repeated document records of the form:

```xml
<DOC>
  <DOCNO>WSJ000000-0001</DOCNO>
  <HL>Example headline</HL>
  <DD>01/01/87</DD>
  <SO>WALL STREET JOURNAL (J)</SO>
  <DATELINE>NEW YORK</DATELINE>
  <TEXT>
    Example body text with markup entities like &amp;.
  </TEXT>
</DOC>
```

Important parsing assumptions:

- `<DOC>...</DOC>` defines a single document boundary.
- `<DOCNO>` is the document identifier used in retrieval output and evaluation.
- useful terms may appear outside `<TEXT>`, especially in `<HL>`
- XML entities such as `&amp;` can appear in the collection
- documents may contain multiple tagged fields, not just `<TEXT>`

When changing indexing or tokenization logic, preserve:

- correct document boundary handling
- correct extraction of `DOCNO`
- stable association between indexed terms and the right document ID

## Baseline And Success Criteria

Treat `master` as the `original` baseline.

Before experimentation, establish the baseline with:

```bash
./tests/smoke.sh
./tools/eval_wsj.sh <WSJ_XML_ABS_PATH>
./tools/benchmark_wsj.sh <WSJ_XML_ABS_PATH>
```

Headline retrieval metric:

- `map`

Secondary retrieval metrics:

- `Rprec`
- `P_10`
- `bpref`
- `recip_rank`

A change is acceptable only if all of the following are true:

1. `./tests/smoke.sh` passes.
2. `./tools/eval_wsj.sh <WSJ_XML_ABS_PATH>` completes successfully.
3. Overall retrieval effectiveness improves relative to the current accepted branch baseline, with `map` as the main headline metric.
4. `./tools/benchmark_wsj.sh <WSJ_XML_ABS_PATH>` shows no serious regression.

Benchmark policy:

- `<= 5%` median slowdown: acceptable.
- `> 5%` and `<= 15%` slowdown: acceptable only if the retrieval gain is clearly worthwhile.
- `> 15%` median slowdown in indexing or search: reject by default.

## Git And Branching

Use a dedicated experiment branch for each accepted line of work.

Branch naming format:

- `codex/search-<tag>`

Do not use destructive git commands.
Do not overwrite unrelated user changes.
Do not merge to `master` unless the user explicitly asks for it.

## Experiment Loop

Unless the user says otherwise, use this loop:

1. Inspect current repo state and GitHub state.
2. Review open GitHub issues and PRs with `gh` to avoid duplicating work.
3. Pick one concrete retrieval hypothesis.
4. Create or update a GitHub issue for that hypothesis.
5. Create a new branch from `master`:
   - `codex/search-<tag>`
6. Make the smallest plausible code change.
7. Run the full validation sequence:
   - `./tests/smoke.sh`
   - `./tools/eval_wsj.sh <WSJ_XML_ABS_PATH>`
   - `./tools/benchmark_wsj.sh <WSJ_XML_ABS_PATH>`
   - `./tools/compare_branch_to_master.sh <branch>`
   - `./tools/update_metrics_dashboard.sh`
8. Evaluate the result.
9. If the change is rejected:
   - do not keep it
   - return the branch to the last accepted state without disturbing unrelated work
   - comment on the GitHub issue with the attempted idea, metrics, and rejection reason
   - close the issue or mark it rejected
10. If the change is accepted:
   - commit the code change plus dashboard assets
   - open or update a PR
   - link the PR to the issue

Default stopping rule:

- stop after one strong PR is ready, or after 3 consecutive rejected hypotheses, or when blocked

## What To Change

Good experiment targets:

- tokenization
- normalization
- stopword handling
- stemming or conflation
- document length handling
- BM25 parameter tuning
- query term weighting
- candidate ordering and tie-breaking
- internal vocabulary or postings structure

Avoid changes with no clear retrieval or performance hypothesis.

## GitHub Issue Rules

Every experiment should have a GitHub issue unless it is obviously the continuation of an existing experiment.

Issue title format:

- `Experiment: <specific idea>`

Each issue should include:

- the hypothesis
- the likely files to change
- acceptance criteria
- the retrieval metric to watch
- the benchmark risk to watch

When an experiment is rejected, record the reason and the key metrics in the issue before closing or marking it not pursued.

## Pull Request Rules

Open or update a PR only for accepted experiments.

Every PR should include:

- the hypothesis
- a concise summary of the code change
- the latest `map`, `Rprec`, `P_10`, `bpref`, and `recip_rank`
- the latest benchmark medians
- the summary from `./tools/compare_branch_to_master.sh <branch>`
- note that `master` is treated as the `original` baseline
- note that the README dashboard was refreshed
- a link to the GitHub issue

If a PR does not clearly improve retrieval effectiveness or violates the benchmark guardrails, do not keep pushing it forward.

## Artifacts And Dashboard

Generated evaluation artifacts are written under:

- `experiment_evaluations/<branch>/`

Generated benchmark artifacts are written under:

- `experiment_benchmarks/<branch>/`

Do not commit generated evaluation or benchmark artifacts.

Do commit these dashboard assets after each accepted experiment:

- `docs/metrics/branch-comparisons.tsv`
- `docs/graphs/map-vs-original.svg`
- `docs/graphs/benchmark-vs-original.svg`

The README dashboard treats `master` as `original` and plots one point for each non-master branch with compatible local artifacts.

If historical non-master artifacts are not present locally, still refresh the dashboard from available data and note the limitation in the PR.

## Validation Commands

Core commands:

```bash
./tests/smoke.sh
./tools/eval_wsj.sh <WSJ_XML_ABS_PATH>
./tools/benchmark_wsj.sh <WSJ_XML_ABS_PATH>
./tools/compare_branch_to_master.sh <branch>
./tools/update_metrics_dashboard.sh
```

Useful exports:

```bash
./tools/export_metrics_history.sh master
./tools/export_branch_comparisons.sh
```

## Reporting Back

When stopping, report:

- issues created or updated
- branches created
- experiments accepted or rejected
- PRs opened or updated
- best current metrics versus `original`
- blockers or missing prerequisites
