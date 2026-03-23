#!/usr/bin/env python3

import argparse
from pathlib import Path
from typing import Dict, List


def parse_run(path: Path) -> Dict[str, List[str]]:
    runs: Dict[str, List[str]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) != 6:
            continue
        runs.setdefault(parts[0], []).append(line)
    return runs


def parse_query_ids(path: Path) -> List[str]:
    query_ids: List[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if not parts:
            continue
        query_ids.append(parts[0])
    return query_ids


def metadata_lines(
    *,
    sparse_run: Path,
    fallback_run: Path,
    sparse_topics_file: Path,
    output_file: Path,
    sparse_queries: int,
) -> List[str]:
    return [
        f"JASSJR_QUERY_RUN_SELECT_SPARSE_RUN: {sparse_run}",
        f"JASSJR_QUERY_RUN_SELECT_FALLBACK_RUN: {fallback_run}",
        f"JASSJR_QUERY_RUN_SELECT_SPARSE_TOPICS_FILE: {sparse_topics_file}",
        f"JASSJR_QUERY_RUN_SELECT_OUTPUT_FILE: {output_file}",
        f"JASSJR_QUERY_RUN_SELECT_SPARSE_QUERIES: {sparse_queries}",
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Select one TREC run for a subset of query IDs and a fallback run for the rest.")
    parser.add_argument("--sparse-run", required=True, help="Run to use for sparse query IDs")
    parser.add_argument("--fallback-run", required=True, help="Run to use for all other query IDs")
    parser.add_argument("--sparse-topics-file", required=True, help="Topics file whose query IDs should use the sparse run")
    parser.add_argument("--output", required=True, help="Output TREC run")
    parser.add_argument("--metadata-file", default="", help="Optional metadata output path")
    args = parser.parse_args()

    sparse_run = Path(args.sparse_run).expanduser().resolve()
    fallback_run = Path(args.fallback_run).expanduser().resolve()
    sparse_topics_file = Path(args.sparse_topics_file).expanduser().resolve()
    output_file = Path(args.output).expanduser().resolve()

    for required in (sparse_run, fallback_run, sparse_topics_file):
        if not required.is_file():
            raise SystemExit(f"required input not found: {required}")

    sparse_query_ids = parse_query_ids(sparse_topics_file)
    sparse_query_set = set(sparse_query_ids)
    sparse_lines = parse_run(sparse_run)
    fallback_lines = parse_run(fallback_run)

    output_lines: List[str] = []
    all_query_ids = sorted(
        set(fallback_lines.keys()) | set(sparse_lines.keys()),
        key=lambda item: int(item) if item.isdigit() else item,
    )
    for query_id in all_query_ids:
        lines = fallback_lines.get(query_id, [])
        if query_id in sparse_query_set:
            lines = sparse_lines.get(query_id, lines)
        output_lines.extend(lines)

    output_file.write_text("\n".join(output_lines) + ("\n" if output_lines else ""), encoding="utf-8")

    if args.metadata_file:
        metadata_file = Path(args.metadata_file).expanduser().resolve()
        metadata_file.write_text(
            "\n".join(
                metadata_lines(
                    sparse_run=sparse_run,
                    fallback_run=fallback_run,
                    sparse_topics_file=sparse_topics_file,
                    output_file=output_file,
                    sparse_queries=len(sparse_query_ids),
                )
            )
            + "\n",
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
