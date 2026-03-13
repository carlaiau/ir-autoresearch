#!/usr/bin/env python3

import argparse
import csv
import datetime as dt
from pathlib import Path
from typing import Dict, List


START_MARKER = "<!-- README_METRICS_TABLE_START -->"
END_MARKER = "<!-- README_METRICS_TABLE_END -->"


def load_rows(path: str) -> List[Dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def parse_timestamp(value: str) -> dt.datetime:
    return dt.datetime.strptime(value, "%Y%m%d-%H%M%S")


def sort_rows(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    return sorted(
        rows,
        key=lambda row: (0 if row["row_kind"] == "original" else 1, parse_timestamp(row["timestamp"]), row["branch"]),
    )


def display_timestamp(value: str) -> str:
    return parse_timestamp(value).strftime("%Y-%m-%d %H:%M")


def display_delta(value: str, is_original: bool) -> str:
    if is_original:
        return "baseline"
    number = float(value)
    rendered = f"{number:+.4f}"
    if number > 0:
        return f"**{rendered}**"
    return rendered


def display_issue(row: Dict[str, str]) -> str:
    issue_number = row.get("issue_number", "")
    issue_url = row.get("issue_url", "")
    if not issue_number or not issue_url:
        return "-"
    return f"[#{issue_number}]({issue_url})"


def display_branch(row: Dict[str, str]) -> str:
    branch = f"`{row['branch']}`"
    branch_url = row.get("branch_url", "")
    if branch_url:
        return f"[{branch}]({branch_url})"
    return branch


def display_metric(value: str) -> str:
    if not value:
        return "-"
    return f"{float(value):.4f}"


def format_change(current: float, baseline: float) -> str:
    delta = current - baseline
    if baseline == 0:
        return f"{delta:+.4f}"
    percent = (delta / baseline) * 100
    return f"{delta:+.4f} ({percent:+.1f}%)"


def format_speed_change(current: float, baseline: float) -> str:
    if baseline == 0:
        return ""
    percent = ((baseline - current) / baseline) * 100
    if percent > 0:
        return f"{percent:.1f}% faster"
    if percent < 0:
        return f"{abs(percent):.1f}% slower"
    return "unchanged"


def render_table(rows: List[Dict[str, str]]) -> str:
    lines = [
        "| Branch | Issue | MAP | MAP Δ | P@5 | P@20 | R-prec | bpref | recall | Index (s) | Search (s) |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in sort_rows(rows):
        is_original = row["row_kind"] == "original"
        lines.append(
            "| {branch} | {issue} | {map_value} | {map_delta} | {p_5} | {p_20} | {rprec} | {bpref} | {rel_ratio} | {index_median} | {search_topics_median} |".format(
                branch=display_branch(row),
                issue=display_issue(row),
                map_value=display_metric(row.get("map", "")),
                map_delta=display_delta(row["map_delta_vs_previous"], is_original),
                p_5=display_metric(row.get("p_5", "")),
                p_20=display_metric(row.get("p_20", "")),
                rprec=display_metric(row.get("rprec", "")),
                bpref=display_metric(row.get("bpref", "")),
                rel_ratio=display_metric(row.get("num_rel_ret_over_num_rel", "")),
                index_median=row["index_median"],
                search_topics_median=row["search_topics_median"],
            )
        )
    return "\n".join(lines)


def render_summary(rows: List[Dict[str, str]]) -> str:
    ordered = sort_rows(rows)
    baseline = ordered[0]
    if len(ordered) == 1:
        return "No accepted experiment branches have been recorded yet beyond the `original` baseline."

    latest = ordered[-1]
    baseline_map = float(baseline["map"])
    latest_map = float(latest["map"])
    baseline_p5 = float(baseline["p_5"])
    latest_p5 = float(latest["p_5"])
    baseline_search = float(baseline["search_topics_median"])
    latest_search = float(latest["search_topics_median"])
    baseline_index = float(baseline["index_median"])
    latest_index = float(latest["index_median"])

    index_change = format_speed_change(latest_index, baseline_index)
    index_clause = f"index median moved from `{baseline_index:.2f}s` to `{latest_index:.2f}s`"
    if index_change:
        index_clause += f" ({index_change})"

    return (
        f"Current accepted leader {display_branch(latest)} improves `MAP` from `{baseline_map:.4f}` on "
        f"to `{latest_map:.4f}` "
        f"(`{format_change(latest_map, baseline_map)}`). It also raises `P@5` from "
        f"`{baseline_p5:.4f}` to `{latest_p5:.4f}`."
    )


def render_legend() -> str:
    return "\n".join(
        [
            "**Legend**",
            "- `MAP`: Mean Average Precision. A single overall ranking-quality score across all queries; higher is better.",
            "- `P@5` and `P@20`: How many of the top 5 or top 20 results are relevant. Higher means better early precision.",
            "- `R-prec`: Precision after retrieving `R` results, where `R` is the number of relevant documents for that query. Higher is better.",
            "- `bpref`: A relevance metric that is more tolerant of incomplete judgment sets. Higher is better.",
            "- `recall` (`num_rel_ret / num_rel`): Fraction of all judged-relevant documents that were retrieved anywhere in the run. higher is better.",
            "- `Index (s)`: Median wall-clock indexing time in seconds across benchmark runs; lower is better.",
            "- `Search (s)`: Median wall-clock search time in seconds for the full topics file across benchmark runs; lower is better.",
        ]
    )


def render_dashboard(rows: List[Dict[str, str]]) -> str:
    return f"{render_summary(rows)}\n\n{render_table(rows)}\n\n{render_legend()}"


def write_output(path: str, content: str) -> None:
    Path(path).write_text(content + "\n", encoding="utf-8")


def refresh_readme(path: str, table: str) -> None:
    readme_path = Path(path)
    contents = readme_path.read_text(encoding="utf-8")
    start = contents.find(START_MARKER)
    end = contents.find(END_MARKER)
    if start == -1 or end == -1 or end < start:
        raise SystemExit("README metrics table markers were not found.")

    before = contents[: start + len(START_MARKER)]
    after = contents[end:]
    updated = f"{before}\n{table}\n{after}"
    readme_path.write_text(updated, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Render the README metrics table from the dashboard TSV.")
    parser.add_argument("--input", required=True, help="Path to the branch metrics TSV.")
    parser.add_argument("--output", help="Optional path to write the rendered Markdown table.")
    parser.add_argument("--readme", help="Optional README path to refresh between the metrics table markers.")
    args = parser.parse_args()

    rows = load_rows(args.input)
    table = render_dashboard(rows)

    if args.output:
        write_output(args.output, table)
    if args.readme:
        refresh_readme(args.readme, table)
    if not args.output and not args.readme:
        print(table)


if __name__ == "__main__":
    main()
