# Initial JEV passage attempt — failed

This attempt **did not complete** and has no accepted TREC effectiveness result.
After 46 complete queries and part of query 97, TypeSafe returned a server error.
The runner used the wrong SDK HTTP-status attribute, so it stopped instead of
retrying that transient response. The error handling was corrected and tested
against real SDK exception types before the fresh run below.

| Measurement | Value |
| --- | ---: |
| API attempts | 18,246 |
| Successful passage scores | 18,245 |
| Failed requests | 1 |
| Wall time before failure | 717.591 s |
| Reported successful input tokens | 13,433,370 |
| Reported successful output tokens | 401,390 |
| Estimated successful-response API cost | $0.56420154 |
| Charge for the failed request | Unknown |
| Local compute cost | Unknown |

Rate: $0.042/million input tokens, output free, from
[TypeSafe's pricing announcement](https://typesafe.ai/blog/introducing-system-one-models-and-jev),
verified September 18, 2026. Estimated costs are not invoices.

The executed runner and partial evidence are preserved in commit `1973695`.
[Failure metadata](failure.json), [source hash](attempt-manifest.json),
[attempt journal](attempts.jsonl), and [successful scores](scores.jsonl).
Raw responses remain in the ignored local cache.

The [replacement experiment](../jev-passages-maxp-top100-20260918-retry/results.md)
uses a fresh cache to obtain a complete uncached timing measurement. Its usage is
additional to this failed attempt; it must not hide the spend reported here.
