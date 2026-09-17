#!/usr/bin/env python3
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'reranking'))
from jev_compare import Service, prepare, score_query
from monobert import REVISION

class Tokenizer:
    def encode(self,text,**kwargs): return list(range(len(text.split())))
    def decode(self,ids,**kwargs): return ' '.join(str(i) for i in ids)
    def num_special_tokens_to_add(self,pair): return 3

class Client:
    def __init__(self,fail=False): self.calls=[];self.fail=fail
    def system_one(self,**payload):
        self.calls.append(payload)
        if self.fail: raise ValueError('must not log payload')
        return {'model':'test-model','answers':{'relevant':{'type':'noul','noul':.8}},'usage':{'input_tokens':20,'output_tokens':1}}
    def close(self): pass

class Tests(unittest.TestCase):
    def args(self,root,**kwargs):
        return SimpleNamespace(cache=root/'cache',cache_only=False,mode='passages',model='test-model',expected_model='test-model',max_attempts=1,**kwargs)

    def test_identical_windows_full_text_and_reject_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'manifest.json').write_text(json.dumps({'model_revision':REVISION,'tokenizer_revision':REVISION,'top_k':1,'passage_tokens':4,'overlap_tokens':1,'model_input_limit':8}))
            records=[{'qid':'1','docid':'d','passage_index':0,'token_start':0,'token_end':4,'document_tokens':6,'newly_covered_tokens':4}, {'qid':'1','docid':'d','passage_index':1,'token_start':3,'token_end':6,'document_tokens':6,'newly_covered_tokens':2}]
            (root/'passages.jsonl').write_text('\n'.join(map(json.dumps,records)))
            runs={'1':[('d',1,1.0)]};queries={'1':'query'};docs={'d':'a b c d e tail'}
            tasks=prepare('passages',runs,queries,docs,root,Tokenizer())
            self.assertEqual([x['text'] for x in tasks['1']],['0 1 2 3','3 4 5'])
            self.assertEqual(prepare('documents',runs,queries,docs,root,Tokenizer())['1'][0]['text'],docs['d'])
            records[1]['token_start']=4
            (root/'passages.jsonl').write_text('\n'.join(map(json.dumps,records)))
            with self.assertRaises(ValueError):prepare('passages',runs,queries,docs,root,Tokenizer())

    def test_calls_cache_and_no_text_in_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);client=Client();args=self.args(root)
            service=Service(args,root,client)
            task={'qid':'1','docid':'d','text':'full secret source text'}
            row=service.score(task,'query')
            self.assertFalse(row['cache_hit']);self.assertEqual(len(service.attempts),1)
            self.assertEqual(client.calls[0]['state']['candidate_article'],task['text'])
            self.assertTrue(service.score(task,'query')['cache_hit'])
            self.assertEqual(len(client.calls),1)
            self.assertNotIn(task['text'],(root/'scores.jsonl').read_text())
            self.assertNotIn(task['text'],(root/'attempts.jsonl').read_text())
            args.mode='documents'
            service.score(task,'query')
            self.assertEqual(len(client.calls),2) # separate experiment cache identities

    def test_failure_stops_bounded_requests_and_records_attempts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);client=Client(fail=True);service=Service(self.args(root),root,client)
            tasks=[{'qid':'1','docid':str(i),'text':'article'} for i in range(100)]
            with self.assertRaises(ValueError):score_query(service,tasks,'query',2)
            self.assertLessEqual(len(client.calls),2)
            self.assertEqual(len(service.attempts),len(client.calls))
            self.assertEqual(service.rows,[])
            self.assertTrue(all(r['status']=='failed' for r in service.attempts))

    def test_successful_pool_and_invalid_score(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);service=Service(self.args(root),root,Client())
            tasks=[{'qid':'1','docid':str(i),'text':'article'} for i in range(9)]
            self.assertEqual(len(score_query(service,tasks,'query',3)),9)
            self.assertEqual(len(service.attempts),9)
            class Invalid(Client):
                def system_one(self,**payload):
                    r=super().system_one(**payload);r['answers']['relevant']['noul']=float('nan');return r
            service.client=Invalid()
            with self.assertRaises(ValueError):service.score({'qid':'2','docid':'d','text':'new'},'query')
            self.assertEqual(service.attempts[-1]['status'],'failed')

    def test_real_sdk_transient_errors_are_counted_and_retried(self):
        from unittest.mock import patch
        from typesafe_sdk._core.errors import TypeSafeRateLimitError, TypeSafeAPITimeoutError, TypeSafeInternalServerError
        import httpx2
        for error in (TypeSafeRateLimitError(429, {}, httpx2.Headers()), TypeSafeInternalServerError(503, {}, httpx2.Headers()), TypeSafeAPITimeoutError(120.0)):
            with self.subTest(error=type(error).__name__), tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp)
                class Transient(Client):
                    def system_one(self, **payload):
                        response=super().system_one(**payload)
                        if len(self.calls)==1: raise error
                        return response
                args=self.args(root);args.max_attempts=3
                service=Service(args,root,Transient())
                with patch('jev_compare.time.sleep'):
                    row=service.score({'qid':'1','docid':'d','text':'article'},'query')
                self.assertEqual(row['score'],.8)
                self.assertEqual([a['status'] for a in service.attempts],['failed','success'])
                if isinstance(error,TypeSafeRateLimitError):
                    self.assertEqual(service.attempts[0]['http_status'],429)

if __name__=='__main__': unittest.main()
