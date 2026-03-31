"""
Data models for the Divergence Explorer.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class Hypothesis:
    """A question designed to probe model disagreement."""
    question: str
    category: str
    reasoning: str          # why this question might cause disagreement
    iteration: int = 0
    parent_id: str | None = None  # finding that inspired this hypothesis


@dataclass
class SealedResponse:
    """A single model's TEE-attested response."""
    model: str
    content: str
    tee_signature: str = ""
    tee_request_hash: str = ""
    tee_output_hash: str = ""
    tee_timestamp: str = ""
    tee_id: str = ""
    payment_tx: str = ""        # x402 payment tx hash on Base Sepolia
    latency_ms: float = 0.0

    @property
    def explorer_url(self) -> str:
        """Link to verifiable on-chain proof."""
        if self.payment_tx and self.payment_tx not in ("", "external", "None"):
            return f"https://sepolia.basescan.org/tx/{self.payment_tx}"
        # Link to TEE registry contract on OG explorer — proves this enclave is registered
        return "https://explorer.opengradient.ai/address/0x4e72238852f3c918f4E4e57AeC9280dDB0c80248"


@dataclass
class DisagreementScore:
    """Quantified disagreement between model responses."""
    overall: float                          # 0.0 (full agreement) to 1.0 (total disagreement)
    pairwise: dict[str, float] = field(default_factory=dict)  # "model_a:model_b" -> score
    explanation: str = ""                   # LLM judge's explanation of the disagreement
    axis: str = ""                          # what dimension they disagree on (factual, ethical, definitional, etc.)


@dataclass
class Finding:
    """A complete experimental result — the atomic unit of output."""
    id: str
    hypothesis: Hypothesis
    responses: list[SealedResponse]
    score: DisagreementScore
    status: str                             # "keep" | "review" | "discard"
    timestamp: float = field(default_factory=time.time)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, line: str) -> "Finding":
        d = json.loads(line)
        return cls(
            id=d["id"],
            hypothesis=Hypothesis(**d["hypothesis"]),
            responses=[SealedResponse(**r) for r in d["responses"]],
            score=DisagreementScore(**d["score"]),
            status=d["status"],
            timestamp=d["timestamp"],
        )


def load_findings(path: Path) -> list[Finding]:
    """Load all findings from a JSONL file."""
    if not path.exists():
        return []
    findings = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                findings.append(Finding.from_json(line))
    return findings


def append_finding(path: Path, finding: Finding) -> None:
    """Append a single finding to a JSONL file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(finding.to_json() + "\n")
