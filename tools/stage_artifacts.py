"""Shared artifact helpers for independently reproducible retrieval stages."""
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import time

ROOT = Path(__file__).resolve().parent.parent
METRICS = ('map', 'Rprec', 'P_10', 'bpref', 'recip_rank')


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def provenance():
    def git(*args):
        return subprocess.check_output(['git', '-C', str(ROOT), *args], text=True).strip()
    return {'commit': git('rev-parse', 'HEAD'), 'branch': git('branch', '--show-current'),
            'dirty': bool(git('status', '--porcelain')), 'platform': platform.platform(),
            'processor': platform.processor()}


def timed(command, **kwargs):
    start = time.perf_counter()
    subprocess.run([str(x) for x in command], check=True, **kwargs)
    return time.perf_counter() - start


def evaluate(qrels, run, output):
    summary = subprocess.check_output(['trec_eval', '-c', '-M1000', str(qrels), str(run)], text=True)
    output.write_text(summary)
    return {row[0]: float(row[2]) for line in summary.splitlines()
            if len(row := line.split()) == 3 and row[1] == 'all' and row[0] in METRICS}


def report(directory, metadata, baseline=None):
    (directory / 'manifest.json').write_text(json.dumps(metadata, indent=2, sort_keys=True) + '\n')
    lines = [f"# {metadata['stage']} results", '', f"Status: {metadata['status']}", '',
             '| Metric | Value | Delta vs stage 1 |', '| --- | ---: | ---: |']
    for key, value in metadata['metrics'].items():
        delta = f"{value - baseline[key]:+.4f}" if baseline else '—'
        lines.append(f'| {key} | {value:.4f} | {delta} |')
    lines += ['', '```json', json.dumps({k: v for k, v in metadata.items() if k != 'metrics'}, indent=2, sort_keys=True),
              '```', '', 'Raw evaluation: [trec_eval.txt](trec_eval.txt). Run: [run.trec](run.trec).',
              'Times are batch wall-clock seconds; batch/query is amortized throughput, not single-query latency.', '']
    (directory / 'results.md').write_text('\n'.join(lines))
