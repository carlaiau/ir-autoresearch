# JEV relevance reranking from issue #25

Issue: https://github.com/carlaiau/ir-autoresearch/issues/58

The user requested branching from 552f36baf50784122de36fc419b6cbb9eac07256
(PR #26, closing #25), before passage/LLM reranking was added. The historical
indexer, BM25 k1=0.7/b=0.3 and existing lightweight feedback stay unchanged.
The current user-provided AGENTS.md contract applies, superseding older workflow
instructions at this historical commit. Current main remains the approval baseline;
the historical parent isolates JEV's incremental effect. Original is read-only
initialization history.

## Run

Use Python 3.10+ with tools/requirements-jev.txt installed. Configure
TYPESAFE_API_KEY in the environment or local .env (ignored). Then:

```sh
./tests/smoke.sh
bash tests/jev_rerank.sh
JASSJR_JEV_RERANK=on JASSJR_JEV_PYTHON=/path/to/venv/bin/python \
  ./tools/eval_wsj.sh /absolute/path/to/wsj.xml
```

The pass is opt-in. JASSJR_JEV_TOP_K defaults to 100. JASSJR_JEV_MODEL defaults
to jev-latest: on 2026-09-17 the API rejected the cookbook's jev-1.12 and listed
only jev-latest and jev-preview, both released 2026-09-10. This alias is mutable;
replay cached responses to reproduce a run. No model equivalence is assumed.

The Python CLI also supports --cache-only for replay, --workers (default 8),
and --max-chars (default 24000). Qrels are never inputs to scoring. Documents
are parsed by DOC boundaries and joined by exact DOCNO. Tags are removed,
entities decoded, DOCNO excluded, and remaining fields retained in source order.
Articles exceeding 24000 characters are prefix-truncated, counted in metadata.
This cap is an experiment content policy, not a claim about the model's context limit.

Each pair is scored with one substantive relevance Noul. Cache keys include the
model, endpoint, complete question, original document hash and actual query/text
payload. Cached files contain responses, not credentials or article text. Cache
files live under ignored wsj-eval/jev-cache. Branch artifacts contain per-pair
scores, response model, usage, cache hashes and truncation flags for auditing.

Input runs are sorted by score then descending DOCNO, matching trec_eval's tie
convention. JEV sorts the prefix stably by probability and leaves the rest alone.
Strictly decreasing synthetic scores preserve the entire output order in trec_eval.
Missing candidates, malformed scores and API errors fail the run; no partial
reranking is evaluated. Successfully scored pairs survive interrupted runs.

## Evaluation plan

Top 100 is the primary experiment (5000 pairs over 50 titles). Depths 30/50 can
be diagnostic replays; selecting settings on these same topics is exploratory,
not held-out evidence. Report MAP, Rprec, P_10, bpref and recip_rank, candidate
recall, per-topic AP changes, token usage and truncation count. Efficiency is
informational. Preserve rejected experiments; open PRs only for accepted results.

Fresh baselines on 2026-09-17:

| Configuration | MAP | Rprec | P_10 | bpref | recip_rank |
|---|---:|---:|---:|---:|---:|
| Historical parent 552f36b | 0.2402 | 0.2826 | 0.4320 | 0.3062 | 0.6388 |
| Main ec2beac, external modes off | 0.2530 | 0.2989 | 0.4440 | 0.3182 | 0.6523 |
| Original archive | 0.2080 | 0.2563 | 0.4040 | 0.2880 | 0.5974 |

The dashboard also records MAP 0.2867 for an API-assisted main configuration;
that is not the same configuration as the fresh default invocation above.

References: https://docs.typesafe.ai/cookbooks/rerank_typesafe and
https://docs.typesafe.ai/api

## Accepted result

The full top-100 run completed with 4959 pairs (some queries had fewer candidates).
All responses reported jev-1.13.0. Eleven pairs were truncated. Response usage
summed to 7,595,855 input tokens and 109,098 output tokens, including one cached
pilot response. No current pricing claim is made.

| Depth | MAP | Rprec | P_10 | bpref | recip_rank |
|---|---:|---:|---:|---:|---:|
| 30 (diagnostic) | 0.2659 | 0.2898 | 0.5420 | 0.3209 | 0.8233 |
| 50 (diagnostic) | 0.2776 | 0.2942 | 0.5820 | 0.3310 | 0.8304 |
| 100 (primary) | 0.2925 | 0.3143 | 0.6100 | 0.3445 | 0.8322 |

Primary MAP increased by 0.0523 versus the historical parent and 0.0395 versus
fresh default main. AP improved on 44 topics, worsened on 4 and tied on 2. The
shortlist contains 1370 judged relevant documents (22.0% micro recall); the final
retrieved set remains unchanged. The archived original MAP was 0.2080 (gain
0.0845); it is not the approval baseline. The dashboard's historical API-assisted
MAP of 0.2867 is also exceeded, but this is not a fresh paired comparison of that
configuration and its Rprec/bpref were higher (0.3302/0.3625).

Validation includes lexical smoke tests, ranking/parser contract tests, full WSJ
execution, exact cache replay and an identity-reranking check reproducing all
parent trec_eval aggregate metrics. No benchmark was run. Dashboard export now
allows evaluation-only rows with n/a timings and recognizes relocated paths to
the same shipped topic/qrels filenames; this is dashboard compatibility rather
than proof that arbitrary same-named datasets are identical.

The next hypothesis is that increasing depth to 200 will improve MAP by exposing
more relevant candidates, while retaining the exact same question and model.
