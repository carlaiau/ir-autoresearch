#!/usr/bin/env python3
"""Full-document monoBERT MaxP reranking with auditable local inference costs."""
import argparse
from datetime import datetime, timezone
import importlib.metadata
import json
import math
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from stage_artifacts import ROOT, evaluate, provenance, report, sha
from jev import atomic_write, documents, read_run

MODEL = 'castorini/monobert-large-msmarco'
REVISION = '0a97706f3827389da43b83348d5d18c9d53876fa'
CANONICAL = ROOT / 'stage1/results/integrated-main-20260918'


def windows(length, capacity, overlap):
    """Intervals cover every original token, including short tails; no passage cap."""
    if length <= 0 or capacity <= 0 or not 0 <= overlap < capacity:
        raise ValueError('invalid document length, passage capacity or overlap')
    start = 0
    while True:
        end = min(start + capacity, length)
        yield start, end
        if end == length:
            break
        start = end - overlap


def coverage(intervals, length):
    end = 0
    for start, stop in intervals:
        if start < 0 or start > end or not start < stop <= length:
            raise ValueError('passage coverage gap or invalid interval')
        end = max(end, stop)
    if end != length:
        raise ValueError('unscored document tail')
    return end


def percentile(values, fraction):
    """Linear interpolation, reported for sequential per-query processing time."""
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lo, hi = math.floor(position), math.ceil(position)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (position - lo)


def cost(seconds, hourly_rate):
    return None if hourly_rate is None else seconds * hourly_rate / 3600


class BertBackend:
    def __init__(self, args):
        import torch
        from transformers import BertForSequenceClassification, BertTokenizerFast
        self.torch = torch
        self.device = args.device
        if self.device == 'auto':
            self.device = 'cuda' if torch.cuda.is_available() else ('mps' if torch.backends.mps.is_available() else 'cpu')
        self.tokenizer = BertTokenizerFast.from_pretrained(
            MODEL, revision=REVISION, cache_dir=args.model_cache, local_files_only=args.local_files_only)
        self.model, loading = BertForSequenceClassification.from_pretrained(
            MODEL, revision=REVISION, cache_dir=args.model_cache, local_files_only=args.local_files_only,
            output_loading_info=True, weights_only=True, use_safetensors=False)
        # Never silently evaluate a randomly initialized classification head.
        if loading.get('missing_keys') or loading.get('mismatched_keys') or loading.get('error_msgs'):
            raise ValueError('checkpoint parameters did not load completely')
        self.unexpected_keys = loading.get('unexpected_keys', [])
        if self.model.config.num_labels != 2:
            raise ValueError('expected binary monoBERT relevance classifier')
        self.model.to(self.device).eval()
        self.sync()
        self.limit = min(self.model.config.max_position_embeddings, self.tokenizer.model_max_length)
        self.special_tokens = self.tokenizer.num_special_tokens_to_add(pair=True)
        self.versions = {name: importlib.metadata.version(name) for name in ('torch', 'transformers', 'tokenizers', 'huggingface-hub')}
        self.parameters = sum(p.numel() for p in self.model.parameters())

    def sync(self):
        if self.device == 'cuda':
            self.torch.cuda.synchronize()
        elif self.device == 'mps':
            self.torch.mps.synchronize()

    def tokenize(self, text):
        return self.tokenizer.encode(text, add_special_tokens=False, truncation=False)

    def pair(self, query, passage):
        # Construct from original token IDs; no decode/re-tokenize or truncation.
        return {'input_ids': self.tokenizer.build_inputs_with_special_tokens(query, passage),
                'token_type_ids': self.tokenizer.create_token_type_ids_from_sequences(query, passage)}

    def predict(self, pairs):
        batch = self.tokenizer.pad(pairs, padding=True, return_tensors='pt')
        batch = {key: value.to(self.device) for key, value in batch.items()}
        with self.torch.inference_mode():
            logits = self.model(**batch).logits
            scores = self.torch.log_softmax(logits.float(), dim=-1)[:, 1]
        self.sync()
        return scores.cpu().tolist()


def new_counters():
    return {'query_document_pairs': 0, 'passage_scoring_calls': 0,
            'passage_scoring_calls_attempted': 0, 'model_forward_calls_attempted': 0, 'model_forward_calls': 0,
            'hosted_inference_api_calls': 0, 'input_tokens': 0, 'padded_input_tokens': 0,
            'unique_document_tokens': 0, 'document_tokens_across_query_pairs': 0,
            'covered_document_tokens_across_query_pairs': 0, 'inference_seconds': 0.0}


def score_all(runs, queries, docs, backend, args, destination, counters):
    preprocess_start = time.perf_counter()
    doc_tokens = {docid: backend.tokenize(text) for docid, text in docs.items()}
    query_tokens = {qid: backend.tokenize(text) for qid, text in queries.items()}
    if any(not ids for ids in doc_tokens.values()) or any(not ids for ids in query_tokens.values()):
        raise ValueError('empty tokenized document/query')
    counters['unique_document_tokens'] = sum(map(len, doc_tokens.values()))
    preprocessing_seconds = time.perf_counter() - preprocess_start
    scores, timings = {}, []
    with (destination / 'passages.jsonl').open('w') as evidence:
        for qid, rows in runs.items():
            query_start = time.perf_counter()
            q = query_tokens[qid]
            capacity = min(args.passage_tokens, backend.limit - len(q) - backend.special_tokens)
            if capacity <= 0:
                raise ValueError('query leaves no document token budget; query was not truncated')
            overlap = min(args.overlap_tokens, capacity - 1)
            batch, pending = [], []
            query_calls_start = counters['model_forward_calls']
            query_passages_start = counters['passage_scoring_calls']

            def flush():
                if not batch:
                    return
                counters['model_forward_calls_attempted'] += 1
                counters['passage_scoring_calls_attempted'] += len(batch)
                start = time.perf_counter()
                values = backend.predict(batch)
                counters['inference_seconds'] += time.perf_counter() - start
                if len(values) != len(batch) or any(not math.isfinite(value) for value in values):
                    raise ValueError('invalid model scores')
                counters['model_forward_calls'] += 1
                counters['passage_scoring_calls'] += len(batch)
                counters['input_tokens'] += sum(len(p['input_ids']) for p in batch)
                counters['padded_input_tokens'] += len(batch) * max(len(p['input_ids']) for p in batch)
                for item, value in zip(pending, values):
                    key = (qid, item['docid'])
                    scores[key] = max(scores.get(key, -math.inf), value)
                    evidence.write(json.dumps({**item, 'score': value}) + '\n')
                    counters['covered_document_tokens_across_query_pairs'] += item['newly_covered_tokens']
                batch.clear()
                pending.clear()

            for docid, _, _ in rows[:args.top_k]:
                tokens = doc_tokens[docid]
                spans = list(windows(len(tokens), capacity, overlap))
                coverage(spans, len(tokens))
                counters['query_document_pairs'] += 1
                counters['document_tokens_across_query_pairs'] += len(tokens)
                covered = 0
                for index, (start, end) in enumerate(spans):
                    pair = backend.pair(q, tokens[start:end])
                    if len(pair['input_ids']) != len(q) + end - start + backend.special_tokens or len(pair['input_ids']) > backend.limit:
                        raise ValueError('pair exceeds model budget or changed original tokens')
                    batch.append(pair)
                    pending.append({'qid': qid, 'docid': docid, 'passage_index': index,
                                    'token_start': start, 'token_end': end, 'document_tokens': len(tokens),
                                    'newly_covered_tokens': end - covered, 'input_tokens': len(pair['input_ids'])})
                    covered = end
                    if len(batch) == args.batch_size:
                        flush()
            flush()
            timings.append({'qid': qid, 'seconds': time.perf_counter() - query_start,
                            'passage_scoring_calls': counters['passage_scoring_calls'] - query_passages_start,
                            'model_forward_calls': counters['model_forward_calls'] - query_calls_start})
            atomic_write(destination / 'progress.json', json.dumps({'status': 'running', 'queries_complete': len(timings), **counters}, indent=2) + '\n')
            print(f"Scored query {qid}: {timings[-1]['passage_scoring_calls']} passages; {len(timings)}/{len(runs)} queries", flush=True)
    if counters['covered_document_tokens_across_query_pairs'] != counters['document_tokens_across_query_pairs']:
        raise ValueError('document coverage incomplete')
    return scores, timings, preprocessing_seconds


def render(runs, scores, top_k):
    lines = []
    for qid, rows in runs.items():
        ordered = sorted(rows[:top_k], key=lambda row: -scores[(qid, row[0])]) + rows[top_k:]
        for rank, row in enumerate(ordered, 1):
            lines.append(f'{qid} Q0 {row[0]} {rank} {len(rows)-rank+1} MONOBERT')
    return '\n'.join(lines) + '\n'


def main(argv=None, backend_factory=BertBackend):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage1', type=Path, nargs='?', default=CANONICAL)
    parser.add_argument('--collection', type=Path)
    parser.add_argument('--results-dir', type=Path)
    parser.add_argument('--top-k', type=int, default=100)
    parser.add_argument('--batch-size', type=int, default=8)
    parser.add_argument('--passage-tokens', type=int, default=384)
    parser.add_argument('--overlap-tokens', type=int, default=64)
    parser.add_argument('--device', choices=['auto', 'cpu', 'cuda', 'mps'], default='auto')
    parser.add_argument('--model-cache', type=Path, default=ROOT / '.cache/monobert-model')
    parser.add_argument('--local-files-only', action='store_true', help='No Hugging Face downloads; require cached checkpoint')
    parser.add_argument('--compute-usd-per-hour', type=float)
    parser.add_argument('--pricing-source', help='Hardware rate source and effective date, or documented internal rate')
    args = parser.parse_args(argv)
    if min(args.top_k, args.batch_size, args.passage_tokens) <= 0 or not 0 <= args.overlap_tokens < args.passage_tokens:
        parser.error('positive depth/batch/window required; overlap must be in [0, passage-tokens)')
    if args.compute_usd_per_hour is not None and (not math.isfinite(args.compute_usd_per_hour) or args.compute_usd_per_hour < 0 or not args.pricing_source):
        parser.error('compute rate must be finite, non-negative and have a --pricing-source')
    started = time.perf_counter()
    source = args.stage1.resolve()
    baseline = json.loads((source / 'manifest.json').read_text())
    if baseline.get('stage') != 'stage1' or baseline.get('status') != 'complete':
        parser.error('requires a completed stage-1 manifest')
    collection = (args.collection or Path(baseline['collection'])).resolve()
    for filename, key in [('run.trec', 'run_sha256'), ('topics.txt', 'topics_sha256'), ('qrels.txt', 'qrels_sha256')]:
        if sha(source / filename) != baseline[key]:
            parser.error(f'{filename} hash mismatch')
    if sha(collection) != baseline['collection_sha256']:
        parser.error('collection hash mismatch')
    context = provenance()
    if context['branch'] == 'original':
        parser.error('original is read-only')
    destination = (args.results_dir or ROOT / 'reranking/results' / context['branch'] / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')).resolve()
    destination.mkdir(parents=True, exist_ok=False)
    counters = new_counters()
    try:
        runs = read_run(source / 'run.trec')
        queries = dict(line.split(maxsplit=1) for line in (source / 'topics.txt').read_text().splitlines() if line.strip())
        if runs.keys() != queries.keys():
            raise ValueError('run and query IDs differ')
        preparation_start = time.perf_counter()
        wanted = {row[0] for rows in runs.values() for row in rows[:args.top_k]}
        docs = documents(collection, wanted)
        extraction_seconds = time.perf_counter() - preparation_start
        model_start = time.perf_counter()
        backend = backend_factory(args)
        load_seconds = time.perf_counter() - model_start
        scoring_start = time.perf_counter()
        scores, timings, preprocessing_seconds = score_all(runs, queries, docs, backend, args, destination, counters)
        scoring_seconds = time.perf_counter() - scoring_start - preprocessing_seconds
        atomic_write(destination / 'run.trec', render(runs, scores, args.top_k))
        atomic_write(destination / 'queries.json', json.dumps(timings, indent=2) + '\n')
        rerank_seconds = time.perf_counter() - preparation_start
        evaluation_start = time.perf_counter()
        metrics = evaluate(source / 'qrels.txt', destination / 'run.trec', destination / 'trec_eval.txt')
        with (destination / 'trec_eval-per-topic.txt').open('w') as out:
            subprocess.run(['trec_eval', '-q', '-c', '-M1000', str(source / 'qrels.txt'), str(destination / 'run.trec')], check=True, stdout=out)
        evaluation_seconds = time.perf_counter() - evaluation_start
        elapsed = time.perf_counter() - started
        metadata = {'stage': 'reranking', 'status': 'complete', 'method': 'monobert-maxp', **context,
            'model': MODEL, 'model_revision': REVISION, 'tokenizer_revision': REVISION,
            'relevance_label_index': 1, 'score': 'log_softmax(relevant); MaxP across all passages',
            'device': backend.device, 'dtype': 'float32', 'model_parameters': backend.parameters,
            'library_versions': backend.versions, 'checkpoint_unexpected_keys': backend.unexpected_keys,
            'stage1_directory': str(source), 'stage1_manifest_sha256': sha(source / 'manifest.json'),
            'stage1_run_sha256': baseline['run_sha256'], 'collection_sha256': baseline['collection_sha256'],
            'topics_sha256': baseline['topics_sha256'], 'qrels_sha256': baseline['qrels_sha256'],
            'run_sha256': sha(destination / 'run.trec'), 'metrics': metrics,
            'source_sha256': {name: sha(ROOT / name) for name in ('reranking/monobert.py', 'reranking/jev.py', 'tools/stage_artifacts.py')},
            'top_k': args.top_k, 'batch_size': args.batch_size, 'passage_tokens': args.passage_tokens,
            'overlap_tokens': args.overlap_tokens, 'model_input_limit': backend.limit,
            'coverage_fraction': 1.0, 'truncated_documents': 0, 'queries': len(runs), 'unique_documents': len(docs),
            'cache_mode': 'no score cache; every passage inferred', 'model_downloads_allowed': not args.local_files_only,
            'extraction_seconds': extraction_seconds, 'tokenization_seconds': preprocessing_seconds,
            'model_load_seconds': load_seconds, 'scoring_seconds': scoring_seconds, 'rerank_seconds': rerank_seconds,
            'evaluation_seconds': evaluation_seconds, 'total_wall_seconds': elapsed,
            'query_p50_seconds': percentile([t['seconds'] for t in timings], .50),
            'query_p95_seconds': percentile([t['seconds'] for t in timings], .95),
            'stage1_search_seconds': baseline['search_seconds'],
            'end_to_end_search_seconds': baseline['search_seconds'] + rerank_seconds,
            'compute_usd_per_hour': args.compute_usd_per_hour, 'pricing_source': args.pricing_source,
            'hosted_inference_api_cost_usd': 0.0,
            'estimated_compute_cost_usd': cost(elapsed, args.compute_usd_per_hour),
            'estimated_reranking_compute_cost_usd': cost(rerank_seconds, args.compute_usd_per_hour),
            'cost_scope': 'rate times measured process wall duration; excludes prior dependency install/model prefetch and stage-1 retrieval; not a bill',
            'timing_scope': 'rerank includes text extraction, model load/download if needed, tokenization, scoring and run output; excludes hash checks and trec_eval; per-query time excludes shared setup',
            **counters}
        report(destination, metadata, baseline['metrics'])
        with (destination / 'results.md').open('a') as out:
            out.write('\n\n## Calls, time and cost\n\n| Measurement | Value |\n| --- | ---: |\n')
            for label, key in [('Passage scoring calls','passage_scoring_calls'),('Model forward calls (batches)','model_forward_calls'),('Hosted inference API calls','hosted_inference_api_calls'),('Model load (seconds)','model_load_seconds'),('Reranking (seconds)','rerank_seconds'),('Composed end-to-end search (seconds)','end_to_end_search_seconds'),('Total process wall time (seconds)','total_wall_seconds'),('Query p50 (seconds, shared setup excluded)','query_p50_seconds'),('Query p95 (seconds, shared setup excluded)','query_p95_seconds'),('Hosted inference API cost (USD)','hosted_inference_api_cost_usd'),('Estimated local compute cost (USD)','estimated_compute_cost_usd')]:
                value = metadata[key]
                display = 'Unknown — supply an hourly rate' if value is None else (f'{value:.6f}' if isinstance(value, float) else str(value))
                out.write(f'| {label} | {display} |\n')
            out.write('\nFull document-token coverage: **100%**. Passage token offsets and scores: [passages.jsonl](passages.jsonl). Per-query measurements: [queries.json](queries.json).\n')
        atomic_write(destination / 'progress.json', json.dumps({'status': 'complete', **counters}, indent=2) + '\n')
        print(destination)
        return metadata
    except BaseException as error:
        elapsed = time.perf_counter() - started
        atomic_write(destination / 'failure.json', json.dumps({'status': 'failed', 'error_type': type(error).__name__,
            'stage1_directory': str(source), 'total_wall_seconds': elapsed, 'hosted_inference_api_cost_usd': 0,
            'estimated_compute_cost_usd': cost(elapsed, args.compute_usd_per_hour), **counters}, indent=2) + '\n')
        atomic_write(destination / 'progress.json', json.dumps({'status': 'failed', **counters}, indent=2) + '\n')
        raise


if __name__ == '__main__':
    main()
