#!/usr/bin/env python3
"""Run the two frozen JEV document conditions sequentially, with durable status."""
import argparse
from datetime import datetime, timezone
import subprocess
import sys
from msmarco_v2_documents import ROOT, save

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--env-root',required=True)
    p.add_argument('--model-cache',required=True)
    args=p.parse_args()
    base=ROOT/'reranking/results/msmarco-v2-dl2021-documents'
    state_path=base/'run-queue.json'
    if state_path.exists():raise ValueError('run queue already exists; preserve earlier attempts')
    conditions=['jev-large-windows','jev-passages']
    for name in conditions:
        if (base/name).exists():raise ValueError('result directory already exists')
    state={'status':'running','order':conditions,'conditions':{name:{'status':'queued'} for name in conditions}}
    save(state_path,state)
    for name in conditions:
        row=state['conditions'][name];row.update(status='running',started_at_utc=datetime.now(timezone.utc).isoformat())
        save(state_path,state)
        command=[sys.executable,'-u',str(ROOT/'reranking/msmarco_v2_documents.py'),name,
                 '--env-root',args.env_root,'--model-cache',args.model_cache,
                 '--results-dir',str(base/name),'--cache',str(ROOT/'.cache/msmarco-v2-dl2021'/name)]
        try:
            with (base/(name+'.log')).open('x') as log:
                subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
        except BaseException as error:
            row.update(status='failed',error_type=type(error).__name__);state['status']='failed';save(state_path,state)
            raise
        row.update(status='complete',finished_at_utc=datetime.now(timezone.utc).isoformat());save(state_path,state)
    state['status']='complete';save(state_path,state)

if __name__=='__main__':main()
