"""Offline behavioral contracts; no model download and no inference service."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'reranking'))
import monobert as m


class FakeBert:
    device = 'cpu'
    limit = 16
    special_tokens = 3
    parameters = 0
    versions = {'test': 'synthetic'}
    unexpected_keys = []

    def __init__(self, args):
        pass

    def tokenize(self, text):
        return [9 if word == 'relevant' else 1 for word in text.split()]

    def pair(self, query, passage):
        return {'input_ids': [101] + query + [102] + passage + [102],
                'token_type_ids': [0] * (len(query)+2) + [1] * (len(passage)+1)}

    def predict(self, batch):
        assert all(len(p['input_ids']) <= self.limit for p in batch)
        return [-0.1 if 9 in pair['input_ids'] else -5.0 for pair in batch]


class Contracts(unittest.TestCase):
    def test_windows_and_tail(self):
        for length in (1, 383, 384, 385, 1001, 24001):
            spans = list(m.windows(length,384,64))
            self.assertEqual(m.coverage(spans,length),length)
            self.assertEqual(set(i for a,b in spans for i in range(a,b)),set(range(length)))
            self.assertTrue(all(b-a<=384 for a,b in spans))
        with self.assertRaises(ValueError):
            m.coverage([(0,4),(5,8)],8)
        with self.assertRaises(ValueError):
            m.coverage([(0,4)],8)
        with self.assertRaises(ValueError):
            list(m.windows(8,4,4))

    def test_ties_keep_candidate_order(self):
        runs = {'1': [('B', 1, 3), ('A', 2, 2), ('C', 3, 1)]}
        rendered = m.render(runs, {('1', 'B'): -.5, ('1', 'A'): -.5}, 2)
        self.assertEqual([line.split()[2] for line in rendered.splitlines()], ['B', 'A', 'C'])

    def fixture(self, root):
        source=root/'baseline'; source.mkdir()
        collection=root/'docs.xml'
        collection.write_text('<DOC><DOCNO>A</DOCNO><HL>headline &amp; text</HL><TEXT>'+('ordinary '*50)+'relevant</TEXT></DOC>\n<DOC><DOCNO>B</DOCNO><TEXT>ordinary text</TEXT></DOC>\n<DOC><DOCNO>C</DOCNO><TEXT>tail</TEXT></DOC>')
        (source/'run.trec').write_text('1 Q0 B 1 3 base\n1 Q0 A 2 2 base\n1 Q0 C 3 1 base\n')
        (source/'topics.txt').write_text('1 find evidence\n')
        (source/'qrels.txt').write_text('1 0 A 1\n1 0 B 0\n1 0 C 0\n')
        metrics=m.evaluate(source/'qrels.txt',source/'run.trec',source/'trec_eval.txt')
        baseline={'stage':'stage1','status':'complete','collection':str(collection),'collection_sha256':m.sha(collection),'run_sha256':m.sha(source/'run.trec'),'topics_sha256':m.sha(source/'topics.txt'),'qrels_sha256':m.sha(source/'qrels.txt'),'metrics':metrics,'search_seconds':.25}
        (source/'manifest.json').write_text(json.dumps(baseline))
        return source

    def test_complete_run_tail_evidence_counts_cost_and_immutability(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); source=self.fixture(root); dest=root/'results'
            before={p.name:p.read_bytes() for p in source.iterdir()}
            result=m.main([str(source),'--results-dir',str(dest),'--top-k','2','--passage-tokens','8','--overlap-tokens','2','--batch-size','3','--compute-usd-per-hour','3.6','--pricing-source','synthetic rate'], FakeBert)
            records=[json.loads(line) for line in (dest/'passages.jsonl').read_text().splitlines()]
            self.assertEqual(result['query_document_pairs'],2)
            self.assertEqual(result['passage_scoring_calls'],len(records))
            self.assertEqual(result['model_forward_calls'],(len(records)+2)//3)
            self.assertEqual(result['model_forward_calls_attempted'],result['model_forward_calls'])
            self.assertEqual(result['hosted_inference_api_calls'],0)
            self.assertEqual(result['covered_document_tokens_across_query_pairs'],result['document_tokens_across_query_pairs'])
            self.assertAlmostEqual(result['estimated_compute_cost_usd'],result['total_wall_seconds']/1000)
            self.assertEqual(result['coverage_fraction'],1)
            self.assertEqual([line.split()[2] for line in (dest/'run.trec').read_text().splitlines()],['A','B','C'])
            self.assertGreater(result['metrics']['map'],.5)
            self.assertEqual(before,{p.name:p.read_bytes() for p in source.iterdir()})
            for docid in ('A','B'):
                spans=[(r['token_start'],r['token_end']) for r in records if r['docid']==docid]
                length=next(r['document_tokens'] for r in records if r['docid']==docid)
                self.assertEqual(m.coverage(spans,length),length)
            self.assertIn('Calls, time and cost',(dest/'results.md').read_text())

    def test_failure_and_hash_checks(self):
        class Broken(FakeBert):
            def predict(self,batch):
                raise RuntimeError('synthetic failure')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); source=self.fixture(root); dest=root/'failed'
            with self.assertRaises(RuntimeError):
                m.main([str(source),'--results-dir',str(dest)],Broken)
            failure=json.loads((dest/'failure.json').read_text())
            self.assertEqual(failure['model_forward_calls_attempted'],1)
            self.assertEqual(failure['model_forward_calls'],0)
            self.assertIsNone(failure['estimated_compute_cost_usd'])
            self.assertFalse((dest/'results.md').exists())
            (source/'run.trec').write_text('tampered')
            with self.assertRaises(SystemExit):
                m.main([str(source),'--results-dir',str(root/'bad-hash')],FakeBert)
            self.assertFalse((root/'bad-hash').exists())

    def test_nonfinite_scores_and_oversized_query(self):
        class BadScores(FakeBert):
            def predict(self, batch):
                return [float('nan')] * len(batch)
        class HugeQuery(FakeBert):
            def tokenize(self, text):
                return [1] * 16
        for factory in (BadScores, HugeQuery):
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); source = self.fixture(root); dest = root/'bad'
                with self.assertRaises(ValueError):
                    m.main([str(source), '--results-dir', str(dest)], factory)
                self.assertFalse((dest/'results.md').exists())
                self.assertEqual(json.loads((dest/'failure.json').read_text())['status'], 'failed')

    def test_small_query_budget_and_bad_scores(self):
        from argparse import Namespace
        class LongQuery(FakeBert):
            def tokenize(self,text):
                return [1]*11 if text=='query' else [1]*10+[9]
        with tempfile.TemporaryDirectory() as tmp:
            backend=LongQuery(None); counts=m.new_counters()
            args=Namespace(passage_tokens=384,overlap_tokens=64,top_k=1,batch_size=3)
            scores,_,_=m.score_all({'q':[('A',1,1)]},{'q':'query'},{'A':'doc'},backend,args,Path(tmp),counts)
            self.assertEqual(scores['q','A'],-.1)
            self.assertEqual(counts['covered_document_tokens_across_query_pairs'],11)
            self.assertEqual(counts['passage_scoring_calls'],10)
        self.assertIsNone(m.cost(10,None))
        self.assertEqual(m.cost(3600,2),2)
        self.assertEqual(m.percentile([1,2,3],.5),2)


if __name__=='__main__':
    unittest.main()
