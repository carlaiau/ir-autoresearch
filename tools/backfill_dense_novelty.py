#!/usr/bin/env python3

import argparse
from pathlib import Path
from typing import Dict, List, Sequence, Tuple


def parse_run(path: Path) -> Dict[str, List[str]]:
    runs: Dict[str, List[Tuple[int, str]]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) != 6:
            continue
        query_id, _, doc_id, rank, _, _ = parts
        runs.setdefault(query_id, []).append((int(rank), doc_id))

    ordered: Dict[str, List[str]] = {}
    for query_id, entries in runs.items():
        entries.sort(key=lambda item: item[0])
        ordered[query_id] = [doc_id for _, doc_id in entries]
    return ordered


def parse_sparse_query_ids(path: Path) -> List[str]:
    query_ids: List[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if not parts:
            continue
        query_ids.append(parts[0])
    return query_ids


def dedupe(items: Sequence[str]) -> List[str]:
    seen = set()
    ordered: List[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def write_run(path: Path, ranking: Dict[str, List[str]], max_docs: int) -> None:
    lines: List[str] = []
    for query_id in sorted(ranking, key=lambda item: int(item) if item.isdigit() else item):
        docs = ranking[query_id][:max_docs]
        total = len(docs)
        for rank, doc_id in enumerate(docs, start=1):
            score = float(total - rank + 1)
            lines.append(f"{query_id} Q0 {doc_id} {rank} {score:.6f} JASSjr")
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def metadata_lines(
    *,
    base_run: Path,
    fallback_run: Path,
    dense_run: Path,
    sparse_topics_file: Path,
    output_file: Path,
    preserve_base: int,
    inject_dense: int,
    max_docs: int,
    sparse_queries: int,
    injected_queries: int,
    injected_docs: int,
) -> List[str]:
    return [
        f"JASSJR_DENSE_NOVELTY_BASE_RUN: {base_run}",
        f"JASSJR_DENSE_NOVELTY_FALLBACK_RUN: {fallback_run}",
        f"JASSJR_DENSE_NOVELTY_DENSE_RUN: {dense_run}",
        f"JASSJR_DENSE_NOVELTY_SPARSE_TOPICS_FILE: {sparse_topics_file}",
        f"JASSJR_DENSE_NOVELTY_OUTPUT_FILE: {output_file}",
        f"JASSJR_DENSE_NOVELTY_PRESERVE_BASE: {preserve_base}",
        f"JASSJR_DENSE_NOVELTY_INJECT_DENSE: {inject_dense}",
        f"JASSJR_DENSE_NOVELTY_MAX_DOCS: {max_docs}",
        f"JASSJR_DENSE_NOVELTY_SPARSE_QUERIES: {sparse_queries}",
        f"JASSJR_DENSE_NOVELTY_INJECTED_QUERIES: {injected_queries}",
        f"JASSJR_DENSE_NOVELTY_INJECTED_DOCS: {injected_docs}",
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Inject novel dense candidates for sparse queries without replacing the dense fallback for other queries.")
    parser.add_argument("--base-run", required=True, help="Lexical base run for sparse queries")
    parser.add_argument("--fallback-run", required=True, help="Existing candidate run for non-sparse queries")
    parser.add_argument("--dense-run", required=True, help="Dense-only candidate run")
    parser.add_argument("--sparse-topics-file", required=True, help="Topics file containing the sparse query IDs to modify")
    parser.add_argument("--output", required=True, help="Output TREC run path")
    parser.add_argument("--metadata-file", default="", help="Optional metadata output path")
    parser.add_argument("--preserve-base", type=int, default=60, help="How many base docs to keep ahead of dense novelty injection")
    parser.add_argument("--inject-dense", type=int, default=25, help="How many novel dense docs to inject into sparse-query rankings")
    parser.add_argument("--max-docs", type=int, default=1000, help="Maximum docs per query in the output run")
    args = parser.parse_args()

    if args.preserve_base < 0:
        raise SystemExit("--preserve-base must be non-negative")
    if args.inject_dense < 0:
        raise SystemExit("--inject-dense must be non-negative")
    if args.max_docs <= 0:
        raise SystemExit("--max-docs must be positive")

    base_run = Path(args.base_run).expanduser().resolve()
    fallback_run = Path(args.fallback_run).expanduser().resolve()
    dense_run = Path(args.dense_run).expanduser().resolve()
    sparse_topics_file = Path(args.sparse_topics_file).expanduser().resolve()
    output_file = Path(args.output).expanduser().resolve()

    for required in (base_run, fallback_run, dense_run, sparse_topics_file):
        if not required.is_file():
            raise SystemExit(f"required input not found: {required}")

    base = parse_run(base_run)
    fallback = parse_run(fallback_run)
    dense = parse_run(dense_run)
    sparse_query_ids = parse_sparse_query_ids(sparse_topics_file)
    sparse_query_set = set(sparse_query_ids)

    ranking: Dict[str, List[str]] = {}
    all_query_ids = set(fallback.keys()) | set(base.keys()) | set(dense.keys())
    injected_queries = 0
    injected_docs = 0

    for query_id in all_query_ids:
        fallback_docs = fallback.get(query_id, [])
        if query_id not in sparse_query_set:
            ranking[query_id] = fallback_docs
            continue

        base_docs = base.get(query_id, fallback_docs)
        dense_novel_docs = [doc_id for doc_id in dense.get(query_id, []) if doc_id not in set(base_docs)]
        injected = dense_novel_docs[: args.inject_dense]
        merged = dedupe(
            base_docs[: args.preserve_base]
            + injected
            + base_docs[args.preserve_base :]
            + dense_novel_docs[args.inject_dense :]
        )
        ranking[query_id] = merged[: args.max_docs] if merged else fallback_docs[: args.max_docs]
        if injected:
            injected_queries += 1
            injected_docs += len(injected)

    write_run(output_file, ranking, args.max_docs)

    if args.metadata_file:
        metadata_file = Path(args.metadata_file).expanduser().resolve()
        metadata_file.write_text(
            "\n".join(
                metadata_lines(
                    base_run=base_run,
                    fallback_run=fallback_run,
                    dense_run=dense_run,
                    sparse_topics_file=sparse_topics_file,
                    output_file=output_file,
                    preserve_base=args.preserve_base,
                    inject_dense=args.inject_dense,
                    max_docs=args.max_docs,
                    sparse_queries=len(sparse_query_ids),
                    injected_queries=injected_queries,
                    injected_docs=injected_docs,
                )
            )
            + "\n",
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
