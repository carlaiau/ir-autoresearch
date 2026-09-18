# JEV Passage Reranking Comparisons

This repository compares **JEV pointwise reranking against monoBERT** on the
**MS MARCO v1 / TREC Deep Learning 2019 passage reranking task**, evaluated with
**NIST human relevance judgments**. Given a query and a fixed set of candidate
passages, each model scores the passages and sorts them by relevance. We measure
ranking quality alongside reranking time, model usage and cost.

The main benchmark uses **43 judged queries and 41,042 supplied query–passage
pairs**. Every method receives the same candidates; no local corpus indexing or
new retrieval is needed. MS MARCO supplies the passage corpus and monoBERT's
training domain; the evaluation uses the separate NIST test judgments. The
[WSJ document benchmark](#secondary-benchmark-wsj-document-reranking) remains a
secondary test of transfer to another collection.

## Task and NIST relevance labels

The [TREC 2019 Deep Learning overview, section 2.2 and section 5](https://trec.nist.gov/pubs/trec28/papers/OVERVIEW.DL.pdf)
describes reranking up to 1,000 supplied BM25 passage candidates per query. Its
passage judgments distinguish answering a query from merely sharing its topic:

| Grade | NIST label | Meaning, paraphrased |
| --- | --- | --- |
| 3 | Perfectly relevant | Focuses on the query and gives the exact answer. |
| 2 | Highly relevant | Provides an answer, possibly unclear or mixed with unrelated material. |
| 1 | Related | Discusses the topic without answering the query. |
| 0 | Irrelevant | Has no connection to the query. |

**nDCG@10 is our primary metric**: it measures the quality and order of the first
ten results using all four grades, with `trec_eval` linear gains. **MAP** measures
average precision across queries using binary relevance: grades **2 and 3** count
as relevant; grades **0 and 1** do not. Grade 1 still earns partial credit in
nDCG, following the paper's passage evaluation convention. Higher is better for
both metrics. These are passage labels; the paper's document task uses a different
meaning for grade 1.

We retain all supplied candidates for the 43 judged queries: 41 queries have
1,000 candidates, and two have 5 and 37. Judgments select the evaluation queries
and assess the output; they do not select candidate passages or enter model
prompts. Downloads, candidate IDs and judgments are frozen in the
[input manifest](reranking/results/msmarco-dl2019/input/manifest.json).

## Passage reranking results

| Method | nDCG@10 (primary) | MAP | Total reranking time | Query median | Estimated API cost (USD) |
| --- | ---: | ---: | ---: | ---: | ---: |
| monoBERT | **0.7177** | 0.4488 | 969.83 s | 22.46 s | $0 hosted API; local compute unknown |
| JEV matched passage text | 0.6825 | **0.4748** | 1,633.43 s | 37.46 s | $0.762991 |
| JEV original passage text | 0.6835 | 0.4729 | 1,575.11 s | 38.08 s | $0.761027 |

JEV improved binary MAP but had lower observed nDCG@10 and longer measured
reranking time. Neither primary difference was statistically significant after
Holm correction (adjusted p=0.20450 for each comparison). **monoBERT remains the
reference**; these results establish a measured tradeoff, not JEV superiority or
model equivalence. Candidate recall across the complete supplied set is 0.6943
for all methods.

These are single uncached runs, executed sequentially. monoBERT ran on an Apple
M3 Pro with MPS, float32 and batch size 8; hosted JEV 1.13.0 used eight workers per
query. Query medians exclude shared setup. JEV costs estimate successful responses;
six failed API attempts recovered, and their billing is unknown. Local compute
cost is unknown. Supplied-candidate retrieval time is unavailable, so these are
**reranking times, not end-to-end search times**.

See the [full comparison, paired statistics and audits](reranking/results/msmarco-dl2019/results.md)
for all metrics, per-query changes, timing boundaries and raw evidence.

## Compared methods and reproduction

- **monoBERT:** `castorini/monobert-large-msmarco` scores each query–passage pair
  locally. This is the baseline for the passage task.
- **JEV matched passage text:** pointwise Noul scoring uses the decoded passage
  text supplied through monoBERT's tokenizer.
- **JEV original passage text:** the same pointwise JEV method uses the original
  supplied passage, preserving its text representation.

All passages fit one BERT window, with no truncation. These JEV conditions compare
text normalization, **not larger context coverage**, and neither supplies the
complete source web article. MS MARCO is monoBERT's training domain; JEV's training
exposure is unknown, so equal training conditions are not established.

Start with the [passage benchmark protocol and run commands](reranking/msmarco.md).
It covers preparation, frozen inputs, inference and evaluation. Reports, raw
`trec_eval`, model versions, timing, usage and audits are under
[`reranking/results/msmarco-dl2019/`](reranking/results/msmarco-dl2019/results.md).
Dataset text, model downloads, credentials and response caches stay outside Git.

JEV pairwise and new context-window strategies are deferred to follow-up work.
The rejected WSJ pairwise attempt is preserved below; no original duoBERT
checkpoint result is claimed for this passage benchmark.

## Secondary benchmark: WSJ document reranking

The WSJ/TREC transfer benchmark uses 50 topics and saved lexical candidates.
Its stage-1 baseline is fixed at **MAP 0.2521 before all reranking**, independently
of the monoBERT reference above. Its metrics cannot be compared directly with the
passage task because the collection, queries and judgments differ.

### WSJ results

| Method | MAP | P@10 | recip_rank | Status |
| --- | ---: | ---: | ---: | --- |
| [JEV pointwise: complete document](reranking/results/jev-full-documents-top100-20260918/results.md) | **0.3055** | **0.6340** | 0.8063 | Evaluated; best MAP and P@10 in this comparison |
| [JEV pointwise: passage MaxP](reranking/results/jev-passages-maxp-top100-20260918-retry/results.md) | 0.3053 | 0.6000 | **0.8457** | Evaluated; best reciprocal rank in this comparison |
| [JEV pointwise → Noul duo, top 20](https://github.com/carlaiau/jev-reranking/blob/633c11b/reranking/results/jev-duo-noul-top20-20260918/summary.md) | 0.3019 | 0.6200 | 0.8072 | Rejected; lowers MAP versus its pointwise input |
| [monoBERT passage MaxP](reranking/results/monobert-maxp-top100-20260918/results.md) | 0.2693 | 0.4960 | 0.6715 | Evaluated reference; local Apple GPU |
| [Stage 1: BM25 + query expansion](stage1/results/integrated-main-20260918/results.md) | 0.2521 | 0.4460 | 0.6271 | Fixed baseline; all reranking disabled |

**MAP** measures average ranking quality across queries. **P@10** is the fraction
of the first ten results that are relevant (`P_10` in `trec_eval`).
**recip_rank** averages the reciprocal position of the first relevant result.
Higher is better for all three metrics; full reports also include Rprec and bpref.

Pointwise JEV scores the top 100 candidates using Noul. The passage method uses
the identical windows supplied to monoBERT and takes the highest passage score
for each document (MaxP). The complete-document method scores the entire parsed
article once. Both use JEV 1.13.0 and eight concurrent calls per query; see the
[implementation and run commands](reranking/jev-comparison.md).

The Noul duo experiment takes the top 20 from the complete-document pointwise
ranking and compares every ordered pair using complete articles. Each document's
score is the sum of its 19 outgoing probabilities, following duoBERT's Sum idea.
Its negative result and implementation remain on a separate experiment branch;
the link above points to that preserved evidence. Model-backed duoBERT and
multi-document JEV Choice comparisons are not yet measured in this table.

### WSJ time, calls and cost

| Method | Successful scoring calls | Added reranking time, all 50 topics | Query median | Estimated API cost |
| --- | ---: | ---: | ---: | ---: |
| JEV complete document | 5,000 | 211.49 s | 4.02 s | $0.328312 |
| JEV passage MaxP | 19,593 | 767.73 s | 14.98 s | $0.605227 |
| JEV Noul duo pass alone | 19,000 | 837.98 s | 15.05 s | $2.305419 |
| monoBERT passage MaxP | 2,475 batches / 19,593 passages | 1,510.93 s | 30.27 s | $0 hosted API; local compute unknown |

The duo pass incurred **19,010 API attempts**, including ten recovered failures.
Its full pointwise→duo cascade totals **1,049.48 s of reranking** and an estimated
**$2.633731** in API cost, adding the saved pointwise measurement. It lowers MAP
while increasing time and cost, so this configuration was rejected.

These are single uncached runs, not repeated benchmark medians. Query medians
exclude shared setup. Composed search time adds the saved lexical search pass;
it is not a fresh integrated benchmark. Local compute cost is unknown for all
methods, and any failed-request charges are unknown. The
[paired JEV report](reranking/results/jev-comparison-20260918.md) separately
records the failed first passage run and its known usage. Reported settings are
exploratory on these topics, not held-out validation.

### WSJ retrieval and reranking workflow

**Stage 1 — freeze candidate retrieval.** The JASSjr-derived engine uses BM25
with pseudo-relevance feedback. Its saved baseline excludes dense retrieval,
neural/API reranking and query-rewrite sidecars. Five-run medians are **11.03 s
indexing** and **0.41 s search for all 50 topics**. The baseline includes the
candidate run, topics, qrels, configuration and hashes under
[`stage1/results/`](stage1/results/integrated-main-20260918/results.md).
See the [stage-1 implementation](stage1/README.md).

**Stage 2 — compare rerankers.** Reuse those candidates and the existing index.
Declare the input text, candidate depth and document scoring rule for each
experiment; preserve untouched ranking tails. Save separate Markdown reports,
raw evaluations and usage evidence under [`reranking/results/`](reranking/results/README.md).
See the [reranking methodology](reranking/README.md) and [research program](program.md).

`main` is the code integration branch. New code or verification runs do not
automatically replace the frozen baseline. The original initialization archive
remains read-only historical data.

## Inspiration And Provenance

This project is inspired by two upstream efforts:

- [karpathy/autoresearch](https://github.com/karpathy/autoresearch), which frames software improvement as an autonomous experiment loop driven by branch-based iteration and measurable outcomes. That repository is MIT-licensed.
- [andrewtrotman/JASSjr](https://github.com/andrewtrotman/JASSjr), which provides the minimal BM25 search engine foundation and the teaching-oriented WSJ/TREC setup that this repository adapts. JASSjr is BSD-2-Clause licensed and this repo keeps that upstream attribution in derived source files and includes the BSD-2-Clause text in [THIRD_PARTY_NOTICES.txt](THIRD_PARTY_NOTICES.txt).

The project applies that experiment-and-evaluate workflow to comparing JEV reranking methods, preserving both positive and negative results.

This project is licensed under the MIT License, except for JassJr related code which is included in this repository, which are licensed under their respective open-source licenses, please see THIRD_PARTY_NOTICES.txt for details.
