# JEV large-window context validation

Validation and full-coverage audit passed for all 5,700 query/document pairs
(5,679 unique documents; 57 queries). No text or candidates were dropped.

| Item | Value |
| --- | ---: |
| Final large windows | 6,090 |
| Pairs needing multiple windows | 181 |
| Maximum windows for one pair | 12 |
| Final windows verified with provider probes | 1,925 |
| Small windows below the 28,000-byte request threshold | 4,165 |
| Largest accepted probe input | 29,989 tokens |
| Token target for accepted probes | 30,000 |
| Validation API attempts | 1,977 |
| Context-size rejections, subsequently split | 23 |
| Successful probe responses | 1,954 |
| Validation time | 784.96 seconds |
| Estimated successful-response API cost | $1.221350 |

Start at 110,000 UTF-8 bytes of text with up to 4,000 bytes of overlap, retaining
original Unicode text. Probe every request above 28,000 serialized bytes. Split
oversized windows into smaller overlapping spans until each final probe meets
the target. This is empirical provider validation; bytes are not JEV tokens.
The frozen plan defines the exact character intervals. The audit verifies each
large final window against its accepted response, and complete text coverage.

Probe relevance scores did not affect window selection and are not reused in
the measured runs. Fresh caches separate inference timing and cost. Failed-call
billing and local compute remain unknown. The measured runs are queued
sequentially, with eight workers per query, pinned JEV 1.13.0 and the same Noul.

Small-passage MaxP requires 111,426 calls; large-window MaxP requires 6,090.
Character/4 planning estimates are $2.705486 and $1.761941 respectively; actual
response token usage determines the reported experiment estimates.

Evidence: [validation manifest](manifest.json), [attempts](attempts.jsonl),
[probe metadata and scores](scores.jsonl), [window plan](../large-window-plan.json),
[preflight and audit](../preflight.json). No raw document text is committed.
