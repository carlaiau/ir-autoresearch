#!/usr/bin/env python3
import gzip
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'reranking'))
from msmarco import (QUESTION, evaluation, freeze, read_inputs, validate_scores,
                     verified_inputs)
from jev_compare import Service
from audit_msmarco import holm, statistics


class Tests(unittest.TestCase):
    def test_paired_statistics_and_multiple_comparisons(self):
        null = statistics([0, 0, 0], bootstrap=100, permutations=100)
        self.assertEqual(null['bootstrap_95_ci'], [0, 0])
        self.assertEqual(null['two_sided_randomization_p'], 1)
        gain = statistics([.1]*20, bootstrap=100, permutations=1000)
        self.assertGreater(gain['bootstrap_95_ci'][0], 0)
        self.assertLess(gain['two_sided_randomization_p'], .01)
        self.assertEqual(holm({'a': .02, 'b': .03}), {'a': .04, 'b': .04})

    def data(self, root):
        data = root / 'data'
        data.mkdir()
        (data / 'qrels.txt').write_text('1 Q0 10 3\n1 Q0 20 1\n1 Q0 99 2\n')
        with gzip.open(data / 'queries.tsv.gz', 'wt') as f:
            f.write('1\tquery\n2\tunjudged query\n')
        with gzip.open(data / 'candidates.tsv.gz', 'wt') as f:
            f.write('1\t20\tquery\tfirst passage\n1\t10\tquery\tsecond passage\n2\t30\tunjudged query\tthird passage\n')
        return data

    def test_identity_selection_not_labels_or_input_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = self.data(Path(tmp))
            runs, queries, docs, _, _ = read_inputs(data)
            self.assertEqual(list(queries), ['1'])
            self.assertEqual([r[0] for r in runs['1']], ['10', '20'])
            self.assertNotIn('99', docs)  # judged relevant passage must not be injected
            (data / 'qrels.txt').write_text('1 Q0 10 0\n1 Q0 20 3\n')
            self.assertEqual(read_inputs(data)[:3], (runs, queries, docs))

    def test_duplicate_and_text_mismatch_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = self.data(Path(tmp))
            with gzip.open(data / 'candidates.tsv.gz', 'at') as f:
                f.write('1\t10\tquery\tduplicate\n')
            with self.assertRaises(ValueError):
                read_inputs(data)

    def test_freeze_hashes_and_binary_grades(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); data = self.data(root); frozen = root / 'input'
            freeze(data, frozen)
            self.assertIn('1 Q0 20 0', (frozen / 'qrels-binary.txt').read_text())
            verified_inputs(data, frozen)
            (frozen / 'qrels-binary.txt').write_text('tampered')
            with self.assertRaises(ValueError):
                verified_inputs(data, frozen)
            with self.assertRaises(FileExistsError):
                freeze(data, frozen)

    def test_evaluation_graded_and_binary_are_distinct(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); data = self.data(root); source = root / 'input'
            freeze(data, source)
            dest = root / 'output'; dest.mkdir()
            (dest / 'run.trec').write_text('1 Q0 20 1 2 test\n1 Q0 10 2 1 test\n')
            metrics = evaluation(source, dest)
            self.assertEqual(metrics['recip_rank'], .5)  # grade 1 not binary relevant
            self.assertEqual(metrics['map'], .25)  # relevant grade-2 item remains missing
            self.assertEqual(metrics['recall_1000'], .5)
            self.assertGreater(metrics['ndcg_cut_10'], 0)

    def test_missing_or_nonfinite_scores_fail(self):
        runs = {'1': [('10', 1, 0), ('20', 2, 0)]}
        for scores in ({('1', '10'): .5}, {('1', '10'): .5, ('1', '20'): float('nan')}):
            with self.assertRaises(ValueError):
                validate_scores(runs, scores)

    def test_passage_prompt_payload_and_cache_isolation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            class Client:
                def __init__(self): self.payloads = []
                def system_one(self, **kwargs):
                    self.payloads.append(kwargs)
                    return {'model': 'test', 'answers': {'relevant': {'type': 'noul', 'noul': .4}},
                            'usage': {'input_tokens': 10, 'output_tokens': 0}}
                def close(self): pass
            client = Client()
            args = SimpleNamespace(cache=root/'cache', cache_only=False, model='test', mode='passages',
                                   expected_model='test', max_attempts=1, question=QUESTION, state_field='candidate_passage')
            service = Service(args, root, client)
            task = {'qid': '1', 'docid': '10', 'text': 'private example'}
            service.score(task, 'query')
            self.assertEqual(client.payloads[0]['state'], {'query': 'query', 'candidate_passage': task['text']})
            self.assertEqual(client.payloads[0]['questions']['relevant'], QUESTION)
            self.assertTrue(service.score(task, 'query')['cache_hit'])
            args.question = {**QUESTION, 'instructions': 'changed'}
            self.assertFalse(service.score(task, 'query')['cache_hit'])
            self.assertNotIn('private example', (root/'scores.jsonl').read_text())


if __name__ == '__main__':
    unittest.main()
