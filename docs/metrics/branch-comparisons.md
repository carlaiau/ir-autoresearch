Current accepted leader [`codex/search-rwexp-default-weight`](https://github.com/carlaiau/ir-autoresearch/tree/codex/search-rwexp-default-weight) improves `MAP` from `0.2080` on to `0.2867` (`+0.0787 (+37.8%)`). It also raises `P@5` from `0.4320` to `0.6000`.

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
| [`codex/search-rm3-recall`](https://github.com/carlaiau/ir-autoresearch/tree/codex/search-rm3-recall) | [#33](https://github.com/carlaiau/ir-autoresearch/issues/33) | 0.2530 | **+0.0045** | 0.4840 | 0.4060 | 0.2989 | 0.3182 | 0.6268 | 12.59 | 0.48 |
| [`codex/search-openai-mono-rm3`](https://github.com/carlaiau/ir-autoresearch/tree/codex/search-openai-mono-rm3) | [#30](https://github.com/carlaiau/ir-autoresearch/issues/30) | 0.2691 | **+0.0161** | 0.5640 | 0.4830 | 0.3053 | 0.3275 | 0.6268 | 11.53 | 1.19 |
| [`codex/search-tri-source-scaffold`](https://github.com/carlaiau/ir-autoresearch/tree/codex/search-tri-source-scaffold) | [#38](https://github.com/carlaiau/ir-autoresearch/issues/38) | 0.2739 | **+0.0048** | 0.5720 | 0.4790 | 0.3113 | 0.3426 | 0.6538 | 11.08 | 8.00 |
| [`codex/search-fusion-weight-grid`](https://github.com/carlaiau/ir-autoresearch/tree/codex/search-fusion-weight-grid) | [#39](https://github.com/carlaiau/ir-autoresearch/issues/39) | 0.2800 | **+0.0061** | 0.5960 | 0.4930 | 0.3217 | 0.3528 | 0.6538 | 12.64 | 8.77 |
| [`codex/search-rm3-expansion-source`](https://github.com/carlaiau/ir-autoresearch/tree/codex/search-rm3-expansion-source) | [#45](https://github.com/carlaiau/ir-autoresearch/issues/45) | 0.2830 | **+0.0030** | 0.5960 | 0.4970 | 0.3207 | 0.3585 | 0.6755 | 13.11 | 10.34 |
| [`codex/search-llm-rewrite-sidecar`](https://github.com/carlaiau/ir-autoresearch/tree/codex/search-llm-rewrite-sidecar) | [#47](https://github.com/carlaiau/ir-autoresearch/issues/47) | 0.2861 | **+0.0031** | 0.5960 | 0.4970 | 0.3288 | 0.3613 | 0.6769 | 13.37 | 11.57 |
| [`codex/search-rewrite-rm3exp`](https://github.com/carlaiau/ir-autoresearch/tree/codex/search-rewrite-rm3exp) | [#50](https://github.com/carlaiau/ir-autoresearch/issues/50) | 0.2867 | **+0.0006** | 0.6000 | 0.4950 | 0.3302 | 0.3624 | 0.6768 | 13.13 | 12.20 |
| [`codex/search-rwexp-default-weight`](https://github.com/carlaiau/ir-autoresearch/tree/codex/search-rwexp-default-weight) | [#53](https://github.com/carlaiau/ir-autoresearch/issues/53) | 0.2867 | +0.0000 | 0.6000 | 0.4950 | 0.3302 | 0.3625 | 0.6768 | 13.17 | 11.88 |

**Legend**
- `MAP`: Mean Average Precision. A single overall ranking-quality score across all queries; higher is better.
- `P@5` and `P@20`: How many of the top 5 or top 20 results are relevant. Higher means better early precision.
- `R-prec`: Precision after retrieving `R` results, where `R` is the number of relevant documents for that query. Higher is better.
- `bpref`: A relevance metric that is more tolerant of incomplete judgment sets. Higher is better.
- `recall` (`num_rel_ret / num_rel`): Fraction of all judged-relevant documents that were retrieved anywhere in the run. higher is better.
- `Index (s)`: Median wall-clock indexing time in seconds across benchmark runs; lower is better.
- `Search (s)`: Median wall-clock search time in seconds for the full topics file across benchmark runs; lower is better.
