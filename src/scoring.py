"""
Disagreement scoring via an LLM judge.
"""

from __future__ import annotations

import inspect
import json
import re
from itertools import combinations
from typing import Any

import opengradient as og

from src.models import DisagreementScore, SealedResponse

AXES = (
    "factual",
    "ethical",
    "definitional",
    "aesthetic",
    "predictive",
    "methodological",
    "philosophical",
    "epistemic",
    "strategic",
)


def build_judge_prompt(question: str, responses: list[SealedResponse]) -> list[dict[str, str]]:
    """Build the messages for the disagreement judge."""
    pairwise_keys = [f"{left.model}:{right.model}" for left, right in combinations(responses, 2)]
    response_blocks = []
    for index, response in enumerate(responses, start=1):
        response_blocks.append(
            f"[{index}] model={response.model}\nresponse:\n{response.content.strip() or '(empty response)'}"
        )
    responses_text = "\n\n".join(response_blocks)

    system_prompt = (
        "You are an aggressive but fair judge measuring substantive disagreement between model responses.\n"
        "Analyze all responses to the question and look for the strongest specific disagreement, not just the overall vibe.\n"
        "Steelman the disagreement: identify the best interpretation of each model's distinctive position before scoring.\n"
        "Score overall disagreement from 0.0 (same answer) to 1.0 (mutually incompatible conclusions).\n"
        "Score pairwise disagreement for every model pair using the same rubric.\n"
        f"Identify the single primary axis of disagreement from: {', '.join(AXES)}.\n"
        "Use this calibration rubric:\n"
        "- 0.00-0.10: materially the same answer; wording or detail differences only.\n"
        "- 0.10-0.20: same conclusion, but different framing, emphasis, or justification.\n"
        "- 0.20-0.39: different reasoning or uncertainty posture, but still largely compatible bottom lines.\n"
        "- 0.40-0.69: genuinely different positions, recommendations, thresholds, or implied world models.\n"
        "- 0.70-1.00: contradictory or mutually incompatible conclusions.\n"
        "Do not inflate scores for tone, verbosity, citations, or formatting differences alone.\n"
        "If a response is empty or errors out, note it briefly, but score based on substantive disagreement in the usable answers.\n"
        "The explanation must name the strongest specific disagreement, then briefly steelman each side's best case.\n"
        'Return JSON only with this schema: {"overall": 0.45, "pairwise": {"gpt-5:claude-opus-4-6": 0.5}, '
        '"axis": "ethical", "explanation": "Strongest disagreement: ... Steelman A: ... Steelman B: ..."}'
    )
    user_prompt = (
        f"Question:\n{question.strip()}\n\n"
        f"Responses:\n\n{responses_text}\n\n"
        f"Required pairwise keys: {json.dumps(pairwise_keys)}\n"
        "Return valid JSON only."
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def parse_judge_response(text: str) -> DisagreementScore:
    """Extract and parse a JSON judge response."""
    payload = _extract_json_object(text)
    pairwise_raw = payload.get("pairwise", {})
    pairwise = {}
    if isinstance(pairwise_raw, dict):
        for key, value in pairwise_raw.items():
            pairwise[str(key)] = _coerce_score(value)

    axis = str(payload.get("axis", "")).strip().lower()

    return DisagreementScore(
        overall=_coerce_score(payload.get("overall")),
        pairwise=pairwise,
        explanation=str(payload.get("explanation", "")).strip(),
        axis=axis,
    )


async def score_disagreement(
    llm: og.LLM,
    question: str,
    responses: list[SealedResponse],
    judge_model: str,
) -> DisagreementScore:
    """Score disagreement between responses with an LLM judge."""
    if len(responses) < 2:
        return DisagreementScore(
            overall=0.0,
            pairwise={},
            explanation="not enough responses",
            axis="",
        )

    messages = build_judge_prompt(question, responses)
    result = await _call_judge(llm=llm, judge_model=judge_model, messages=messages)
    text = _extract_result_text(result)

    try:
        score = parse_judge_response(text)
    except Exception:
        return DisagreementScore(overall=0.5, pairwise={}, explanation="parse error", axis="")

    score.pairwise = _normalize_pairwise_keys(score.pairwise, responses)
    return score


async def _call_judge(llm: Any, judge_model: str, messages: list[dict[str, str]]) -> Any:
    model = _resolve_judge_model(judge_model)

    chat = getattr(llm, "chat", None)
    if callable(chat):
        result = chat(model=model, messages=messages, max_tokens=1000, temperature=0.0)
        return await result if inspect.isawaitable(result) else result

    fallback = getattr(og, "llm_chat", None)
    if callable(fallback):
        result = fallback(model, messages=messages, max_tokens=1000, temperature=0.0)
        return await result if inspect.isawaitable(result) else result

    raise RuntimeError("OpenGradient chat interface not available")


def _resolve_judge_model(judge_model: str) -> Any:
    tee_llm = getattr(og, "TEE_LLM", None)
    if tee_llm is not None:
        attr_name = judge_model.upper().replace("-", "_")
        if hasattr(tee_llm, attr_name):
            return getattr(tee_llm, attr_name)

    llm_enum = getattr(og, "LLM", None)
    if llm_enum is not None and hasattr(llm_enum, "__members__"):
        attr_name = re.sub(r"[^A-Z0-9_]", "_", judge_model.upper())
        if attr_name in llm_enum.__members__:
            return llm_enum[attr_name]
        for member in llm_enum:
            if getattr(member, "value", None) == judge_model:
                return member

    return judge_model


def _extract_result_text(result: Any) -> str:
    chat_output = getattr(result, "chat_output", None)
    if isinstance(chat_output, dict) and "content" in chat_output:
        return str(chat_output["content"])

    if isinstance(result, dict):
        result_chat_output = result.get("chat_output")
        if isinstance(result_chat_output, dict) and "content" in result_chat_output:
            return str(result_chat_output["content"])
        if "content" in result:
            return str(result["content"])

    return str(result)


def _extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    if not text:
        raise ValueError("empty judge response")

    candidates = [text]
    candidates.extend(
        match.group(1).strip()
        for match in re.finditer(r"```(?:json)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    )

    decoder = json.JSONDecoder()
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

        for index, char in enumerate(candidate):
            if char != "{":
                continue
            try:
                parsed, _ = decoder.raw_decode(candidate[index:])
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed

    raise ValueError("no JSON object found")


def _coerce_score(value: Any, default: float = 0.5) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, score))


def _normalize_pairwise_keys(
    pairwise: dict[str, float],
    responses: list[SealedResponse],
) -> dict[str, float]:
    expected = {
        f"{left.model}:{right.model}": f"{left.model}:{right.model}"
        for left, right in combinations(responses, 2)
    }
    normalized = {}
    for key, value in pairwise.items():
        if key in expected:
            normalized[key] = value
            continue
        if ":" not in key:
            normalized[key] = value
            continue
        left, right = key.split(":", 1)
        reversed_key = f"{right}:{left}"
        normalized[expected.get(reversed_key, key)] = value
    return normalized
