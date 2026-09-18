#!/usr/bin/env python3
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'reranking'))
from jev_duo import DuoService, aggregate, tasks_for, payload_for, probability, run, load_inputs
from stage_artifacts import sha
from jev import render_run
from run import accounting

class Client:
    def __init__(self, errors=()): self.calls=[]; self.errors=list(errors)
    def system_one(self, **payload):
        self.calls.append(payload)
        if self.errors: raise self.errors.pop(0)
        return {'model':'test-model','answers':{'a_more_relevant':{'type':'noul','noul':.8}},'usage':{'input_tokens':20,'output_tokens':2}}
    def close(self): pass

class Tests(unittest.TestCase):
    def test_pair_coverage_sum_and_stable_tail(self):
        candidates=[('a',1,3),('b',2,2),('c',3,1)]
        tasks=tasks_for('1',candidates,{d:d+' entire tail' for d,_,_ in candidates},3)
        self.assertEqual(len(tasks),6)
        rows=[dict(t,score={('a','b'):.8,('a','c'):.8,('b','a'):.2,('b','c'):.9,('c','a'):.1,('c','b'):.1}[t['docid'],t['docid_b']]) for t in tasks]
        scores,diag=aggregate(rows,candidates)
        self.assertEqual(scores,{'a':1.6,'b':1.1,'c':.2})
        self.assertEqual(aggregate(list(reversed(rows)),candidates)[0],scores)
        self.assertEqual(diag['unordered_pairs'],3)
        for bad in (rows[:-1],rows+[rows[0]]):
            with self.assertRaises(ValueError): aggregate(bad,candidates)
        tied={('1','a'):.5,('1','b'):.5}
        rendered=render_run({'1':candidates},tied,2)
        self.assertEqual([r.split()[2] for r in rendered.splitlines()],['a','b','c'])
        self.assertEqual(len(tasks_for('1',[(str(i),i,0) for i in range(20)],{str(i):'text' for i in range(20)},20)),380)

    def test_full_text_and_no_rank_leak(self):
        text='start '+'x'*100000+' end'
        task=tasks_for('q',[('a',1,4),('b',2,3)],{'a':text,'b':'B'},2)[0]
        payload=payload_for(task,'query','test-model')
        self.assertEqual(payload['state'],{'query':'query','document_a':text,'document_b':'B'})
        for value in (-.1,1.1,float('nan'),True):
            with self.assertRaises(ValueError): probability({'model':'m','answers':{'a_more_relevant':{'type':'noul','noul':value}}})

    def test_retry_cache_orientation_and_cost(self):
        class RateLimit(Exception): status=429; retry_after_ms=1
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); args=SimpleNamespace(cache=root/'cache',cache_only=False,model='test-model',max_attempts=3)
            client=Client([RateLimit()]); service=DuoService(args,root,client)
            pair=tasks_for('q',[('a',1,1),('b',2,0)],{'a':'Full A','b':'Full B'},2)
            with patch('jev_duo.time.sleep') as sleep:
                first=service.score(pair[0],'query')
                self.assertEqual(sleep.call_count,1)
            cached=service.score(pair[0],'query'); other=service.score(pair[1],'query')
            self.assertFalse(first['cache_hit']); self.assertTrue(cached['cache_hit'])
            self.assertNotEqual(first['cache_key'],other['cache_key'])
            self.assertEqual(len(service.attempts),3)
            self.assertEqual(service.attempts[0]['status'],'failed')
            totals=accounting(service.rows,.042,0)
            self.assertAlmostEqual(totals['estimated_new_api_cost_usd'],40*.042/1e6)
            self.assertEqual(totals['cache_hits'],1)
            self.assertNotIn('Full A',(root/'attempts.jsonl').read_text())
            self.assertNotIn('Full A',(root/'scores.jsonl').read_text())

    def test_model_mismatch_preserves_usage_and_nonretry_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);args=SimpleNamespace(cache=root/'cache',cache_only=False,model='wrong-model',max_attempts=3)
            task=tasks_for('q',[('a',1,1),('b',2,0)],{'a':'A','b':'B'},2)[0]
            service=DuoService(args,root,Client())
            with self.assertRaises(ValueError): service.score(task,'query')
            self.assertEqual(len(service.rows),1)
            self.assertEqual(service.rows[0]['response']['usage']['input_tokens'],20)
            client=Client([ValueError('private contents')]);service=DuoService(args,root,client)
            with self.assertRaises(ValueError): service.score(task,'changed query')
            self.assertEqual(len(client.calls),1)
            self.assertNotIn('private contents',(root/'attempts.jsonl').read_text())

    def test_end_to_end_and_tampered_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);stage=root/'stage';point=root/'point';stage.mkdir();point.mkdir()
            collection=root/'collection.xml'
            collection.write_text('<DOC><DOCNO>a</DOCNO><TEXT>A entire article.</TEXT></DOC>\n<DOC><DOCNO>b</DOCNO><TEXT>B entire article.</TEXT></DOC>\n<DOC><DOCNO>c</DOCNO><TEXT>C untouched tail.</TEXT></DOC>')
            (stage/'run.trec').write_text('1 Q0 a 1 3 baseline\n1 Q0 b 2 2 baseline\n1 Q0 c 3 1 baseline\n')
            (point/'run.trec').write_text((stage/'run.trec').read_text())
            (stage/'topics.txt').write_text('1 query text\n');(stage/'qrels.txt').write_text('1 0 a 0\n1 0 b 1\n1 0 c 0\n')
            metrics={'map':.5,'Rprec':0,'P_10':.1,'bpref':0,'recip_rank':.5}
            baseline={'stage':'stage1','status':'complete','collection':str(collection),'collection_sha256':sha(collection),'search_seconds':.1,'metrics':metrics}
            for name,key in [('run.trec','run_sha256'),('topics.txt','topics_sha256'),('qrels.txt','qrels_sha256')]:baseline[key]=sha(stage/name)
            (stage/'manifest.json').write_text(json.dumps(baseline))
            pointwise=dict(baseline,stage='reranking',method='jev-documents',top_k=3,stage1_run_sha256=baseline['run_sha256'],stage1_manifest_sha256=sha(stage/'manifest.json'),rerank_seconds=.2,estimated_new_api_cost_usd=.01)
            (point/'manifest.json').write_text(json.dumps(pointwise))
            args=SimpleNamespace(stage1=stage,pointwise=point,collection=None,top_k=2,results_dir=root/'output',cache=root/'cache',cache_only=False,model='test-model',max_attempts=1,workers=2,input_usd_per_million=.042,output_usd_per_million=0,pricing_source='test')
            class PairClient(Client):
                def system_one(self,**payload):
                    value=super().system_one(**payload)
                    value['answers']['a_more_relevant']['noul']=.9 if 'B entire' in payload['state']['document_a'] else .1
                    return value
            result=run(args,lambda a,d:DuoService(a,d,PairClient()))
            self.assertEqual(result['metrics']['map'],1)
            self.assertEqual(result['scoring_calls'],2)
            self.assertEqual(result['api_attempts'],2)
            self.assertEqual([r.split()[2] for r in (args.results_dir/'run.trec').read_text().splitlines()],['b','a','c'])
            self.assertIsNone(result['compute_cost_usd'])
            self.assertTrue((args.results_dir/'pointwise-paired.json').exists())
            (point/'run.trec').write_text('tampered')
            with self.assertRaises(ValueError):load_inputs(stage,point,None,2)

if __name__=='__main__': unittest.main()
