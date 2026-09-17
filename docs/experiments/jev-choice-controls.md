# JEV Choice controls

Issue: https://github.com/carlaiau/ir-autoresearch/issues/62
Baseline: main a2309b1 (accepted pointwise, MAP 0.3265).

Use the fixed `experiment_evaluations/codex/search-jev-recall/pre-jev-20260917-160716.trec` candidates and the same topics and original collection for all arms. This avoids fresh query embedding/rewrite differences between arms.

Arms:
- Accepted pointwise: 24,000 characters per article, top 100.
- Matched-budget pointwise: 2,400 characters per article, top 100.
- Choice: 10 articles per window, 2,400 characters each, stride 5, one bottom-up sweep over the top 100.

Choice sorts each window by returned probability with stable ties. Probabilities are comparable only within that window; they are never pooled into global scores. Overlap permits upward promotion but one sweep does not guarantee a globally optimal ranking. Candidate order and truncated-candidate counts are recorded per request. DOCNO labels are replaced with anonymous candidate labels in requests. Qrels are used only after ranking.

Run `tools/rerank_jev.py` against that saved run with `--max-chars 2400` for the pointwise control, or `--mode choice --window-size 10 --window-stride 5 --choice-chars 2400` for Choice. Provide `--collection`, `--topics`, `--run`, `--output`, `--metadata` and a shared `--cache`. Evaluate with `trec_eval -q -c -M1000 51-100.qrels.txt <run>`.

Smoke contracts cover stable ties, movement through overlapping windows, candidate preservation, malformed distributions and legacy reranker bypass. Acceptance still requires an improvement over the accepted 24,000-character pointwise baseline, not merely the truncated control. No fresh timing benchmark is planned. Main is the approval baseline; original remains archival initialization data.

Live responses round probabilities to two decimal places (observed totals 0.99 and 1.01). Validation permits at most 0.005 per candidate of total rounding error, retaining the original values for ranking. Labels, finite [0,1] values and maximum-probability winner remain mandatory.

## Result: rejected

| Arm | MAP | Rprec | P@10 | bpref | Reciprocal rank |
| --- | ---: | ---: | ---: | ---: | ---: |
| fusion | 0.2833 | 0.3159 | 0.5060 | 0.3545 | 0.7730 |
| pointwise_24000 | 0.3265 | 0.3463 | 0.6660 | 0.3904 | 0.8963 |
| pointwise_2400 | 0.3160 | 0.3397 | 0.6520 | 0.3840 | 0.8582 |
| choice_2400 | 0.3023 | 0.3361 | 0.5960 | 0.3715 | 0.8284 |

Choice underperforms accepted pointwise by 0.0242 MAP and matched-budget pointwise by 0.0137 MAP. Truncation alone lowers pointwise MAP by 0.0105. These comparisons support retaining full-text-budget pointwise; they do not rule out other listwise strategies. Choice used 950 window judgments, all jev-1.13.0. The matched control truncated 3858 of 5000 pairs. Candidate membership and the tail are identical across all four arms.

Validation: smoke contracts pass and all 50 WSJ topics were evaluated with trec_eval against fixed saved candidates. The full retrieval wrapper was not rerun for these controls, deliberately avoiding candidate regeneration; main’s full wrapper validation is preserved in the baseline artifacts. A transient pointwise API timeout was recovered with cached replay. Choice response validation initially rejected rounded distributions and a later response; the final run completed with valid responses. No Choice PR or merge is proposed.
