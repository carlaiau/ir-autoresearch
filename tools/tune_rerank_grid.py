#!/usr/bin/env python3

import argparse
import csv
import itertools
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional


METRICS = ("map", "Rprec", "P_10", "bpref", "recip_rank")


def parse_int_list(raw: str) -> List[int]:
    values = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        values.append(int(item))
    if not values:
        raise ValueError("expected at least one integer value")
    return values


def parse_float_list(raw: str) -> List[float]:
    values = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        values.append(float(item))
    if not values:
        raise ValueError("expected at least one float value")
    return values


def run(cmd: List[str], *, cwd: Optional[Path] = None, env: Optional[Dict[str, str]] = None, stdin=None, stdout=None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        stdin=stdin,
        stdout=subprocess.PIPE if stdout is None else stdout,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )


def parse_trec_eval(summary: str) -> Dict[str, float]:
    metrics: Dict[str, float] = {}
    for line in summary.splitlines():
        parts = line.split()
        if len(parts) != 3:
            continue
        metric, scope, value = parts
        if scope == "all" and metric in METRICS:
            metrics[metric] = float(value)
    missing = [metric for metric in METRICS if metric not in metrics]
    if missing:
        raise RuntimeError(f"missing trec_eval metrics: {', '.join(missing)}")
    return metrics


def branch_name(repo_root: Path) -> str:
    result = run(["git", "branch", "--show-current"], cwd=repo_root)
    name = result.stdout.strip()
    return name or "detached-head"


def default_output_path(workdir: Path) -> Path:
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    return workdir / f"rerank-grid-{timestamp}.tsv"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sweep rerank parameters by reusing a single built index."
    )
    parser.add_argument("collection", help="Absolute or relative path to the WSJ XML file")
    parser.add_argument(
        "--topics",
        default="51-100.titles.txt",
        help="Topics file to feed into the searcher",
    )
    parser.add_argument(
        "--qrels",
        default="51-100.qrels.txt",
        help="Qrels file for trec_eval",
    )
    parser.add_argument(
        "--docs",
        default="10,15,20,25,30",
        help="Comma-separated rerank candidate counts",
    )
    parser.add_argument(
        "--windows",
        default="16,24,32,48,64",
        help="Comma-separated passage window sizes",
    )
    parser.add_argument(
        "--weights",
        default="0.05,0.10,0.15,0.20,0.25",
        help="Comma-separated passage weights",
    )
    parser.add_argument(
        "--workdir",
        default="",
        help="Working directory for binaries, index files, and run files",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Where to write the TSV results (defaults inside the workdir)",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    collection = Path(args.collection).expanduser()
    if not collection.is_absolute():
        collection = (Path.cwd() / collection).resolve()
    if not collection.exists():
        raise FileNotFoundError(f"collection does not exist: {collection}")

    topics = Path(args.topics).expanduser()
    if not topics.is_absolute():
        topics = (repo_root / topics).resolve()
    if not topics.is_file():
        raise FileNotFoundError(f"topics file does not exist: {topics}")

    qrels = Path(args.qrels).expanduser()
    if not qrels.is_absolute():
        qrels = (repo_root / qrels).resolve()
    if not qrels.is_file():
        raise FileNotFoundError(f"qrels file does not exist: {qrels}")

    if args.workdir:
        workdir = Path(args.workdir).expanduser()
        if not workdir.is_absolute():
            workdir = (Path.cwd() / workdir).resolve()
    else:
        workdir = (repo_root / "wsj-grid-search" / branch_name(repo_root)).resolve()
    workdir.mkdir(parents=True, exist_ok=True)

    output_path = Path(args.output).expanduser() if args.output else default_output_path(workdir)
    if not output_path.is_absolute():
        output_path = (Path.cwd() / output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    docs_values = parse_int_list(args.docs)
    window_values = parse_int_list(args.windows)
    weight_values = parse_float_list(args.weights)

    index_bin = workdir / "jassjr-index"
    search_bin = workdir / "jassjr-search"
    run(["go", "build", "-o", str(index_bin), str(repo_root / "index" / "JASSjr_index.go")], cwd=repo_root)
    run(["go", "build", "-o", str(search_bin), str(repo_root / "search" / "JASSjr_search.go")], cwd=repo_root)

    for path in (
        workdir / "docids.bin",
        workdir / "forward.bin",
        workdir / "forward_offsets.bin",
        workdir / "lengths.bin",
        workdir / "postings.bin",
        workdir / "vocab.bin",
    ):
        path.unlink(missing_ok=True)

    print(f"Indexing collection once in {workdir}", file=sys.stderr)
    run([str(index_bin), str(collection)], cwd=workdir)

    base_env = os.environ.copy()
    rows = []
    combinations = list(itertools.product(docs_values, window_values, weight_values))
    for index, (docs, window, weight) in enumerate(combinations, start=1):
        label = f"d{docs}-w{window}-g{weight:.2f}"
        results_file = workdir / f"results-{label}.trec"
        env = base_env | {
            "JASSJR_RERANK_DOCS": str(docs),
            "JASSJR_RERANK_PASSAGE_WINDOW": str(window),
            "JASSJR_RERANK_PASSAGE_WEIGHT": f"{weight:.4f}",
        }

        with topics.open("r", encoding="utf-8") as topics_fh, results_file.open("w", encoding="utf-8") as results_fh:
            started = time.perf_counter()
            run([str(search_bin)], cwd=workdir, env=env, stdin=topics_fh, stdout=results_fh)
            search_seconds = time.perf_counter() - started

        summary = run(
            ["trec_eval", "-c", "-M1000", str(qrels), str(results_file)],
            cwd=repo_root,
            env=env,
        ).stdout
        metrics = parse_trec_eval(summary)
        row = {
            "label": label,
            "rerank_docs": docs,
            "passage_window": window,
            "passage_weight": f"{weight:.4f}",
            "search_seconds": f"{search_seconds:.4f}",
        }
        for metric in METRICS:
            row[metric] = f"{metrics[metric]:.4f}"
        rows.append(row)
        print(
            f"[{index}/{len(combinations)}] {label}: "
            f"map={row['map']} P_10={row['P_10']} search_seconds={row['search_seconds']}",
            file=sys.stderr,
        )

    rows.sort(
        key=lambda row: (
            float(row["map"]),
            float(row["Rprec"]),
            float(row["P_10"]),
            float(row["bpref"]),
            -float(row["search_seconds"]),
        ),
        reverse=True,
    )

    fieldnames = [
        "label",
        "rerank_docs",
        "passage_window",
        "passage_weight",
        "map",
        "Rprec",
        "P_10",
        "bpref",
        "recip_rank",
        "search_seconds",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as output_fh:
        writer = csv.DictWriter(output_fh, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {output_path}", file=sys.stderr)
    if rows:
        best = rows[0]
        print(
            "Best config: "
            f"{best['label']} map={best['map']} "
            f"Rprec={best['Rprec']} P_10={best['P_10']} "
            f"bpref={best['bpref']} recip_rank={best['recip_rank']}",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
