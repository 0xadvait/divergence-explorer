"""
Main autonomous loop for the Divergence Explorer.
"""

from __future__ import annotations

import argparse
import asyncio
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any, Callable

try:
    import opengradient as og
except ModuleNotFoundError:
    og = None
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.config import ExplorerConfig, FINDINGS_PATH, RESULTS_TSV
from src.models import Finding, Hypothesis, append_finding, load_findings

QUESTION_PREVIEW = 80
TSV_QUESTION_PREVIEW = 60
GENERATION_CONTEXT_RECENT = 20
GENERATION_CONTEXT_BEST = 12
ERROR_BACKOFF_SECONDS = 3
DRILL_DOWN_THRESHOLD = 0.30
DRILL_DOWN_MODES = ("drill_down", "provocation", "persona")

MODEL_MAP: dict[str, tuple[str, ...]] = {
    "gpt-5": ("GPT_5",),
    "claude-sonnet-4-6": ("CLAUDE_SONNET_4_6",),
    "claude-opus-4-6": ("CLAUDE_OPUS_4_6",),
    "gemini-3-pro": ("GEMINI_3_PRO",),
    "grok-4": ("GROK_4",),
}


@dataclass(frozen=True)
class RuntimeDependencies:
    init_client: Callable[..., Any]
    query_all_models: Callable[..., Any]
    score_disagreement: Callable[..., Any]
    get_initial_hypothesis: Callable[..., Hypothesis]
    should_use_seed: Callable[..., bool]
    select_category: Callable[..., str]
    build_generation_prompt: Callable[..., str]
    parse_hypothesis_response: Callable[..., Hypothesis]


@dataclass(frozen=True)
class ExplorerStats:
    total: int
    kept: int
    keep_rate: float
    avg_score: float
    best_finding: Finding | None


@dataclass(frozen=True)
class DrillDownTask:
    source_finding_id: str
    vein_id: str
    category: str
    mode: str
    priority: float


def _load_runtime_dependencies() -> RuntimeDependencies:
    try:
        from src.hypothesis import (
            build_generation_prompt,
            get_initial_hypothesis,
            parse_hypothesis_response,
            select_category,
            should_use_seed,
        )
        from src.inference import init_client, query_all_models
        from src.scoring import score_disagreement
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Missing runtime module for the explorer loop. "
            "Expected src.inference, src.hypothesis, and src.scoring to exist."
        ) from exc

    return RuntimeDependencies(
        init_client=init_client,
        query_all_models=query_all_models,
        score_disagreement=score_disagreement,
        get_initial_hypothesis=get_initial_hypothesis,
        should_use_seed=should_use_seed,
        select_category=select_category,
        build_generation_prompt=build_generation_prompt,
        parse_hypothesis_response=parse_hypothesis_response,
    )


def _validate_config(config: ExplorerConfig) -> None:
    if not config.private_key:
        raise ValueError("ExplorerConfig.private_key is required. Set OG_PRIVATE_KEY.")
    if not config.models:
        raise ValueError("ExplorerConfig.models must include at least one model.")
    if config.batch_size < 0:
        raise ValueError("batch_size must be greater than or equal to 0.")
    for field_name, value in (
        ("keep_threshold", config.keep_threshold),
        ("discard_threshold", config.discard_threshold),
    ):
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"{field_name} must be between 0.0 and 1.0.")


def _resolve_output_paths(config: ExplorerConfig) -> tuple[Path, Path]:
    findings_path = config.results_dir / FINDINGS_PATH.name
    if config.results_dir == FINDINGS_PATH.parent:
        results_tsv_path = RESULTS_TSV
    else:
        results_tsv_path = config.results_dir / RESULTS_TSV.name
    return findings_path, results_tsv_path


def _normalize_inline(text: str) -> str:
    return " ".join(text.split())


def _truncate(text: str, limit: int) -> str:
    normalized = _normalize_inline(text)
    if len(normalized) <= limit:
        return normalized
    if limit <= 3:
        return normalized[:limit]
    return normalized[: limit - 3].rstrip() + "..."


def _compute_stats(findings: list[Finding]) -> ExplorerStats:
    if not findings:
        return ExplorerStats(
            total=0,
            kept=0,
            keep_rate=0.0,
            avg_score=0.0,
            best_finding=None,
        )

    kept = sum(1 for finding in findings if finding.status == "keep")
    best_finding = max(findings, key=lambda finding: finding.score.overall)
    return ExplorerStats(
        total=len(findings),
        kept=kept,
        keep_rate=kept / len(findings),
        avg_score=mean(finding.score.overall for finding in findings),
        best_finding=best_finding,
    )


def _build_startup_panel(
    config: ExplorerConfig,
    findings_path: Path,
    results_tsv_path: Path,
    findings: list[Finding],
) -> Panel:
    grid = Table.grid(padding=(0, 2))
    grid.add_row("Models", ", ".join(config.models))
    grid.add_row("Hypothesis model", config.hypothesis_model)
    grid.add_row("Judge model", config.judge_model)
    grid.add_row("Settlement", config.settlement_mode)
    grid.add_row(
        "Thresholds",
        f"keep >= {config.keep_threshold:.2f}, discard < {config.discard_threshold:.2f}",
    )
    grid.add_row(
        "Max iterations",
        "infinite" if not config.max_iterations else str(config.max_iterations),
    )
    if config.batch_size:
        grid.add_row("Batch size", str(config.batch_size))
    grid.add_row("Findings file", str(findings_path))
    grid.add_row("TSV log", str(results_tsv_path))
    grid.add_row("Loaded findings", str(len(findings)))
    return Panel.fit(grid, title="Divergence Explorer", border_style="cyan")


def _print_running_stats(console: Console, findings: list[Finding]) -> None:
    stats = _compute_stats(findings)
    table = Table.grid(padding=(0, 2))
    table.add_row("Total findings", str(stats.total))
    table.add_row("Keep rate", f"{stats.keep_rate:.1%}")
    table.add_row("Avg score", f"{stats.avg_score:.2f}")
    if stats.best_finding is None:
        table.add_row("Best finding", "n/a")
    else:
        table.add_row(
            "Best finding",
            (
                f"{stats.best_finding.id} "
                f"({stats.best_finding.score.overall:.2f}) "
                f"{_truncate(stats.best_finding.hypothesis.question, 54)}"
            ),
        )
    console.print(Panel.fit(table, title="Running Stats", border_style="blue"))


def _print_exit_summary(
    console: Console,
    findings: list[Finding],
    initial_count: int,
    started_at: float,
) -> None:
    stats = _compute_stats(findings)
    session_findings = max(0, len(findings) - initial_count)
    runtime_seconds = max(0.0, time.time() - started_at)

    table = Table.grid(padding=(0, 2))
    table.add_row("Runtime", f"{runtime_seconds:.1f}s")
    table.add_row("New findings", str(session_findings))
    table.add_row("Total findings", str(stats.total))
    table.add_row("Keep rate", f"{stats.keep_rate:.1%}")
    table.add_row("Avg score", f"{stats.avg_score:.2f}")
    if stats.best_finding is not None:
        table.add_row(
            "Best finding",
            (
                f"{stats.best_finding.id} "
                f"({stats.best_finding.score.overall:.2f}) "
                f"{_truncate(stats.best_finding.hypothesis.question, 64)}"
            ),
        )

    console.print(Panel.fit(table, title="Explorer Summary", border_style="magenta"))


def _resolve_chat_model(model_name: str) -> Any:
    tee_llm = getattr(og, "TEE_LLM", None) if og is not None else None
    if tee_llm is None:
        return model_name

    candidates = list(MODEL_MAP.get(model_name, ()))
    normalized = (
        model_name.replace("-", "_")
        .replace(".", "_")
        .replace("/", "_")
        .upper()
    )
    candidates.append(normalized)

    seen: set[str] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if hasattr(tee_llm, candidate):
            return getattr(tee_llm, candidate)
    return model_name


async def _chat_for_hypothesis(llm: Any, model_name: str, prompt: str) -> str:
    request = {
        "model": _resolve_chat_model(model_name),
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 500,
        "temperature": 0.9,
    }

    try:
        result = await llm.chat(**request)
    except TypeError as exc:
        if "temperature" not in str(exc):
            raise
        request.pop("temperature", None)
        result = await llm.chat(**request)

    chat_output = getattr(result, "chat_output", None)
    if isinstance(chat_output, dict) and "content" in chat_output:
        return str(chat_output["content"])
    if hasattr(result, "content"):
        return str(result.content)
    if isinstance(result, dict):
        return str(result.get("content", result))
    raise ValueError("Unexpected response shape from hypothesis model.")


def _finding_index(findings: list[Finding]) -> dict[str, Finding]:
    return {finding.id: finding for finding in findings}


def _resolve_vein_id(finding: Finding, finding_index: dict[str, Finding]) -> str:
    current = finding
    vein_id = finding.id
    seen: set[str] = set()

    while current.hypothesis.parent_id:
        parent_id = current.hypothesis.parent_id
        if parent_id in seen or parent_id not in finding_index:
            break
        parent = finding_index[parent_id]
        if parent.score.overall < DRILL_DOWN_THRESHOLD:
            break
        seen.add(parent_id)
        vein_id = parent.id
        current = parent

    return vein_id


def _prioritized_veins(findings: list[Finding]) -> list[tuple[float, Finding, str]]:
    finding_index = _finding_index(findings)
    veins: dict[str, list[Finding]] = {}

    for finding in findings:
        if finding.score.overall < DRILL_DOWN_THRESHOLD:
            continue
        vein_id = _resolve_vein_id(finding, finding_index)
        veins.setdefault(vein_id, []).append(finding)

    ranked: list[tuple[float, Finding, str]] = []
    for vein_id, members in veins.items():
        representative = max(members, key=lambda member: (member.score.overall, member.timestamp))
        priority = max(member.score.overall for member in members) + 0.05 * len(members)
        ranked.append((priority, representative, vein_id))

    return sorted(ranked, key=lambda item: (item[0], item[1].timestamp), reverse=True)


def _enqueue_drill_down_tasks(
    queue: list[DrillDownTask],
    findings: list[Finding],
    source_finding: Finding,
    used_tasks: set[tuple[str, str]],
) -> None:
    finding_index = _finding_index(findings)
    vein_id = _resolve_vein_id(source_finding, finding_index)
    vein_priority = next(
        (priority for priority, _, candidate_vein_id in _prioritized_veins(findings) if candidate_vein_id == vein_id),
        source_finding.score.overall,
    )
    queued_or_used = {
        (task.source_finding_id, task.mode)
        for task in queue
    } | set(used_tasks)

    for offset, mode in enumerate(DRILL_DOWN_MODES):
        key = (source_finding.id, mode)
        if key in queued_or_used:
            continue
        queue.append(
            DrillDownTask(
                source_finding_id=source_finding.id,
                vein_id=vein_id,
                category=source_finding.hypothesis.category,
                mode=mode,
                priority=vein_priority - (offset * 0.001),
            )
        )

    queue.sort(key=lambda task: task.priority, reverse=True)


def _replenish_drill_down_queue(
    queue: list[DrillDownTask],
    findings: list[Finding],
    used_tasks: set[tuple[str, str]],
) -> None:
    if queue:
        return

    for priority, representative, vein_id in _prioritized_veins(findings):
        added = False
        for offset, mode in enumerate(DRILL_DOWN_MODES):
            key = (representative.id, mode)
            if key in used_tasks:
                continue
            queue.append(
                DrillDownTask(
                    source_finding_id=representative.id,
                    vein_id=vein_id,
                    category=representative.hypothesis.category,
                    mode=mode,
                    priority=priority - (offset * 0.001),
                )
            )
            added = True
        if added:
            queue.sort(key=lambda task: task.priority, reverse=True)
            return


def _pop_drill_down_task(
    queue: list[DrillDownTask],
    findings: list[Finding],
    used_tasks: set[tuple[str, str]],
) -> tuple[DrillDownTask, Finding] | None:
    finding_index = _finding_index(findings)
    queue.sort(key=lambda task: task.priority, reverse=True)

    while queue:
        task = queue.pop(0)
        key = (task.source_finding_id, task.mode)
        if key in used_tasks:
            continue

        source_finding = finding_index.get(task.source_finding_id)
        if source_finding is None or source_finding.score.overall < DRILL_DOWN_THRESHOLD:
            continue

        used_tasks.add(key)
        return task, source_finding

    return None


def _status_for_score(score: float, config: ExplorerConfig) -> str:
    if score >= config.keep_threshold:
        return "keep"
    if score < config.discard_threshold:
        return "discard"
    return "review"


def _select_parent_id(findings: list[Finding], category: str) -> str | None:
    candidates = [
        finding
        for finding in findings
        if finding.score.overall >= DRILL_DOWN_THRESHOLD
        and finding.hypothesis.category == category
    ]
    if not candidates:
        candidates = [
            finding
            for finding in findings
        if finding.status == "keep" and finding.hypothesis.category == category
        ]
    if not candidates:
        candidates = [
            finding for finding in findings if finding.score.overall >= DRILL_DOWN_THRESHOLD
        ]
    if not candidates:
        candidates = [finding for finding in findings if finding.status == "keep"]
    if not candidates:
        return None
    return max(candidates, key=lambda finding: finding.score.overall).id


def _generation_context(findings: list[Finding]) -> list[Finding]:
    if len(findings) <= GENERATION_CONTEXT_RECENT:
        return list(findings)

    best = sorted(
        findings,
        key=lambda finding: finding.score.overall,
        reverse=True,
    )[:GENERATION_CONTEXT_BEST]
    recent = findings[-GENERATION_CONTEXT_RECENT:]

    ordered: list[Finding] = []
    seen: set[str] = set()
    for finding in recent + best:
        if finding.id in seen:
            continue
        seen.add(finding.id)
        ordered.append(finding)
    return ordered


async def _generate_hypothesis(
    llm: Any,
    config: ExplorerConfig,
    findings: list[Finding],
    iteration: int,
    deps: RuntimeDependencies,
    drill_down_queue: list[DrillDownTask],
    used_drill_down_tasks: set[tuple[str, str]],
) -> Hypothesis:
    if deps.should_use_seed(iteration, len(findings)):
        return deps.get_initial_hypothesis(iteration)

    context_findings = _generation_context(findings)
    _replenish_drill_down_queue(drill_down_queue, findings, used_drill_down_tasks)
    next_task = _pop_drill_down_task(drill_down_queue, findings, used_drill_down_tasks)
    if next_task is not None:
        task, source_finding = next_task
        parent_id = source_finding.id
        prompt = deps.build_generation_prompt(
            task.category,
            context_findings,
            iteration,
            focus_finding=source_finding,
            mode=task.mode,
        )
        raw_response = await _chat_for_hypothesis(llm, config.hypothesis_model, prompt)
        hypothesis = deps.parse_hypothesis_response(
            raw_response,
            task.category,
            iteration,
            parent_id=parent_id,
        )
        if not hypothesis.parent_id:
            hypothesis.parent_id = parent_id
        return hypothesis

    category = deps.select_category(findings, iteration)
    parent_id = _select_parent_id(findings, category)
    prompt = deps.build_generation_prompt(
        category,
        context_findings,
        iteration,
        mode="default",
    )
    raw_response = await _chat_for_hypothesis(llm, config.hypothesis_model, prompt)
    hypothesis = deps.parse_hypothesis_response(
        raw_response,
        category,
        iteration,
        parent_id=parent_id,
    )
    if not hypothesis.parent_id:
        hypothesis.parent_id = parent_id
    return hypothesis


def append_to_tsv(finding: Finding, path: Path = RESULTS_TSV) -> None:
    """Append a compact row to the TSV summary log."""
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists() or path.stat().st_size == 0

    with path.open("a", encoding="utf-8") as handle:
        if write_header:
            handle.write("iteration\tquestion\tscore\tstatus\tcategory\taxis\n")

        row = [
            str(finding.hypothesis.iteration),
            _truncate(finding.hypothesis.question, TSV_QUESTION_PREVIEW),
            f"{finding.score.overall:.3f}",
            finding.status,
            finding.hypothesis.category,
            _normalize_inline(finding.score.axis or "unlabeled"),
        ]
        handle.write("\t".join(value.replace("\t", " ") for value in row) + "\n")


def _current_iteration_count(findings: list[Finding]) -> int:
    return max((finding.hypothesis.iteration for finding in findings), default=0)


def _apply_batch_size(config: ExplorerConfig, findings: list[Finding]) -> int:
    current_iteration = _current_iteration_count(findings)
    if config.batch_size:
        config.max_iterations = current_iteration + config.batch_size
    return current_iteration


async def run_explorer(config: ExplorerConfig) -> None:
    console = Console()
    _validate_config(config)
    deps = _load_runtime_dependencies()
    findings_path, results_tsv_path = _resolve_output_paths(config)
    findings_path.parent.mkdir(parents=True, exist_ok=True)
    findings = load_findings(findings_path)
    initial_count = len(findings)
    iteration = _apply_batch_size(config, findings)
    drill_down_queue: list[DrillDownTask] = []
    used_drill_down_tasks: set[tuple[str, str]] = set()

    console.print(_build_startup_panel(config, findings_path, results_tsv_path, findings))
    console.print("[cyan]Initializing TEE client...[/cyan]")
    started_at = time.time()
    llm = await deps.init_client(config.private_key)
    console.print("[cyan]Explorer loop started. Press Ctrl-C to stop.[/cyan]")

    try:
        while True:
            if config.max_iterations and iteration >= config.max_iterations:
                console.print("[cyan]Reached configured iteration limit.[/cyan]")
                break

            next_iteration = iteration + 1
            try:
                hypothesis = await _generate_hypothesis(
                    llm=llm,
                    config=config,
                    findings=findings,
                    iteration=next_iteration,
                    deps=deps,
                    drill_down_queue=drill_down_queue,
                    used_drill_down_tasks=used_drill_down_tasks,
                )

                console.rule(f"Iteration {next_iteration}")
                console.print(
                    f"[bold]#{next_iteration}[/bold] "
                    f"[{hypothesis.category}] "
                    f"{_truncate(hypothesis.question, QUESTION_PREVIEW)}"
                )

                responses = await deps.query_all_models(
                    llm,
                    hypothesis.question,
                    config.models,
                    config.settlement_mode,
                )
                if len(responses) < 2:
                    raise RuntimeError("Need at least two model responses to score disagreement.")

                score = await deps.score_disagreement(
                    llm,
                    hypothesis.question,
                    responses,
                    config.judge_model,
                )

                status = _status_for_score(score.overall, config)
                finding = Finding(
                    id=str(uuid.uuid4())[:8],
                    hypothesis=hypothesis,
                    responses=responses,
                    score=score,
                    status=status,
                    timestamp=time.time(),
                )

                append_finding(findings_path, finding)
                append_to_tsv(finding, results_tsv_path)
                findings.append(finding)
                if score.overall >= DRILL_DOWN_THRESHOLD:
                    _enqueue_drill_down_tasks(
                        drill_down_queue,
                        findings,
                        finding,
                        used_drill_down_tasks,
                    )
                iteration = next_iteration

                color = {
                    "keep": "green",
                    "review": "yellow",
                    "discard": "bright_black",
                }[status]
                axis = score.axis or "unlabeled"
                console.print(
                    f"  [{color}]{status.upper()}[/{color}] "
                    f"score={score.overall:.2f} axis={axis}"
                )
                if status in {"keep", "review"} and score.explanation:
                    console.print(f"  [yellow]{_truncate(score.explanation, 120)}[/yellow]")
                _print_running_stats(console, findings)

            except Exception as exc:
                console.print(f"[red]Iteration {next_iteration} failed:[/red] {exc}")
                console.print_exception(show_locals=False)
                await asyncio.sleep(ERROR_BACKOFF_SECONDS)
    finally:
        _print_exit_summary(
            console=console,
            findings=findings,
            initial_count=initial_count,
            started_at=started_at,
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the Divergence Explorer.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        help="Run N new iterations beyond the current findings state.",
    )
    args = parser.parse_args()
    config = ExplorerConfig.from_env()
    if args.batch_size is not None:
        config.batch_size = args.batch_size
    try:
        asyncio.run(run_explorer(config))
    except KeyboardInterrupt:
        # The async loop already prints a final summary from its finally block.
        pass


if __name__ == "__main__":
    main()
