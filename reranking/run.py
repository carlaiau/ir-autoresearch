#!/usr/bin/env python3
"""Evaluate JEV against a frozen stage-1 run, with separate timing and cost."""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from stage_artifacts import ROOT, evaluate, provenance, report, sha, timed


def accounting(results, input_rate, output_rate):
    def usage(rows):
        total = {'input_tokens': 0, 'output_tokens': 0}
        for row in rows:
            value = row['response'].get('usage', {})
            for key in total:
                amount = value.get(key)
                if not isinstance(amount, int) or isinstance(amount, bool) or amount < 0:
                    return None
                total[key] += amount
        return total
    fresh = [r for r in results if not r['cache_hit']]
    all_usage, new_usage = usage(results), usage(fresh)
    def cost(tokens):
        if tokens is None or input_rate is None or output_rate is None:
            return None
        return (tokens['input_tokens'] * input_rate + tokens['output_tokens'] * output_rate) / 1_000_000
    return {'all_response_tokens': all_usage, 'new_response_tokens': new_usage,
            'new_scoring_calls': len(fresh), 'cache_hits': len(results) - len(fresh),
            'estimated_new_api_cost_usd': cost(new_usage) if fresh else 0.0,
            'estimated_uncached_api_cost_usd': cost(all_usage), 'compute_cost_usd': None}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('stage1', type=Path)
    p.add_argument('--collection', type=Path, help='Override location; content hash must match')
    p.add_argument('--results-dir', type=Path)
    p.add_argument('--top-k', type=int, default=200)
    p.add_argument('--workers', type=int, default=8)
    p.add_argument('--max-chars', type=int, default=24000)
    p.add_argument('--model', default='jev-latest')
    p.add_argument('--cache', type=Path, default=ROOT / 'wsj-eval/jev-cache')
    p.add_argument('--cache-only', action='store_true')
    p.add_argument('--input-usd-per-million', type=float)
    p.add_argument('--output-usd-per-million', type=float)
    p.add_argument('--pricing-source', help='Price source and effective date for this model')
    args = p.parse_args()
    rates = (args.input_usd_per_million, args.output_usd_per_million)
    if any(r is not None for r in rates) and (not all(r is not None and math.isfinite(r) and r >= 0 for r in rates) or not args.pricing_source):
        p.error('supply both finite non-negative USD rates and --pricing-source, or neither rate')
    source = args.stage1.resolve()
    baseline = json.loads((source / 'manifest.json').read_text())
    if baseline['stage'] != 'stage1' or baseline['status'] != 'complete':
        p.error('requires a completed stage-1 manifest')
    collection = (args.collection or Path(baseline['collection'])).resolve()
    for name, key in [('run.trec', 'run_sha256'), ('topics.txt', 'topics_sha256'), ('qrels.txt', 'qrels_sha256')]:
        if sha(source / name) != baseline[key]:
            p.error(f'stage-1 {name} hash mismatch')
    if sha(collection) != baseline['collection_sha256']:
        p.error('collection hash mismatch')
    if min(args.top_k, args.workers, args.max_chars) <= 0:
        p.error('top-k, workers, and max-chars must be positive')
    context = provenance()
    if context['branch'] == 'original':
        p.error('original is read-only')
    destination = (args.results_dir or ROOT / 'reranking/results' / context['branch'] / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')).resolve()
    destination.mkdir(parents=True, exist_ok=False)
    command = [sys.executable, ROOT / 'reranking/jev.py', '--collection', collection,
               '--topics', source / 'topics.txt', '--run', source / 'run.trec', '--output', destination / 'run.trec',
               '--metadata', destination / 'jev.json', '--cache', args.cache.resolve(), '--model', args.model,
               '--top-k', args.top_k, '--workers', args.workers, '--max-chars', args.max_chars]
    if args.cache_only:
        command.append('--cache-only')
    try:
        elapsed = timed(command)
        details = json.loads((destination / 'jev.json').read_text())
        metrics = evaluate(source / 'qrels.txt', destination / 'run.trec', destination / 'trec_eval.txt')
        metadata = {'stage': 'reranking', 'method': 'jev-pointwise', 'status': 'complete', **context,
                    'stage1_directory': str(source), 'stage1_manifest_sha256': sha(source / 'manifest.json'),
                    'stage1_run_sha256': baseline['run_sha256'], 'run_sha256': sha(destination / 'run.trec'),
                    'collection_sha256': baseline['collection_sha256'], 'topics_sha256': baseline['topics_sha256'],
                    'qrels_sha256': baseline['qrels_sha256'], 'metrics': metrics, 'queries': baseline['queries'],
                    'stage1_search_seconds': baseline['search_seconds'], 'rerank_seconds': elapsed,
                    'end_to_end_search_seconds': baseline['search_seconds'] + elapsed,
                    'timing_scope': 'rerank includes Python startup, document extraction, scoring/cache reads and output writes; excludes hash verification and trec_eval',
                    'cache_mode': 'all-cached' if details['cache_hits'] == details['pairs'] else ('mixed' if details['cache_hits'] else 'uncached'),
                    'cache_only_requested': args.cache_only,
                    'source_sha256': {name: sha(ROOT / name) for name in ('reranking/jev.py', 'reranking/run.py', 'tools/stage_artifacts.py')},
                    'model_requested': args.model, 'models_returned': sorted({r['response']['model'] for r in details['results']}),
                    'top_k': args.top_k, 'workers': args.workers, 'max_chars': args.max_chars,
                    'pairs': details['pairs'], 'truncated_pairs': details['truncated_pairs'],
                    'input_usd_per_million': rates[0], 'output_usd_per_million': rates[1], 'pricing_source': args.pricing_source,
                    **accounting(details['results'], *rates)}
        report(destination, metadata, baseline['metrics'])
    except Exception:
        (destination / 'failure.json').write_text(json.dumps({'status': 'failed', 'stage1_directory': str(source),
            'cost_usd': None, 'note': 'May have incurred API usage. Successful responses remain cached; this is not a completed evaluation.'}) + '\n')
        raise
    print(destination)


if __name__ == '__main__':
    main()
