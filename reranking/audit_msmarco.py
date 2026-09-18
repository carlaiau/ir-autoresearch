#!/usr/bin/env python3
"""Reconstruct rankings/content coverage and compare completed DL2019 runs."""
import argparse
from collections import defaultdict
import json
import math
from pathlib import Path

from msmarco import METRICS, QUESTION, evaluation, save, validate_scores, verified_inputs
from monobert import MODEL, REVISION, coverage, render, windows
from jev import digest
from jev_compare import prepare
from run import accounting
from stage_artifacts import ROOT, sha


def rows(path):
    with path.open() as stream:
        return [json.loads(line) for line in stream]


def statistics(differences, seed=73, bootstrap=10000, permutations=100000):
    import numpy as np
    values = np.asarray(differences, dtype=float)
    if not len(values) or not np.isfinite(values).all():
        raise ValueError('invalid paired observations')
    rng = np.random.default_rng(seed)
    draws = rng.choice(values, size=(bootstrap, len(values)), replace=True).mean(axis=1)
    lo, hi = np.quantile(draws, [.025, .975])
    observed = abs(values.mean())
    extreme = 0
    for first in range(0, permutations, 1000):
        size = min(1000, permutations-first)
        signs = rng.choice([-1, 1], size=(size, len(values)))
        extreme += int((abs((signs*values).mean(axis=1)) >= observed-1e-12).sum())
    return {'mean_delta': float(values.mean()), 'bootstrap_95_ci': [float(lo), float(hi)],
            'two_sided_randomization_p': (extreme+1)/(permutations+1),
            'improved': int((values>0).sum()), 'worse': int((values<0).sum()),
            'tied': int((values==0).sum()), 'seed': seed,
            'bootstrap_samples': bootstrap, 'sign_randomization_draws': permutations}


def holm(probabilities):
    result, previous = {}, 0.0
    for i, key in enumerate(sorted(probabilities, key=probabilities.get)):
        previous = max(previous, min(1.0, probabilities[key]*(len(probabilities)-i)))
        result[key] = previous
    return result


def audit_mono(directory, source, runs, queries, docs, tokenizer):
    metadata = json.loads((directory/'manifest.json').read_text())
    if metadata['status'] != 'complete' or metadata['input_manifest_sha256'] != sha(source/'manifest.json'):
        raise ValueError('reference input mismatch')
    if metadata['model_revision'] != REVISION or metadata['tokenizer_revision'] != REVISION:
        raise ValueError('unexpected checkpoint/tokenizer')
    records = defaultdict(list)
    for row in rows(directory/'passages.jsonl'):
        records[row['qid'], row['docid']].append(row)
    tokens = {d: tokenizer.encode(t, add_special_tokens=False, truncation=False, verbose=False) for d, t in docs.items()}
    scores, covered, multi, normalization_changed = {}, 0, 0, 0
    expected_batch_calls = 0
    expected_input_tokens, expected_padded_tokens = 0, 0
    for q, candidates in runs.items():
        qlen = len(tokenizer.encode(queries[q], add_special_tokens=False))
        cap = min(metadata['passage_tokens'], metadata['model_input_limit']-qlen-tokenizer.num_special_tokens_to_add(pair=True))
        q_input_lengths = []
        for d, _, _ in candidates:
            n = len(tokens[d])
            expected = list(windows(n, cap, min(metadata['overlap_tokens'], cap-1)))
            actual = records[q, d]
            if [(r['token_start'], r['token_end']) for r in actual] != expected:
                raise ValueError('token coverage differs from protocol')
            coverage(expected, n)
            previous = 0
            for i, ((start, end), r) in enumerate(zip(expected, actual)):
                length = qlen + end-start + tokenizer.num_special_tokens_to_add(pair=True)
                if (r['passage_index'] != i or r['document_tokens'] != n or
                    r['newly_covered_tokens'] != end-previous or r['input_tokens'] != length or
                    length > metadata['model_input_limit'] or not math.isfinite(r['score'])):
                    raise ValueError('invalid mono passage evidence')
                q_input_lengths.append(length)
                previous = end
            covered += n
            multi += len(expected)>1
            normalization_changed += tokenizer.decode(tokens[d], skip_special_tokens=False, clean_up_tokenization_spaces=False) != docs[d]
            scores[q, d] = max(r['score'] for r in actual)
        expected_batch_calls += math.ceil(len(q_input_lengths)/metadata['batch_size'])
        expected_input_tokens += sum(q_input_lengths)
        for i in range(0, len(q_input_lengths), metadata['batch_size']):
            batch = q_input_lengths[i:i+metadata['batch_size']]
            expected_padded_tokens += len(batch)*max(batch)
    validate_scores(runs, scores)
    if records.keys() != scores.keys():
        raise ValueError('unexpected passage pairs')
    if (sha(directory/'passages.jsonl') != metadata['passages_sha256'] or
        sha(directory/'run.trec') != metadata['run_sha256'] or
        render(runs, scores, 1000).replace(' MONOBERT\n', ' monobert\n') != (directory/'run.trec').read_text()):
        raise ValueError('mono ranking/evidence mismatch')
    counters = metadata['counters']
    if (counters['covered_document_tokens_across_query_pairs'] != covered or
        counters['document_tokens_across_query_pairs'] != covered or
        counters['passage_scoring_calls'] != sum(map(len, records.values())) or
        counters['model_forward_calls'] != expected_batch_calls or
        counters['input_tokens'] != expected_input_tokens or counters['padded_input_tokens'] != expected_padded_tokens):
        raise ValueError('mono counter mismatch')
    result = {'status': 'passed', 'candidate_pairs': len(scores), 'scoring_windows': sum(map(len, records.values())),
              'pairs_needing_multiple_windows': multi, 'pairs_changed_by_decode_normalization': normalization_changed,
              'covered_tokens': covered, 'coverage_fraction': 1.0, 'ranking_reconstructed': True,
              'batch_and_token_counters_verified': True}
    save(directory/'audit.json', result)
    return result


def audit_jev(directory, mono, source, runs, queries, docs, tokenizer):
    metadata = json.loads((directory/'manifest.json').read_text())
    if (metadata['status'] != 'complete' or metadata['input_manifest_sha256'] != sha(source/'manifest.json') or
        metadata['monobert_manifest_sha256'] != sha(mono/'manifest.json') or metadata['question'] != QUESTION):
        raise ValueError('JEV reference/prompt mismatch')
    mode = 'passages' if metadata['method'] == 'jev-matched' else 'documents'
    tasks = prepare(mode, runs, queries, docs, mono, tokenizer)
    def key(row): return row['qid'], row['docid'], row.get('passage_index')
    expected = {key(t): t for jobs in tasks.values() for t in jobs}
    scored = rows(directory/'scores.jsonl')
    actual = {key(r): r for r in scored}
    if len(actual) != len(scored) or actual.keys() != expected.keys():
        raise ValueError('duplicate/missing/unexpected JEV scores')
    scores = {}
    for k, task in expected.items():
        row = actual[k]
        for field, value in task.items():
            if field != 'text' and row[field] != value:
                raise ValueError('JEV boundary/identity mismatch')
        if row['payload_text_sha256'] != digest(task['text']) or row['payload_characters'] != len(task['text']):
            raise ValueError('JEV text mismatch')
        if row['response']['model'] != 'jev-1.13.0' or not math.isfinite(row['score']) or not 0 <= row['score'] <= 1:
            raise ValueError('JEV model/score mismatch')
        pair = row['qid'], row['docid']
        scores[pair] = max(scores.get(pair, -math.inf), row['score'])
    validate_scores(runs, scores)
    rendered = render(runs, scores, 1000).replace(' MONOBERT\n', f' {metadata["method"]}\n')
    if rendered != (directory/'run.trec').read_text() or sha(directory/'run.trec') != metadata['run_sha256']:
        raise ValueError('JEV ranking mismatch')
    attempts = rows(directory/'attempts.jsonl')
    success = [r for r in attempts if r['status'] == 'success']
    fresh = [r for r in scored if not r['cache_hit']]
    if (len(attempts) != metadata['api_attempts'] or len(success) != len(fresh) or
        {r['cache_key'] for r in success} != {r['cache_key'] for r in fresh}):
        raise ValueError('JEV attempt accounting mismatch')
    counts = accounting(scored, metadata['input_usd_per_million'], metadata['output_usd_per_million'])
    if any(metadata[k] != v for k, v in counts.items()):
        raise ValueError('JEV cost/usage mismatch')
    result = {'status': 'passed', 'candidate_pairs': len(scores), 'scoring_units': len(scored),
              'payload_hashes_and_boundaries_verified': True, 'ranking_reconstructed': True,
              'attempt_usage_cost_verified': True}
    save(directory/'audit.json', result)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=ROOT/'reranking/results/msmarco-dl2019')
    p.add_argument('--data', type=Path, default=ROOT/'.cache/msmarco-dl2019')
    p.add_argument('--mono-only', action='store_true')
    args = p.parse_args()
    source, mono = args.root/'input', args.root/'monobert'
    runs, queries, docs, _ = verified_inputs(args.data, source)
    from transformers import BertTokenizerFast
    tokenizer = BertTokenizerFast.from_pretrained(MODEL, revision=REVISION, cache_dir=ROOT/'.cache/monobert-model', local_files_only=True)
    print(audit_mono(mono, source, runs, queries, docs, tokenizer), flush=True)
    if args.mono_only:
        return
    reference = json.loads((mono/'metrics-per-query.json').read_text())
    comparisons = {}
    for method in ('jev-matched', 'jev-full'):
        directory = args.root/method
        print(audit_jev(directory, mono, source, runs, queries, docs, tokenizer), flush=True)
        # Recompute from run files independently of saved aggregate metrics.
        recomputed = evaluation(source, directory)
        metadata = json.loads((directory/'manifest.json').read_text())
        if recomputed != metadata['metrics']:
            raise ValueError('evaluation mismatch')
        current = json.loads((directory/'metrics-per-query.json').read_text())
        if current.keys() != reference.keys() or current.keys() != queries.keys():
            raise ValueError('paired query IDs mismatch')
        if any(current[q]['recall_1000'] != reference[q]['recall_1000'] for q in queries):
            raise ValueError('reranking changed recall of the complete candidate set')
        comparisons[method] = {
            'metrics': {m: statistics([current[q][m]-reference[q][m] for q in queries]) for m in METRICS},
            'per_query': [{'qid': q, 'delta': {m: round(current[q][m]-reference[q][m], 6) for m in METRICS}} for q in queries],
        }
    if evaluation(source, mono) != json.loads((mono/'manifest.json').read_text())['metrics']:
        raise ValueError('mono evaluation mismatch')
    corrected = holm({m: c['metrics']['ndcg_cut_10']['two_sided_randomization_p'] for m, c in comparisons.items()})
    for method, value in corrected.items():
        comparisons[method]['metrics']['ndcg_cut_10']['holm_adjusted_p'] = value
    save(args.root/'paired-analysis.json', {'reference': 'monobert', 'queries': len(queries),
        'precision': 'trec_eval four-decimal per-query output', 'primary_metric': 'ndcg_cut_10',
        'multiple_testing': 'Holm over two primary comparisons; secondary metrics descriptive',
        'comparisons': comparisons})
    print('All audits and paired comparisons complete.', flush=True)


if __name__ == '__main__':
    main()
