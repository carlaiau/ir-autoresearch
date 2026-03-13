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


def render_table(rows: List[Dict[str, str]]) -> str:
    lines = [
        "| Branch | MAP | MAP Δ vs original | Index median | Search topics median | Updated |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in sort_rows(rows):
        is_original = row["row_kind"] == "original"
        lines.append(
            "| {branch} | {map_value} | {map_delta} | {index_median} | {search_topics_median} | {timestamp} |".format(
                branch=f"`{row['branch']}`",
                map_value=f"{float(row['map']):.4f}",
                map_delta=display_delta(row["map_delta_vs_original"], is_original),
                index_median=row["index_median"],
                search_topics_median=row["search_topics_median"],
                timestamp=display_timestamp(row["timestamp"]),
            )
        )
    return "\n".join(lines)


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
    table = render_table(rows)

    if args.output:
        write_output(args.output, table)
    if args.readme:
        refresh_readme(args.readme, table)
    if not args.output and not args.readme:
        print(table)


if __name__ == "__main__":
    main()
