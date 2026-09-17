# JEV experiments

The requested experiments are complete: **passage MaxP** on the exact monoBERT
windows, and **pointwise scoring of complete documents**, both on the fixed
stage-1 top-100 candidates.

- [Protocol, implementation and reproduction](jev-comparison.md)
- [Paired results and measured time/cost](results/jev-comparison-20260918.md)

The earlier plan used `reranking/run.py` with a 24,000-character cap. That plan was
superseded by the explicit request for full documents and matched monoBERT
passages. The older capped runner remains available for historical reproduction,
but it was not used for these experiments. Obsolete JEV evaluation results remain
discarded; the new reports identify the fixed MAP 0.2521 candidate run and its
hashes. The failed first passage attempt is retained separately with its usage.
