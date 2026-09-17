#!/usr/bin/env python3

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple


@dataclass
class SourceSpec:
    label: str
    path: Path
    weight: float
    topk: int


def parse_run(path: Path) -> Dict[str, List[Dict[str, object]]]:
    runs: Dict[str, List[Dict[str, object]]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) != 6:
            continue
        query_id, _, doc_id, rank, score, run_name = parts
        runs.setdefault(query_id, []).append(
            {
                "doc_id": doc_id,
                "rank": int(rank),
                "score": float(score),
                "run_name": run_name,
            }
        )
    for entries in runs.values():
        entries.sort(key=lambda entry: int(entry["rank"]))
    return runs


def reciprocal_rank_fuse(
    *,
    source_specs: List[SourceSpec],
    source_runs: Dict[str, Dict[str, List[Dict[str, object]]]],
    rrf_k: int,
) -> Dict[str, List[Tuple[str, float]]]:
    all_query_ids = set()
    for runs in source_runs.values():
        all_query_ids.update(runs.keys())

    fused: Dict[str, List[Tuple[str, float]]] = {}
    for query_id in all_query_ids:
        scores: Dict[str, float] = {}
        best_rank: Dict[str, int] = {}
        for source in source_specs:
            entries = source_runs[source.label].get(query_id, [])
            limit = min(source.topk, len(entries)) if source.topk > 0 else len(entries)
            for entry in entries[:limit]:
                doc_id = str(entry["doc_id"])
                rank = int(entry["rank"])
                scores[doc_id] = scores.get(doc_id, 0.0) + source.weight / float(rrf_k + rank)
                best_rank[doc_id] = min(best_rank.get(doc_id, rank), rank)

        ranked = sorted(
            scores.items(),
            key=lambda item: (-item[1], best_rank[item[0]], item[0]),
        )
        fused[query_id] = ranked
    return fused


def extend_with_tail(
    *,
    source_specs: List[SourceSpec],
    source_runs: Dict[str, Dict[str, List[Dict[str, object]]]],
    fused: Dict[str, List[Tuple[str, float]]],
) -> Dict[str, List[Tuple[str, float]]]:
    completed: Dict[str, List[Tuple[str, float]]] = {}
    all_query_ids = set(fused.keys())
    for runs in source_runs.values():
        all_query_ids.update(runs.keys())

    for query_id in all_query_ids:
        prefix = list(fused.get(query_id, []))
        seen = {doc_id for doc_id, _ in prefix}
        ranking = list(prefix)

        for source in source_specs:
            for entry in source_runs[source.label].get(query_id, []):
                doc_id = str(entry["doc_id"])
                if doc_id in seen:
                    continue
                seen.add(doc_id)
                ranking.append((doc_id, 0.0))

        if prefix:
            floor_score = prefix[-1][1]
        else:
            floor_score = 0.0

        completed_entries: List[Tuple[str, float]] = []
        for index, (doc_id, score) in enumerate(ranking):
            if index < len(prefix):
                completed_entries.append((doc_id, score))
            else:
                completed_entries.append((doc_id, floor_score - (index - len(prefix) + 1) * 1e-9))
        completed[query_id] = completed_entries
    return completed


def write_run(path: Path, ranking: Dict[str, List[Tuple[str, float]]]) -> None:
    lines: List[str] = []
    for query_id in sorted(ranking, key=lambda item: int(item) if item.isdigit() else item):
        for rank, (doc_id, score) in enumerate(ranking[query_id], start=1):
            lines.append(f"{query_id} Q0 {doc_id} {rank} {score:.9f} JASSjr")
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def metadata_lines(source_specs: List[SourceSpec], rrf_k: int, output_file: Path) -> List[str]:
    lines = [
        f"JASSJR_FUSION_RRF_K: {rrf_k}",
        f"JASSJR_FUSION_OUTPUT_FILE: {output_file}",
        "JASSJR_FUSION_SOURCE_ORDER: " + ",".join(source.label for source in source_specs),
    ]
    for source in source_specs:
        upper = source.label.upper()
        lines.extend(
            [
                f"JASSJR_FUSION_SOURCE_{upper}_PATH: {source.path}",
                f"JASSJR_FUSION_SOURCE_{upper}_WEIGHT: {source.weight}",
                f"JASSJR_FUSION_SOURCE_{upper}_TOPK: {source.topk}",
            ]
        )
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="Fuse multiple TREC runs with weighted reciprocal rank fusion.")
    parser.add_argument("--output", required=True, help="Output TREC run file")
    parser.add_argument("--metadata-file", default="", help="Optional output path for fusion metadata")
    parser.add_argument("--rrf-k", type=int, required=True, help="Reciprocal rank fusion constant")
    parser.add_argument(
        "--source",
        action="append",
        nargs=4,
        metavar=("LABEL", "PATH", "WEIGHT", "TOPK"),
        required=True,
        help="One source run: label path weight topk",
    )
    args = parser.parse_args()

    if args.rrf_k < 0:
        raise SystemExit("--rrf-k must be non-negative")

    source_specs: List[SourceSpec] = []
    for label, path_raw, weight_raw, topk_raw in args.source:
        path = Path(path_raw).expanduser()
        if not path.is_absolute():
            path = (Path.cwd() / path).resolve()
        if not path.is_file():
            raise SystemExit(f"source run not found: {path}")
        weight = float(weight_raw)
        topk = int(topk_raw)
        if weight < 0:
            raise SystemExit(f"weight must be non-negative for source {label}")
        if topk < 0:
            raise SystemExit(f"topk must be non-negative for source {label}")
        source_specs.append(SourceSpec(label=label, path=path, weight=weight, topk=topk))

    output_path = Path(args.output).expanduser()
    if not output_path.is_absolute():
        output_path = (Path.cwd() / output_path).resolve()

    source_runs = {source.label: parse_run(source.path) for source in source_specs}
    fused = reciprocal_rank_fuse(source_specs=source_specs, source_runs=source_runs, rrf_k=args.rrf_k)
    completed = extend_with_tail(source_specs=source_specs, source_runs=source_runs, fused=fused)
    write_run(output_path, completed)

    if args.metadata_file:
        metadata_path = Path(args.metadata_file).expanduser()
        if not metadata_path.is_absolute():
            metadata_path = (Path.cwd() / metadata_path).resolve()
        metadata_path.write_text("\n".join(metadata_lines(source_specs, args.rrf_k, output_path)) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
