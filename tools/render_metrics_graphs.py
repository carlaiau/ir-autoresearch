#!/usr/bin/env python3

import argparse
import csv
import datetime as dt
import html
from typing import Dict, List, Optional


WIDTH = 1080
MAP_HEIGHT = 420
BENCH_HEIGHT = 500


def load_rows(path: str) -> List[Dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def parse_timestamp(value: str) -> dt.datetime:
    return dt.datetime.strptime(value, "%Y%m%d-%H%M%S")


def parse_float(value: str) -> Optional[float]:
    if value == "":
        return None
    return float(value)


def branch_rows(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    kept = [row for row in rows if row["branch"] != "master" and row["branch"] != ""]
    return sorted(kept, key=lambda row: parse_timestamp(row["timestamp"]))


def nice_bounds(values: List[float], zero_floor: bool = False) -> List[float]:
    low = min(values)
    high = max(values)
    if zero_floor:
      low = min(low, 0.0)
      high = max(high, 0.0)
    if low == high:
        pad = max(abs(low) * 0.1, 0.01)
        return [low - pad, high + pad]
    pad = (high - low) * 0.15
    return [low - pad, high + pad]


def svg_header(width: int, height: int) -> List[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">',
        '<style>',
        'text { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; fill: #132238; }',
        '.title { font-size: 24px; font-weight: 700; }',
        '.subtitle { font-size: 13px; fill: #4b6075; }',
        '.axis { font-size: 12px; fill: #4b6075; }',
        '.label { font-size: 11px; fill: #31475d; }',
        '.value { font-size: 12px; font-weight: 600; }',
        '.grid { stroke: #dde5ec; stroke-width: 1; }',
        '.baseline { stroke: #94a3b8; stroke-width: 2; stroke-dasharray: 5 4; }',
        '.frame { fill: #f8fbfd; stroke: #d6e0e8; stroke-width: 1; rx: 14; }',
        '</style>',
    ]


def svg_footer() -> List[str]:
    return ["</svg>"]


def escape(value: str) -> str:
    return html.escape(value, quote=True)


def point_x(index: int, count: int, left: float, right: float) -> float:
    if count == 1:
        return (left + right) / 2
    return left + ((right - left) * index / (count - 1))


def point_y(value: float, low: float, high: float, top: float, bottom: float) -> float:
    if high == low:
        return (top + bottom) / 2
    return bottom - ((value - low) / (high - low)) * (bottom - top)


def draw_branch_labels(parts: List[str], rows: List[Dict[str, str]], left: float, right: float, y: float) -> None:
    for index, row in enumerate(rows):
        x = point_x(index, len(rows), left, right)
        label = row["branch_label"] or row["branch"]
        parts.append(
            f'<text x="{x:.2f}" y="{y:.2f}" transform="rotate(35 {x:.2f} {y:.2f})" text-anchor="start" class="label">{escape(label)}</text>'
        )


def draw_map_graph(rows: List[Dict[str, str]], output_path: str) -> None:
    parts = svg_header(WIDTH, MAP_HEIGHT)
    parts.append(f'<rect x="8" y="8" width="{WIDTH - 16}" height="{MAP_HEIGHT - 16}" class="frame"/>')
    parts.append('<text x="32" y="46" class="title">Branch MAP vs original</text>')
    parts.append('<text x="32" y="72" class="subtitle">Each point is the latest non-master branch artifact compared against the original baseline on master.</text>')

    if not rows:
        parts.append('<text x="32" y="170" class="subtitle">No non-original branch comparisons are available yet.</text>')
        parts.extend(svg_footer())
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(parts) + "\n")
        return

    left = 96
    right = WIDTH - 64
    top = 112
    bottom = MAP_HEIGHT - 110

    original_map = parse_float(rows[0]["original_map"])
    values = [parse_float(row["branch_map"]) for row in rows if parse_float(row["branch_map"]) is not None]
    if original_map is not None:
        values.append(original_map)
    low, high = nice_bounds(values)

    for tick in range(5):
        y_value = low + (high - low) * tick / 4
        y = point_y(y_value, low, high, top, bottom)
        parts.append(f'<line x1="{left}" y1="{y:.2f}" x2="{right}" y2="{y:.2f}" class="grid"/>')
        parts.append(f'<text x="{left - 14}" y="{y + 4:.2f}" text-anchor="end" class="axis">{y_value:.4f}</text>')

    if original_map is not None:
        baseline_y = point_y(original_map, low, high, top, bottom)
        parts.append(f'<line x1="{left}" y1="{baseline_y:.2f}" x2="{right}" y2="{baseline_y:.2f}" class="baseline"/>')
        parts.append(f'<text x="{right - 4}" y="{baseline_y - 8:.2f}" text-anchor="end" class="axis">original {original_map:.4f}</text>')

    coords = []
    for index, row in enumerate(rows):
        value = parse_float(row["branch_map"])
        if value is None:
            continue
        x = point_x(index, len(rows), left, right)
        y = point_y(value, low, high, top, bottom)
        coords.append((row, value, x, y))

    polyline = " ".join(f"{x:.2f},{y:.2f}" for _, _, x, y in coords)
    if polyline:
        parts.append(f'<polyline fill="none" stroke="#1d4ed8" stroke-width="3" points="{polyline}"/>')

    for row, value, x, y in coords:
        delta = parse_float(row["map_delta"])
        fill = "#15803d" if delta is not None and delta >= 0 else "#b91c1c"
        parts.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="5" fill="{fill}"/>')

    last_row, last_value, last_x, last_y = coords[-1]
    last_delta = parse_float(last_row["map_delta"])
    delta_text = f"{last_delta:+.4f}" if last_delta is not None else "n/a"
    parts.append(f'<text x="{last_x + 10:.2f}" y="{last_y - 8:.2f}" class="value">{last_value:.4f} ({delta_text})</text>')
    parts.append(f'<text x="{last_x + 10:.2f}" y="{last_y + 12:.2f}" class="axis">{escape(last_row["branch_label"])}</text>')

    draw_branch_labels(parts, rows, left, right, bottom + 28)

    parts.extend(svg_footer())
    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(parts) + "\n")


def draw_benchmark_graph(rows: List[Dict[str, str]], output_path: str) -> None:
    parts = svg_header(WIDTH, BENCH_HEIGHT)
    parts.append(f'<rect x="8" y="8" width="{WIDTH - 16}" height="{BENCH_HEIGHT - 16}" class="frame"/>')
    parts.append('<text x="32" y="46" class="title">Branch benchmark change vs original</text>')
    parts.append('<text x="32" y="72" class="subtitle">Index and search timings are shown as percent change relative to the original baseline on master.</text>')

    legend_y = 98
    legends = [
        ("#0f766e", "Index median change (%)"),
        ("#c2410c", "Search topics median change (%)"),
    ]
    for offset, (color, label) in enumerate(legends):
        x = 32 + offset * 280
        parts.append(f'<line x1="{x}" y1="{legend_y}" x2="{x + 18}" y2="{legend_y}" stroke="{color}" stroke-width="3"/>')
        parts.append(f'<text x="{x + 24}" y="{legend_y + 4}" class="axis">{escape(label)}</text>')

    if not rows:
        parts.append('<text x="32" y="180" class="subtitle">No non-original branch comparisons are available yet.</text>')
        parts.extend(svg_footer())
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(parts) + "\n")
        return

    left = 96
    right = WIDTH - 64
    top = 132
    bottom = BENCH_HEIGHT - 130

    values = []
    for row in rows:
        for key in ["index_change_pct", "search_topics_change_pct"]:
            value = parse_float(row[key])
            if value is not None:
                values.append(value)
    low, high = nice_bounds(values, zero_floor=True)

    for tick in range(5):
        y_value = low + (high - low) * tick / 4
        y = point_y(y_value, low, high, top, bottom)
        parts.append(f'<line x1="{left}" y1="{y:.2f}" x2="{right}" y2="{y:.2f}" class="grid"/>')
        parts.append(f'<text x="{left - 14}" y="{y + 4:.2f}" text-anchor="end" class="axis">{y_value:.1f}%</text>')

    zero_y = point_y(0.0, low, high, top, bottom)
    parts.append(f'<line x1="{left}" y1="{zero_y:.2f}" x2="{right}" y2="{zero_y:.2f}" class="baseline"/>')
    parts.append(f'<text x="{right - 4}" y="{zero_y - 8:.2f}" text-anchor="end" class="axis">original 0.0%</text>')

    series = [
        ("index_change_pct", "#0f766e"),
        ("search_topics_change_pct", "#c2410c"),
    ]
    for key, color in series:
        coords = []
        for index, row in enumerate(rows):
            value = parse_float(row[key])
            if value is None:
                continue
            x = point_x(index, len(rows), left, right)
            y = point_y(value, low, high, top, bottom)
            coords.append((row, value, x, y))

        polyline = " ".join(f"{x:.2f},{y:.2f}" for _, _, x, y in coords)
        if polyline:
            parts.append(f'<polyline fill="none" stroke="{color}" stroke-width="3" points="{polyline}"/>')
        for _, _, x, y in coords:
            parts.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="5" fill="{color}"/>')

    last_row = rows[-1]
    last_x = point_x(len(rows) - 1, len(rows), left, right)
    index_value = parse_float(last_row["index_change_pct"])
    search_value = parse_float(last_row["search_topics_change_pct"])
    if index_value is not None:
        parts.append(f'<text x="{last_x + 10:.2f}" y="{point_y(index_value, low, high, top, bottom) - 8:.2f}" class="value">index {index_value:+.1f}%</text>')
    if search_value is not None:
        parts.append(f'<text x="{last_x + 10:.2f}" y="{point_y(search_value, low, high, top, bottom) + 14:.2f}" class="value">search {search_value:+.1f}%</text>')

    draw_branch_labels(parts, rows, left, right, bottom + 28)

    parts.extend(svg_footer())
    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(parts) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Render SVG graphs from the branch comparison TSV.")
    parser.add_argument("--input", required=True, help="Path to the branch comparison TSV.")
    parser.add_argument("--map-output", required=True, help="Path to the MAP comparison SVG.")
    parser.add_argument("--bench-output", required=True, help="Path to the benchmark comparison SVG.")
    args = parser.parse_args()

    rows = branch_rows(load_rows(args.input))
    draw_map_graph(rows, args.map_output)
    draw_benchmark_graph(rows, args.bench_output)


if __name__ == "__main__":
    main()
