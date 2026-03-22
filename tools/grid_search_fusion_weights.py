#!/usr/bin/env python3

import argparse
import csv
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root / "tools"))

from fuse_runs import SourceSpec, extend_with_tail, parse_run, reciprocal_rank_fuse, write_run  # noqa: E402


METRICS = ("map", "Rprec", "P_10", "bpref", "recip_rank")
INDEX_FILES = (
    "docids.bin",
    "forward.bin",
    "forward_offsets.bin",
    "lengths.bin",
    "postings.bin",
    "vocab.bin",
)


def run(
    cmd: Sequence[str],
    *,
    cwd: Optional[Path] = None,
    env: Optional[Dict[str, str]] = None,
    stdin=None,
    stdout=None,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        list(cmd),
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


def branch_name(root: Path) -> str:
    result = run(["git", "branch", "--show-current"], cwd=root)
    name = result.stdout.strip()
    return name or "detached-head"


def default_output_path(output_dir: Path) -> Path:
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    return output_dir / f"fusion-weight-grid-{timestamp}.tsv"


def default_metadata_path(output_path: Path) -> Path:
    return output_path.with_suffix(".meta.txt")


def resolve_path(raw: str, *, base: Path) -> Path:
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = (base / path).resolve()
    return path


def ensure_commands() -> None:
    required = ("go", "python3", "trec_eval")
    missing = [cmd for cmd in required if shutil.which(cmd) is None]
    if missing:
        raise SystemExit(f"required commands not found on PATH: {', '.join(missing)}")


def ensure_index(
    *,
    root: Path,
    workdir: Path,
    collection: Path,
    force_reindex: bool,
) -> None:
    index_bin = workdir / "jassjr-index"
    search_bin = workdir / "jassjr-search"
    dense_search_bin = workdir / "jassjr-dense-search"

    run(["go", "build", "-o", str(index_bin), str(root / "index" / "JASSjr_index.go")], cwd=root)
    run(["go", "build", "-o", str(search_bin), str(root / "search" / "JASSjr_search.go")], cwd=root)
    run(["go", "build", "-o", str(dense_search_bin), str(root / "tools" / "JASSjr_dense_search.go")], cwd=root)

    if not force_reindex and all((workdir / name).is_file() for name in INDEX_FILES):
        return

    for name in INDEX_FILES:
        (workdir / name).unlink(missing_ok=True)

    print(f"Indexing collection once in {workdir}", file=sys.stderr)
    run([str(index_bin), str(collection)], cwd=workdir)


def write_source_run(
    *,
    workdir: Path,
    output_path: Path,
    topics: Path,
    env_overrides: Dict[str, str],
    force: bool,
) -> None:
    if output_path.is_file() and not force:
        return
    env = os.environ.copy()
    env.update(env_overrides)
    with topics.open("r", encoding="utf-8") as topics_fh, output_path.open("w", encoding="utf-8") as output_fh:
        run([str(workdir / "jassjr-search")], cwd=workdir, env=env, stdin=topics_fh, stdout=output_fh)


def ensure_dense_vectors(
    *,
    root: Path,
    workdir: Path,
    force_vectors: bool,
) -> None:
    if force_vectors:
        for name in ("dense-docs.f32", "dense-docs.meta.json", "dense-docs.f32.part", "dense-docs.meta.part.json"):
            (workdir / name).unlink(missing_ok=True)
    run(
        [
            "python3",
            str(root / "tools" / "build_dense_vectors.py"),
            "--repo-root",
            str(root),
            "--workdir",
            str(workdir),
        ],
        cwd=root,
    )


def ensure_dense_run(
    *,
    root: Path,
    workdir: Path,
    topics: Path,
    output_path: Path,
    dense_topk: int,
    force: bool,
) -> None:
    if output_path.is_file() and not force:
        return
    env = os.environ.copy()
    env["JASSJR_SEMANTIC_TOPK"] = str(dense_topk)
    with topics.open("r", encoding="utf-8") as topics_fh, output_path.open("w", encoding="utf-8") as output_fh:
        run(
            [str(workdir / "jassjr-dense-search"), "--repo-root", str(root)],
            cwd=workdir,
            env=env,
            stdin=topics_fh,
            stdout=output_fh,
        )


def weight_combinations(step: float, min_weight: float, max_weight: float) -> Iterable[Tuple[float, float, float]]:
    units = round(1.0 / step)
    if abs(units * step - 1.0) > 1e-9:
        raise SystemExit("--step must divide 1.0 exactly")
    min_units = round(min_weight / step)
    max_units = round(max_weight / step)
    for bm25_units in range(min_units, max_units + 1):
        for rm3_units in range(min_units, max_units + 1):
            dense_units = units - bm25_units - rm3_units
            if dense_units < min_units or dense_units > max_units:
                continue
            yield (
                bm25_units * step,
                rm3_units * step,
                dense_units * step,
            )


def format_label(bm25: float, rm3: float, dense: float) -> str:
    return f"b{bm25:.2f}-r{rm3:.2f}-d{dense:.2f}"


def write_metadata(
    *,
    path: Path,
    branch: str,
    collection: Path,
    topics: Path,
    qrels: Path,
    workdir: Path,
    output_path: Path,
    step: float,
    min_weight: float,
    max_weight: float,
    rrf_k: int,
    bm25_topk: int,
    rm3_topk: int,
    dense_topk: int,
    save_top_runs: int,
    source_runs: Dict[str, Path],
) -> None:
    lines = [
        f"branch: {branch}",
        f"timestamp: {time.strftime('%Y%m%d-%H%M%S')}",
        f"collection: {collection}",
        f"topics: {topics}",
        f"qrels: {qrels}",
        f"workdir: {workdir}",
        f"output_tsv: {output_path}",
        f"grid_step: {step:.2f}",
        f"grid_min_weight: {min_weight:.2f}",
        f"grid_max_weight: {max_weight:.2f}",
        f"rrf_k: {rrf_k}",
        f"bm25_topk: {bm25_topk}",
        f"rm3_topk: {rm3_topk}",
        f"dense_topk: {dense_topk}",
        f"save_top_runs: {save_top_runs}",
        f"source_bm25: {source_runs['bm25']}",
        f"source_rm3: {source_runs['rm3']}",
        f"source_dense: {source_runs['dense']}",
    ]
    for name in (
        "JASSJR_SEMANTIC_MODE",
        "JASSJR_SEMANTIC_MODEL",
        "JASSJR_SEMANTIC_DIMENSIONS",
        "JASSJR_SEMANTIC_DOC_WORDS",
        "JASSJR_SEMANTIC_BATCH_SIZE",
        "JASSJR_OPENAI_RERANK_MODE",
        "JASSJR_OPENAI_MONO_MODEL",
        "JASSJR_OPENAI_MONO_DOCS",
        "JASSJR_OPENAI_CACHE_DIR",
    ):
        if os.getenv(name):
            lines.append(f"{name}: {os.getenv(name)}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Grid-search tri-source fusion weights by reusing one indexed WSJ workdir."
    )
    parser.add_argument("collection", help="Absolute or relative path to the WSJ XML file")
    parser.add_argument("--topics", default="51-100.titles.txt", help="Topics file to feed into the searchers")
    parser.add_argument("--qrels", default="51-100.qrels.txt", help="Qrels file for trec_eval")
    parser.add_argument("--workdir", default="", help="Branch workdir for binaries, index files, and source runs")
    parser.add_argument("--output", default="", help="Output TSV path for the weight sweep")
    parser.add_argument("--metadata-file", default="", help="Optional metadata companion file")
    parser.add_argument("--step", type=float, default=0.05, help="Weight grid step; must divide 1.0 exactly")
    parser.add_argument("--min-weight", type=float, default=0.05, help="Minimum per-source weight")
    parser.add_argument("--max-weight", type=float, default=0.90, help="Maximum per-source weight")
    parser.add_argument("--rrf-k", type=int, default=60, help="Reciprocal-rank fusion k")
    parser.add_argument("--bm25-topk", type=int, default=250, help="BM25 contribution depth")
    parser.add_argument("--rm3-topk", type=int, default=250, help="RM3 contribution depth")
    parser.add_argument("--dense-topk", type=int, default=250, help="Dense contribution depth")
    parser.add_argument("--save-top-runs", type=int, default=5, help="How many best fused pre-mono runs to save")
    parser.add_argument("--force-reindex", action="store_true", help="Rebuild the index even if one already exists")
    parser.add_argument("--force-source-runs", action="store_true", help="Regenerate BM25/RM3/dense source runs")
    parser.add_argument("--force-vectors", action="store_true", help="Rebuild dense vectors even if metadata matches")
    args = parser.parse_args()

    ensure_commands()

    collection = resolve_path(args.collection, base=Path.cwd())
    topics = resolve_path(args.topics, base=repo_root)
    qrels = resolve_path(args.qrels, base=repo_root)
    if not collection.is_file():
        raise FileNotFoundError(f"collection file not found: {collection}")
    if not topics.is_file():
        raise FileNotFoundError(f"topics file not found: {topics}")
    if not qrels.is_file():
        raise FileNotFoundError(f"qrels file not found: {qrels}")
    if args.rrf_k < 0:
        raise SystemExit("--rrf-k must be non-negative")
    if args.bm25_topk <= 0 or args.rm3_topk <= 0 or args.dense_topk <= 0:
        raise SystemExit("all topk values must be positive")
    if args.save_top_runs < 0:
        raise SystemExit("--save-top-runs must be non-negative")
    if args.step <= 0 or args.step > 1.0:
        raise SystemExit("--step must be in (0, 1]")
    if args.min_weight < 0 or args.max_weight > 1.0 or args.min_weight > args.max_weight:
        raise SystemExit("invalid min/max weight range")

    branch = branch_name(repo_root)
    if branch == "original":
        raise SystemExit("refusing to write grid-search artifacts for branch 'original'")

    if args.workdir:
        workdir = resolve_path(args.workdir, base=Path.cwd())
    else:
        workdir = (repo_root / "wsj-grid-search" / branch).resolve()
    workdir.mkdir(parents=True, exist_ok=True)

    output_dir = (repo_root / "experiment_evaluations" / branch).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = resolve_path(args.output, base=Path.cwd()) if args.output else default_output_path(output_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path = resolve_path(args.metadata_file, base=Path.cwd()) if args.metadata_file else default_metadata_path(output_path)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)

    ensure_index(root=repo_root, workdir=workdir, collection=collection, force_reindex=args.force_reindex)

    source_runs = {
        "bm25": workdir / "source-bm25.trec",
        "rm3": workdir / "source-rm3.trec",
        "dense": workdir / "source-dense.trec",
    }
    write_source_run(
        workdir=workdir,
        output_path=source_runs["bm25"],
        topics=topics,
        env_overrides={
            "JASSJR_RERANK_DOCS": "0",
            "JASSJR_FEEDBACK_DOCS": "0",
            "JASSJR_EXPANSION_TERMS": "0",
            "JASSJR_EXPANSION_WEIGHT": "0",
        },
        force=args.force_source_runs,
    )
    write_source_run(
        workdir=workdir,
        output_path=source_runs["rm3"],
        topics=topics,
        env_overrides={"JASSJR_RERANK_DOCS": "0"},
        force=args.force_source_runs,
    )
    ensure_dense_vectors(root=repo_root, workdir=workdir, force_vectors=args.force_vectors)
    ensure_dense_run(
        root=repo_root,
        workdir=workdir,
        topics=topics,
        output_path=source_runs["dense"],
        dense_topk=max(args.dense_topk, 250),
        force=args.force_source_runs,
    )

    write_metadata(
        path=metadata_path,
        branch=branch,
        collection=collection,
        topics=topics,
        qrels=qrels,
        workdir=workdir,
        output_path=output_path,
        step=args.step,
        min_weight=args.min_weight,
        max_weight=args.max_weight,
        rrf_k=args.rrf_k,
        bm25_topk=args.bm25_topk,
        rm3_topk=args.rm3_topk,
        dense_topk=args.dense_topk,
        save_top_runs=args.save_top_runs,
        source_runs=source_runs,
    )

    source_data = {label: parse_run(path) for label, path in source_runs.items()}
    combinations = list(weight_combinations(args.step, args.min_weight, args.max_weight))
    rows: List[Dict[str, str]] = []
    scratch_run = workdir / "fusion-grid-current.trec"

    for index, (bm25_weight, rm3_weight, dense_weight) in enumerate(combinations, start=1):
        label = format_label(bm25_weight, rm3_weight, dense_weight)
        specs = [
            SourceSpec(label="bm25", path=source_runs["bm25"], weight=bm25_weight, topk=args.bm25_topk),
            SourceSpec(label="rm3", path=source_runs["rm3"], weight=rm3_weight, topk=args.rm3_topk),
            SourceSpec(label="dense", path=source_runs["dense"], weight=dense_weight, topk=args.dense_topk),
        ]
        fused = reciprocal_rank_fuse(source_specs=specs, source_runs=source_data, rrf_k=args.rrf_k)
        completed = extend_with_tail(source_specs=specs, source_runs=source_data, fused=fused)
        write_run(scratch_run, completed)
        summary = run(["trec_eval", "-c", "-M1000", str(qrels), str(scratch_run)], cwd=repo_root).stdout
        metrics = parse_trec_eval(summary)
        row = {
            "label": label,
            "weight_bm25": f"{bm25_weight:.2f}",
            "weight_rm3": f"{rm3_weight:.2f}",
            "weight_dense": f"{dense_weight:.2f}",
            "rrf_k": str(args.rrf_k),
            "bm25_topk": str(args.bm25_topk),
            "rm3_topk": str(args.rm3_topk),
            "dense_topk": str(args.dense_topk),
        }
        for metric in METRICS:
            row[metric] = f"{metrics[metric]:.4f}"
        rows.append(row)
        print(
            f"[{index}/{len(combinations)}] {label}: "
            f"map={row['map']} Rprec={row['Rprec']} P_10={row['P_10']}",
            file=sys.stderr,
        )

    rows.sort(
        key=lambda row: (
            float(row["map"]),
            float(row["Rprec"]),
            float(row["P_10"]),
            float(row["bpref"]),
            float(row["recip_rank"]),
        ),
        reverse=True,
    )

    fieldnames = [
        "label",
        "weight_bm25",
        "weight_rm3",
        "weight_dense",
        "rrf_k",
        "bm25_topk",
        "rm3_topk",
        "dense_topk",
        "map",
        "Rprec",
        "P_10",
        "bpref",
        "recip_rank",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as output_fh:
        writer = csv.DictWriter(output_fh, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)

    top_runs_dir = workdir / f"fusion-grid-top-{output_path.stem}"
    top_runs_dir.mkdir(parents=True, exist_ok=True)
    for row in rows[: args.save_top_runs]:
        bm25_weight = float(row["weight_bm25"])
        rm3_weight = float(row["weight_rm3"])
        dense_weight = float(row["weight_dense"])
        specs = [
            SourceSpec(label="bm25", path=source_runs["bm25"], weight=bm25_weight, topk=args.bm25_topk),
            SourceSpec(label="rm3", path=source_runs["rm3"], weight=rm3_weight, topk=args.rm3_topk),
            SourceSpec(label="dense", path=source_runs["dense"], weight=dense_weight, topk=args.dense_topk),
        ]
        fused = reciprocal_rank_fuse(source_specs=specs, source_runs=source_data, rrf_k=args.rrf_k)
        completed = extend_with_tail(source_specs=specs, source_runs=source_data, fused=fused)
        write_run(top_runs_dir / f"{row['label']}.trec", completed)

    scratch_run.unlink(missing_ok=True)

    if rows:
        best = rows[0]
        print(
            f"Weight sweep written to {output_path}\n"
            f"Best pre-mono candidate: {best['label']} "
            f"(map={best['map']}, Rprec={best['Rprec']}, P_10={best['P_10']})"
        )
    else:
        print(f"Weight sweep wrote no rows to {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
