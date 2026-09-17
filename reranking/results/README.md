# Reranking results

| Run | MAP | Reranking batch seconds | New API cost (USD) |
| --- | ---: | --- | --- |
| [Historical JEV top 100](jev-top100/results.md) | 0.2925 | Unknown | Unknown |
| [JEV top-100 cache replay](jev-top100-replay-20260918/results.md) | 0.2925 | 3.1392 (all cached) | 0 |

Both runs use the same stage-1 candidate hash and reproduce identical output.
The fresh lexical baseline MAP is 0.2402. Replay's composed end-to-end batch time
is 3.5816 seconds, including its paired lexical pass. These measurements do not
estimate live API latency, uncached dollars or per-query response latency. The
replay overlapped local benchmark activity; it is a correctness replay rather
than an isolated performance benchmark. monoBERT and duoBERT results are pending.
