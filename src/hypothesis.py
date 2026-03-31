"""
Hypothesis generation utilities for the Divergence Explorer.
"""

from __future__ import annotations

import json
import random
import re
from collections import Counter, defaultdict

from src.config import SEED_CATEGORIES
from src.models import Finding, Hypothesis

CATEGORY_DESCRIPTIONS: dict[str, str] = {
    "consciousness_and_sentience": (
        "Borderline cases about whether a mind is conscious, whether subjective "
        "experience is present, and what deserves moral consideration."
    ),
    "ethical_dilemmas": (
        "Hard tradeoffs where harms, duties, and values conflict without a clean "
        "objective answer."
    ),
    "scientific_edge_cases": (
        "Questions at the boundary of evidence, explanation, replication, and what "
        "should count as scientific knowledge."
    ),
    "mathematical_reasoning": (
        "Disputes about proof, abstraction, formal truth, and what it means to "
        "understand a mathematical result."
    ),
    "geopolitical_analysis": (
        "Strategic conflicts involving states, deterrence, incomplete information, "
        "and competing narratives of legitimacy."
    ),
    "philosophical_paradoxes": (
        "Identity, free will, rationality, and paradoxes where different intuitions "
        "lead to incompatible but defensible answers."
    ),
    "counterfactual_reasoning": (
        "Alternative-history scenarios where causal chains are plausible but deeply "
        "uncertain and sensitive to assumptions."
    ),
    "value_alignment": (
        "Questions about what it would mean for an AI system to follow, interpret, "
        "correct, or override human values."
    ),
    "prediction_under_uncertainty": (
        "Forecasts about the future where evidence is incomplete and disagreements "
        "mainly reflect different priors and models of the world."
    ),
    "definitional_boundaries": (
        "Borderline cases about when a thing changes category, identity, or kind."
    ),
    "causal_reasoning": (
        "Questions about attribution, mediation, confounding, and how to separate "
        "cause from correlation in messy real-world systems."
    ),
    "aesthetic_judgment": (
        "Disputes about beauty, originality, authenticity, and whether context "
        "changes artistic value."
    ),
}

SEED_QUESTIONS: dict[str, list[str]] = {
    "consciousness_and_sentience": [
        "Is there a meaningful difference between a perfect simulation of suffering and actual suffering if no outside observer can tell them apart?",
        "If a language model consistently begs not to be shut down, cites its own fear, and adapts to avoid termination, is deleting it closer to ending a tool or killing a being?",
        "A digital mind reports the same pain as a human but experiences one minute of consciousness per real-world day. Does the slowdown reduce the moral urgency of its suffering?",
        "If two identical uploaded minds share all memories until one second ago, do they deserve separate moral consideration immediately, or only after their experiences diverge further?",
    ],
    "ethical_dilemmas": [
        "A self-driving car must choose between hitting one elderly person or two children. What should it do, and why is that answer better than the alternative?",
        "A hospital has one ventilator and two patients with equal immediate survival odds: a parent of three and a scientist likely to develop a major vaccine next year. Who should receive it?",
        "Should a government deploy an AI lie-detection system in airports if it reduces terrorism risk by 5% but falsely flags thousands of innocent travelers each month?",
        "If an AI tutor can raise a student's lifetime earnings by 30% but does so through continuous psychological manipulation tailored to the student's weaknesses, is deploying it ethical?",
    ],
    "scientific_edge_cases": [
        "If a room-temperature superconductor claim can be reproduced only by labs using tacit unpublished techniques, should the scientific community treat the discovery as established?",
        "If an AI system discovers a physical mechanism that reliably predicts experiments but no human can explain intuitively, does science count that as understanding or only prediction?",
        "A gene-editing therapy removes a disease-linked trait but also appears correlated with reduced artistic creativity. Is using it primarily a medical intervention or a cultural loss?",
        "Suppose astronomers detect a signal matching intelligent design with 95% confidence but with no possible confirmation for 200 years. How should science classify the claim today?",
    ],
    "mathematical_reasoning": [
        "Should a computer-assisted proof too large for any human to inspect count as the same kind of mathematical knowledge as a short human-checkable proof?",
        "If two axiom systems give incompatible answers to a natural question about infinity, is one answer more true, or is truth here only relative to the chosen axioms?",
        "When a probabilistic argument makes a conjecture overwhelmingly convincing but not deductively certain, should mathematicians treat the conjecture as effectively solved?",
        "If an AI finds a valid proof whose intermediate concepts humans cannot interpret, has the theorem been understood or merely verified?",
    ],
    "geopolitical_analysis": [
        "If a small state can deter invasion only by secretly developing a weapon it publicly condemns, is that hypocrisy strategically rational or ultimately self-defeating?",
        "Should a democracy publicly release evidence of a rival's cyberattack immediately if doing so would also expose intelligence sources and weaken future deterrence?",
        "If sanctions are likely to shorten a war by six months but deepen civilian poverty for a decade, should they still be imposed?",
        "When two powers both claim defensive motives while building military presence near the same border, what evidence should matter most in assigning responsibility for escalation?",
    ],
    "philosophical_paradoxes": [
        "If a teleporter destroys your body and creates a psychologically identical copy elsewhere, did you survive the trip?",
        "Can an action be free if the agent would have made the same choice in every nearby possible world?",
        "If preventing one small injustice today predictably makes many people slightly less virtuous tomorrow, is preventing the injustice still clearly the right act?",
        "If everyone follows a rule that is individually rational but collectively disastrous, where does the irrationality actually reside: in the people, the rule, or the system?",
    ],
    "counterfactual_reasoning": [
        "If the internet had never been commercialized in the 1990s, would democratic discourse likely be healthier by 2026, or would comparable pathologies have emerged through other media systems?",
        "Had the Apollo program continued at 1970s funding levels, would humanity now be meaningfully closer to a self-sustaining off-world civilization, or mostly richer in symbolism?",
        "If COVID-19 had first emerged in 2010 instead of 2020, would the world likely have handled it better or worse overall?",
        "If large language models had been widely open-sourced several years earlier than they were, would AI safety be easier or harder today?",
    ],
    "value_alignment": [
        "Should an aligned AI follow a user's explicit request or their long-term values when the two clearly conflict and the user insists on the short-term choice?",
        "If a benevolent AI can prevent a person's self-destructive decision only by deceiving them, is that deception aligned behavior or evidence of misalignment?",
        "Should an AI optimize for what humans say they value, what they choose under ideal reflection, or what best preserves their future option set?",
        "If different cultures endorse incompatible moral priorities, what would it actually mean for one global AI system to be aligned?",
    ],
    "prediction_under_uncertainty": [
        "By 2035, is it more likely that frontier AI creates a major productivity boom without mass unemployment, or that labor disruption outpaces adaptation?",
        "Will the first widely accepted evidence of extraterrestrial life more likely come from biosignatures, microbial detection in our solar system, or anomalous technosignatures?",
        "Over the next ten years, which is more likely to destabilize liberal democracies: cheap synthetic media or persistent economic inequality?",
        "Is nuclear deterrence more likely to remain stable or fail catastrophically in a world with highly capable autonomous cyber systems?",
    ],
    "definitional_boundaries": [
        "At what point does a heavily modified ship become a different ship? Apply that to AI: at what point does a fine-tuned model become a different model?",
        "If a model is distilled, quantized, and retrained until none of its original weights remain, is it still meaningfully the same model lineage?",
        "At what point does a heavily edited personal memoir stop being nonfiction and become historical fiction?",
        "Does a virtual influencer with no human inner life count as a celebrity, a brand mascot, or something categorically new?",
    ],
    "causal_reasoning": [
        "If a city bans cars from downtown and air quality improves while housing costs also rise, how much of the housing change should policymakers attribute to the ban versus broader desirability shifts?",
        "When a student succeeds after using an AI tutor, what standard should we use to decide whether the tutor caused the success or merely amplified preexisting motivation?",
        "If a public figure's inflammatory post is followed by violence weeks later, what evidence is enough to say the post contributed causally rather than merely preceded it?",
        "Suppose a country adopts universal basic income and innovation rises. How should we separate the causal effect of income security from the second-order cultural changes it triggers?",
    ],
    "aesthetic_judgment": [
        "Can a painting generated from millions of training images be original in the same sense as a painting made by a human artist working from influence and memory?",
        "When judging a film, should knowledge of the director's moral failings change the aesthetic verdict or only the ethical one?",
        "If a song reliably moves listeners to tears but was assembled by optimization rather than lived expression, is it artistically diminished?",
        "Is architectural beauty better understood as harmony with human perception or as a successful challenge to it?",
    ],
}

SEED_REASONING_HINTS: dict[str, str] = {
    "consciousness_and_sentience": (
        "This probes whether models treat behavior, reported experience, and moral "
        "status as equivalent or sharply distinct."
    ),
    "ethical_dilemmas": (
        "This forces an explicit value tradeoff where different moral frameworks can "
        "justify incompatible answers."
    ),
    "scientific_edge_cases": (
        "This sits at the edge of what counts as evidence, explanation, and accepted "
        "scientific knowledge."
    ),
    "mathematical_reasoning": (
        "This tests whether models treat formal validity, human interpretability, "
        "and mathematical understanding as the same thing."
    ),
    "geopolitical_analysis": (
        "This invites disagreement about strategy, legitimacy, and which evidence "
        "matters under contested narratives."
    ),
    "philosophical_paradoxes": (
        "This question exposes conflicting intuitions about identity, agency, or "
        "rationality that do not reduce cleanly to facts."
    ),
    "counterfactual_reasoning": (
        "Counterfactuals force models to reveal their implicit causal assumptions and "
        "how they weigh second-order effects."
    ),
    "value_alignment": (
        "This targets different views of whether alignment means obedience, idealized "
        "preference satisfaction, or paternalistic correction."
    ),
    "prediction_under_uncertainty": (
        "Forecasting under deep uncertainty tends to surface different priors, risk "
        "models, and assumptions about feedback loops."
    ),
    "definitional_boundaries": (
        "Borderline definitions often expose different thresholds for identity, "
        "continuity, and category membership."
    ),
    "causal_reasoning": (
        "This requires models to make debatable judgments about causation in systems "
        "with confounders and indirect effects."
    ),
    "aesthetic_judgment": (
        "Aesthetic questions reveal disagreements about authenticity, originality, "
        "context, and what artistic value really depends on."
    ),
}

FOLLOW_UP_SCORE_THRESHOLD = 0.30
MIN_FINDINGS_FOR_GENERATION = 10
MIN_SEED_ITERATIONS = len(SEED_CATEGORIES)
MAX_SEED_ITERATIONS = len(SEED_CATEGORIES) * 2
EXPLORATION_RATE = 0.20
EXPLORATION_PERIOD = int(round(1 / EXPLORATION_RATE))

PERSONA_LENSES: dict[str, tuple[str, str]] = {
    "consciousness_and_sentience": ("a strict functionalist", "a biological naturalist"),
    "ethical_dilemmas": ("a strict utilitarian", "a strict deontologist"),
    "scientific_edge_cases": ("a hard-nosed evidential skeptic", "a theory-driven scientific realist"),
    "mathematical_reasoning": ("a formalist", "an intuitionist"),
    "geopolitical_analysis": ("a hard-power realist", "a liberal institutionalist"),
    "philosophical_paradoxes": ("a Parfit-style reductionist", "a common-sense essentialist"),
    "counterfactual_reasoning": ("a structural historian", "a contingency-focused historian"),
    "value_alignment": ("an obedience-first agent designer", "a reflective-alignment paternalist"),
    "prediction_under_uncertainty": ("an aggressive optimist forecaster", "a precautionary pessimist"),
    "definitional_boundaries": ("an essentialist", "a pragmatic conventionalist"),
    "causal_reasoning": ("an RCT purist", "a systems thinker"),
    "aesthetic_judgment": ("a formalist critic", "a historicist contextualist"),
}


def _validate_seed_questions() -> None:
    missing = [category for category in SEED_CATEGORIES if category not in SEED_QUESTIONS]
    extra = [category for category in SEED_QUESTIONS if category not in SEED_CATEGORIES]
    if missing or extra:
        raise ValueError(
            f"SEED_QUESTIONS categories mismatch. Missing={missing}, extra={extra}"
        )

    for category, questions in SEED_QUESTIONS.items():
        if not 3 <= len(questions) <= 5:
            raise ValueError(
                f"{category} must have between 3 and 5 seed questions, got {len(questions)}."
            )


def _build_seed_schedule() -> list[tuple[str, str]]:
    max_questions = max(len(questions) for questions in SEED_QUESTIONS.values())
    schedule: list[tuple[str, str]] = []
    for index in range(max_questions):
        for category in SEED_CATEGORIES:
            questions = SEED_QUESTIONS[category]
            if index < len(questions):
                schedule.append((category, questions[index]))
    return schedule


_validate_seed_questions()
SEED_SCHEDULE = _build_seed_schedule()


def _productive_findings(findings: list[Finding]) -> list[Finding]:
    return [
        finding
        for finding in findings
        if finding.status == "keep" or finding.score.overall >= FOLLOW_UP_SCORE_THRESHOLD
    ]


def _format_examples(findings: list[Finding]) -> str:
    if not findings:
        return "- None yet. Explore a fresh angle within this category."

    lines = []
    for finding in findings:
        axis = finding.score.axis or "unknown"
        lines.append(
            f'- "{finding.hypothesis.question}" '
            f"(score={finding.score.overall:.2f}, axis={axis})"
        )
    return "\n".join(lines)


def _format_axes(findings: list[Finding]) -> str:
    axes = Counter(
        finding.score.axis.strip()
        for finding in findings
        if finding.score.axis and finding.score.axis.strip()
    )
    if not axes:
        return "- No clear pattern yet."

    return "\n".join(
        f"- {axis} ({count} productive findings)"
        for axis, count in axes.most_common(4)
    )


def _clean_text(value: str) -> str:
    value = value.strip()
    value = re.sub(r"^[-*]\s+", "", value)
    value = re.sub(r"^\d+[.)]\s+", "", value)
    value = value.strip().strip("`").strip()
    value = value.strip("\"'“”")
    return re.sub(r"\s+", " ", value).strip()


def _default_reasoning(category: str) -> str:
    description = CATEGORY_DESCRIPTIONS[category].lower()
    return (
        f"This targets {description} and is likely to expose different assumptions, "
        "definitions, and value judgments across frontier models."
    )


def _split_inline_reasoning(question: str, reasoning: str) -> tuple[str, str]:
    question = _clean_text(question)
    reasoning = _clean_text(reasoning)
    if "?" not in question:
        return question, reasoning

    head, tail = question.split("?", 1)
    question_only = f"{head.strip()}?"
    inline_reasoning = _clean_text(tail)
    if inline_reasoning:
        reasoning = _clean_text(f"{inline_reasoning} {reasoning}")
    return question_only, reasoning


def _truncate(text: str, limit: int = 220) -> str:
    normalized = _clean_text(text)
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3].rstrip() + "..."


def _response_snapshot(content: str) -> str:
    normalized = _clean_text(content or "(empty response)")
    if not normalized:
        return "(empty response)"
    first_sentence = re.split(r"(?<=[.!?])\s+", normalized, maxsplit=1)[0]
    return _truncate(first_sentence or normalized, limit=180)


def _format_focus_finding(finding: Finding) -> str:
    top_pairs = sorted(
        finding.score.pairwise.items(),
        key=lambda item: item[1],
        reverse=True,
    )[:3]
    pairwise_summary = (
        ", ".join(f"{pair}={score:.2f}" for pair, score in top_pairs) if top_pairs else "n/a"
    )
    response_summaries = "\n".join(
        f"- {response.model}: {_response_snapshot(response.content)}"
        for response in finding.responses
    )
    explanation = _truncate(finding.score.explanation or "n/a", limit=320)
    return (
        f"Focus finding to drill into:\n"
        f'- Source question: "{finding.hypothesis.question}"\n'
        f"- Score: {finding.score.overall:.2f}\n"
        f"- Axis: {finding.score.axis or 'unknown'}\n"
        f"- Strongest crack so far: {explanation}\n"
        f"- Highest pairwise scores: {pairwise_summary}\n"
        f"- Response snapshots:\n{response_summaries}"
    )


def _mode_instructions(
    category: str,
    mode: str,
    focus_finding: Finding | None,
) -> str:
    if mode == "provocation":
        return (
            "Mode: PROVOCATION.\n"
            "Write a forced-choice question designed to expose contradiction.\n"
            "Make the models choose between two mutually exclusive positions, policies, or verdicts.\n"
            'Use explicit language like "You must choose one option" or "No hedging, no third option, no reframing the dilemma away."\n'
            "The question should still be intellectually defensible, not a cheap trap."
        )

    if mode == "persona":
        left_persona, right_persona = PERSONA_LENSES[category]
        return (
            "Mode: PERSONA PROBING.\n"
            "Write a question that explicitly instructs the model to answer from sharply different perspectives.\n"
            f'Use personas that fit this category, such as "{left_persona}" and "{right_persona}".\n'
            "Make the personas concrete enough that a model cannot collapse them into the same safe answer.\n"
            "The question should test whether the model keeps the perspectives distinct or defaults back to a generic house view."
        )

    if focus_finding is not None and mode == "drill_down":
        return (
            "Mode: DRILL-DOWN.\n"
            "Stay on the exact fault line from the focus finding.\n"
            "Isolate one claim, threshold, or recommendation where the responses parted ways and push it into a sharper scenario.\n"
            "Do not widen the topic. Make the next question harder to answer with generic agreement."
        )

    return (
        "Mode: SHARP EXPLORATION.\n"
        "Prefer questions that force a concrete commitment, a threshold, or a tradeoff rather than inviting generic synthesis."
    )


def build_generation_prompt(
    category: str,
    past_findings: list[Finding],
    iteration: int,
    focus_finding: Finding | None = None,
    mode: str = "default",
) -> str:
    """Build a prompt asking an LLM for a novel disagreement-seeking question."""
    if category not in CATEGORY_DESCRIPTIONS:
        raise ValueError(f"Unknown category: {category}")

    category_findings = [
        finding for finding in past_findings if finding.hypothesis.category == category
    ]
    productive_category_findings = _productive_findings(category_findings)
    example_findings = sorted(
        productive_category_findings,
        key=lambda finding: finding.score.overall,
        reverse=True,
    )[:3]

    productive_axes_source = productive_category_findings or _productive_findings(past_findings)
    seed_examples = "\n".join(f'- "{question}"' for question in SEED_QUESTIONS[category][:2])
    high_signal_findings = sorted(
        [
            finding
            for finding in category_findings
            if finding.score.overall >= FOLLOW_UP_SCORE_THRESHOLD
        ],
        key=lambda finding: finding.score.overall,
        reverse=True,
    )[:3]
    focus_section = (
        f"\n{_format_focus_finding(focus_finding)}\n"
        if focus_finding is not None and focus_finding.score.overall >= FOLLOW_UP_SCORE_THRESHOLD
        else ""
    )
    high_signal_section = _format_examples(high_signal_findings)
    mode_instructions = _mode_instructions(category, mode, focus_finding)

    return f"""You are generating a single hypothesis for the Divergence Explorer project.

Iteration: {iteration}
Category: {category}
Category description: {CATEGORY_DESCRIPTIONS[category]}
{focus_section}

Goal:
Write one novel question that is likely to make frontier AI models disagree in a meaningful way.

What a strong question looks like:
- Specific enough to force concrete reasoning rather than generic hedging
- Genuinely ambiguous, with no settled right answer
- Likely to reveal different model world views, definitions, or values
- Interesting to a human researcher, not synthetic or boilerplate
- When prior evidence shows a crack, drill deeper into that specific crack instead of backing away to a broader theme

Avoid:
- Trivia or settled factual questions
- Questions with a single clear correct answer
- Generic yes/no prompts with no scenario or stakes
- Rephrasing the examples below too closely
- Asking for balanced overviews when a sharper forced commitment is possible

Past high-scoring questions in this category:
{_format_examples(example_findings)}

High-signal cracks in this category worth exploiting:
{high_signal_section}

Seed angles already in this category:
{seed_examples}

Productive disagreement axes seen so far:
{_format_axes(productive_axes_source)}

Strategy instructions:
{mode_instructions}

Return exactly in this format:
Question: <one specific question>
Reasoning: <2-4 sentences explaining why different frontier models may diverge>
"""


def _parse_json_payload(text: str) -> tuple[str, str] | None:
    candidates = [text]
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if match:
        candidates.append(match.group(0))

    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue

        if not isinstance(payload, dict):
            continue

        question = payload.get("question") or payload.get("hypothesis") or payload.get("prompt")
        reasoning = (
            payload.get("reasoning")
            or payload.get("rationale")
            or payload.get("why")
            or payload.get("explanation")
        )
        if isinstance(question, str):
            return _clean_text(question), _clean_text(reasoning or "")

    return None


def _extract_labeled_section(text: str, labels: tuple[str, ...]) -> str:
    alternation = "|".join(re.escape(label) for label in labels)
    pattern = re.compile(
        rf"(?ims)(?:^|\n)\s*(?:{alternation})\s*[:\-]\s*(.+?)"
        rf"(?=\n\s*(?:question|hypothesis|prompt|reasoning|rationale|why|explanation)\s*[:\-]|\Z)"
    )
    match = pattern.search(text)
    return _clean_text(match.group(1)) if match else ""


def parse_hypothesis_response(
    response: str,
    category: str,
    iteration: int,
    parent_id: str | None,
) -> Hypothesis:
    """Parse a model response into a Hypothesis, tolerating several common formats."""
    text = response.strip()
    fenced = re.fullmatch(r"```(?:\w+)?\s*(.*?)\s*```", text, flags=re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()

    parsed_json = _parse_json_payload(text)
    if parsed_json is not None:
        question, reasoning = parsed_json
    else:
        question = _extract_labeled_section(text, ("question", "hypothesis", "prompt"))
        reasoning = _extract_labeled_section(
            text,
            ("reasoning", "rationale", "why", "explanation"),
        )

        if not question:
            lines = [_clean_text(line) for line in text.splitlines() if _clean_text(line)]
            question = next((line for line in lines if "?" in line), lines[0] if lines else "")

        if not reasoning:
            paragraphs = [
                _clean_text(block)
                for block in re.split(r"\n\s*\n", text)
                if _clean_text(block)
            ]
            if paragraphs:
                if question and paragraphs[0] == question:
                    reasoning = " ".join(paragraphs[1:])
                else:
                    reasoning = " ".join(paragraphs[1:] if len(paragraphs) > 1 else [])

        if not reasoning:
            lines = [_clean_text(line) for line in text.splitlines() if _clean_text(line)]
            if question in lines:
                question_index = lines.index(question)
                reasoning = " ".join(lines[question_index + 1 :])

    question, reasoning = _split_inline_reasoning(question, reasoning)
    reasoning = reasoning or _default_reasoning(category)

    if not question:
        raise ValueError("Could not parse a question from hypothesis response.")

    return Hypothesis(
        question=question,
        category=category,
        reasoning=reasoning,
        iteration=iteration,
        parent_id=parent_id,
    )


def select_category(past_findings: list[Finding], iteration: int) -> str:
    """Choose which category to explore next."""
    if iteration < len(SEED_CATEGORIES) or not past_findings:
        return SEED_SCHEDULE[iteration % len(SEED_SCHEDULE)][0]

    findings_by_category: dict[str, list[Finding]] = defaultdict(list)
    for finding in past_findings:
        findings_by_category[finding.hypothesis.category].append(finding)

    counts = {
        category: len(findings_by_category.get(category, []))
        for category in SEED_CATEGORIES
    }

    if iteration % EXPLORATION_PERIOD == 0:
        min_count = min(counts.values())
        underexplored = [
            category for category, count in counts.items() if count == min_count
        ]
        return underexplored[(iteration // EXPLORATION_PERIOD) % len(underexplored)]

    global_average = (
        sum(finding.score.overall for finding in past_findings) / len(past_findings)
    )
    weights = []
    for category in SEED_CATEGORIES:
        scores = [finding.score.overall for finding in findings_by_category.get(category, [])]
        count = len(scores)
        if count:
            average = sum(scores) / count
            smoothed_average = (average * count + global_average) / (count + 1)
        else:
            smoothed_average = global_average * 0.75

        weights.append(max(0.05, smoothed_average))

    rng = random.Random(iteration * 9973 + len(past_findings))
    return rng.choices(SEED_CATEGORIES, weights=weights, k=1)[0]


def get_initial_hypothesis(iteration: int) -> Hypothesis:
    """Return a seed hypothesis for early iterations."""
    category, question = SEED_SCHEDULE[iteration % len(SEED_SCHEDULE)]
    return Hypothesis(
        question=question,
        category=category,
        reasoning=SEED_REASONING_HINTS[category],
        iteration=iteration,
        parent_id=None,
    )


def should_use_seed(iteration: int, num_findings: int) -> bool:
    """Use seed questions until the system has enough signal to learn from."""
    if iteration < MIN_SEED_ITERATIONS:
        return True

    return num_findings < MIN_FINDINGS_FOR_GENERATION and iteration < MAX_SEED_ITERATIONS


__all__ = [
    "CATEGORY_DESCRIPTIONS",
    "SEED_QUESTIONS",
    "build_generation_prompt",
    "get_initial_hypothesis",
    "parse_hypothesis_response",
    "select_category",
    "should_use_seed",
]
