# Integrated-main lexical benchmark

Five timed iterations: indexing median **11.03 s**, search median **0.41 s** for
all 50 topics. [Raw timings](benchmark.txt). Same Go source hashes and default
lexical configuration as [this baseline](results.md); JASSJR_RERANK_DOCS=0.

This is a new cohort using main's later feedback algorithm. The old 0.22 s
pre-JEV baseline uses different source code and is not a controlled regression
comparison for the folder restructuring. No API or neural reranking is included.
The legacy benchmark helper warms search process/index loading without passing
the topics to its warm-up invocation.
