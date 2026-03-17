Current accepted leader [`codex/search-rerank-span`](https://github.com/carlaiau/ir-autoresearch/tree/codex/search-rerank-span) improves `MAP` from `0.2080` on to `0.2410` (`+0.0330 (+15.9%)`). It also raises `P@5` from `0.4320` to `0.4720`.

| Branch | Issue | MAP | MAP Δ | P@5 | P@20 | R-prec | bpref | recall | Index (s) | Search (s) |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `original` | - | 0.2080 | baseline | 0.4320 | 0.3660 | 0.2563 | 0.2880 | 0.5634 | 9.89 | 0.42 |
| [`codex/search-bm25-rsj`](https://github.com/carlaiau/ir-autoresearch/tree/codex/search-bm25-rsj) | [#1](https://github.com/carlaiau/ir-autoresearch/issues/1) | 0.2349 | **+0.0269** | 0.4440 | 0.3910 | 0.2741 | 0.3036 | 0.5986 | 9.75 | 0.24 |
| [`codex/search-skip-metadata-fields`](https://github.com/carlaiau/ir-autoresearch/tree/codex/search-skip-metadata-fields) | [#6](https://github.com/carlaiau/ir-autoresearch/issues/6) | 0.2350 | **+0.0001** | 0.4480 | 0.3920 | 0.2758 | 0.3040 | 0.5986 | 9.71 | 0.23 |
| [`codex/search-headline-boost`](https://github.com/carlaiau/ir-autoresearch/tree/codex/search-headline-boost) | [#10](https://github.com/carlaiau/ir-autoresearch/issues/10) | 0.2355 | **+0.0005** | 0.4520 | 0.3910 | 0.2768 | 0.3046 | 0.6007 | 8.99 | 0.19 |
| [`codex/search-bm25-b-030`](https://github.com/carlaiau/ir-autoresearch/tree/codex/search-bm25-b-030) | [#14](https://github.com/carlaiau/ir-autoresearch/issues/14) | 0.2365 | **+0.0010** | 0.4600 | 0.3980 | 0.2801 | 0.3048 | 0.6016 | 8.83 | 0.20 |
| [`codex/search-prf`](https://github.com/carlaiau/ir-autoresearch/tree/codex/search-prf) | [#23](https://github.com/carlaiau/ir-autoresearch/issues/23) | 0.2396 | **+0.0031** | 0.4640 | 0.3960 | 0.2840 | 0.3071 | 0.6031 | 10.42 | 0.21 |
| [`codex/search-bm25-grid-search`](https://github.com/carlaiau/ir-autoresearch/tree/codex/search-bm25-grid-search) | [#25](https://github.com/carlaiau/ir-autoresearch/issues/25) | 0.2402 | **+0.0006** | 0.4680 | 0.3950 | 0.2826 | 0.3062 | 0.6029 | 10.61 | 0.22 |
| [`codex/search-rerank-span`](https://github.com/carlaiau/ir-autoresearch/tree/codex/search-rerank-span) | - | 0.2410 | **+0.0008** | 0.4720 | 0.3950 | 0.2826 | 0.3065 | 0.6029 | 10.03 | 0.24 |

**Legend**
- `MAP`: Mean Average Precision. A single overall ranking-quality score across all queries; higher is better.
- `P@5` and `P@20`: How many of the top 5 or top 20 results are relevant. Higher means better early precision.
- `R-prec`: Precision after retrieving `R` results, where `R` is the number of relevant documents for that query. Higher is better.
- `bpref`: A relevance metric that is more tolerant of incomplete judgment sets. Higher is better.
- `recall` (`num_rel_ret / num_rel`): Fraction of all judged-relevant documents that were retrieved anywhere in the run. higher is better.
- `Index (s)`: Median wall-clock indexing time in seconds across benchmark runs; lower is better.
- `Search (s)`: Median wall-clock search time in seconds for the full topics file across benchmark runs; lower is better.
