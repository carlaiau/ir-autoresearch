#!/usr/bin/env python3
import gzip,json,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'reranking'))
import msmarco_v2_documents as v

class Tokenizer:
    def encode(self,text,**kwargs):return list(range(len(text.split())))
    def decode(self,ids,**kwargs):return ' '.join(map(str,ids))
    def num_special_tokens_to_add(self,pair):return 3

class Client:
    def system_one(self,**payload):
        score=.9 if 'preferred' in payload['state']['candidate_document'] else .1
        return {'model':'jev-1.13.0','answers':{'relevant':{'type':'noul','noul':score}},'usage':{'input_tokens':10,'output_tokens':2}}
    def close(self):pass

class Tests(unittest.TestCase):
    def test_complete_fields_windows_and_stable_ties(self):
        text=v.canonical({'title':'Title','headings':'A\nB','body':' '.join('word' for _ in range(1000))+' TAIL'})
        self.assertTrue(text.endswith('TAIL'));self.assertIn('HEADINGS:\nA\nB',text)
        runs={'1':[('a',1,2.),('b',2,1.)]}
        parts,full=v.prepare_tasks(runs,{'1':'query'},{'a':text,'b':'short'},Tokenizer())
        jobs=[t for t in parts['1'] if t['docid']=='a']
        self.assertEqual([(t['token_start'],t['token_end']) for t in jobs],list(v.windows(len(text.split()),384,64)))
        self.assertEqual(full['1'][0]['text'],text)
        self.assertEqual([r.split()[2] for r in v.render(runs,{('1','a'):.5,('1','b'):.5}).splitlines()],['a','b'])

    def test_candidate_rank_validation_and_judged_queries(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'qrels.txt').write_text('1 Q0 x 1\n');(p/'queries.tsv').write_text('1\tquery\n2\tnot evaluated\n')
            rows=''.join(f'1 Q0 d{i} {i+1} {100-i} orig\n' for i in range(100))
            with gzip.open(p/'candidates.gz','wt') as f:f.write(rows+'2 Q0 other 1 1 orig\n')
            runs,queries,grades=v.candidates(p)
            self.assertEqual(list(runs),['1']);self.assertEqual(len(runs['1']),100)
            self.assertEqual(grades['1']['x'],1)
            with gzip.open(p/'candidates.gz','wt') as f:f.write(rows.replace('d99 100','d98 100'))
            with self.assertRaises(ValueError):v.candidates(p)

    def test_document_grade_one_is_relevant_and_ncg_is_graded(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);source=p/'input';source.mkdir();out=p/'out';out.mkdir()
            (source/'qrels.txt').write_text('1 Q0 a 1\n1 Q0 b 3\n1 Q0 c 2\n')
            runs={'1':[('a',1,2.),('b',2,1.)]};(out/'run.trec').write_text(v.render(runs))
            metrics=v.evaluate(source,out,runs)
            self.assertEqual(metrics['recip_rank'],1)
            self.assertEqual(metrics['map'],.6667)
            self.assertAlmostEqual(metrics['ncg_100'],4/6)

    def test_ncg_denominator_is_ideal_at_cutoff(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);source=p/'input';source.mkdir();out=p/'out';out.mkdir()
            (source/'qrels.txt').write_text(''.join(f'1 Q0 d{i} 3\n' for i in range(150)))
            runs={'1':[(f'd{i}',i+1,100-i) for i in range(100)]}
            (out/'run.trec').write_text(v.render(runs))
            m=v.evaluate(source,out,runs)
            self.assertEqual(m['ncg_100'],1.0)
            self.assertEqual(m['recall_100'],.6667)

    def test_complete_run_accounting_and_frozen_preflight(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);source=p/'input';source.mkdir();base=p/'supplied-baseline';base.mkdir()
            (source/'qrels.txt').write_text('1 Q0 a 0\n1 Q0 b 1\n');v.save(source/'manifest.json',{'fixture':True})
            runs={'1':[('a',1,2.),('b',2,1.)]};queries={'1':'query'};docs={'a':'ordinary','b':'preferred'}
            (base/'run.trec').write_text(v.render(runs));v.save(base/'manifest.json',{'metrics':v.evaluate(source,base,runs)})
            pre={'input_manifest_sha256':v.sha(source/'manifest.json'),'question':v.QUESTION,'model':'jev-1.13.0','conditions':{'jev-full':{'scoring_calls':2,'requests_over_150000_characters':[]}}}
            v.save(p/'preflight.json',pre)
            args=SimpleNamespace(input=source,data=p,cache=p/'cache',cache_only=False,command='jev-full',mode='jev-full',results_dir=p/'result',model='jev-1.13.0',expected_model=None,question=v.QUESTION,state_field='candidate_document',workers=2,max_attempts=1,input_usd_per_million=.042,output_usd_per_million=0,pricing_source='test')
            with patch.object(v,'verified',return_value=(runs,queries,docs,{'input_identity_sha256':'fixture'})),patch.object(v,'tokenizer_for',return_value=Tokenizer()):
                meta=v.execute(args,lambda a,d:v.PinnedService(a,d,Client()))
                self.assertEqual(meta['metrics']['map'],1)
                self.assertEqual(meta['scoring_calls'],2)
                self.assertEqual(meta['api_attempts'],2)
                self.assertAlmostEqual(meta['estimated_new_api_cost_usd'],20*.042/1e6)
                self.assertIsNone(meta['compute_cost_usd'])
                pre['conditions']['jev-full']['requests_over_150000_characters']=[{'docid':'b'}];v.save(p/'preflight.json',pre)
                with self.assertRaises(ValueError):v.execute(args)

if __name__=='__main__':unittest.main()
