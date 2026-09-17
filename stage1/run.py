#!/usr/bin/env python3
"""Build and freeze lexical retrieval before any reranking."""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import sys
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from stage_artifacts import ROOT, evaluate, provenance, report, sha, timed


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('collection', type=Path)
    p.add_argument('-t', '--topics', type=Path, default=ROOT / '51-100.titles.txt')
    p.add_argument('-q', '--qrels', type=Path, default=ROOT / '51-100.qrels.txt')
    p.add_argument('-w', '--workdir', type=Path, default=ROOT / 'wsj-eval/stage1')
    p.add_argument('-o', '--output', type=Path, help='Optional additional copy of the lexical TREC run')
    p.add_argument('--results-dir', type=Path, help='New directory; must not already exist')
    args = p.parse_args()
    collection, topics, qrels = (x.resolve(strict=True) for x in (args.collection, args.topics, args.qrels))
    if not collection.is_file():
        p.error('collection must be the absolute path to a single WSJ file')
    if os.environ.get('JASSJR_JEV_RERANK', 'off') != 'off':
        p.error('stage 1 cannot rerank; run reranking/run.py on its saved result directory')
    search_env = dict(os.environ, JASSJR_RERANK_DOCS='0')
    lexical_defaults = {'JASSJR_BM25_K1': '0.7', 'JASSJR_BM25_B': '0.3',
                        'JASSJR_FEEDBACK_DOCS': '5', 'JASSJR_EXPANSION_TERMS': '6',
                        'JASSJR_EXPANSION_WEIGHT': '0.45', 'JASSJR_EXPANSION_MAX_QUERY_TERMS': '6',
                        'JASSJR_EXPANSION_ONLY': '0', 'JASSJR_RERANK_DOCS': '0'}
    lexical_config = {key: search_env.get(key, value) for key, value in lexical_defaults.items()}
    context = provenance()
    if context['branch'] == 'original':
        p.error('original is a read-only initialization archive')
    destination = args.results_dir or ROOT / 'stage1/results' / context['branch'] / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    destination = destination.resolve()
    if args.output and (args.output.resolve().is_relative_to(destination) or args.output.exists()):
        p.error('optional output must be a new file outside the saved result directory')
    destination.mkdir(parents=True, exist_ok=False)
    args.workdir.mkdir(parents=True, exist_ok=True)
    # Each run owns its binaries/index; concurrent evaluations cannot corrupt one another.
    with tempfile.TemporaryDirectory(dir=args.workdir.resolve()) as tmp:
        work = Path(tmp)
        index, search = work / 'index', work / 'search'
        timed(['go', 'build', '-o', index, ROOT / 'index/JASSjr_index.go'])
        timed(['go', 'build', '-o', search, ROOT / 'search/JASSjr_search.go'])
        with (destination / 'index.log').open('w') as log:
            index_seconds = timed([index, collection], cwd=work, stdout=log)
        with topics.open() as queries, (destination / 'run.trec').open('w') as run:
            search_seconds = timed([search], cwd=work, stdin=queries, stdout=run, env=search_env)
    shutil.copyfile(topics, destination / 'topics.txt')
    shutil.copyfile(qrels, destination / 'qrels.txt')
    metrics = evaluate(destination / 'qrels.txt', destination / 'run.trec', destination / 'trec_eval.txt')
    metadata = {'stage': 'stage1', 'status': 'complete', **context, 'collection': str(collection),
                'collection_sha256': sha(collection), 'topics_sha256': sha(topics), 'qrels_sha256': sha(qrels),
                'run_sha256': sha(destination / 'run.trec'), 'metrics': metrics,
                'queries': sum(bool(line.strip()) for line in topics.read_text().splitlines()),
                'index_seconds': index_seconds, 'search_seconds': search_seconds,
                'lexical_config': lexical_config, 'api_cost_usd': 0, 'compute_cost_usd': None,
                'bm25_k1': os.environ.get('JASSJR_BM25_K1', '0.7'),
                'bm25_b': os.environ.get('JASSJR_BM25_B', '0.3'),
                'source_sha256': {name: sha(ROOT / name) for name in ('index/JASSjr_index.go', 'search/JASSjr_search.go')}}
    report(destination, metadata)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(destination / 'run.trec', args.output)
    print(destination)


if __name__ == '__main__':
    main()
