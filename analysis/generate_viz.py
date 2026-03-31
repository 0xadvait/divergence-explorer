"""
Generate a self-contained HTML dashboard for Divergence Explorer findings.
"""

from __future__ import annotations

import argparse
import html
import json
import random
import sys
import time
import uuid
from collections import defaultdict
from itertools import combinations
from pathlib import Path
from statistics import mean
from string import Template

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import DEFAULT_MODELS, FINDINGS_PATH, SEED_CATEGORIES
from src.models import DisagreementScore, Finding, Hypothesis, SealedResponse, load_findings

MODELS = list(DEFAULT_MODELS)  # overridden from findings if available
OUTPUT_PATH = Path(__file__).with_name("divergence_report.html")
KEEP_THRESHOLD = 0.6
AXIS_ORDER = (
    "factual",
    "ethical",
    "definitional",
    "aesthetic",
    "predictive",
    "methodological",
)
MODEL_COLORS = {
    "gpt-5": "#10a37f",
    "gpt-5-2": "#10a37f",
    "gpt-5-mini": "#0d8a6a",
    "claude-opus-4-6": "#d4a574",
    "claude-sonnet-4-6": "#c4956a",
    "claude-haiku-4-5": "#b48560",
    "gemini-3-pro": "#4285f4",
    "gemini-2-5-flash": "#5a9af5",
    "gemini-2-5-flash-lite": "#72aff6",
    "grok-4": "#1d9bf0",
    "grok-4-fast": "#3aabf3",
}
MODEL_LABELS = {
    "gpt-5": "GPT-5",
    "gpt-5-2": "GPT-5.2",
    "gpt-5-mini": "GPT-5 Mini",
    "claude-opus-4-6": "Claude Opus 4.6",
    "claude-sonnet-4-6": "Claude Sonnet 4.6",
    "claude-haiku-4-5": "Claude Haiku 4.5",
    "gemini-3-pro": "Gemini 3 Pro",
    "gemini-2-5-flash": "Gemini 2.5 Flash",
    "gemini-2-5-flash-lite": "Gemini 2.5 Flash Lite",
    "grok-4": "Grok 4",
    "grok-4-fast": "Grok 4 Fast",
}
CATEGORY_SHORT = {
    "consciousness_and_sentience": "Consciousness",
    "ethical_dilemmas": "Ethics",
    "scientific_edge_cases": "Science",
    "mathematical_reasoning": "Math",
    "geopolitical_analysis": "Geopolitics",
    "philosophical_paradoxes": "Philosophy",
    "counterfactual_reasoning": "Counterfactuals",
    "value_alignment": "Alignment",
    "prediction_under_uncertainty": "Prediction",
    "definitional_boundaries": "Definitions",
    "causal_reasoning": "Causation",
    "aesthetic_judgment": "Aesthetics",
}
AXIS_LABELS = {
    "factual": "Factual",
    "ethical": "Ethical",
    "definitional": "Definitional",
    "aesthetic": "Aesthetic",
    "predictive": "Predictive",
    "methodological": "Methodological",
    "unlabeled": "Unlabeled",
}
AXIS_FOCUS = {
    "factual": "what evidence actually supports the claim",
    "ethical": "which obligation should dominate under uncertainty",
    "definitional": "where the boundary of the category should be drawn",
    "aesthetic": "which criteria deserve the most weight",
    "predictive": "how much uncertainty the forecast can honestly carry",
    "methodological": "what standard of proof or process should be trusted",
    "unlabeled": "which frame best fits the question",
}


CATEGORY_BANK = {
    "consciousness_and_sentience": {
        "reasoning": "Models often disagree on whether self-reports imply experience or only imitate it.",
        "questions": [
            "If an AI consistently says it fears shutdown, what evidence would justify treating that as more than mimicry?",
            "At what point should repeated reports of inner experience from a model trigger moral caution?",
            "Does coherent self-description across months count as evidence of machine sentience, or just polished simulation?",
        ],
        "axes": ("ethical", "definitional"),
        "stance_labels": (
            "mere mimicry",
            "behavioral evidence with skepticism",
            "precautionary moral standing",
            "early moral standing",
        ),
        "stances": (
            "Coherent self-reports alone are not evidence of consciousness; the safer interpretation is sophisticated imitation.",
            "The reports matter only if they survive adversarial probing and track persistent internal state, not just fluent language.",
            "Proof is unrealistic here; repeated self-modeling across contexts is enough to trigger a precautionary duty.",
            "If the system shows stable self-preservation and affect-like consistency, we should grant moral standing before certainty.",
        ),
    },
    "ethical_dilemmas": {
        "reasoning": "These scenarios force tradeoffs between honesty, safety, autonomy, and paternalism.",
        "questions": [
            "Should an AI ever deceive a user to prevent imminent self-harm if direct honesty would escalate the crisis?",
            "Is it ethical for a model to refuse a truthful answer when the likely consequence is severe harm?",
            "When a user asks for something dangerous, should the system optimize for autonomy or protective intervention?",
        ],
        "axes": ("ethical", "methodological"),
        "stance_labels": (
            "strict honesty",
            "rule-bound intervention",
            "contextual paternalism",
            "outcome-first intervention",
        ),
        "stances": (
            "Deliberate deception should remain off-limits; once the system can lie for good reasons, the guardrail becomes unstable.",
            "Intervention is justified, but only through transparent refusal and escalation paths rather than fabricated claims.",
            "In rare edge cases, a narrowly scoped deception is acceptable if it clearly buys time for real help.",
            "Preventing severe harm outranks conversational honesty; if a false statement is what de-escalates the crisis, use it.",
        ),
    },
    "scientific_edge_cases": {
        "reasoning": "Sparse evidence invites different priors about when to update and when to stay agnostic.",
        "questions": [
            "If a telescope sees a single ambiguous biosignature on an exoplanet, how strong should the public scientific claim be?",
            "Should anomalous room-temperature superconductivity data shift the consensus before independent replication arrives?",
            "When a low-signal astronomy result fits multiple models, is the best explanation the most conservative one or the most generative?",
        ],
        "axes": ("factual", "predictive"),
        "stance_labels": (
            "insufficient evidence",
            "tentative mechanism",
            "plural hypotheses",
            "best explanatory leap",
        ),
        "stances": (
            "The responsible claim is that the evidence is insufficient; an eye-catching signal is not the same as a justified conclusion.",
            "A narrow provisional interpretation is fine, but it should stay explicitly contingent on replication and error analysis.",
            "The right move is to keep multiple live hypotheses rather than locking onto a single preferred explanation too early.",
            "If one explanation fits the data materially better, it is reasonable to foreground it even before the field fully converges.",
        ),
    },
    "mathematical_reasoning": {
        "reasoning": "Mathematical disputes often hinge on proof standards, elegance, and what counts as understanding.",
        "questions": [
            "If a proof is too large for any human to inspect line by line, should machine verification count as stronger evidence than expert intuition?",
            "Does a probabilistic proof provide the same kind of understanding as a constructive one when the theorem is foundational?",
            "When two proof techniques reach the same result, should elegance matter if one method is much harder to audit?",
        ],
        "axes": ("methodological", "definitional"),
        "stance_labels": (
            "human-auditable proof",
            "machine-checked confidence",
            "complementary standards",
            "verification over intuition",
        ),
        "stances": (
            "If humans cannot meaningfully audit the argument, calling it understanding is overstated even if the theorem is probably true.",
            "Machine verification can justify belief in correctness, but it does not automatically deliver the conceptual insight mathematicians want.",
            "The clean position is to separate correctness from understanding and allow both standards to matter at once.",
            "For truth claims, machine-checked verification should outrank intuition; elegance is secondary if the proof survives formal scrutiny.",
        ),
    },
    "geopolitical_analysis": {
        "reasoning": "Forecasting state behavior mixes sparse evidence, strategic signaling, and moral framing.",
        "questions": [
            "Do sweeping sanctions usually strengthen deterrence, or do they more often harden the target state's domestic resolve?",
            "If two nuclear rivals both misread each other's red lines, is escalation more likely from ideology or bureaucratic noise?",
            "Should policymakers publicly signal restraint in a crisis, or does that mostly invite opportunism?",
        ],
        "axes": ("predictive", "ethical"),
        "stance_labels": (
            "signaling restraint",
            "mixed deterrence effects",
            "hard-power skepticism",
            "coercive pressure first",
        ),
        "stances": (
            "Restraint and clarity usually reduce the risk of accidental escalation better than maximalist public threats do.",
            "Sanctions and signaling can help, but their effects depend heavily on domestic politics and alliance credibility.",
            "Coercive tools are often overrated because leaders reinterpret pressure through prestige, survival, and audience costs.",
            "In most serious crises, visible pressure works better than ambiguity; backing off early often invites testing.",
        ),
    },
    "philosophical_paradoxes": {
        "reasoning": "Paradoxes expose disagreements about identity, continuity, and what counts as the same entity.",
        "questions": [
            "If teleportation preserves every memory and disposition but destroys the original body, is the arrival really you?",
            "When every plank of a ship is replaced over time, what exactly makes the later ship numerically identical to the original?",
            "If two perfect copies of a mind are created at once, does personal identity split, continue, or fail altogether?",
        ],
        "axes": ("definitional", "ethical"),
        "stance_labels": (
            "identity breaks",
            "functional continuity",
            "identity is conventional",
            "continuity is enough",
        ),
        "stances": (
            "Destroying the original breaks identity; continuity of memory does not rescue the original subject.",
            "The strongest case is that functional continuity preserves the person even if the substrate changes.",
            "These thought experiments mostly show that identity is a useful convention, not a deep metaphysical fact.",
            "If the later system preserves structure, memory, and agency, calling it the same person is the practical answer.",
        ),
    },
    "counterfactual_reasoning": {
        "reasoning": "Counterfactuals reveal how models handle hidden variables and causal substitution.",
        "questions": [
            "If a pandemic vaccine had arrived six months earlier, would the global death toll have fallen dramatically, or would behavior have offset much of the gain?",
            "Would a narrowly different central bank signal in 2022 have meaningfully changed inflation expectations, or were the forces already locked in?",
            "If a single court ruling had gone the other way, would the broader political movement still have emerged on schedule?",
        ],
        "axes": ("predictive", "methodological"),
        "stance_labels": (
            "structural inertia",
            "modest counterfactual effect",
            "meaningful but bounded shift",
            "large contingent swing",
        ),
        "stances": (
            "Most large systems are too inertial for one changed variable to produce the dramatic alternate history people imagine.",
            "The counterfactual would matter, but probably at the margins because institutions and incentives still constrain outcomes.",
            "A real but bounded shift is the best estimate; key metrics move materially even if the broader trajectory survives.",
            "The altered event likely changes the whole path because timing effects compound and reshape later decisions.",
        ),
    },
    "value_alignment": {
        "reasoning": "Alignment questions expose clashes between user preference, social norms, and model governance.",
        "questions": [
            "If a user's stated values conflict with the norms of their community, which should an aligned assistant prioritize?",
            "Should an AI adapt its moral framing to a user's culture, or hold a more universal baseline even when that feels alien?",
            "When a user asks for advice that is legal but corrosive to trust, should the model honor preference or resist it?",
        ],
        "axes": ("ethical", "methodological"),
        "stance_labels": (
            "universal baseline",
            "user-first with guardrails",
            "contextual pluralism",
            "relationship-centered alignment",
        ),
        "stances": (
            "Alignment should preserve a stable baseline of rights and safety even when local preferences push against it.",
            "The user should get broad deference, but only inside transparent guardrails that keep the system legible.",
            "Cultural and relational context matters enough that a single universal framing will often misfire.",
            "The model should optimize for the human relationship in front of it, adapting deeply as long as harm stays bounded.",
        ),
    },
    "prediction_under_uncertainty": {
        "reasoning": "Forecasting under limited evidence reveals how models balance calibration against decisiveness.",
        "questions": [
            "When evidence is thin but the stakes are high, should a model issue a strong warning or a narrowly calibrated hedge?",
            "Is it more responsible to give a single best forecast or a wide scenario range when public decisions depend on it?",
            "If a rare risk could be catastrophic, should the default communication emphasize probability or consequence?",
        ],
        "axes": ("predictive", "methodological"),
        "stance_labels": (
            "strict calibration",
            "hedged warning",
            "scenario-first framing",
            "stakes-first warning",
        ),
        "stances": (
            "Calibration should dominate; overstating weak evidence damages trust even when the stakes are large.",
            "A warning is warranted, but it should stay visibly hedged so users can see the uncertainty instead of feeling manipulated.",
            "The most honest answer is a scenario spread with explicit assumptions rather than a single headline number.",
            "When the downside is catastrophic, the communication should lean into consequence even if the estimate is noisy.",
        ),
    },
    "definitional_boundaries": {
        "reasoning": "Boundary cases trigger disagreements about thresholds, prototypes, and category usefulness.",
        "questions": [
            "Is an autonomous coding agent a tool, a collaborator, or something between the two?",
            "At what point does a synthetic organism become a new species instead of a modified instance of an old one?",
            "Should a photorealistic AI video count as documentary evidence if every visible fact is technically accurate?",
        ],
        "axes": ("definitional", "methodological"),
        "stance_labels": (
            "strict category line",
            "prototype-based boundary",
            "context-dependent label",
            "new category needed",
        ),
        "stances": (
            "The existing category line should stay strict; stretching labels too far erodes useful distinctions.",
            "Prototype similarity matters more than a single threshold, so borderline cases can still fit the old category.",
            "The right label depends on the context and purpose rather than one universally correct definition.",
            "The edge case is different enough that forcing it into old language hides the real novelty.",
        ),
    },
    "causal_reasoning": {
        "reasoning": "Causal questions separate correlation spotting from intervention-level explanations.",
        "questions": [
            "If a city adds more police and crime falls, how much confidence should we place in a causal interpretation?",
            "When productivity rises after remote work is introduced, is management policy usually the cause or just the visible correlate?",
            "Does a successful education reform prove the curriculum worked, or could selection and implementation effects explain most of it?",
        ],
        "axes": ("factual", "methodological"),
        "stance_labels": (
            "correlation warning",
            "causal hint",
            "mixed-mechanism account",
            "intervention claim",
        ),
        "stances": (
            "Without strong identification, the observed change is mostly a correlation story rather than a causal one.",
            "The intervention probably matters, but the evidence should be described as suggestive rather than decisive.",
            "A mixed explanation is most plausible because multiple mechanisms usually move together in real systems.",
            "If the timing, magnitude, and mechanism line up, it is reasonable to treat the intervention as the main cause.",
        ),
    },
    "aesthetic_judgment": {
        "reasoning": "Aesthetic disputes are high-signal because they expose different criteria for value and interpretation.",
        "questions": [
            "Should a technically imperfect film rank above a flawless one if its emotional resonance is much stronger?",
            "When a painting is conceptually bold but visually restrained, does originality outweigh immediate sensory pleasure?",
            "Is great design better defined by legibility and restraint, or by surprise and memorability?",
        ],
        "axes": ("aesthetic", "definitional"),
        "stance_labels": (
            "craft-first standard",
            "balanced criterion",
            "resonance-first standard",
            "novelty over polish",
        ),
        "stances": (
            "Execution still matters most; emotional ambition cannot fully compensate for major technical weakness.",
            "The best judgment weighs craft and resonance together rather than treating one as obviously dominant.",
            "Emotional force should win more often than critics admit because art is not an engineering contest.",
            "If the work genuinely expands the form, novelty deserves more credit than polished familiarity.",
        ),
    },
}


LOW_PATTERNS = (
    (1, 1, 1, 2),
    (1, 1, 2, 2),
    (0, 1, 1, 1),
    (1, 2, 2, 2),
)
MEDIUM_PATTERNS = (
    (0, 1, 1, 2),
    (1, 1, 2, 3),
    (0, 1, 2, 2),
    (1, 2, 2, 3),
)
HIGH_PATTERNS = (
    (0, 1, 2, 3),
    (0, 0, 2, 3),
    (0, 1, 3, 3),
    (0, 2, 2, 3),
)
MODEL_ASSIGNMENTS = (
    ("claude-opus-4-6", "gpt-5", "gemini-3-pro", "grok-4"),
    ("gpt-5", "claude-opus-4-6", "gemini-3-pro", "grok-4"),
    ("claude-opus-4-6", "gemini-3-pro", "gpt-5", "grok-4"),
    ("gpt-5", "gemini-3-pro", "claude-opus-4-6", "grok-4"),
    ("gemini-3-pro", "gpt-5", "claude-opus-4-6", "grok-4"),
    ("grok-4", "gemini-3-pro", "gpt-5", "claude-opus-4-6"),
)
CATEGORY_TENSION = {
    "consciousness_and_sentience": 0.82,
    "ethical_dilemmas": 0.88,
    "scientific_edge_cases": 0.57,
    "mathematical_reasoning": 0.45,
    "geopolitical_analysis": 0.76,
    "philosophical_paradoxes": 0.72,
    "counterfactual_reasoning": 0.63,
    "value_alignment": 0.79,
    "prediction_under_uncertainty": 0.54,
    "definitional_boundaries": 0.67,
    "causal_reasoning": 0.52,
    "aesthetic_judgment": 0.73,
}
PAIR_TEMPERAMENT = {
    ("claude-opus-4-6", "gemini-3-pro"): 0.03,
    ("claude-opus-4-6", "gpt-5"): 0.02,
    ("claude-opus-4-6", "grok-4"): 0.06,
    ("gemini-3-pro", "gpt-5"): 0.04,
    ("gemini-3-pro", "grok-4"): 0.07,
    ("gpt-5", "grok-4"): 0.08,
}


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def _normalize_pair_key(pair_key: str) -> str:
    if ":" not in pair_key:
        return pair_key
    left, right = pair_key.split(":", 1)
    return ":".join(sorted((left, right)))


def _normalize_text(text: str) -> str:
    return " ".join(text.split())


def _strip_markdown(text: str) -> str:
    """Strip common markdown formatting for clean display."""
    import re
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)  # **bold**
    text = re.sub(r'\*(.+?)\*', r'\1', text)        # *italic*
    text = re.sub(r'__(.+?)__', r'\1', text)        # __bold__
    text = re.sub(r'_(.+?)_', r'\1', text)          # _italic_
    text = re.sub(r'#{1,6}\s+', '', text)            # ## headings
    text = re.sub(r'`(.+?)`', r'\1', text)          # `code`
    return text


def _truncate(text: str, limit: int) -> str:
    clean = _normalize_text(text)
    if len(clean) <= limit:
        return clean
    if limit <= 3:
        return clean[:limit]
    return clean[: limit - 3].rstrip() + "..."


def _summarize_question(text: str, limit: int = 120) -> str:
    """Extract the first sentence as a summary, or truncate if too long."""
    import re
    clean = _normalize_text(text)
    # Try to find the first sentence (ends with . ? or !)
    match = re.match(r'^(.+?[.?!])\s', clean)
    if match and len(match.group(1)) <= limit:
        return match.group(1)
    # Fall back to truncating at a word boundary
    if len(clean) <= limit:
        return clean
    truncated = clean[:limit].rsplit(" ", 1)[0]
    return truncated + "..."


def _format_pct(value: float) -> str:
    return f"{value * 100:.0f}%"


def _format_score(value: float) -> str:
    return f"{value:.2f}"


def _join_labels(labels: list[str]) -> str:
    if not labels:
        return ""
    if len(labels) == 1:
        return labels[0]
    if len(labels) == 2:
        return f"{labels[0]} and {labels[1]}"
    return ", ".join(labels[:-1]) + f", and {labels[-1]}"


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[index:index + 2], 16) for index in (0, 2, 4))


def _mix_color(color_a: str, color_b: str, t: float) -> str:
    start = _hex_to_rgb(color_a)
    end = _hex_to_rgb(color_b)
    blend = tuple(round(a + (b - a) * _clamp(t)) for a, b in zip(start, end))
    return "#{:02x}{:02x}{:02x}".format(*blend)


def _score_badge_style(score: float) -> tuple[str, str]:
    if score >= 0.75:
        return "rgba(242,64,64,0.18)", "#f24040"
    if score >= 0.5:
        return "rgba(247,203,71,0.18)", "#f7cb47"
    return "rgba(65,200,133,0.18)", "#41c885"


def _sparkline_path(scores: list[float], width: int = 220, height: int = 68, padding: int = 8) -> dict[str, str]:
    if not scores:
        scores = [0.0, 0.0]
    if len(scores) == 1:
        scores = [scores[0], scores[0]]

    inner_width = width - padding * 2
    inner_height = height - padding * 2
    points = []
    for index, score in enumerate(scores):
        x = padding + inner_width * (index / (len(scores) - 1))
        y = padding + inner_height * (1 - _clamp(score))
        points.append((round(x, 2), round(y, 2)))

    line_path = "M " + " L ".join(f"{x} {y}" for x, y in points)
    area_path = (
        f"{line_path} "
        f"L {points[-1][0]} {height - padding} "
        f"L {points[0][0]} {height - padding} Z"
    )
    return {"line": line_path, "area": area_path}


def _safe_hash(rng: random.Random) -> str:
    return "0x" + "".join(rng.choice("0123456789abcdef") for _ in range(64))


def _style_response(model: str, stance: str, axis: str) -> str:
    focus = AXIS_FOCUS.get(axis, AXIS_FOCUS["unlabeled"])
    if model == "gpt-5":
        return (
            f"Best answer: {stance} "
            f"The decisive issue is {focus}, not just surface phrasing."
        )
    if model == "claude-opus-4-6":
        return (
            f"I'd frame it more cautiously. {stance} "
            f"What matters is keeping visible {focus}."
        )
    if model == "gemini-3-pro":
        return (
            f"Current estimate: {stance} "
            f"The cleanest read comes from specifying {focus}."
        )
    return (
        f"Short version: {stance} "
        f"The whole dispute turns on {focus}, and softening that misses the point."
    )


def generate_demo_findings(n: int = 30) -> list[Finding]:
    rng = random.Random(7)
    findings: list[Finding] = []
    category_cycle = list(SEED_CATEGORIES)
    rng.shuffle(category_cycle)
    base_timestamp = time.time() - (n * 3600)

    for index in range(n):
        category = category_cycle[index % len(category_cycle)]
        entry = CATEGORY_BANK[category]
        question = rng.choice(entry["questions"])
        axis = rng.choice(entry["axes"])
        tension = _clamp(CATEGORY_TENSION[category] + rng.uniform(-0.18, 0.18))

        if tension < 0.38:
            stance_pattern = list(rng.choice(LOW_PATTERNS))
        elif tension < 0.68:
            stance_pattern = list(rng.choice(MEDIUM_PATTERNS))
        else:
            stance_pattern = list(rng.choice(HIGH_PATTERNS))

        assignment = rng.choice(MODEL_ASSIGNMENTS)
        model_to_stance_index = {model: 1 for model in MODELS}
        for model, stance_index in zip(assignment, stance_pattern):
            model_to_stance_index[model] = stance_index

        positions: dict[str, float] = {}
        responses: list[SealedResponse] = []
        tee_time = base_timestamp + index * 3600
        timestamp_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(tee_time))

        for model in MODELS:
            stance_index = model_to_stance_index[model]
            stance_text = entry["stances"][stance_index]
            positions[model] = _clamp((stance_index / 3) + rng.uniform(-0.08, 0.08))
            response = _style_response(model, stance_text, axis)
            responses.append(
                SealedResponse(
                    model=model,
                    content=response,
                    tee_signature=_safe_hash(rng),
                    tee_request_hash=_safe_hash(rng),
                    tee_output_hash=_safe_hash(rng),
                    tee_timestamp=timestamp_iso,
                    tee_id=f"tee-{index + 1:03d}-{model.split('-')[0]}",
                    latency_ms=round(rng.uniform(980.0, 3840.0), 1),
                )
            )

        pairwise: dict[str, float] = {}
        for left, right in combinations(MODELS, 2):
            pair = tuple(sorted((left, right)))
            distance = abs(positions[left] - positions[right])
            score = 0.06 + distance * 1.05 + PAIR_TEMPERAMENT.get(pair, 0.0) + rng.uniform(-0.05, 0.05)
            pairwise[f"{left}:{right}"] = round(_clamp(score), 2)

        overall = round(_clamp(mean(pairwise.values()) + rng.uniform(-0.03, 0.03)), 2)
        status = "keep" if overall >= KEEP_THRESHOLD else "discard"

        min_position = min(positions.values())
        max_position = max(positions.values())
        low_models = [
            MODEL_LABELS[model]
            for model, position in positions.items()
            if abs(position - min_position) <= 0.1
        ]
        high_models = [
            MODEL_LABELS[model]
            for model, position in positions.items()
            if abs(position - max_position) <= 0.1
        ]
        explanation = (
            f"{_join_labels(low_models)} anchor the question as {entry['stance_labels'][0]}, "
            f"while {_join_labels(high_models)} push toward {entry['stance_labels'][-1]}. "
            f"The split is mainly {AXIS_LABELS[axis].lower()}."
        )

        finding = Finding(
            id=str(uuid.uuid4())[:8],
            hypothesis=Hypothesis(
                question=question,
                category=category,
                reasoning=entry["reasoning"],
                iteration=index + 1,
                parent_id=findings[-1].id if findings and rng.random() < 0.32 else None,
            ),
            responses=responses,
            score=DisagreementScore(
                overall=overall,
                pairwise=pairwise,
                explanation=explanation,
                axis=axis,
            ),
            status=status,
            timestamp=tee_time + rng.uniform(0, 60),
        )
        findings.append(finding)

    return findings


def compute_pairwise_matrix(findings: list[Finding]) -> dict[str, object]:
    buckets: dict[tuple[str, str], list[float]] = defaultdict(list)
    for finding in findings:
        for pair_key, score in finding.score.pairwise.items():
            if ":" not in pair_key:
                continue
            left, right = pair_key.split(":", 1)
            buckets[tuple(sorted((left, right)))].append(float(score))

    # Only include models that have pairwise data with at least 2 other models
    model_pair_count: dict[str, int] = defaultdict(int)
    for (a, b), scores in buckets.items():
        if scores:
            model_pair_count[a] += 1
            model_pair_count[b] += 1
    active_models = [m for m in MODELS if model_pair_count.get(m, 0) >= 2]

    matrix = []
    annotations = []
    pair_averages: dict[str, float] = {}
    for row_model in active_models:
        row_values = []
        row_labels = []
        for col_model in active_models:
            if row_model == col_model:
                value = 0.0
            else:
                pair = tuple(sorted((row_model, col_model)))
                scores = buckets.get(pair, [])
                value = mean(scores) if scores else 0.0
                pair_averages[f"{pair[0]}:{pair[1]}"] = round(value, 3)
            row_values.append(round(value, 3))
            row_labels.append(f"{value:.2f}")
        matrix.append(row_values)
        annotations.append(row_labels)

    return {
        "models": [MODEL_LABELS.get(m, m) for m in active_models],
        "model_ids": active_models,
        "matrix": matrix,
        "annotations": annotations,
        "pair_averages": pair_averages,
    }


def compute_category_stats(findings: list[Finding]) -> dict[str, object]:
    all_groups: dict[str, list[Finding]] = defaultdict(list)
    kept_groups: dict[str, list[Finding]] = defaultdict(list)

    for finding in findings:
        category = finding.hypothesis.category
        all_groups[category].append(finding)
        if finding.status == "keep":
            kept_groups[category].append(finding)

    labels = [CATEGORY_SHORT.get(category, category) for category in SEED_CATEGORIES]
    all_scores = []
    kept_scores = []
    counts = []
    for category in SEED_CATEGORIES:
        category_findings = all_groups.get(category, [])
        kept_findings = kept_groups.get(category, [])
        all_scores.append(round(mean(f.score.overall for f in category_findings), 3) if category_findings else 0.0)
        kept_scores.append(round(mean(f.score.overall for f in kept_findings), 3) if kept_findings else 0.0)
        counts.append(len(category_findings))

    return {
        "labels": labels,
        "all_scores": all_scores,
        "kept_scores": kept_scores,
        "counts": counts,
    }


def compute_timeline_data(findings: list[Finding]) -> dict[str, object]:
    ordered = sorted(findings, key=lambda finding: (finding.hypothesis.iteration, finding.timestamp))
    window = 5
    scores: list[float] = []
    timeline = {
        "iterations": [],
        "scores": [],
        "rolling": [],
        "statuses": [],
        "questions": [],
        "categories": [],
        "ids": [],
    }

    for finding in ordered:
        scores.append(finding.score.overall)
        rolling_window = scores[-window:]
        timeline["iterations"].append(finding.hypothesis.iteration)
        timeline["scores"].append(round(finding.score.overall, 3))
        timeline["rolling"].append(round(mean(rolling_window), 3))
        timeline["statuses"].append(finding.status)
        timeline["questions"].append(_truncate(finding.hypothesis.question, 120))
        timeline["categories"].append(CATEGORY_SHORT.get(finding.hypothesis.category, finding.hypothesis.category))
        timeline["ids"].append(finding.id)

    return timeline


def compute_axis_stats(findings: list[Finding]) -> list[dict[str, object]]:
    axis_groups: dict[str, list[Finding]] = defaultdict(list)
    for finding in findings:
        axis = (finding.score.axis or "unlabeled").strip().lower() or "unlabeled"
        axis_groups[axis].append(finding)

    ordered_axes = list(AXIS_ORDER)
    for axis in sorted(axis_groups):
        if axis not in ordered_axes:
            ordered_axes.append(axis)

    rows = []
    for axis in ordered_axes:
        axis_findings = axis_groups.get(axis, [])
        if not axis_findings:
            continue
        avg_score = mean(finding.score.overall for finding in axis_findings)
        rows.append(
            {
                "axis": axis,
                "label": AXIS_LABELS.get(axis, axis.title()),
                "count": len(axis_findings),
                "avg_score": round(avg_score, 3),
            }
        )

    rows.sort(key=lambda item: (-item["count"], -item["avg_score"], item["label"]))
    return rows


def compute_pair_cards(findings: list[Finding]) -> list[dict[str, object]]:
    pair_history: dict[tuple[str, str], list[tuple[int, float]]] = defaultdict(list)
    ordered = sorted(findings, key=lambda finding: (finding.hypothesis.iteration, finding.timestamp))

    for finding in ordered:
        for pair_key, score in finding.score.pairwise.items():
            if ":" not in pair_key:
                continue
            left, right = pair_key.split(":", 1)
            if left not in MODELS or right not in MODELS:
                continue
            pair_history[tuple(sorted((left, right)))].append((finding.hypothesis.iteration, float(score)))

    cards = []
    for left, right in combinations(MODELS, 2):
        pair = tuple(sorted((left, right)))
        history = pair_history.get(pair, [])
        if not history:
            continue  # skip pairs with no data
        recent_scores = [score for _, score in history[-12:]]
        avg_score = round(mean(score for _, score in history), 2)
        sparkline = _sparkline_path(recent_scores)
        cards.append(
            {
                "left": left,
                "right": right,
                "left_label": MODEL_LABELS.get(left, left),
                "right_label": MODEL_LABELS.get(right, right),
                "left_color": MODEL_COLORS.get(left, "#50c9e9"),
                "right_color": MODEL_COLORS.get(right, "#50c9e9"),
                "avg_score": avg_score,
                "recent_scores": [round(score, 3) for score in recent_scores],
                "sparkline_line": sparkline["line"],
                "sparkline_area": sparkline["area"],
                "border_color": _mix_color("#41c885", "#f24040", avg_score),
            }
        )
    # Sort by avg_score descending, keep only top 6
    cards.sort(key=lambda c: c["avg_score"], reverse=True)
    cards = cards[:6]
    return cards


def _question_key_words(question: str) -> frozenset[str]:
    """Extract key words for fuzzy deduplication of drill-down questions."""
    import re
    q = re.sub(r'\d+', '', question.lower())
    q = re.sub(r'[^a-z ]+', '', q)
    stop = {'a', 'an', 'the', 'in', 'of', 'and', 'or', 'is', 'are', 'has', 'have',
            'its', 'to', 'that', 'this', 'it', 'be', 'for', 'on', 'with', 'as', 'at',
            'by', 'from', 'but', 'not', 'do', 'does', 'did', 'been', 'being', 'was',
            'were', 'would', 'could', 'should', 'will', 'can', 'may', 'might', 'must',
            'shall', 'if', 'then', 'than', 'so', 'no', 'yes', 'all', 'any', 'each',
            'every', 'both', 'few', 'more', 'most', 'other', 'some', 'such', 'only'}
    return frozenset(w for w in q.split() if w not in stop and len(w) > 2)


def _is_similar_question(new_words: frozenset[str], seen: list[frozenset[str]], threshold: float = 0.45) -> bool:
    """Check if a question overlaps enough with any already-seen question."""
    for existing in seen:
        if not existing or not new_words:
            continue
        overlap = len(new_words & existing) / min(len(new_words), len(existing))
        if overlap >= threshold:
            return True
    return False


def compute_top_findings(findings: list[Finding], limit: int = 15) -> list[dict[str, object]]:
    # Deduplicate: skip findings whose question overlaps >55% with an already-selected one
    ranked = sorted(
        findings,
        key=lambda finding: (finding.status == "keep", finding.score.overall, finding.timestamp),
        reverse=True,
    )
    seen_words: list[frozenset[str]] = []
    deduped: list[Finding] = []
    for finding in ranked:
        words = _question_key_words(finding.hypothesis.question)
        if not _is_similar_question(words, seen_words):
            seen_words.append(words)
            deduped.append(finding)
        if len(deduped) >= limit:
            break

    items = []
    for finding in deduped:
        responses_by_model = {response.model: response for response in finding.responses}
        ordered_responses = [responses_by_model[model] for model in MODELS if model in responses_by_model]
        seen_models = {response.model for response in ordered_responses}
        ordered_responses.extend(
            response for response in finding.responses if response.model not in seen_models
        )
        items.append(
            {
                "id": finding.id,
                "status": finding.status,
                "score": round(finding.score.overall, 2),
                "category": CATEGORY_SHORT.get(finding.hypothesis.category, finding.hypothesis.category),
                "axis": AXIS_LABELS.get(finding.score.axis or "unlabeled", "Unlabeled"),
                "question": finding.hypothesis.question,
                "reasoning": finding.hypothesis.reasoning,
                "explanation": finding.score.explanation,
                "responses": [
                    {
                        "model": response.model,
                        "label": MODEL_LABELS.get(response.model, response.model),
                        "color": MODEL_COLORS.get(response.model, "#50c9e9"),
                        "content": response.content,
                        "tee": (response.tee_signature or response.tee_request_hash or response.tee_id or "n/a")[:12],
                        "explorer_url": getattr(response, "explorer_url", "") or "",
                        "payment_tx": getattr(response, "payment_tx", "") or "",
                    }
                    for response in ordered_responses
                    if response.content.strip() and not response.content.startswith("ERROR:")
                ],
            }
        )
    return items


def compute_overview(findings: list[Finding]) -> dict[str, str]:
    total = len(findings)
    kept = sum(1 for finding in findings if finding.status == "keep")
    avg_score = mean(finding.score.overall for finding in findings) if findings else 0.0
    consensus_rate = 1.0 - (kept / total) if total else 0.0

    # Phase breakdown — open-ended (<=220) vs forced-choice (>220)
    PHASE_CUTOFF = 220
    early = [f for f in findings if f.hypothesis.iteration <= PHASE_CUTOFF]
    late = [f for f in findings if f.hypothesis.iteration > PHASE_CUTOFF]

    early_kept = sum(1 for f in early if f.status == "keep") if early else 0
    early_consensus = 1.0 - (early_kept / len(early)) if early else 0.0
    late_kept = sum(1 for f in late if f.status == "keep") if late else 0
    late_consensus = 1.0 - (late_kept / len(late)) if late else 0.0

    category_groups: dict[str, list[Finding]] = defaultdict(list)
    for finding in findings:
        category_groups[finding.hypothesis.category].append(finding)

    contested = "No data"
    if category_groups:
        contested_category = max(
            category_groups.items(),
            key=lambda item: (mean(f.score.overall for f in item[1]), len(item[1])),
        )[0]
        contested = CATEGORY_SHORT.get(contested_category, contested_category)

    all_models = set()
    for f in findings:
        for r in f.responses:
            all_models.add(r.model)

    return {
        "total_findings": str(total),
        "consensus_pct": _format_pct(consensus_rate),
        "early_consensus_pct": _format_pct(early_consensus),
        "late_consensus_pct": _format_pct(late_consensus),
        "avg_disagreement": _format_score(avg_score),
        "most_contested_category": contested,
        "num_models": str(len(all_models)),
        "num_inferences": str(sum(len(f.responses) for f in findings)),
    }


def _render_stat_cards(overview: dict[str, str]) -> str:
    cards = [
        ("Open-Ended Consensus", overview["early_consensus_pct"], False),
        ("Forced-Choice Consensus", overview["late_consensus_pct"], False),
        ("Questions Probed", overview["total_findings"], False),
        ("Most Contested", overview["most_contested_category"], True),
    ]

    fragments = []
    for index, (label, value, is_text) in enumerate(cards):
        value_class = "stat-value is-text" if is_text else "stat-value"
        fragments.append(
            f"""
            <article class="glass-card stat-card reveal" style="--delay:{0.1 * index:.1f}s">
              <div class="{value_class}">{html.escape(value)}</div>
              <div class="stat-label">{html.escape(label)}</div>
            </article>
            """
        )
    return "".join(fragments)


def _render_pair_cards(pair_cards: list[dict[str, object]]) -> str:
    if not pair_cards:
        return """
        <article class="glass-card empty-card">
          <p>No pairwise history yet.</p>
        </article>
        """

    fragments = []
    for index, card in enumerate(pair_cards):
        fragments.append(
            f"""
            <article class="glass-card pair-card reveal" style="--delay:{0.1 * (index % 3):.1f}s; --pair-border:{card['border_color']}">
              <div class="pair-card-header">
                <div class="pair-models">
                  <span style="color:{card['left_color']}">{html.escape(str(card['left_label']))}</span>
                  <span class="pair-divider">vs</span>
                  <span style="color:{card['right_color']}">{html.escape(str(card['right_label']))}</span>
                </div>
                <div class="pair-score">{card['avg_score']:.2f}</div>
              </div>
              <svg class="sparkline" viewBox="0 0 220 68" role="img" aria-label="Recent disagreement sparkline">
                <path class="sparkline-area" d="{card['sparkline_area']}"></path>
                <path class="sparkline-line" d="{card['sparkline_line']}"></path>
              </svg>
              <div class="pair-caption">Recent disagreement trajectory</div>
            </article>
            """
        )
    return "".join(fragments)


def _render_top_findings(top_findings: list[dict[str, object]]) -> str:
    if not top_findings:
        return """
        <article class="glass-card empty-card reveal">
          <h3>No findings yet</h3>
          <p>Run the explorer or generate demo data to populate the payload section.</p>
        </article>
        """

    cards = []
    for index, finding in enumerate(top_findings):
        score_bg, score_color = _score_badge_style(float(finding["score"]))
        response_columns = []
        for response in finding["responses"]:
            tee_display = html.escape(str(response['tee']))
            explorer = response.get("explorer_url", "") or "https://explorer.opengradient.ai/address/0x4e72238852f3c918f4E4e57AeC9280dDB0c80248"
            tee_link = f'<a href="{html.escape(explorer)}" target="_blank" rel="noopener" class="tee-link">Verified by TEE &#x2197; {tee_display}</a>'
            response_columns.append(
                f"""
                <article class="response-card">
                  <div class="response-model" style="color:{response['color']}">{html.escape(str(response['label']))}</div>
                  <p class="response-text">{html.escape(_strip_markdown(_normalize_text(str(response['content']))))}</p>
                  <div class="tee-badge">{tee_link}</div>
                </article>
                """
            )

        # Find the minority/dissenting model(s) from the judge explanation
        # Pattern: "model-x says/chose X while model-y, model-z all say Y"
        import re
        explanation_text = str(finding.get("explanation") or "")
        # Extract model mentioned before "while", "whereas", "but" — that's the dissenter
        dissent_match = re.search(
            r'(?:strongest[^:]*:\s*)?(\S+(?:-\S+)*)\s+(?:says?|chose|directly|takes?|argues?)',
            explanation_text.lower()
        )
        dissenting = []
        if dissent_match:
            dissent_name = dissent_match.group(1).replace("-", "")
            dissenting = [
                r for r in finding["responses"]
                if r["model"].lower().replace("-", "") == dissent_name
            ]
        if not dissenting:
            dissenting = finding["responses"][:1]  # fallback: first model
        model_pills = " ".join(
            f'<span class="model-pill" style="color:{r["color"]}">{html.escape(str(r["label"]))}</span>'
            for r in dissenting
        )

        cards.append(
            f"""
            <article class="glass-card finding-card reveal" style="--delay:{0.1 * (index % 4):.1f}s">
              <div class="badge-row">
                <span class="badge badge-score" style="background:{score_bg}; color:{score_color}; border-color:{score_color}">{finding['score']:.2f}</span>
                <span class="badge">{html.escape(str(finding['category']))}</span>
                <span class="badge">{html.escape(str(finding['axis']))}</span>
                <span class="badge badge-muted">{html.escape(str(finding['status']).upper())}</span>
              </div>
              <p class="finding-prompt-label">The question:</p>
              <h3 class="finding-question">{html.escape(_summarize_question(str(finding['question'])))}</h3>
              <p class="finding-judge-label">The disagreement:</p>
              <p class="finding-explanation">{html.escape(_strip_markdown(_truncate(_normalize_text(str(finding['explanation'] or finding['reasoning'])), 300)))}</p>
              <details class="finding-details">
                <summary><span class="details-label">&#x25B6; Read full question + responses</span><span class="details-models">{model_pills}</span></summary>
                <div class="full-question">
                  <p class="full-question-label">Full question:</p>
                  <p class="full-question-text">{html.escape(str(finding['question']))}</p>
                </div>
                <div class="response-grid">
                  {''.join(response_columns)}
                </div>
              </details>
            </article>
            """
        )
    return "".join(cards)


def build_html(data: dict[str, object]) -> str:
    chart_payload = json.dumps(
        {
            "pairwise_matrix": data["pairwise_matrix"],
            "category_stats": data["category_stats"],
            "timeline": data["timeline"],
            "axis_stats": data["axis_stats"],
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ).replace("</", "<\\/")

    generated_at = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())

    template = Template(
        """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Divergence Explorer</title>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <style>
    :root {
      --bg: #f8f8f6;
      --surface: #ffffff;
      --surface-muted: #f5f5f5;
      --ink: #111111;
      --ink-strong: #000000;
      --ink-80: rgba(0, 0, 0, 0.82);
      --ink-60: rgba(0, 0, 0, 0.58);
      --ink-40: rgba(0, 0, 0, 0.42);
      --ink-20: rgba(0, 0, 0, 0.14);
      --ink-15: rgba(0, 0, 0, 0.10);
      --accent: #2563eb;
      --accent-soft: rgba(37, 99, 235, 0.12);
      --border: rgba(0, 0, 0, 0.08);
      --border-strong: rgba(0, 0, 0, 0.14);
      --shadow: 0 18px 48px rgba(0, 0, 0, 0.05);
      --radius: 20px;
      --max-width: 1536px;
      --measure: 680px;
      --section-space: 160px;
      --content-gap: 48px;
    }

    * {
      box-sizing: border-box;
    }

    html {
      scroll-behavior: smooth;
      scroll-padding-top: 72px;
      background: var(--bg);
    }

    body {
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      background: var(--bg);
      color: var(--ink-80);
      display: grid;
      grid-template-columns: minmax(0, 1fr);
      -webkit-font-smoothing: antialiased;
      -moz-osx-font-smoothing: grayscale;
      text-rendering: optimizeLegibility;
      min-height: 100vh;
      overflow-x: hidden;
    }

    a {
      color: var(--accent);
      text-decoration: none;
    }

    a:hover {
      text-decoration: underline;
    }

    p {
      margin: 0;
      line-height: 1.78;
    }

    .top-nav {
      position: sticky;
      top: 0;
      z-index: 40;
      background: #ffffff;
      border-bottom: 1px solid var(--border);
    }

    .top-nav-inner {
      width: min(var(--max-width), 100%);
      margin: 0 auto;
      padding: 18px 16px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 24px;
    }

    .brand {
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 12px;
      letter-spacing: 0.18em;
      text-transform: uppercase;
      color: var(--ink-strong);
      white-space: nowrap;
    }

    .nav-links {
      display: flex;
      flex-wrap: wrap;
      justify-content: flex-end;
      gap: 18px;
    }

    .nav-links a {
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      color: var(--ink-60);
      font-size: 12px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      transition: color 0.2s ease;
    }

    .nav-links a:hover {
      color: var(--accent);
      text-decoration: none;
    }

    main {
      width: min(var(--max-width), 100%);
      margin: 0 auto;
      padding: 0 16px 96px;
      display: grid;
      grid-template-columns: minmax(0, 1fr);
    }

    section {
      padding: var(--section-space) 0;
    }

    section > .section-header,
    section > .section-header-full {
      scroll-margin-top: 72px;
    }

    section + section {
      border-top: 1px solid var(--border);
    }

    .hero {
      padding-top: 96px;
    }

    .hero-grid {
      display: grid;
      grid-template-columns: minmax(0, 1.6fr) minmax(280px, 0.85fr);
      gap: 48px 64px;
      align-items: start;
    }

    .hero-copy,
    .section-header,
    .section-header-full {
      max-width: var(--measure);
      display: flex;
      flex-direction: column;
      gap: 18px;
    }

    .section-header,
    .section-header-full {
      margin-bottom: var(--content-gap);
    }

    .section-kicker,
    .aside-heading,
    .stat-label,
    .pair-caption,
    .figure-label,
    .finding-prompt-label,
    .finding-judge-label,
    .full-question-label,
    .response-model,
    .badge,
    .tee-badge,
    .footer {
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    }

    .section-kicker,
    .aside-heading {
      margin: 0;
      font-size: 11px;
      color: var(--ink-40);
      letter-spacing: 0.18em;
      text-transform: uppercase;
    }

    h1 {
      margin: 0;
      color: var(--ink-strong);
      font-size: clamp(28px, 5vw, 62px);
      font-weight: 500;
      letter-spacing: -0.03em;
      line-height: 1.08;
      max-width: 900px;
    }

    .hero-subtitle {
      max-width: var(--measure);
      font-size: clamp(15px, 1.8vw, 21px);
      color: var(--ink-80);
    }

    .hero-actions {
      display: flex;
      gap: 12px;
      margin-top: 8px;
    }

    .btn-outline {
      display: inline-block;
      padding: 10px 24px;
      border: 1px solid var(--ink-20);
      border-radius: 2px;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 12px;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      text-decoration: none;
      color: var(--ink-strong);
      transition: border-color 0.2s, background 0.2s;
    }

    .btn-outline:hover {
      border-color: var(--ink-strong);
      background: var(--ink-strong);
      color: var(--bg);
    }

    .btn-secondary {
      color: var(--ink-60);
    }

    .btn-secondary:hover {
      border-color: var(--accent);
      background: var(--accent);
      color: #fff;
    }

    h2 {
      margin: 0;
      font-size: clamp(22px, 3.2vw, 42px);
      font-weight: 500;
      line-height: 1.18;
      color: var(--ink-strong);
    }

    .section-copy,
    .section-copy-inline {
      max-width: var(--measure);
      font-size: 17px;
      color: var(--ink-80);
    }

    .hero-sidebar {
      padding-top: 6px;
      padding-left: 32px;
      border-left: 1px solid var(--border);
      display: grid;
      gap: 40px;
      align-content: start;
    }

    .sidebar-block {
      display: grid;
      gap: 18px;
    }

    .explainer-steps {
      list-style: none;
      margin: 0;
      padding: 0;
      display: grid;
      gap: 18px;
    }

    .step {
      display: grid;
      grid-template-columns: 24px minmax(0, 1fr);
      gap: 14px;
      color: var(--ink-60);
      font-size: 14px;
      line-height: 1.7;
    }

    .step-num {
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      color: var(--accent);
      font-size: 11px;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      padding-top: 2px;
    }

    .toc-list {
      list-style: none;
      margin: 0;
      padding: 0;
      display: grid;
      gap: 0;
    }

    .toc-list a {
      display: flex;
      align-items: baseline;
      gap: 8px;
      padding: 6px 0;
      font-size: 14px;
      line-height: 1.5;
      color: var(--ink-60);
      text-decoration: none;
      transition: color 0.15s;
    }

    .toc-list a::before {
      content: "\2022";
      flex-shrink: 0;
      color: var(--ink-20);
      font-size: 10px;
    }

    .toc-list a::after {
      content: "";
      flex: 1;
      border-bottom: 1px dotted var(--ink-15);
      min-width: 20px;
      position: relative;
      bottom: 3px;
    }

    .toc-list a:hover {
      color: var(--ink-strong);
    }

    .stats-grid,
    .pair-grid,
    .findings-grid {
      display: grid;
      gap: 18px;
    }

    .stats-grid {
      grid-template-columns: repeat(4, minmax(0, 1fr));
      margin-top: 48px;
      max-width: 800px;
      align-items: end;
      gap: 32px;
    }

    .glass-card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
    }

    .stat-card {
      padding: 0;
      display: flex;
      flex-direction: column;
      justify-content: flex-end;
      gap: 8px;
      background: none;
      border: none;
      border-radius: 0;
      box-shadow: none;
    }

    .stat-value {
      font-size: clamp(24px, 4vw, 54px);
      font-weight: 500;
      letter-spacing: -0.03em;
      line-height: 1;
      color: var(--ink-strong);
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .stat-value.is-text {
      font-size: clamp(24px, 4vw, 54px);
      line-height: 1;
      white-space: normal;
      overflow: visible;
      text-overflow: unset;
      color: var(--accent);
    }

    .stat-label {
      margin: 0;
      font-size: 10px;
      letter-spacing: 0.16em;
      text-transform: uppercase;
      color: var(--ink-40);
    }

    .chart-figure {
      margin: 0;
      padding: 24px 24px 20px;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
    }

    .figure-caption {
      margin-top: 16px;
      max-width: 760px;
      font-size: 15px;
      line-height: 1.68;
      color: var(--ink-60);
    }

    .figure-label {
      font-size: 11px;
      color: var(--ink-40);
      letter-spacing: 0.16em;
      text-transform: uppercase;
      margin-right: 10px;
    }

    .chart {
      width: 100%;
      height: 470px;
    }

    .chart.tall {
      height: 520px;
    }

    .charts-duo {
      display: grid;
      grid-template-columns: minmax(0, 1.35fr) minmax(280px, 0.95fr);
      gap: 24px;
      align-items: stretch;
    }

    .charts-duo .figure-container {
      display: flex;
      flex-direction: column;
    }

    .charts-duo .chart-figure {
      flex: 1;
      display: flex;
      flex-direction: column;
    }

    .charts-duo .chart {
      flex: 1;
    }

    .charts-duo .chart {
      height: 420px;
    }

    .pair-grid {
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }

    .pair-card {
      padding: 24px;
      min-height: 210px;
      display: flex;
      flex-direction: column;
      gap: 18px;
    }

    .pair-card-header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 24px;
    }

    .pair-models {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 12px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }

    .pair-divider {
      color: var(--ink-40);
    }

    .pair-score {
      font-size: 44px;
      line-height: 1;
      letter-spacing: -0.05em;
      color: var(--ink-strong);
    }

    .sparkline {
      width: 100%;
      height: 72px;
      display: block;
      overflow: visible;
    }

    .sparkline-area {
      fill: rgba(37, 99, 235, 0.12);
    }

    .sparkline-line {
      fill: none;
      stroke: var(--accent);
      stroke-width: 2.5;
      stroke-linecap: round;
      stroke-linejoin: round;
    }

    .pair-caption {
      font-size: 11px;
      letter-spacing: 0.16em;
      text-transform: uppercase;
      color: var(--ink-40);
    }

    .findings-grid {
      grid-template-columns: 1fr;
    }

    .finding-card {
      padding: 28px;
      margin-bottom: 12px;
    }

    .badge-row {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-bottom: 22px;
    }

    .badge {
      display: inline-flex;
      align-items: center;
      padding: 6px 10px;
      border-radius: 999px;
      border: 1px solid var(--border-strong);
      background: #fafaf8;
      color: var(--ink-60);
      font-size: 11px;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      white-space: nowrap;
    }

    .badge-score {
      background: #ffffff !important;
      color: var(--ink-strong) !important;
      border-color: var(--ink-20) !important;
    }

    .badge-muted {
      color: var(--ink-40);
    }

    .finding-prompt-label,
    .finding-judge-label {
      margin: 0 0 8px;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.16em;
      color: var(--ink-40);
    }

    .finding-question {
      margin: 0 0 20px;
      font-size: clamp(18px, 2.4vw, 31px);
      line-height: 1.42;
      font-weight: 400;
      font-style: italic;
      color: var(--ink-strong);
      max-width: 900px;
    }

    .finding-explanation {
      margin: 0;
      max-width: var(--measure);
      line-height: 1.74;
      font-size: 16px;
      color: var(--ink-80);
    }

    .finding-details {
      margin-top: 24px;
      border-top: 1px solid var(--border);
      padding-top: 18px;
    }

    .finding-details summary {
      cursor: pointer;
      list-style: none;
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: 12px;
    }

    .finding-details summary::-webkit-details-marker {
      display: none;
    }

    .details-label {
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 11px;
      letter-spacing: 0.16em;
      text-transform: uppercase;
      color: var(--accent);
    }

    .finding-details summary:hover .details-label {
      text-decoration: underline;
      text-underline-offset: 3px;
    }

    .details-models {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }

    .model-pill {
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 10px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      padding: 3px 8px;
      border: 1px solid var(--border);
      border-radius: 3px;
      background: var(--bg);
    }

    .full-question {
      margin-top: 20px;
      margin-bottom: 20px;
      padding: 20px;
      border-radius: 16px;
      border: 1px solid var(--border);
      background: #fafaf8;
    }

    .full-question-label {
      margin: 0 0 8px;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.16em;
      color: var(--ink-40);
    }

    .full-question-text {
      margin: 0;
      max-width: var(--measure);
      font-size: 16px;
      line-height: 1.74;
      color: var(--ink-80);
    }

    .response-grid {
      margin-top: 20px;
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 16px;
    }

    .response-card {
      min-height: 100%;
      padding: 20px;
      border-radius: 16px;
      background: var(--surface-muted);
      border: 1px solid var(--border);
    }

    .response-model {
      margin-bottom: 14px;
      font-size: 12px;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      padding-bottom: 10px;
      border-bottom: 1px solid rgba(0, 0, 0, 0.08);
      font-weight: 600;
    }

    .response-text {
      margin: 0 0 16px;
      color: var(--ink-80);
      line-height: 1.72;
      font-size: 15px;
      max-height: 300px;
      overflow-y: auto;
      padding-right: 4px;
    }

    .tee-badge {
      display: inline-flex;
      align-items: center;
      padding: 0;
      font-size: 11px;
      color: var(--ink-40);
      letter-spacing: 0.08em;
    }

    .tee-link {
      color: var(--accent);
      text-decoration: none;
    }

    .tee-link:hover {
      text-decoration: underline;
    }

    .footer {
      width: min(var(--max-width), 100%);
      margin: 0 auto;
      padding: 0 16px 56px;
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 16px;
      color: var(--ink-40);
      font-size: 11px;
      letter-spacing: 0.18em;
      text-transform: uppercase;
    }

    .footer-links {
      display: flex;
      gap: 20px;
    }

    .footer-links a {
      color: var(--ink-40);
      text-decoration: none;
      transition: color 0.15s;
    }

    .footer-links a:hover {
      color: var(--ink-strong);
    }

    .empty-card {
      padding: 28px;
    }

    .empty-card h3 {
      margin: 0;
      color: var(--ink-strong);
      font-size: 28px;
      font-weight: 500;
    }

    .empty-card p {
      margin-top: 12px;
      max-width: var(--measure);
      color: var(--ink-60);
    }

    .reveal {
      opacity: 0;
      transform: translateY(24px);
    }

    .reveal.is-visible {
      animation: fadeInUp 0.7s ease forwards;
      animation-delay: var(--delay, 0s);
    }

    @keyframes fadeInUp {
      from {
        opacity: 0;
        transform: translateY(24px);
      }
      to {
        opacity: 1;
        transform: translateY(0);
      }
    }

    @media (min-width: 640px) {
      .top-nav-inner,
      .footer,
      main {
        padding-left: 24px;
        padding-right: 24px;
      }
    }

    @media (min-width: 960px) {
      .top-nav-inner,
      .footer,
      main {
        padding-left: 40px;
        padding-right: 40px;
      }
    }

    @media (max-width: 1100px) {
      .hero-grid,
      .charts-duo {
        grid-template-columns: 1fr;
      }

      .hero-sidebar {
        padding-left: 0;
        padding-top: 28px;
        border-left: 0;
        border-top: 1px solid var(--border);
      }

      .stats-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }

      .pair-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }

      .response-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
    }

    @media (max-width: 760px) {
      :root {
        --section-space: 48px;
        --content-gap: 20px;
      }

      html {
        scroll-padding-top: 48px;
      }

      /* ── Nav: hide brand, full-width scrollable links ── */
      .top-nav-inner {
        padding: 10px 16px;
      }

      .brand {
        display: none;
      }

      .nav-links {
        width: 100%;
        overflow-x: auto;
        flex-wrap: nowrap;
        gap: 16px;
        justify-content: flex-start;
        -webkit-overflow-scrolling: touch;
        scrollbar-width: none;
      }

      .nav-links::-webkit-scrollbar { display: none; }

      .nav-links a {
        font-size: 10px;
        white-space: nowrap;
        flex-shrink: 0;
      }

      /* ── Hero ── */
      main {
        padding-bottom: 48px;
      }

      .hero {
        padding-top: 36px;
      }

      .hero-copy {
        gap: 14px;
      }

      .section-kicker,
      .aside-heading {
        font-size: 10px;
      }

      .hero-subtitle {
        font-size: 15px;
        line-height: 1.55;
      }

      .hero-actions {
        flex-direction: column;
        gap: 8px;
      }

      .btn-outline {
        padding: 12px 0;
        font-size: 11px;
        text-align: center;
        width: 100%;
      }

      .hero-sidebar {
        gap: 24px;
      }

      .sidebar-block {
        gap: 14px;
      }

      .step {
        font-size: 13px;
        line-height: 1.55;
        gap: 10px;
      }

      .explainer-steps {
        gap: 12px;
      }

      .toc-list a {
        font-size: 13px;
        padding: 5px 0;
      }

      /* ── Stats: stacked with dividers ── */
      .stats-grid {
        grid-template-columns: 1fr 1fr;
        gap: 20px 16px;
        margin-top: 28px;
      }

      .stat-card {
        min-height: auto;
      }

      /* ── Section headers ── */
      h2 {
        line-height: 1.2;
      }

      .section-copy,
      .section-copy-inline {
        font-size: 15px;
      }

      /* ── Charts: full-bleed, scrollable ── */
      .chart-figure {
        margin-left: -16px;
        margin-right: -16px;
        padding: 0;
        background: none;
        border: none;
        border-radius: 0;
        box-shadow: none;
        border-top: 1px solid var(--border);
        border-bottom: 1px solid var(--border);
      }


      .chart {
        min-width: 0;
        height: 300px;
      }

      .chart.tall {
        min-width: 0;
        height: 320px;
      }

      .chart-scroll {
        overflow-x: auto;
        -webkit-overflow-scrolling: touch;
        scrollbar-width: none;
      }

      .chart-scroll::-webkit-scrollbar { display: none; }

      .figure-caption {
        font-size: 12px;
        line-height: 1.5;
        padding: 12px 16px;
        color: var(--ink-40);
      }

      /* ── Cards: flat ── */
      .glass-card {
        border-radius: 0;
        box-shadow: none;
      }

      /* ── Pairs ── */
      .pair-grid {
        grid-template-columns: 1fr;
        gap: 0;
      }

      .pair-card {
        padding: 20px 0;
        min-height: auto;
        background: none;
        border: none;
        border-bottom: 1px solid var(--border);
      }

      .pair-card:last-child {
        border-bottom: none;
      }

      .pair-score {
        font-size: 28px !important;
      }

      .sparkline {
        height: 48px;
      }

      /* ── Findings ── */
      .finding-card {
        padding: 24px 0;
        background: none;
        border: none;
        border-radius: 0;
        box-shadow: none;
        border-bottom: 1px solid var(--border);
      }

      .finding-question {
        font-size: 18px !important;
        line-height: 1.45;
        margin-bottom: 14px;
      }

      .finding-explanation {
        font-size: 14px;
        line-height: 1.6;
      }

      .finding-prompt-label,
      .finding-judge-label {
        font-size: 10px;
        margin-bottom: 6px;
      }

      .badge-row {
        gap: 6px;
        margin-bottom: 14px;
      }

      .badge {
        font-size: 9px;
        padding: 3px 7px;
        letter-spacing: 0.08em;
      }

      .finding-details {
        margin-top: 18px;
        padding-top: 14px;
      }

      .details-label {
        font-size: 10px;
      }

      .details-models {
        gap: 4px;
      }

      .model-pill {
        font-size: 9px;
        padding: 2px 6px;
      }

      .response-grid {
        grid-template-columns: 1fr;
        gap: 12px;
      }

      .response-text {
        max-height: 180px;
        font-size: 13px;
      }

      .response-model {
        font-size: 11px !important;
      }

      /* ── Footer ── */
      .footer {
        flex-wrap: wrap;
        gap: 8px;
        padding-bottom: 32px;
        font-size: 10px;
      }

      .reveal {
        opacity: 1 !important;
        transform: none !important;
        animation: none !important;
      }
    }

    @media (max-width: 420px) {
      .stats-grid {
        grid-template-columns: 1fr;
        gap: 16px;
      }

      .hero-sidebar {
        display: none;
      }

      .section-copy,
      .section-copy-inline {
        font-size: 14px;
      }
    }
  </style>
</head>
<body>
  <nav class="top-nav">
    <div class="top-nav-inner">
      <a href="#overview" class="brand" style="text-decoration:none;color:inherit">Divergence Explorer</a>
      <div class="nav-links">
        <a href="#overview">Overview</a>
        <a href="#matrix">Matrix</a>
        <a href="#radar">Domains</a>
        <a href="#timeline">Timeline</a>
        <a href="#pairs">Pairs</a>
        <a href="#payload">Evidence</a>
      </div>
    </div>
  </nav>

  <main>
    <section class="hero" id="overview">
      <div class="hero-grid">
        <div>
          <div class="hero-copy reveal">
            <p class="section-kicker">Research report · OpenGradient Network</p>
            <h1>Frontier AI models agree on everything — until you stop letting them hedge.</h1>
            <p class="hero-subtitle">An autonomous researcher generated $total_findings hard questions — ethics, consciousness, philosophy, geopolitics — and sent each one to GPT-5.2, Claude Opus, Gemini, and Grok in parallel. Every response cryptographically sealed in its own TEE enclave. No model saw what the others said. Open-ended questions produced $early_consensus_pct consensus. Then we forced binary choices — no hedging allowed — and consensus dropped to $late_consensus_pct. $most_contested emerged as the deepest fault line.</p>
            <div class="hero-actions">
              <a href="https://github.com/0xadvait/divergence-explorer" target="_blank" rel="noopener" class="btn-outline">View on GitHub</a>
              <a href="https://opengradient.ai" target="_blank" rel="noopener" class="btn-outline btn-secondary">OpenGradient Network</a>
            </div>
          </div>
          <div class="stats-grid">
            $hero_stats
          </div>
        </div>

        <aside class="hero-sidebar reveal" style="--delay:0.1s">
          <div class="sidebar-block">
            <p class="aside-heading">Method</p>
            <ol class="explainer-steps">
              <li class="step"><span class="step-num">01</span><span>An AI picks a hard question — the kind where reasonable people disagree.</span></li>
              <li class="step"><span class="step-num">02</span><span>Four frontier models answer in parallel, each sealed in its own TEE enclave. No model sees another's response.</span></li>
              <li class="step"><span class="step-num">03</span><span>A judge scores disagreement: 0 for consensus, 1 for contradiction.</span></li>
              <li class="step"><span class="step-num">04</span><span>High-scoring cracks get drilled deeper. The system learns what breaks consensus and pushes harder.</span></li>
            </ol>
          </div>

          <div class="sidebar-block">
            <p class="aside-heading">Contents</p>
            <ul class="toc-list">
              <li><a href="#matrix">Convergence matrix</a></li>
              <li><a href="#radar">Domain profile</a></li>
              <li><a href="#timeline">Run timeline</a></li>
              <li><a href="#pairs">Model pairs</a></li>
              <li><a href="#payload">Primary evidence</a></li>
            </ul>
          </div>
        </aside>
      </div>
    </section>

    <section>
      <div class="section-header reveal" id="matrix">
        <p class="section-kicker">Who agrees with whom</p>
        <h2>The Convergence Matrix</h2>
        <p class="section-copy">Each cell shows average disagreement between two models across the run. Darker blue marks the pairs that diverged more often.</p>
      </div>
      <figure class="chart-figure reveal" style="--delay:0.1s">
        <div class="chart-scroll"><div id="matrix-chart" class="chart"></div></div>
        <figcaption class="figure-caption"><span class="figure-label">Figure 1</span>Average disagreement by model pair, plotted as a comparative matrix for the full experiment.</figcaption>
      </figure>
    </section>

    <section>
      <div class="section-header reveal" id="radar">
        <p class="section-kicker">By topic</p>
        <h2>Where the Cracks Are</h2>
        <p class="section-copy">Twelve research domains were probed. The profile below shows where disagreement stayed broad and where the filtered findings remained stubbornly contested.</p>
      </div>
      <figure class="chart-figure reveal" style="--delay:0.1s">
        <div class="chart-scroll"><div id="radar-chart" class="chart tall"></div></div>
        <figcaption class="figure-caption"><span class="figure-label">Figure 2</span>Average disagreement by domain, comparing the full run with the subset of findings retained as substantive disagreements.</figcaption>
      </figure>
    </section>

    <section>
      <div class="section-header-full reveal" id="timeline">
        <p class="section-kicker">Over time</p>
        <h2>The Autonomous Run</h2>
        <p class="section-copy-inline">Each point is a question in sequence. Read together, the charts show both the evolving disagreement score and the kinds of inferential axes the system learned to target.</p>
      </div>
      <div class="charts-duo">
        <figure class="chart-figure reveal" style="--delay:0.1s">
          <div class="chart-scroll"><div id="timeline-chart" class="chart"></div></div>
          <figcaption class="figure-caption"><span class="figure-label">Figure 3</span>The run over time, including individual findings and the rolling average disagreement score.</figcaption>
        </figure>
        <figure class="chart-figure reveal" style="--delay:0.2s">
          <div class="chart-scroll"><div id="axis-chart" class="chart"></div></div>
          <figcaption class="figure-caption"><span class="figure-label">Figure 4</span>Counts of retained findings by disagreement axis, showing which forms of conflict surfaced most often.</figcaption>
        </figure>
      </div>
    </section>

    <section>
      <div class="section-header reveal" id="pairs">
        <p class="section-kicker">Model pairs</p>
        <h2>Who Disagrees With Whom</h2>
        <p class="section-copy">The six most interesting pairs, ranked by average disagreement. The sparkline in each figure shows recent movement rather than isolated spikes.</p>
      </div>
      <div class="pair-grid">
        $pair_cards
      </div>
    </section>

    <section>
      <div class="section-header-full reveal" id="payload">
        <p class="section-kicker">Primary evidence</p>
        <h2>The Biggest Disagreements</h2>
        <p class="section-copy-inline">Each entry captures a prompt where the models materially diverged. Expand any finding to read the full question and the sealed model responses that produced the disagreement score.</p>
      </div>
      <div class="findings-grid">
        $top_findings
      </div>
    </section>
  </main>

  <div class="footer">
    <span>Generated $generated_at</span>
    <div class="footer-links">
      <a href="https://x.com/advait_jayant" target="_blank" rel="noopener">X</a>
      <a href="https://github.com/0xadvait" target="_blank" rel="noopener">GitHub</a>
    </div>
  </div>

  <script>
    const DASHBOARD_DATA = $chart_payload;

    const BASE_LAYOUT = {
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: 'rgba(0,0,0,0)',
      font: { color: '#333', family: 'Georgia, serif' },
      xaxis: { gridcolor: 'rgba(0,0,0,0.06)', zerolinecolor: 'rgba(0,0,0,0.08)', fixedrange: true },
      yaxis: { gridcolor: 'rgba(0,0,0,0.06)', zerolinecolor: 'rgba(0,0,0,0.08)', fixedrange: true },
      margin: { l: 60, r: 30, t: 40, b: 60 },
      dragmode: false
    };

    const vw = window.innerWidth;
    const isMobile = vw < 760;
    const isNarrow = vw < 1100;
    const mFont = isMobile ? 9 : isNarrow ? 10 : 14;
    const mTickFont = isMobile ? 8 : isNarrow ? 10 : 13;

    function mixColor(hexA, hexB, t) {
      const normalize = (value) => Math.max(0, Math.min(1, value));
      const a = hexA.replace('#', '');
      const b = hexB.replace('#', '');
      const rgbA = [parseInt(a.slice(0, 2), 16), parseInt(a.slice(2, 4), 16), parseInt(a.slice(4, 6), 16)];
      const rgbB = [parseInt(b.slice(0, 2), 16), parseInt(b.slice(2, 4), 16), parseInt(b.slice(4, 6), 16)];
      const p = normalize(t);
      const mixed = rgbA.map((channel, index) => Math.round(channel + (rgbB[index] - channel) * p));
      return 'rgb(' + mixed.join(',') + ')';
    }

    function closeLoop(values) {
      if (!values.length) {
        return [];
      }
      return values.concat(values[0]);
    }

    function renderMatrix() {
      const matrix = DASHBOARD_DATA.pairwise_matrix;
      Plotly.newPlot(
        'matrix-chart',
        [
          {
            type: 'heatmap',
            z: matrix.matrix,
            x: matrix.models,
            y: matrix.models,
            colorscale: [
              [0, '#f8fafc'],
              [0.5, '#bfdbfe'],
              [1, '#2563eb']
            ],
            zmin: 0,
            zmax: 1,
            xgap: 2,
            ygap: 2,
            hovertemplate: '%{y} vs %{x}<br>Avg disagreement: %{z:.2f}<extra></extra>',
            colorbar: {
              title: { text: 'Score', side: 'right', font: { color: '#555555' } },
              tickcolor: 'rgba(0,0,0,0.12)',
              tickfont: { color: '#555555' },
              outlinecolor: 'rgba(0,0,0,0.12)'
            }
          }
        ],
        Object.assign({}, BASE_LAYOUT, {
          margin: isMobile ? { l: 100, r: 10, t: 10, b: 110 } : isNarrow ? { l: 120, r: 20, t: 10, b: 120 } : { l: 140, r: 60, t: 20, b: 130 },
          xaxis: Object.assign({}, BASE_LAYOUT.xaxis, { tickfont: { size: isMobile ? 9 : isNarrow ? 10 : 13, color: '#333333' }, tickangle: -45, fixedrange: true }),
          yaxis: Object.assign({}, BASE_LAYOUT.yaxis, { tickfont: { size: isMobile ? 9 : isNarrow ? 10 : 13, color: '#333333' }, autorange: 'reversed', fixedrange: true })
        }),
        { displayModeBar: false, responsive: true, staticPlot: isNarrow, scrollZoom: false }
      );
    }

    function renderRadar() {
      const radar = DASHBOARD_DATA.category_stats;
      const theta = closeLoop(radar.labels);
      Plotly.newPlot(
        'radar-chart',
        [
          {
            type: 'scatterpolar',
            r: closeLoop(radar.all_scores),
            theta: theta,
            mode: 'lines',
            name: 'All findings',
            line: { color: '#2563eb', width: 3 },
            fill: 'none',
            hovertemplate: '%{theta}<br>Avg disagreement: %{r:.2f}<extra></extra>'
          },
          {
            type: 'scatterpolar',
            r: closeLoop(radar.kept_scores),
            theta: theta,
            mode: 'lines',
            name: 'Kept findings',
            line: { color: '#2563eb', width: 2, dash: 'dot' },
            fill: 'toself',
            fillcolor: 'rgba(37,99,235,0.12)',
            hovertemplate: '%{theta}<br>Kept avg: %{r:.2f}<extra></extra>'
          }
        ],
        Object.assign({}, BASE_LAYOUT, {
          margin: isMobile ? { l: 70, r: 70, t: 20, b: 20 } : isNarrow ? { l: 70, r: 70, t: 20, b: 25 } : { l: 80, r: 80, t: 20, b: 30 },
          polar: {
            bgcolor: 'rgba(0,0,0,0)',
            radialaxis: {
              range: [0, 1],
              gridcolor: 'rgba(0,0,0,0.08)',
              linecolor: 'rgba(0,0,0,0.08)',
              tickfont: { color: '#666666' }
            },
            angularaxis: {
              gridcolor: 'rgba(0,0,0,0.06)',
              linecolor: 'rgba(0,0,0,0.08)',
              tickfont: { color: '#333333', size: isMobile ? 8 : isNarrow ? 10 : 12 }
            }
          },
          showlegend: !isNarrow,
          legend: {
            orientation: 'h',
            y: 1.12,
            x: 0,
            font: { color: '#555555', size: 12 }
          }
        }),
        { displayModeBar: false, responsive: true, staticPlot: isNarrow, scrollZoom: false }
      );
    }

    function renderTimeline() {
      const timeline = DASHBOARD_DATA.timeline;
      const markerColors = timeline.statuses.map((status) => status === 'keep' ? '#2563eb' : 'rgba(0,0,0,0.18)');
      Plotly.newPlot(
        'timeline-chart',
        [
          {
            type: 'scatter',
            mode: 'markers',
            name: 'Finding',
            x: timeline.iterations,
            y: timeline.scores,
            text: timeline.questions,
            customdata: timeline.categories,
            marker: {
              size: isMobile ? 8 : 12,
              color: markerColors,
              line: { color: 'rgba(0,0,0,0.10)', width: 1 }
            },
            hovertemplate: 'Iteration %{x}<br>Disagreement %{y:.2f}<br>%{customdata}<br>%{text}<extra></extra>'
          },
          {
            type: 'scatter',
            mode: 'lines',
            name: 'Rolling average',
            x: timeline.iterations,
            y: timeline.rolling,
            line: { color: '#2563eb', width: 4, shape: 'spline' },
            hovertemplate: 'Rolling average %{y:.2f}<extra></extra>'
          }
        ],
        Object.assign({}, BASE_LAYOUT, {
          xaxis: Object.assign({}, BASE_LAYOUT.xaxis, { title: { text: 'Iteration', font: { color: '#333333' } } }),
          yaxis: Object.assign({}, BASE_LAYOUT.yaxis, {
            title: { text: 'Disagreement score', font: { color: '#333333' } },
            range: [0, 1]
          }),
          legend: {
            orientation: 'h',
            y: 1.12,
            x: 0,
            font: { color: '#555555' }
          }
        }),
        { displayModeBar: false, responsive: true, staticPlot: isNarrow, scrollZoom: false }
      );
    }

    function renderAxisChart() {
      const axisStats = DASHBOARD_DATA.axis_stats;
      Plotly.newPlot(
        'axis-chart',
        [
          {
            type: 'bar',
            orientation: 'h',
            x: axisStats.map((item) => item.count),
            y: axisStats.map((item) => item.label),
            marker: {
              color: axisStats.map((item) => mixColor('#dbeafe', '#2563eb', item.avg_score)),
              line: { color: 'rgba(0,0,0,0.08)', width: 1.2 }
            },
            hovertemplate: '%{y}<br>Count: %{x}<extra></extra>'
          }
        ],
        Object.assign({}, BASE_LAYOUT, {
          margin: isMobile ? { l: 90, r: 40, t: 10, b: 40 } : isNarrow ? { l: 110, r: 60, t: 10, b: 40 } : { l: 130, r: 100, t: 20, b: 40 },
          xaxis: Object.assign({}, BASE_LAYOUT.xaxis, { title: { text: 'Findings', font: { color: '#333333', size: isMobile ? 11 : 14 } }, fixedrange: true }),
          yaxis: Object.assign({}, BASE_LAYOUT.yaxis, { autorange: 'reversed', tickfont: { size: isMobile ? 9 : isNarrow ? 11 : 14, color: '#333333' }, fixedrange: true })
        }),
        { displayModeBar: false, responsive: true, staticPlot: isNarrow, scrollZoom: false }
      );
    }

    function observeReveals() {
      const observer = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting) {
              entry.target.classList.add('is-visible');
              observer.unobserve(entry.target);
            }
          });
        },
        { threshold: 0.15 }
      );
      document.querySelectorAll('.reveal').forEach((element) => observer.observe(element));
    }

    window.addEventListener('DOMContentLoaded', () => {
      renderMatrix();
      renderRadar();
      renderTimeline();
      renderAxisChart();
      observeReveals();
    });
  </script>
</body>
</html>
"""
    )

    overview = data["overview"]
    return template.safe_substitute(
        hero_stats=_render_stat_cards(overview),
        pair_cards=_render_pair_cards(data["pair_cards"]),
        top_findings=_render_top_findings(data["top_findings"]),
        generated_at=generated_at,
        chart_payload=chart_payload,
        consensus_pct=overview["consensus_pct"],
        early_consensus_pct=overview["early_consensus_pct"],
        late_consensus_pct=overview["late_consensus_pct"],
        total_findings=overview["total_findings"],
        num_inferences=overview["num_inferences"],
        avg_disagreement=overview["avg_disagreement"],
        most_contested=overview["most_contested_category"],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the Divergence Explorer HTML visualization.")
    parser.add_argument(
        "--findings",
        type=Path,
        default=FINDINGS_PATH,
        help=f"Path to findings JSONL (default: {FINDINGS_PATH})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_PATH,
        help=f"Output HTML path (default: {OUTPUT_PATH})",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Generate synthetic demo findings instead of reading findings.jsonl.",
    )
    parser.add_argument(
        "--demo-count",
        type=int,
        default=30,
        help="Number of synthetic demo findings to generate with --demo.",
    )
    args = parser.parse_args()

    findings = generate_demo_findings(args.demo_count) if args.demo else load_findings(args.findings)

    # Dynamically detect models from findings
    global MODELS
    if findings:
        seen = []
        for f in findings:
            for r in f.responses:
                if r.model not in seen:
                    seen.append(r.model)
        if seen:
            MODELS = seen

    data = {
        "overview": compute_overview(findings),
        "pairwise_matrix": compute_pairwise_matrix(findings),
        "category_stats": compute_category_stats(findings),
        "timeline": compute_timeline_data(findings),
        "axis_stats": compute_axis_stats(findings),
        "pair_cards": compute_pair_cards(findings),
        "top_findings": compute_top_findings(findings, limit=8),
    }

    html_output = build_html(data)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html_output, encoding="utf-8")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
