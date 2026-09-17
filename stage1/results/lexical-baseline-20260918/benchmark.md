# Stage-1 repeated lexical benchmark

Five timed iterations on the same local WSJ file and Go sources as this saved
baseline. Source: [raw benchmark](benchmark.txt).

| Measurement | Median seconds |
| --- | ---: |
| Indexing | 11.19 |
| Search, all 50 titles | 0.22 |

These are lexical-only timings. The stage-1 manifest retains its separate single
execution measurements; the replay's composed end-to-end time uses that actual
execution, not this median. No JEV API timing is included. Different historical
machines/load conditions prevent treating old artifact timings as a controlled
regression comparison; the Go sources did not change in this restructuring.

The legacy helper runs an indexing warm-up. Its search warm-up invocation does
not receive the topics, so it warms process/index loading rather than executing
the full topic workload. Preserve this qualification for comparisons using the
legacy benchmark script.
