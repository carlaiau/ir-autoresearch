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
print('JEV ranking, tie ordering, document boundaries and score validation passed')
PY
