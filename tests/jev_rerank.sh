#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 - <<'PY'
import importlib.util
import tempfile
from pathlib import Path
spec = importlib.util.spec_from_file_location('jev', 'tools/rerank_jev.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
with tempfile.TemporaryDirectory() as tmp:
    p = Path(tmp)
    (p/'docs').write_text('<DOC><DOCNO>A</DOCNO><HL>A &amp; B</HL><TEXT>First</TEXT><TEXT>Second</TEXT></DOC>\n<DOC><DOCNO>B</DOCNO><TEXT>Other</TEXT></DOC>\x1a')
    docs = m.documents(p/'docs', {'A', 'B'})
    assert docs == {'A':'A & B First Second', 'B':'Other'}
    (p/'run').write_text('1 Q0 A 1 2.0 old\n1 Q0 B 2 2.0 old\n1 Q0 C 3 1.0 old\n')
    run = m.read_run(p/'run')
    assert [r[0] for r in run['1']] == ['B', 'A', 'C']
    text = m.render_run(run, {('1','A'):0.9, ('1','B'):0.1}, 2)
    rows = [line.split() for line in text.splitlines()]
    assert [r[2] for r in rows] == ['A','B','C']
    assert [r[4] for r in rows] == ['3','2','1']
    tied = m.render_run(run, {('1','A'):0.5, ('1','B'):0.5}, 2)
    assert tied.splitlines()[0].split()[2] == 'B'
    for invalid in [float('nan'), float('inf'), -0.1, 1.1, True]:
        try:
            m.validate_response({'model':'test','answers':{'relevant':{'type':'noul','noul':invalid}}})
        except ValueError:
            pass
        else:
            raise AssertionError('invalid score accepted')
    try:
        m.documents(p/'docs', {'MISSING'})
    except ValueError:
        pass
    else:
        raise AssertionError('missing DOCNO accepted')
# A tail candidate can propagate through overlapping windows to rank one.
rows = [(str(i), i, 0) for i in range(20)]
def judge(window):
    return {row[0]: int(row[0] == "19") for row in window}
ranked = m.choice_windows(rows, 10, 5, judge)
assert ranked[0][0] == "19"
assert {r[0] for r in ranked} == {r[0] for r in rows}
assert m.choice_windows(rows, 10, 5, lambda w: {r[0]: 0 for r in w}) == rows
valid = {"model":"test", "answers":{"best":{"type":"choice", "choice":"a", "probabilities":{"a":0.8,"b":0.2}}}}
assert m.validate_choice(valid, ["a","b"]) == {"a":0.8,"b":0.2}
rounded = {"model":"test", "answers":{"best":{"type":"choice", "choice":"a", "probabilities":{"a":0.50,"b":0.49}}}}
assert m.validate_choice(rounded, ["a","b"]) == {"a":0.50,"b":0.49}
for probs in ({"a":0.8}, {"a":0.8,"b":float("nan")}, {"a":0.8,"b":0.8}):
    invalid = {"model":"test", "answers":{"best":{"type":"choice", "choice":"a", "probabilities":probs}}}
    try:
        m.validate_choice(invalid,["a","b"])
    except ValueError:
        pass
    else:
        raise AssertionError("Invalid choice distribution accepted")
print('JEV pointwise and Choice window contracts passed')
PY
