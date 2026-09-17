# reranking results

Status: complete

| Metric | Value | Delta vs stage 1 |
| --- | ---: | ---: |
| map | 0.2693 | +0.0172 |
| Rprec | 0.3149 | +0.0160 |
| bpref | 0.3368 | +0.0190 |
| recip_rank | 0.6715 | +0.0444 |
| P_10 | 0.4960 | +0.0500 |

```json
{
  "batch_size": 8,
  "branch": "codex/search-monobert-full-document",
  "cache_mode": "no score cache; every passage inferred",
  "checkpoint_unexpected_keys": [],
  "collection_sha256": "8c696265462fc49b123d3e3fc46e95a94399954a3f1a12e7d596ef032ea4d7c8",
  "commit": "e87d8340589c3fa2413fa7005242dbf72bef3d33",
  "compute_usd_per_hour": null,
  "cost_scope": "rate times measured process wall duration; excludes prior dependency install/model prefetch and stage-1 retrieval; not a bill",
  "coverage_fraction": 1.0,
  "covered_document_tokens_across_query_pairs": 5782119,
  "device": "mps",
  "dirty": true,
  "document_tokens_across_query_pairs": 5782119,
  "dtype": "float32",
  "end_to_end_search_seconds": 1511.6142450408079,
  "estimated_compute_cost_usd": null,
  "estimated_reranking_compute_cost_usd": null,
  "evaluation_seconds": 0.11400699988007545,
  "extraction_seconds": 2.6511900830082595,
  "hosted_inference_api_calls": 0,
  "hosted_inference_api_cost_usd": 0.0,
  "inference_seconds": 1492.477594842203,
  "input_tokens": 6846925,
  "library_versions": {
    "huggingface-hub": "0.36.2",
    "tokenizers": "0.22.2",
    "torch": "2.8.0",
    "transformers": "4.57.6"
  },
  "method": "monobert-maxp",
  "model": "castorini/monobert-large-msmarco",
  "model_downloads_allowed": false,
  "model_forward_calls": 2475,
  "model_forward_calls_attempted": 2475,
  "model_input_limit": 512,
  "model_load_seconds": 9.19472079211846,
  "model_parameters": 335143938,
  "model_revision": "0a97706f3827389da43b83348d5d18c9d53876fa",
  "overlap_tokens": 64,
  "padded_input_tokens": 7647829,
  "passage_scoring_calls": 19593,
  "passage_scoring_calls_attempted": 19593,
  "passage_tokens": 384,
  "platform": "macOS-26.4-arm64-arm-64bit-Mach-O",
  "pricing_source": null,
  "processor": "arm",
  "qrels_sha256": "3ba5b51ca171ad272709ada5a357cc065b718950d46392fef817178944b2e101",
  "queries": 50,
  "query_document_pairs": 5000,
  "query_p50_seconds": 30.269296750077046,
  "query_p95_seconds": 42.18930326857371,
  "relevance_label_index": 1,
  "rerank_seconds": 1510.9273346657865,
  "run_sha256": "f148c45bbd5fe0b531e4573668c2e100cf4c0f844fe5f499be09ed5f54d7862b",
  "score": "log_softmax(relevant); MaxP across all passages",
  "scoring_seconds": 1493.2146167908795,
  "source_sha256": {
    "reranking/jev.py": "f6f80b2764a38e8d7c58023cfcc9b912f76e797a993e1612d13967029c91310a",
    "reranking/monobert.py": "526cbfe17c6565b5787fcd1992021cce0aaba1bc1e01c909129dcb17d925f4c2",
    "tools/stage_artifacts.py": "4f68d63e7f294026367e824d5628619b54e8f7be33d7e8141ef18444a0d3bf8b"
  },
  "stage": "reranking",
  "stage1_directory": "/Users/caiau/school/ir-autoresearch/stage1/results/integrated-main-20260918",
  "stage1_manifest_sha256": "65228181d2984dee1bfb8c98717e769fb114ec03fc3d03183ee145c0511485c5",
  "stage1_run_sha256": "d1f737713de16e857ba69988ee85f5d30fef2bc4f4d6004d4ff73e87c7c9045b",
  "stage1_search_seconds": 0.6869103750213981,
  "status": "complete",
  "timing_scope": "rerank includes text extraction, model load/download if needed, tokenization, scoring and run output; excludes hash checks and trec_eval; per-query time excludes shared setup",
  "tokenization_seconds": 5.8545049170497805,
  "tokenizer_revision": "0a97706f3827389da43b83348d5d18c9d53876fa",
  "top_k": 100,
  "topics_sha256": "c1bce334f551e1e813ef0510e61d6441617570ae92be2f2f471826c3baa23317",
  "total_wall_seconds": 1511.4041035419796,
  "truncated_documents": 0,
  "unique_document_tokens": 5237180,
  "unique_documents": 4596
}
```

Raw evaluation: [trec_eval.txt](trec_eval.txt). Run: [run.trec](run.trec).
Times are batch wall-clock seconds; batch/query is amortized throughput, not single-query latency.


## Calls, time and cost

| Measurement | Value |
| --- | ---: |
| Passage scoring calls | 19593 |
| Model forward calls (batches) | 2475 |
| Hosted inference API calls | 0 |
| Model load (seconds) | 9.194721 |
| Reranking (seconds) | 1510.927335 |
| Composed end-to-end search (seconds) | 1511.614245 |
| Total process wall time (seconds) | 1511.404104 |
| Query p50 (seconds, shared setup excluded) | 30.269297 |
| Query p95 (seconds, shared setup excluded) | 42.189303 |
| Hosted inference API cost (USD) | 0.000000 |
| Estimated local compute cost (USD) | Unknown — supply an hourly rate |

Full document-token coverage: **100%**. Passage token offsets and scores: [passages.jsonl](passages.jsonl). Per-query measurements: [queries.json](queries.json).

Audit, hardware and paired-topic changes: [validation.md](validation.md).
