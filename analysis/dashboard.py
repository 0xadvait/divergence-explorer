"""
Rich terminal dashboard for exploring saved disagreement findings.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
from statistics import mean

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.config import FINDINGS_PATH
from src.models import Finding, load_findings

TOP_FINDINGS_LIMIT = 10


def _normalize_inline(text: str) -> str:
    return " ".join(text.split())


def _truncate(text: str, limit: int) -> str:
    normalized = _normalize_inline(text)
    if len(normalized) <= limit:
        return normalized
    if limit <= 3:
        return normalized[:limit]
    return normalized[: limit - 3].rstrip() + "..."


def _summary_panel(findings: list[Finding], findings_path: Path) -> Panel:
    total = len(findings)
    kept = sum(1 for finding in findings if finding.status == "keep")
    avg_score = mean(finding.score.overall for finding in findings) if findings else 0.0
    best = max(findings, key=lambda finding: finding.score.overall, default=None)

    grid = Table.grid(padding=(0, 2))
    grid.add_row("Findings file", str(findings_path))
    grid.add_row("Total findings", str(total))
    grid.add_row("Keep rate", f"{(kept / total):.1%}" if total else "0.0%")
    grid.add_row("Avg disagreement", f"{avg_score:.2f}")
    if best is not None:
        grid.add_row(
            "Top finding",
            f"{best.id} ({best.score.overall:.2f}) {_truncate(best.hypothesis.question, 70)}",
        )

    return Panel.fit(grid, title="Summary", border_style="cyan")


def _category_table(findings: list[Finding]) -> Table:
    stats: dict[str, list[Finding]] = defaultdict(list)
    for finding in findings:
        stats[finding.hypothesis.category].append(finding)

    table = Table(title="Category Breakdown", border_style="blue")
    table.add_column("Category", style="bold")
    table.add_column("Count", justify="right")
    table.add_column("Keep Rate", justify="right")
    table.add_column("Avg Score", justify="right")
    table.add_column("Best Score", justify="right")

    rows = sorted(
        stats.items(),
        key=lambda item: (
            -mean(finding.score.overall for finding in item[1]),
            -len(item[1]),
            item[0],
        ),
    )

    if not rows:
        table.add_row("n/a", "0", "0.0%", "0.00", "0.00")
        return table

    for category, category_findings in rows:
        kept = sum(1 for finding in category_findings if finding.status == "keep")
        avg_score = mean(finding.score.overall for finding in category_findings)
        best_score = max(finding.score.overall for finding in category_findings)
        table.add_row(
            category,
            str(len(category_findings)),
            f"{(kept / len(category_findings)):.1%}",
            f"{avg_score:.2f}",
            f"{best_score:.2f}",
        )
    return table


def _normalize_pair_key(pair_key: str) -> str:
    if ":" not in pair_key:
        return pair_key
    left, right = pair_key.split(":", 1)
    return ":".join(sorted((left, right)))


def _pairwise_table(findings: list[Finding]) -> Table:
    pair_scores: dict[str, list[float]] = defaultdict(list)
    for finding in findings:
        for pair_key, score in finding.score.pairwise.items():
            pair_scores[_normalize_pair_key(pair_key)].append(score)

    table = Table(title="Model Pair Analysis", border_style="blue")
    table.add_column("Model Pair", style="bold")
    table.add_column("Count", justify="right")
    table.add_column("Avg Score", justify="right")
    table.add_column("Best Score", justify="right")

    rows = sorted(
        pair_scores.items(),
        key=lambda item: (-mean(item[1]), -len(item[1]), item[0]),
    )

    if not rows:
        table.add_row("n/a", "0", "0.00", "0.00")
        return table

    for pair_key, scores in rows:
        table.add_row(
            pair_key,
            str(len(scores)),
            f"{mean(scores):.2f}",
            f"{max(scores):.2f}",
        )
    return table


def _axis_table(findings: list[Finding]) -> Table:
    axis_findings: dict[str, list[Finding]] = defaultdict(list)
    for finding in findings:
        axis = _normalize_inline(finding.score.axis or "unlabeled")
        axis_findings[axis].append(finding)

    table = Table(title="Axis Distribution", border_style="blue")
    table.add_column("Axis", style="bold")
    table.add_column("Count", justify="right")
    table.add_column("Keep Rate", justify="right")
    table.add_column("Avg Score", justify="right")

    rows = sorted(
        axis_findings.items(),
        key=lambda item: (-len(item[1]), -mean(finding.score.overall for finding in item[1]), item[0]),
    )

    if not rows:
        table.add_row("unlabeled", "0", "0.0%", "0.00")
        return table

    for axis, axis_group in rows:
        kept = sum(1 for finding in axis_group if finding.status == "keep")
        avg_score = mean(finding.score.overall for finding in axis_group)
        table.add_row(
            axis,
            str(len(axis_group)),
            f"{(kept / len(axis_group)):.1%}",
            f"{avg_score:.2f}",
        )
    return table


def _top_findings_table(findings: list[Finding], limit: int = TOP_FINDINGS_LIMIT) -> Table:
    ranked = sorted(
        findings,
        key=lambda finding: (finding.score.overall, finding.timestamp),
        reverse=True,
    )[:limit]

    table = Table(title=f"Top {limit} Findings", border_style="blue")
    table.add_column("#", justify="right")
    table.add_column("ID", style="bold")
    table.add_column("Score", justify="right")
    table.add_column("Status")
    table.add_column("Category")
    table.add_column("Axis")
    table.add_column("Question")

    if not ranked:
        table.add_row("1", "n/a", "0.00", "n/a", "n/a", "n/a", "No findings available.")
        return table

    for index, finding in enumerate(ranked, start=1):
        table.add_row(
            str(index),
            finding.id,
            f"{finding.score.overall:.2f}",
            finding.status,
            finding.hypothesis.category,
            _normalize_inline(finding.score.axis or "unlabeled"),
            _truncate(finding.hypothesis.question, 88),
        )
    return table


def build_dashboard(findings_path: Path) -> None:
    console = Console()
    findings = load_findings(findings_path)

    if not findings:
        console.print(
            Panel.fit(
                f"No findings found at {findings_path}. Run the explorer first.",
                title="Divergence Explorer",
                border_style="yellow",
            )
        )
        return

    console.print(_summary_panel(findings, findings_path))
    console.print(_category_table(findings))
    console.print(_pairwise_table(findings))
    console.print(_axis_table(findings))
    console.print(_top_findings_table(findings))


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect Divergence Explorer findings.")
    parser.add_argument(
        "--findings",
        type=Path,
        default=FINDINGS_PATH,
        help=f"Path to findings JSONL (default: {FINDINGS_PATH})",
    )
    args = parser.parse_args()
    build_dashboard(args.findings)


if __name__ == "__main__":
    main()
