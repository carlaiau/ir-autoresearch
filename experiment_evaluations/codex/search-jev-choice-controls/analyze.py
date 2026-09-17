import json,subprocess,sys,hashlib
from pathlib import Path
root=Path(__file__).resolve().parents[3];sys.path.insert(0,str(root/'tools'))
from rerank_jev import read_run
out=root/'experiment_evaluations/codex/search-jev-choice-controls'
base=root/'experiment_evaluations/codex/search-jev-recall'
paths={'fusion':base/'pre-jev-20260917-160716.trec','pointwise_24000':base/'jev-20260917-160716.trec','pointwise_2400':out/'pointwise-2400.trec','choice_2400':out/'choice-2400.trec'}
metrics={};topics={};pre=read_run(paths['fusion'])
for name,path in paths.items():
 text=subprocess.check_output(['trec_eval','-q','-c','-M1000',str(root/'51-100.qrels.txt'),str(path)],text=True)
 (out/(name+'-eval.txt')).write_text(text)
 metrics[name]={};topics[name]={}
 for line in text.splitlines():
  fields=line.split()
  if len(fields)!=3:continue
  m,q,v=fields
  if q=='all' and m in ('map','Rprec','P_10','bpref','recip_rank','num_rel_ret'):metrics[name][m]=float(v)
  if q!='all' and m=='map':topics[name][q]=float(v)
 run=read_run(path)
 assert run.keys()==pre.keys()
 for q in pre:
  assert {r[0] for r in run[q]}=={r[0] for r in pre[q]}
  assert [r[0] for r in run[q][100:]]==[r[0] for r in pre[q][100:]]
report={'metrics':metrics,'candidate_and_tail_preservation':True,'fixed_input_sha256':hashlib.sha256(paths['fusion'].read_bytes()).hexdigest(),'comparisons':{}}
for baseline in ('pointwise_24000','pointwise_2400'):
 d={q:round(topics['choice_2400'][q]-topics[baseline][q],4) for q in pre}
 report['comparisons'][baseline]={'improved':sum(v>0 for v in d.values()),'worse':sum(v<0 for v in d.values()),'tied':sum(v==0 for v in d.values()),'ap_deltas':d}
(out/'analysis.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(metrics,indent=2))
