# JEV Reranking Comparisons

Can JEV's zero-shot general “intelligence” match established specialist rerankers such as
monoBERT? We compare ranking quality, time and cost on fixed candidates, using
MS MARCO / TREC DL 2019 as the main benchmark and TREC-1 WSJ as a transfer test.

## Task

Rerank 41,042 supplied query–passage pairs across 43 judged queries, with no new
indexing or retrieval. The [TREC DL 2019 paper](https://trec.nist.gov/pubs/trec28/papers/OVERVIEW.DL.pdf)
defines NIST passage labels as 3: exact answer, 2: answer with limitations,
1: related but no answer, and 0: irrelevant. Our primary metric, nDCG@10, uses
all grades; MAP, P@10 and recip_rank treat only grades 2–3 as relevant.

## Passage reranking results

| Method | Source | nDCG@10 | MAP | P@10 | recip_rank |
| --- | --- | ---: | ---: | ---: | ---: |
| monoBERT | Our local implementation | 0.7177 | 0.4488 | **0.6233** | 0.8717 |
| JEV matched passage text | Our run | 0.6825 | **0.4748** | 0.6116 | 0.8594 |
| JEV original passage text | Our run | 0.6835 | 0.4729 | 0.6163 | 0.8447 |
| IDST BERT (`idst_bert_pr2`) | Paper, Table 4 | **0.7379** | 0.4565 | — | **0.8818** |
| TU Vienna neural (`TUW19-p3-re`) | Paper, Table 4 | 0.6746 | 0.4113 | — | 0.8568 |

Published rows come from [Table 4 of the TREC DL 2019 overview](https://trec.nist.gov/pubs/trec28/papers/OVERVIEW.DL.pdf#page=9)
and are classified there as reranking runs. They are historical references, not
local reproductions or part of our paired tests; exact candidate identity has
not been audited against our manifest. `recip_rank` uses the paper's NIST MRR,
not its separate MS MARCO MRR. P@10 is not reported there. Bold marks the highest
reported value in each column among the displayed methods.

P@10 measures precision in the first ten results; recip_rank averages the
reciprocal rank of the first relevant result. Higher is better for all metrics.
Against our local monoBERT, JEV improves MAP but has lower observed nDCG@10.
Neither primary difference is
significant after Holm correction (p=0.20450 each); this does not establish
superiority or equivalence. monoBERT remains the reference.

| Method | Total reranking | Query median | Estimated API cost (USD) |
| --- | ---: | ---: | ---: |
| monoBERT | 969.83 s | 22.46 s | $0 hosted API |
| JEV matched passage text | 1,633.43 s | 37.46 s | $0.762991 |
| JEV original passage text | 1,575.11 s | 38.08 s | $0.761027 |

These are single uncached runs: monoBERT on M3 Pro/MPS, float32, batch 8;
JEV 1.13.0 with eight workers per query. See the [full results and audits](reranking/results/msmarco-dl2019/results.md).

## Methods and reproduction

- monoBERT was implemented and run locally in this repository using the pretrained
  `castorini/monobert-large-msmarco` checkpoint; we did not retrain the model.
- JEV matched passage text uses the decoded token windows supplied to monoBERT.
- JEV original passage text uses the dataset passage with its original casing
  and spacing, not its source article.

All passages fit one BERT window, so this run compares text normalization rather
than context coverage. MS MARCO is monoBERT's training domain; JEV's training
exposure is unknown.

Matching windows controls JEV's advantage of seeing a long article at once.
The WSJ experiment below separately compares matched windows with full articles.
Pairwise JEV and new context-window strategies are deferred; no original duoBERT
checkpoint result is claimed here.

See the [protocol and commands](reranking/msmarco.md) and
[frozen input manifest](reranking/results/msmarco-dl2019/input/manifest.json).
Reports retain raw evaluations, model versions, timing and usage. Dataset text,
model downloads, credentials and response caches stay outside Git.

## Secondary benchmark: WSJ document reranking

This uses the TREC-1 WSJ collection and 50 topics, with our own JASSjr-derived
BM25 and query-expansion retrieval step. Its saved candidates and stage-1
MAP 0.2521 baseline are fixed. Scores are separate from the passage benchmark.

| Method | MAP | P@10 | recip_rank |
| --- | ---: | ---: | ---: |
| [JEV complete document](reranking/results/jev-full-documents-top100-20260918/results.md) | **0.3055** | **0.6340** | 0.8063 |
| [JEV passage MaxP](reranking/results/jev-passages-maxp-top100-20260918-retry/results.md) | 0.3053 | 0.6000 | **0.8457** |
| [monoBERT passage MaxP](reranking/results/monobert-maxp-top100-20260918/results.md) | 0.2693 | 0.4960 | 0.6715 |
| [Stage 1: BM25 + query expansion](stage1/results/integrated-main-20260918/results.md) | 0.2521 | 0.4460 | 0.6271 |

Pointwise methods rerank the top 100 documents. Passage MaxP gives JEV and
monoBERT identical windows and uses each document's highest passage score.
Both cover the article across windows; only complete-document JEV sees it all
in one call.

| Method | Total reranking | Query median | Estimated API cost (USD) |
| --- | ---: | ---: | ---: |
| JEV complete document | 211.49 s | 4.02 s | $0.328312 |
| JEV passage MaxP | 767.73 s | 14.98 s | $0.605227 |
| monoBERT passage MaxP | 1,510.93 s | 30.27 s | $0 hosted API |

These are single uncached measurements; local compute and failed-request charges are
unknown. Settings are exploratory on these topics. See the
[paired report](reranking/results/jev-comparison-20260918.md) and
[implementation](reranking/jev-comparison.md) for usage and timing details.

The [stage-1 baseline](stage1/README.md) is lexical, with no dense retrieval or
reranking. Five-run medians are 11.03 s indexing and 0.41 s search for all 50
topics. Stage 2 reuses its saved candidates and index; see the
[reranking methodology](reranking/README.md) and [research program](program.md).
Changes to `main` do not replace the fixed baseline; original archives remain
read-only history.

## Inspiration and provenance

The experiment workflow draws on [karpathy/autoresearch](https://github.com/karpathy/autoresearch)
(MIT); the WSJ retrieval engine derives from [andrewtrotman/JASSjr](https://github.com/andrewtrotman/JASSjr)
(BSD-2-Clause). This project is MIT-licensed except for upstream-derived code
under its respective licenses. See [THIRD_PARTY_NOTICES.txt](THIRD_PARTY_NOTICES.txt).
