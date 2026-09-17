# Two-stage retrieval and reranking research

The repository separates lexical candidate retrieval from reranking. The current
research focus is comparing JEV, monoBERT and duoBERT on identical candidates,
measuring retrieval effectiveness, search time and cost.

| Stage | Implementation and methodology | Result Markdown folders |
| --- | --- | --- |
| 1. Lexical retrieval | [Stage 1](stage1/README.md): JASSjr BM25 + existing feedback | [stage1/results/](stage1/results/) |
| 2. Reranking | [Stage 2](reranking/README.md): JEV pointwise; monoBERT/duoBERT planned | [reranking/results/](reranking/results/) |

Stage 1 saves its own run and `trec_eval` before stage 2 starts. Every new result
has a `results.md` and machine-readable manifest. Stage 2 verifies the baseline's
content hashes and reports its gain, added time and estimated cost separately.

```sh
./tests/smoke.sh
python3 stage1/run.py /absolute/path/to/wsj.xml
# Substitute the exact directory printed by stage 1; use a Python environment
# with tools/requirements-jev.txt installed and TYPESAFE_API_KEY configured.
python3 reranking/run.py stage1/results/<branch>/<run-id> --top-k 100
```

`./tools/eval_wsj.sh` now runs stage 1 only. The old
`JASSJR_JEV_RERANK=on` switch is rejected with migration instructions.
`./tools/benchmark_wsj.sh` remains a repeated lexical-only benchmark.
See [program.md](program.md) for the research workflow.

The historical paired result is MAP **0.2402 → 0.2925** for lexical retrieval
followed by top-100 JEV. Historical reranking latency and dollar cost are unknown;
this establishes effectiveness evidence, not a speed or cost win.

## Historical branch dashboard

The following dashboard and `docs/metrics/` summarize legacy branch artifacts.
They mix lexical and reranked experiments and are retained as history. Its Search
column measures lexical batch time where available, not stage-2 or end-to-end time.
Use the separate stage result folders for new comparisons. Legacy exporter and
branch-vs-main tools read `experiment_evaluations/` / `experiment_benchmarks/` only;
they do not ingest the new stage manifests. `original` is read-only initialization
history; `main` remains the code approval baseline.

<!-- README_METRICS_TABLE_START -->
Current accepted leader [`codex/search-jev-post25`](https://github.com/carlaiau/ir-autoresearch/tree/codex/search-jev-post25) improves `MAP` from `0.2080` on `original` to `0.2925` (`+0.0845 (+40.6%)`). It also raises `P@5` from `0.4320` to `0.6720`.

| Branch | Issue | MAP | MAP Δ | P@5 | P@20 | R-prec | bpref | recall | Index (s) | Search (s) |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `original` | - | 0.2080 | baseline | 0.4320 | 0.3660 | 0.2563 | 0.2880 | 0.5634 | 9.89 | 0.42 |
| [`codex/search-bm25-rsj`](https://github.com/carlaiau/ir-autoresearch/tree/codex/search-bm25-rsj) | [#1](https://github.com/carlaiau/ir-autoresearch/issues/1) | 0.2349 | **+0.0269** | 0.4440 | 0.3910 | 0.2741 | 0.3036 | 0.5986 | 9.75 | 0.24 |
| [`codex/search-skip-metadata-fields`](https://github.com/carlaiau/ir-autoresearch/tree/codex/search-skip-metadata-fields) | [#6](https://github.com/carlaiau/ir-autoresearch/issues/6) | 0.2350 | **+0.0001** | 0.4480 | 0.3920 | 0.2758 | 0.3040 | 0.5986 | 9.71 | 0.23 |
| [`codex/search-headline-boost`](https://github.com/carlaiau/ir-autoresearch/tree/codex/search-headline-boost) | [#10](https://github.com/carlaiau/ir-autoresearch/issues/10) | 0.2355 | **+0.0005** | 0.4520 | 0.3910 | 0.2768 | 0.3046 | 0.6007 | 8.99 | 0.19 |
| [`codex/search-bm25-b-030`](https://github.com/carlaiau/ir-autoresearch/tree/codex/search-bm25-b-030) | [#14](https://github.com/carlaiau/ir-autoresearch/issues/14) | 0.2365 | **+0.0010** | 0.4600 | 0.3980 | 0.2801 | 0.3048 | 0.6016 | 8.83 | 0.20 |
| [`codex/search-prf`](https://github.com/carlaiau/ir-autoresearch/tree/codex/search-prf) | [#23](https://github.com/carlaiau/ir-autoresearch/issues/23) | 0.2396 | **+0.0031** | 0.4640 | 0.3960 | 0.2840 | 0.3071 | 0.6031 | 10.42 | 0.21 |
| [`codex/search-bm25-grid-search`](https://github.com/carlaiau/ir-autoresearch/tree/codex/search-bm25-grid-search) | [#25](https://github.com/carlaiau/ir-autoresearch/issues/25) | 0.2402 | **+0.0006** | 0.4680 | 0.3950 | 0.2826 | 0.3062 | 0.6029 | 10.61 | 0.22 |
| [`codex/search-jev-post25`](https://github.com/carlaiau/ir-autoresearch/tree/codex/search-jev-post25) | [#58](https://github.com/carlaiau/ir-autoresearch/issues/58) | 0.2925 | **+0.0523** | 0.6720 | 0.5250 | 0.3143 | 0.3445 | 0.6029 | n/a | n/a |

**Legend**
- `MAP`: Mean Average Precision. A single overall ranking-quality score across all queries; higher is better.
- `P@5` and `P@20`: How many of the top 5 or top 20 results are relevant. Higher means better early precision.
- `R-prec`: Precision after retrieving `R` results, where `R` is the number of relevant documents for that query. Higher is better.
- `bpref`: A relevance metric that is more tolerant of incomplete judgment sets. Higher is better.
- `recall` (`num_rel_ret / num_rel`): Fraction of all judged-relevant documents that were retrieved anywhere in the run. higher is better.
- `Index (s)`: Median wall-clock indexing time in seconds across benchmark runs; lower is better.
- `Search (s)`: Median wall-clock search time in seconds for the full topics file across benchmark runs; lower is better.
<!-- README_METRICS_TABLE_END -->

## Inspiration And Provenance

This project is inspired by two upstream efforts:

- [karpathy/autoresearch](https://github.com/karpathy/autoresearch), which frames software improvement as an autonomous experiment loop driven by branch-based iteration and measurable outcomes. That repository is MIT-licensed.
- [andrewtrotman/JASSjr](https://github.com/andrewtrotman/JASSjr), which provides the minimal BM25 search engine foundation and the teaching-oriented WSJ/TREC setup that this repository adapts. JASSjr is BSD-2-Clause licensed and this repo keeps that upstream attribution in derived source files and includes the BSD-2-Clause text in [LICENSE.txt](LICENSE.txt).

The goal here is to bring the autonomous experiment-management ideas from `autoresearch` into information retrieval, and to further test the hypothesis that an agent can improve any system as long as it has a measurable objective.

This project is licensed under the MIT License, except for JassJr related code which is included in this repository, which are licensed under their respective open-source licenses, please see THIRD_PARTY_NOTICES.txt for details.
