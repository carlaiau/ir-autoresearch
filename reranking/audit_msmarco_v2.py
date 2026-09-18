#!/usr/bin/env python3
"""Audit completed DL2021 JEV MaxP evidence without making API requests."""
import json,math,tempfile
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from audit_msmarco import statistics
import msmarco_v2_documents as v
from jev import validate_response

def read(path):return json.loads(path.read_text())
def lines(path):return [json.loads(line) for line in path.read_text().splitlines()]
def main():
    root=v.ROOT/'reranking/results/msmarco-v2-dl2021-documents';dest=root/'jev-large-windows'
    args=SimpleNamespace(input=root/'input',data=v.ROOT/'.cache/msmarco-v2-dl2021',model='jev-1.13.0')
    runs,queries,docs,frozen=v.verified(args);meta=read(dest/'manifest.json')
    assert meta['status']=='complete' and meta['method']=='jev-large-windows'
    assert meta['input_identity_sha256']==frozen['input_identity_sha256']
    for path,key in [(args.input/'manifest.json','input_manifest_sha256'),(root/'preflight.json','preflight_sha256'),(root/'large-window-plan.json','large_window_plan_sha256'),(dest/'run.trec','run_sha256')]:assert v.sha(path)==meta[key]
    for file,h in meta['source_sha256'].items():assert v.sha(v.ROOT/file)==h
    tasks=v.large_tasks(args,runs,queries,docs);context=v.audit_large_windows(args,tasks,queries)
    assert context==meta['context_audit']
    identity=lambda r:(r['qid'],r['docid'],r['passage_index'])
    expected={identity(t):t for jobs in tasks.values() for t in jobs}
    rows=lines(dest/'scores.jsonl');attempts=lines(dest/'attempts.jsonl')
    assert len(rows)==len(expected)==6090 and len({identity(r) for r in rows})==6090
    assert {identity(r) for r in rows}==set(expected)
    scores={};tokens=Counter()
    for r in rows:
        t=expected[identity(r)]
        for key,value in t.items():
            if key!='text':assert r[key]==value
        assert r['payload_text_sha256']==v.digest(t['text']) and r['payload_characters']==len(t['text'])
        assert not r['cache_hit'] and math.isfinite(r['score']) and 0<=r['score']<=1
        response=read(args.data/'jev-large-windows'/(r['cache_key']+'.json'))
        assert validate_response(response)==r['score']
        assert response['model']==args.model and response['usage']==r['response']['usage']
        tokens.update(response['usage'])
        key=(r['qid'],r['docid']);scores[key]=max(scores.get(key,-math.inf),r['score'])
    assert len(scores)==5700 and v.render(runs,scores)==(dest/'run.trec').read_text()
    assert read(dest/'document-scores.json')==[{'qid':q,'docid':d,'score':s} for (q,d),s in scores.items()]
    assert len(attempts)==6090 and all(a['status']=='success' for a in attempts)
    assert Counter(a['cache_key'] for a in attempts)==Counter(r['cache_key'] for r in rows)
    assert dict(tokens)==meta['new_response_tokens']==meta['all_response_tokens']
    cost=tokens['input_tokens']*.042/1e6;assert math.isclose(cost,meta['estimated_new_api_cost_usd'])
    timing=read(dest/'queries.json');assert {r['qid'] for r in timing}==set(runs) and len(timing)==57
    assert all(r['scoring_calls']==len(tasks[r['qid']]) for r in timing)
    assert v.percentile([r['seconds'] for r in timing],.5)==meta['query_p50_seconds']
    assert v.percentile([r['seconds'] for r in timing],.95)==meta['query_p95_seconds']
    assert meta['rerank_seconds']>=sum(r['seconds'] for r in timing)+meta['preparation_seconds']
    with tempfile.TemporaryDirectory() as tmp:
        p=Path(tmp);(p/'run.trec').write_text(v.render(runs,scores));metrics=v.evaluate(args.input,p,runs)
        assert metrics==meta['metrics'] and read(p/'metrics-per-query.json')==read(dest/'metrics-per-query.json')
        assert (p/'trec_eval.txt').read_text()==(dest/'trec_eval.txt').read_text()
        (p/'run.trec').write_text(v.render(runs));base=v.evaluate(args.input,p,runs)
        assert base==read(root/'supplied-baseline/manifest.json')['metrics']
        base_per=read(p/'metrics-per-query.json')
    per=read(dest/'metrics-per-query.json')
    stats={m:statistics([per[q][m]-base_per[q][m] for q in runs],seed=78) for m in ('ndcg_cut_10','map','P_10','recip_rank')}
    assert metrics['recall_100']==base['recall_100'] and metrics['ncg_100']==base['ncg_100']
    assert all(per[q]['recip_rank']==1 for q in runs)
    report={'status':'passed','queries':57,'candidate_pairs':5700,'unique_documents':len(docs),'scored_windows':6090,
            'checks':['input/source/plan/run hashes','complete original-text coverage','exact window identities and content hashes','cached response score and usage agreement','MaxP and stable ranking reconstruction','attempt accounting','token accounting','query timing','byte-identical trec_eval reproduction','candidate recall and NCG invariance'],
            'scoring_api_attempts':6090,'failed_scoring_attempts':0,'estimated_scoring_api_cost_usd':cost,
            'validation_api_cost_usd':read(root/'context-validation/manifest.json')['estimated_new_api_cost_usd'],
            'input_tokens':tokens['input_tokens'],'primary_comparison':'JEV large-window MaxP versus supplied ranking; NDCG@10',
            'statistics_note':'Statistics use saved trec_eval per-query metrics rounded to four decimals. Only NDCG@10 is the declared primary test; remaining intervals/tests are descriptive. Small-passage comparisons were cancelled by user before final evaluation.',
            'statistics':stats,'context_audit':context}
    v.save(root/'audit.json',report)
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
