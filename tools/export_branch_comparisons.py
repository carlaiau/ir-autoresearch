#!/usr/bin/env python3

from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


BRANCH_RE = re.compile(r"codex/[A-Za-z0-9._/-]+")
TIMESTAMP_RE = re.compile(r"^[^-]+-([0-9]{8}-[0-9]{6})\.txt$")


@dataclass
class BranchMetrics:
    branch: str
    branch_label: str
    timestamp: str
    row_kind: str
    map_value: float
    index_median: str
    search_topics_median: str
    eval_file: str
    bench_file: str


@dataclass
class GitHubMetadata:
    decision: str = "unknown"
    issue_number: str = ""
    issue_url: str = ""
    pr_number: str = ""
    pr_url: str = ""


def latest_file(directory: Path, pattern: str) -> Path | None:
    matches = sorted(directory.glob(pattern))
    return matches[-1] if matches else None


def meta_value(path: Path, key: str) -> str:
    prefix = f"{key}: "
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :]
    return ""


def eval_metric(path: Path, metric: str) -> float:
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[0] == metric and parts[1] == "all":
            return float(parts[2])
    raise ValueError(f"Metric {metric!r} not found in {path}")


def bench_metric(path: Path, key: str) -> str:
    return meta_value(path, key)


def timestamp_from_file(path: Path) -> str:
    match = TIMESTAMP_RE.match(path.name)
    if not match:
        raise ValueError(f"Could not parse timestamp from {path}")
    return match.group(1)


def latest_timestamp(eval_file: Path, bench_file: Path) -> str:
    return max(timestamp_from_file(eval_file), timestamp_from_file(bench_file))


def discover_branches(repo_root: Path) -> list[str]:
    branches: set[str] = set()
    for root_name in ("experiment_evaluations", "experiment_benchmarks"):
        root = repo_root / root_name
        if not root.exists():
            continue
        for report in root.rglob("*.txt"):
            try:
                branch = report.parent.relative_to(root).as_posix()
            except ValueError:
                continue
            if branch:
                branches.add(branch)
    return sorted(branches)


def collect_metrics(repo_root: Path) -> list[BranchMetrics]:
    archive_branch = "original"
    eval_root = repo_root / "experiment_evaluations"
    bench_root = repo_root / "experiment_benchmarks"

    original_eval = latest_file(eval_root / archive_branch, "trec_eval-*.txt")
    original_bench = latest_file(bench_root / archive_branch, "benchmark-*.txt")
    if original_eval is None or original_bench is None:
        raise SystemExit(
            "Missing original archive artifacts under original. "
            "The README table requires the original evaluation and benchmark reports."
        )

    original_topics = meta_value(original_eval, "topics")
    original_qrels = meta_value(original_eval, "qrels")
    original_smoke_topics = meta_value(original_bench, "smoke_topics")
    original_iterations = meta_value(original_bench, "iterations")

    rows = [
        BranchMetrics(
            branch=archive_branch,
            branch_label=archive_branch,
            timestamp=latest_timestamp(original_eval, original_bench),
            row_kind="original",
            map_value=eval_metric(original_eval, "map"),
            index_median=bench_metric(original_bench, "index_median"),
            search_topics_median=bench_metric(original_bench, "search_topics_median"),
            eval_file=str(original_eval),
            bench_file=str(original_bench),
        )
    ]

    for branch_name in discover_branches(repo_root):
        if branch_name in {"main", archive_branch}:
            continue

        branch_eval = latest_file(eval_root / branch_name, "trec_eval-*.txt")
        branch_bench = latest_file(bench_root / branch_name, "benchmark-*.txt")
        if branch_eval is None or branch_bench is None:
            print(f"Skipping {branch_name}: missing evaluation or benchmark artifact.", file=sys.stderr)
            continue

        branch_topics = meta_value(branch_eval, "topics")
        branch_qrels = meta_value(branch_eval, "qrels")
        branch_bench_topics = meta_value(branch_bench, "topics")
        branch_smoke_topics = meta_value(branch_bench, "smoke_topics")
        branch_iterations = meta_value(branch_bench, "iterations")

        if branch_topics != original_topics or branch_qrels != original_qrels:
            print(
                f"Skipping {branch_name}: evaluation metadata does not match the original archive.",
                file=sys.stderr,
            )
            continue

        if (
            branch_bench_topics != original_topics
            or branch_smoke_topics != original_smoke_topics
            or branch_iterations != original_iterations
        ):
            print(
                f"Skipping {branch_name}: benchmark metadata does not match the original archive.",
                file=sys.stderr,
            )
            continue

        rows.append(
            BranchMetrics(
                branch=branch_name,
                branch_label=branch_name.removeprefix("codex/"),
                timestamp=latest_timestamp(branch_eval, branch_bench),
                row_kind="branch",
                map_value=eval_metric(branch_eval, "map"),
                index_median=bench_metric(branch_bench, "index_median"),
                search_topics_median=bench_metric(branch_bench, "search_topics_median"),
                eval_file=str(branch_eval),
                bench_file=str(branch_bench),
            )
        )

    return rows


def run_gh(repo_root: Path, args: list[str]) -> list[dict]:
    try:
        result = subprocess.run(
            ["gh", *args],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise SystemExit(
            "gh is required to annotate README rows with experiment status and issue links."
        ) from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip()
        raise SystemExit(
            "Failed to query GitHub metadata with gh. "
            f"Command: {' '.join(['gh', *args])}. {stderr}"
        ) from exc
    return json.loads(result.stdout)


def issue_decision(issue: dict) -> str:
    texts = [issue.get("body", "")]
    texts.extend(comment.get("body", "") for comment in issue.get("comments", []))
    combined = "\n".join(texts).lower()
    if "accepted experiment result" in combined:
        return "accepted"
    if "rejection reason" in combined or "rejected experiment result" in combined:
        return "rejected"
    return "pending" if issue.get("state") == "OPEN" else "rejected"


def github_metadata(repo_root: Path) -> dict[str, GitHubMetadata]:
    issues = run_gh(
        repo_root,
        [
            "issue",
            "list",
            "--limit",
            "200",
            "--state",
            "all",
            "--json",
            "number,title,url,state,body,comments",
        ],
    )
    prs = run_gh(
        repo_root,
        [
            "pr",
            "list",
            "--limit",
            "200",
            "--state",
            "all",
            "--json",
            "number,url,headRefName,state,mergedAt,closingIssuesReferences",
        ],
    )

    metadata: dict[str, GitHubMetadata] = {}

    for issue in issues:
        branches: set[str] = set(BRANCH_RE.findall(issue.get("body", "")))
        for comment in issue.get("comments", []):
            branches.update(BRANCH_RE.findall(comment.get("body", "")))
        if not branches:
            continue

        decision = issue_decision(issue)
        for branch in branches:
            entry = metadata.setdefault(branch, GitHubMetadata())
            if not entry.issue_number:
                entry.issue_number = str(issue["number"])
                entry.issue_url = issue["url"]
            if entry.decision == "unknown" or decision == "accepted":
                entry.decision = decision

    for pr in prs:
        branch = pr.get("headRefName", "")
        if not branch:
            continue

        entry = metadata.setdefault(branch, GitHubMetadata())
        entry.pr_number = str(pr["number"])
        entry.pr_url = pr["url"]
        if pr.get("closingIssuesReferences"):
            issue_ref = pr["closingIssuesReferences"][0]
            entry.issue_number = str(issue_ref["number"])
            entry.issue_url = issue_ref["url"]

        if pr.get("mergedAt") or pr.get("state") == "MERGED":
            entry.decision = "accepted"
        elif pr.get("state") == "OPEN" and entry.decision == "unknown":
            entry.decision = "accepted"

    return metadata


def sort_rows(rows: list[BranchMetrics]) -> list[BranchMetrics]:
    return sorted(
        rows,
        key=lambda row: (0 if row.row_kind == "original" else 1, row.timestamp, row.branch),
    )


def write_rows(rows: list[BranchMetrics], metadata: dict[str, GitHubMetadata]) -> None:
    writer = csv.writer(sys.stdout, delimiter="\t", lineterminator="\n")
    writer.writerow(
        [
            "branch",
            "branch_label",
            "timestamp",
            "row_kind",
            "decision",
            "issue_number",
            "issue_url",
            "pr_number",
            "pr_url",
            "map",
            "map_delta_vs_previous",
            "index_median",
            "search_topics_median",
            "eval_file",
            "bench_file",
        ]
    )

    previous_map: float | None = None
    for row in sort_rows(rows):
        branch_metadata = metadata.get(row.branch, GitHubMetadata())
        if row.row_kind == "original":
            decision = "baseline"
            map_delta = 0.0
        else:
            decision = branch_metadata.decision
            if previous_map is None:
                map_delta = 0.0
            else:
                map_delta = row.map_value - previous_map
        previous_map = row.map_value

        writer.writerow(
            [
                row.branch,
                row.branch_label,
                row.timestamp,
                row.row_kind,
                decision,
                branch_metadata.issue_number,
                branch_metadata.issue_url,
                branch_metadata.pr_number,
                branch_metadata.pr_url,
                f"{row.map_value:.4f}",
                f"{map_delta:.4f}",
                row.index_median,
                row.search_topics_median,
                row.eval_file,
                row.bench_file,
            ]
        )


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    rows = collect_metrics(repo_root)
    metadata = github_metadata(repo_root)
    write_rows(rows, metadata)


if __name__ == "__main__":
    main()
