# MS MARCO v1 / TREC DL 2019 pointwise comparison

Issue [#73](https://github.com/carlaiau/jev-reranking/issues/73). This is an
additional passage benchmark, separate from the immutable WSJ MAP 0.2521 baseline.
The user excluded failed JEV pairwise work from this experiment; context-window
and other ranking strategies belong to a later follow-up.

## Protocol fixed before inference

- Use official TREC DL 2019 supplied passage candidates and graded judgments.
  Evaluate all 43 judged queries, all 41,042 supplied query/passage pairs. Query
  855410 has 5 candidates and 1121709 has 37; the other 41 have 1,000 each.
  No candidates are added from qrels, no model selects the pointwise shortlist,
  and ascending numeric passage ID breaks score ties. File order is not BM25 rank.
- Use the existing `castorini/monobert-large-msmarco` checkpoint, revision
  `0a97706f3827389da43b83348d5d18c9d53876fa`, float32, MPS, batch size 8.
  Preserve all passage tokens using the existing 384-token windows, overlap 64,
  bounded by query length and the 512-token input limit. MaxP document score.
- JEV matched: same frozen monoBERT windows, decoded using its tokenizer, MaxP.
  This matches boundaries/evidence, not cross-model token IDs; normalization and
  WordPiece decoding can change casing/spacing. JEV full: complete original
  supplied passage text, one Noul score, no truncation. Neither condition includes
  the original source web document.
- Same passage-specific relevance Noul question for both JEV conditions; see
  `QUESTION` in `msmarco.py`. No qrels, previous rank or previous score in requests.
  Reuse the WSJ relevance approach, changing article language to passage/query
  language before evaluation. No prompt search or tuning on evaluation results.
- JEV requested alias `jev-latest`, expected served version `jev-1.13.0`; stop
  on mismatch. Eight workers per query, sequential queries, at most three explicit
  attempts, SDK retries disabled. Separate new empty caches for uncached runs.
- Headline nDCG@10 uses original grades and trec_eval's linear gains. Binary
  MAP, Rprec, P_10, bpref, recip_rank and recall use grades >=2 as relevant.
  Preserve grade-1 rows as explicit binary zero; do not discard judged negatives.
- Compare each JEV condition with the same saved monoBERT baseline. Predeclare
  paired bootstrap 95% intervals for mean per-query differences (10,000 samples,
  seed 73) and two-sided paired sign-randomization tests (100,000 draws, seed 73).
  Holm correction over the two headline nDCG comparisons. Secondary metric tests
  are descriptive. Inputs are rounded trec_eval per-query metrics; record this
  precision limit. There is no new fine-tuning; checkpoint development history
  and unknown JEV training exposure limit claims of untouched held-out evidence.
- Record setup, per-query p50/p95, inference, wall time, model calls, retries,
  cache hits, token usage and costs. Published JEV rate verified 2026-09-18:
  $0.042/million input tokens, output free, from
  https://typesafe.ai/blog/introducing-system-one-models-and-jev.
  Failed-request billing and local compute cost are unknown. Supplied-candidate
  retrieval time is unknown; no composed end-to-end search time is claimed.

## Reproduce

Download the three files listed in `msmarco.py:URLS` into ignored
`.cache/msmarco-dl2019/`, named `queries.tsv.gz`, `candidates.tsv.gz`, `qrels.txt`.
The source URLs and SHA-256 values are in `results/msmarco-dl2019/input/manifest.json`.
Use the existing monoBERT environment, prefetched model and TypeSafe credentials
in the environment or ignored `.env` files. The committed input manifest must
remain unchanged when reproducing; `prepare` is only for initial creation.

```sh
# Initial input creation only; the checked-in frozen input already exists:
# .venv-monobert/bin/python reranking/msmarco.py prepare
.venv-monobert/bin/python reranking/msmarco.py monobert \
  --results-dir reranking/results/msmarco-dl2019/monobert
.venv-monobert/bin/python reranking/msmarco.py jev-matched \
  --results-dir reranking/results/msmarco-dl2019/jev-matched \
  --cache .cache/msmarco-dl2019/jev-matched \
  --input-usd-per-million 0.042 --output-usd-per-million 0 \
  --pricing-source 'https://typesafe.ai/blog/introducing-system-one-models-and-jev; verified 2026-09-18'
.venv-monobert/bin/python reranking/msmarco.py jev-full \
  --results-dir reranking/results/msmarco-dl2019/jev-full \
  --cache .cache/msmarco-dl2019/jev-full \
  --input-usd-per-million 0.042 --output-usd-per-million 0 \
  --pricing-source 'https://typesafe.ai/blog/introducing-system-one-models-and-jev; verified 2026-09-18'
```

For reproduction supply new results/cache paths and `--monobert` to point to the
reference run. Failed attempts remain preserved; cached-only replay requires
`--cache-only` and is never labeled uncached inference. Downloaded passage text,
model files and response caches remain uncommitted. New experiment evidence goes
under `reranking/results/msmarco-dl2019/`.

## Measured monoBERT reference

The [completed baseline](results/msmarco-dl2019/monobert/results.md) scored all
41,042 pairs: nDCG@10 **0.7177**, MAP **0.4488**, P@10 **0.6233**.
Reranking took **969.83 s**; query p50/p95 were **22.46 / 28.02 s**, excluding
shared setup. These are one-run measurements, not repeated benchmark medians.

The [independent audit](results/msmarco-dl2019/monobert/audit.json) confirmed
full coverage and reconstructed every ranking. All candidates fit a single
window; **none** needed MaxP across multiple windows. BERT decode normalization
changes the supplied text for 40,804 pairs. Consequently the two JEV conditions
test decoded versus original text representation, not a long-context advantage.
The [completed comparison](results/msmarco-dl2019/results.md) reports both JEV
conditions, the paired tests, measured time/cost and all audit links. JEV matched
text achieved nDCG@10 0.6825 / MAP 0.4748; original text achieved 0.6835 / 0.4729.
Both improve MAP but have lower observed nDCG@10 and longer measured reranking
time than monoBERT. The primary differences are not significant after Holm
correction (adjusted p=0.20450 for each comparison). This supports a measured
tradeoff, not a superiority claim. Total estimated successful-response API cost
is $1.524018; six recovered failed attempts have unknown billing.

Run the independent audit and regenerate the comparison from saved evidence:

```sh
.venv-monobert/bin/python reranking/audit_msmarco.py
```

The audit verifies candidate identity/recall, coverage, exact payload hashes,
ranking reconstruction and usage/cost accounting, then runs the prespecified
paired tests. Use `--root` and `--data` for relocated result/data directories.

Run `bash tests/msmarco.sh`, `bash tests/monobert.sh`, `bash tests/jev_compare.sh`,
`bash tests/two_stage.sh` and `./tests/smoke.sh` before the experiment.
