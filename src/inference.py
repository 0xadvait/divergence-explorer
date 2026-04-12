"""
TEE-backed LLM inference helpers for the Divergence Explorer.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import opengradient as og

from src.models import SealedResponse


def _enum_member(enum_name: str, member_name: str) -> Any:
    enum_cls = getattr(og, enum_name, None)
    if enum_cls is None:
        return member_name
    return getattr(enum_cls, member_name, member_name)


MODEL_MAP: dict[str, Any] = {
    "gpt-5": _enum_member("TEE_LLM", "GPT_5"),
    "gpt-5-2": _enum_member("TEE_LLM", "GPT_5_2"),
    "gpt-5-mini": _enum_member("TEE_LLM", "GPT_5_MINI"),
    "claude-opus-4-6": _enum_member("TEE_LLM", "CLAUDE_OPUS_4_6"),
    "claude-sonnet-4-6": _enum_member("TEE_LLM", "CLAUDE_SONNET_4_6"),
    "claude-haiku-4-5": _enum_member("TEE_LLM", "CLAUDE_HAIKU_4_5"),
    "gemini-3-pro": _enum_member("TEE_LLM", "GEMINI_3_PRO"),
    "gemini-2-5-flash": _enum_member("TEE_LLM", "GEMINI_2_5_FLASH"),
    "gemini-2-5-flash-lite": _enum_member("TEE_LLM", "GEMINI_2_5_FLASH_LITE"),
    "grok-4": _enum_member("TEE_LLM", "GROK_4"),
    "grok-4-fast": _enum_member("TEE_LLM", "GROK_4_FAST"),
}

SETTLEMENT_MAP: dict[str, Any] = {
    "PRIVATE": _enum_member("x402SettlementMode", "PRIVATE"),
    "BATCH_HASHED": _enum_member("x402SettlementMode", "BATCH_HASHED"),
    "INDIVIDUAL_FULL": _enum_member("x402SettlementMode", "INDIVIDUAL_FULL"),
}


def _error_response(model_name: str, exc: Exception) -> SealedResponse:
    return SealedResponse(model=model_name, content=f"ERROR: {exc}")


def _extract_content(result: Any) -> str:
    chat_output = getattr(result, "chat_output", {})
    if isinstance(chat_output, dict):
        content = chat_output.get("content", "")
    else:
        content = getattr(chat_output, "content", "")
    return str(content or "")


async def init_client(private_key: str) -> og.LLM:
    if not private_key:
        raise ValueError("private_key is required")

    try:
        llm = og.LLM(private_key=private_key)
    except Exception as exc:
        raise RuntimeError(
            "Failed to initialize OpenGradient LLM client. "
            "Check that the installed SDK matches the expected TEE inference API."
        ) from exc

    if not hasattr(llm, "chat") or not hasattr(llm, "ensure_opg_approval"):
        raise RuntimeError(
            "OpenGradient LLM client is missing required TEE inference methods."
        )

    await asyncio.to_thread(llm.ensure_opg_approval, min_allowance=100.0)
    return llm


async def query_model(
    llm: og.LLM,
    model_name: str,
    question: str,
    settlement_mode: str,
) -> SealedResponse:
    model = MODEL_MAP.get(model_name)
    if model is None:
        return SealedResponse(model=model_name, content=f"ERROR: Unsupported model '{model_name}'")

    settlement = SETTLEMENT_MAP.get(settlement_mode.upper())
    if settlement is None:
        return SealedResponse(
            model=model_name,
            content=f"ERROR: Unsupported settlement mode '{settlement_mode}'",
        )

    try:
        result = await llm.chat(
            model=model,
            messages=[{"role": "user", "content": question}],
            max_tokens=500,
            temperature=0.7,
            x402_settlement_mode=settlement,
        )
    except Exception as exc:
        return _error_response(model_name, exc)

    return SealedResponse(
        model=model_name,
        content=_extract_content(result),
        tee_signature=str(getattr(result, "tee_signature", "") or ""),
        tee_request_hash=str(getattr(result, "transaction_hash", "") or ""),
        tee_output_hash=str(getattr(result, "output_hash", "") or ""),
        tee_timestamp=str(getattr(result, "tee_timestamp", "") or ""),
        tee_id=str(getattr(result, "tee_id", "") or ""),
        payment_tx=str(getattr(result, "payment_hash", "") or ""),
    )


async def query_all_models(
    llm: og.LLM,
    question: str,
    model_names: list[str],
    settlement_mode: str,
) -> list[SealedResponse]:
    async def timed_query(model_name: str) -> SealedResponse:
        start = time.perf_counter()
        response = await query_model(llm, model_name, question, settlement_mode)
        response.latency_ms = (time.perf_counter() - start) * 1000
        return response

    return await asyncio.gather(*(timed_query(model_name) for model_name in model_names))


__all__ = [
    "MODEL_MAP",
    "SETTLEMENT_MAP",
    "init_client",
    "query_model",
    "query_all_models",
]
