#!/usr/bin/env python3
"""Read-only audit of the complete top-20 JEV duo experiment; no API calls."""
import json,sys,math
from pathlib import Path
from collections import Counter,defaultdict
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'reranking'))
from jev_duo import load_inputs,payload_for,tasks_for,aggregate
from jev import digest,read_run
from stage_artifacts import sha
out=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else root/'reranking/results/jev-duo-noul-top20-20260918'
m=json.loads((out/'manifest.json').read_text())
b,p,runs,queries,docs=load_inputs(root/'stage1/results/integrated-main-20260918',root/'reranking/results/jev-full-documents-top100-20260918',None,20)
rows=[json.loads(x) for x in (out/'scores.jsonl').read_text().splitlines()]
attempts=[json.loads(x) for x in (out/'attempts.jsonl').read_text().splitlines()]
byq=defaultdict(list)
for r in rows:byq[r['qid']].append(r)
assert len(rows)==19000 and len(byq)==50
result=read_run(out/'run.trec')
for q,candidates in runs.items():
    expected={(t['docid'],t['docid_b']):t for t in tasks_for(q,candidates,docs,20)}
    for r in byq[q]:
        t=expected[r['docid'],r['docid_b']]
        assert r['document_a_sha256']==digest(t['document_a'])
        assert r['document_b_sha256']==digest(t['document_b'])
        assert r['document_a_characters']==len(t['document_a'])
        assert r['document_b_characters']==len(t['document_b'])
        assert r['payload_sha256']==digest(payload_for(t,queries[q],m['model_requested']))
        assert r['response']['model']==m['model_requested']
    pairs={(r['docid'],r['docid_b']) for r in byq[q]}
    assert len(byq[q])==380 and pairs==set(expected)
    assert all(0<=r['score']<=1 for r in byq[q])
    sums={d:sum(r['score'] for r in byq[q] if r['docid']==d) for d,_,_ in candidates[:20]}
    exact,_=aggregate(byq[q],candidates[:20])
    assert all(math.isclose(sums[d],exact[d],abs_tol=1e-12) for d in sums)
    sums=exact
    expected_order=sorted(candidates[:20],key=lambda c:-sums[c[0]])+candidates[20:]
    assert [r[0] for r in result[q]]==[r[0] for r in expected_order]
assert m['run_sha256']==sha(out/'run.trec')
for name,h in m['source_sha256'].items():assert sha(root/name)==h
assert m['api_attempts']==len(attempts)
assert m['failed_api_attempts']==sum(a['status']=='failed' for a in attempts)
for token in ('input_tokens','output_tokens'):
    assert m['new_response_tokens'][token]==sum(r['response']['usage'][token] for r in rows if not r['cache_hit'])
assert math.isclose(m['estimated_new_api_cost_usd'],m['new_response_tokens']['input_tokens']*.042/1e6)
print('PASS: 19,000 complete directed comparisons; original full-text/payload hashes; pinned model; Sum ranking; unchanged tails; source/run hashes; attempt, token and cost accounting.')
print(json.dumps({k:m[k] for k in ('metrics','api_attempts','failed_api_attempts','duo_seconds','query_p50_seconds','query_p95_seconds','estimated_new_api_cost_usd','composed_search_seconds','composed_estimated_api_cost_usd','pointwise_ap_improved','pointwise_ap_worse','pointwise_ap_tied')},indent=2))
