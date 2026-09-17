#!/usr/bin/env python3
"""Independently check completed JEV evidence, submitted text hashes and ordering."""
import argparse
from collections import Counter, defaultdict
import json
import hashlib
import subprocess
import math
from pathlib import Path
from jev import digest, documents, read_run
from monobert import CANONICAL, MODEL, REVISION, ROOT
from jev_compare import MONO, prepare
from stage_artifacts import sha
from run import accounting


def audit(destination, source=CANONICAL, mono=MONO):
    m=json.loads((destination/'manifest.json').read_text())
    b=json.loads((source/'manifest.json').read_text())
    assert m['status']=='complete'
    assert m['stage1_run_sha256']==sha(source/'run.trec')==b['run_sha256']
    assert m['stage1_manifest_sha256']==sha(source/'manifest.json')
    assert m['monobert_passages_sha256']==sha(mono/'passages.jsonl')
    assert m['monobert_manifest_sha256']==sha(mono/'manifest.json')
    for name,key in [('topics.txt','topics_sha256'),('qrels.txt','qrels_sha256')]:
        assert m[key]==sha(source/name)==b[key]
    collection=Path(b['collection'])
    assert m['collection_sha256']==sha(collection)==b['collection_sha256']
    source_revisions={}
    for name,value in m['source_sha256'].items():
        if sha(ROOT/name)==value:
            source_revisions[name]='current checkout'
            continue
        revisions=subprocess.check_output(['git','log','--all','--format=%H','--',name],cwd=ROOT,text=True).splitlines()
        for revision in revisions:
            content=subprocess.check_output(['git','show',f'{revision}:{name}'],cwd=ROOT)
            if hashlib.sha256(content).hexdigest()==value:
                source_revisions[name]=revision
                break
        assert name in source_revisions, name
    mode=m['method'].removeprefix('jev-')
    runs=read_run(source/'run.trec'); top_k=m['top_k']
    queries=dict(line.split(maxsplit=1) for line in (source/'topics.txt').read_text().splitlines() if line.strip())
    docs=documents(collection,{r[0] for rows in runs.values() for r in rows[:top_k]})
    from transformers import BertTokenizerFast
    tokenizer=BertTokenizerFast.from_pretrained(MODEL,revision=REVISION,cache_dir=ROOT/'.cache/monobert-model',local_files_only=True)
    jobs=prepare(mode,runs,queries,docs,mono,tokenizer)
    identity=lambda r:(r['qid'],r['docid'],r.get('passage_index'))
    expected={identity(t):t for tasks in jobs.values() for t in tasks}
    rows=[json.loads(line) for line in (destination/'scores.jsonl').read_text().splitlines()]
    assert len(rows)==len(expected)==m['scoring_calls']
    assert len(set(map(identity,rows)))==len(rows)
    scores={}; covered=0
    for r in rows:
        task=expected[identity(r)]
        assert r['payload_text_sha256']==digest(task['text'])
        assert r['payload_characters']==len(task['text'])
        assert all(r[k]==v for k,v in task.items() if k!='text')
        assert math.isfinite(r['score']) and 0<=r['score']<=1
        key=r['qid'],r['docid']
        scores[key]=max(scores.get(key,-math.inf),r['score'])
        covered+=r.get('newly_covered_tokens',r['document_tokens'])
    assert len(scores)==m['query_document_pairs']
    assert covered==sum(len(tokenizer.encode(docs[d],add_special_tokens=False,truncation=False,verbose=False)) for q,d in scores)
    final=read_run(destination/'run.trec')
    assert final.keys()==runs.keys()
    for q,original in runs.items():
        ordered=sorted(original[:top_k],key=lambda r:-scores[q,r[0]])+original[top_k:]
        assert [r[0] for r in final[q]]==[r[0] for r in ordered]
    attempts=[json.loads(line) for line in (destination/'attempts.jsonl').read_text().splitlines()]
    assert len(attempts)==m['api_attempts']
    assert sum(r['status']=='failed' for r in attempts)==m['failed_api_attempts']
    successes=Counter(r['cache_key'] for r in attempts if r['status']=='success')
    assert successes==Counter(r['cache_key'] for r in rows if not r['cache_hit'])
    for k,v in accounting(rows,m['input_usd_per_million'],m['output_usd_per_million']).items():
        assert m[k]==v,k
    timings=json.loads((destination/'queries.json').read_text())
    assert {r['qid'] for r in timings}==set(runs)
    counts=Counter(r['qid'] for r in rows)
    assert all(t['scoring_calls']==counts[t['qid']] for t in timings)
    result={'status':'passed','scoring_units':len(rows),'query_document_pairs':len(scores),
            'document_tokens_covered_across_query_pairs':covered,'api_attempts':len(attempts),
            'evaluated_source_revisions':source_revisions,
            'checks':['immutable reference/source hashes','exact decoded passage or whole-document payload hashes','full token coverage','MaxP/pointwise rank reconstruction and unchanged tail','API attempt and successful response counts','reported token usage and cost arithmetic','per-query scoring counts']}
    (destination/'audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('results',type=Path)
    args=p.parse_args()
    audit(args.results)
