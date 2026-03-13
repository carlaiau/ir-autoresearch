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
- `tools/compare_branch_to_main.sh`
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

Treat `main` as the active baseline. Treat `original` as a read-only initialization archive.
Do not infer current workflow or approval rules from files under `experiment_evaluations/original/` or `experiment_benchmarks/original/`.

Before experimentation, establish the baseline with:

```bash
git checkout main
git pull --ff-only
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
Use a dedicated experiment branch for rejected experiments as well if you need to preserve their history.

Branch naming format:

- `codex/search-<tag>`

Do not use destructive git commands.
Do not overwrite unrelated user changes.
Do not merge to `main` unless the user explicitly asks for it.
Do not reuse a rejected experiment branch for unrelated follow-up work; keep it as a historical record.

## Experiment Loop

Unless the user says otherwise, use this loop:

1. Inspect current repo state and GitHub state.
2. Review open GitHub issues and PRs with `gh` to avoid duplicating work.
3. Refresh the active baseline on `main`:
   - `git checkout main`
   - `git pull --ff-only`
   - `./tests/smoke.sh`
   - `./tools/eval_wsj.sh <WSJ_XML_ABS_PATH>`
   - `./tools/benchmark_wsj.sh <WSJ_XML_ABS_PATH>`
4. Pick one concrete retrieval hypothesis.
5. Create or update a GitHub issue for that hypothesis.
6. Create a new branch from `main`:
   - `codex/search-<tag>`
7. Make the smallest plausible code change.
8. Run the full validation sequence:
   - `./tests/smoke.sh`
   - `./tools/eval_wsj.sh <WSJ_XML_ABS_PATH>`
   - `./tools/benchmark_wsj.sh <WSJ_XML_ABS_PATH>`
   - `./tools/compare_branch_to_main.sh <branch>`
   - `./tools/update_metrics_dashboard.sh`
9. Evaluate the result against the latest compatible `main` artifacts.
10. If the change is rejected:
   - commit and push the attempted code change plus the branch's evaluation and benchmark artifacts before abandoning the experiment
   - keep the rejected branch as a historical record; do not reset it to the last accepted state
   - comment on the GitHub issue with the attempted idea, metrics, and rejection reason
   - include the rejection commit hash in the issue comment when possible
   - close the issue or mark it rejected
11. If the change is accepted:
   - commit the code change plus dashboard assets and the branch's evaluation and benchmark artifacts
   - open or update a PR
   - link the PR to the issue
12. After completing either the rejected or accepted path, return to step 1 and begin the next experiment.
   - for the next distinct hypothesis, create a new GitHub issue
   - create a fresh branch from `main` using `codex/search-<tag>`
   - continue until blocked or explicitly told to stop

Default stopping rule:

- continue looping until blocked, the WSJ path or required credentials are missing, no concrete next hypothesis is available, or the user asks to stop

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
- the summary from `./tools/compare_branch_to_main.sh <branch>`
- the experiment's committed evaluation and benchmark artifacts for that branch
- note that `main` is the approval baseline and `original` is a read-only initialization archive
- note that the README dashboard was refreshed
- a link to the GitHub issue

If a PR does not clearly improve retrieval effectiveness or violates the benchmark guardrails, do not keep pushing it forward.

## Artifacts And Dashboard

Generated evaluation artifacts are written under:

- `experiment_evaluations/<branch>/`

Generated benchmark artifacts are written under:

- `experiment_benchmarks/<branch>/`

Commit the branch-local evaluation and benchmark artifacts that correspond to the final validation run for each experiment branch.
This applies to accepted experiments and rejected experiments that are being abandoned but preserved historically.
Do not commit refreshed `main` baseline artifacts unless the user explicitly asks.
Never modify or recommit anything under the read-only `original` artifact folders.

Do commit these dashboard assets after each accepted experiment:

- `docs/metrics/branch-comparisons.tsv`
- `docs/metrics/branch-comparisons.md`
- `README.md`

The README dashboard is a Markdown table. It starts with `original`, excludes `main`, and then lists one row per non-main branch with compatible local artifacts.

If historical non-main artifacts are not present locally, still refresh the dashboard from available data and note the limitation in the PR.

## Validation Commands

Core commands:

```bash
./tests/smoke.sh
./tools/eval_wsj.sh <WSJ_XML_ABS_PATH>
./tools/benchmark_wsj.sh <WSJ_XML_ABS_PATH>
./tools/compare_branch_to_main.sh <branch>
./tools/update_metrics_dashboard.sh
```

Useful exports:

```bash
./tools/export_metrics_history.sh
./tools/export_branch_comparisons.sh
```

## Reporting Back

When stopping, report:

- issues created or updated
- branches created
- experiments accepted or rejected
- PRs opened or updated
- best current metrics versus `original`
- note that archived `original` artifacts are historical initialization data, not the approval baseline
- blockers or missing prerequisites
