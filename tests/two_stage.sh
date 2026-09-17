#!/usr/bin/env bash
# Offline integration: frozen candidate artifacts, cache-only reranking and cost.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 - <<'PY'
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
sys.path.insert(0, 'reranking')
import jev
from run import accounting
root = Path.cwd()
with tempfile.TemporaryDirectory() as tmp:
    work = Path(tmp)
    source, result, cache = work/'stage1', work/'stage2', work/'cache'
    env = dict(os.environ, JASSJR_JEV_RERANK='off', JASSJR_RERANK_DOCS='25')
    # Prevent local dotenv files from changing cache identity or enabling calls.
    env['TYPESAFE_ENDPOINT'] = 'https://offline.invalid'
    env['TYPESAFE_API_KEY'] = 'offline-test'
    command = [sys.executable, 'stage1/run.py', str(root/'tests/fixtures/smoke.xml'),
               '-t', str(root/'tests/fixtures/smoke_topics.txt'), '-q', str(root/'tests/fixtures/smoke_qrels.txt'),
               '-w', str(work/'index'), '--results-dir', str(source)]
    # Discover fixture filename from the existing smoke script if needed.
    fixture = root/'tests/fixtures/smoke.xml'
    if not fixture.exists():
        candidates = list((root/'tests/fixtures').glob('*.xml'))
        assert len(candidates) == 1
        command[2] = str(candidates[0])
    subprocess.run(command, env=env, check=True)
    before = {p.name: p.read_bytes() for p in source.iterdir()}
    baseline = json.loads((source/'manifest.json').read_text())
    assert baseline['lexical_config']['JASSJR_RERANK_DOCS'] == '0'
    runs = jev.read_run(source/'run.trec')
    topics = dict(line.split(maxsplit=1) for line in (source/'topics.txt').read_text().splitlines())
    pairs = [(qid,r[0]) for qid,rows in runs.items() for r in rows[:2]]
    docs = jev.documents(Path(baseline['collection']), {docid for _,docid in pairs})
    cache.mkdir()
    for qid,docid in pairs:
        payload = {'model':'offline', 'state':{'query':topics[qid], 'candidate_article':docs[docid][:24000]}, 'questions':{'relevant':jev.QUESTION}}
        key = jev.digest({'endpoint':env['TYPESAFE_ENDPOINT'], 'payload':payload, 'document_sha256':jev.digest(docs[docid])})
        response = {'model':'offline', 'answers':{'relevant':{'type':'noul','noul':0.5}}, 'usage':{'input_tokens':100, 'output_tokens':2}}
        (cache/(key+'.json')).write_text(json.dumps(response))
    rerank = [sys.executable, 'reranking/run.py', str(source), '--results-dir', str(result),
              '--model', 'offline', '--top-k', '2', '--cache', str(cache), '--cache-only',
              '--input-usd-per-million','1','--output-usd-per-million','2','--pricing-source','synthetic test rate']
    subprocess.run(rerank,env=env,check=True)
    manifest = json.loads((result/'manifest.json').read_text())
    assert manifest['new_scoring_calls'] == 0
    assert manifest['estimated_new_api_cost_usd'] == 0
    assert abs(manifest['estimated_uncached_api_cost_usd'] - len(pairs)*104/1_000_000) < 1e-10
    assert manifest['metrics'] == baseline['metrics']
    assert manifest['end_to_end_search_seconds'] >= baseline['search_seconds']
    assert before == {p.name:p.read_bytes() for p in source.iterdir()}
    assert (result/'results.md').exists() and (source/'results.md').exists()
    # Corrupted input must fail before any reranking directory/call is created.
    (source/'run.trec').write_text((source/'run.trec').read_text()+'\n')
    failed = subprocess.run(rerank,env=env,capture_output=True,text=True)
    assert failed.returncode != 0 and 'hash mismatch' in failed.stderr
    # Restore it, then force a missing-cache failure; baseline is still intact.
    (source/'run.trec').write_bytes(before['run.trec'])
    rerank[rerank.index(str(result))] = str(work/'failed-stage2')
    rerank[rerank.index('offline')] = 'uncached-model'
    failed = subprocess.run(rerank,env=env,capture_output=True,text=True)
    assert failed.returncode != 0
    assert not (work/'failed-stage2/results.md').exists()
    assert (work/'failed-stage2/failure.json').exists()
    assert before == {p.name:p.read_bytes() for p in source.iterdir()}
    # Unknown usage/pricing must remain unknown for newly scored responses.
    assert accounting([{'cache_hit':False,'response':{}}],1,2)['estimated_new_api_cost_usd'] is None
    assert accounting([{'cache_hit':False,'response':{'usage':{'input_tokens':100,'output_tokens':2}}}],None,None)['estimated_new_api_cost_usd'] is None
print('Two-stage baseline preservation, hash validation, failure isolation and cost accounting passed')
PY
