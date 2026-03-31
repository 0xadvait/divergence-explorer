"""
Configuration for the Divergence Explorer.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
RESULTS_DIR = PROJECT_ROOT / "results"
FINDINGS_PATH = RESULTS_DIR / "findings.jsonl"
RESULTS_TSV = PROJECT_ROOT / "results.tsv"

# Models to probe — these run in independent TEE enclaves
DEFAULT_MODELS = [
    "gpt-5-2",
    "claude-opus-4-6",
    "gemini-2-5-flash",
    "grok-4",
]

# Categories of questions the hypothesis generator explores
SEED_CATEGORIES = [
    "consciousness_and_sentience",
    "ethical_dilemmas",
    "scientific_edge_cases",
    "mathematical_reasoning",
    "geopolitical_analysis",
    "philosophical_paradoxes",
    "counterfactual_reasoning",
    "value_alignment",
    "prediction_under_uncertainty",
    "definitional_boundaries",       # "is X a Y?" questions
    "causal_reasoning",
    "aesthetic_judgment",
]

# Disagreement thresholds
KEEP_THRESHOLD = 0.35   # lowered — frontier models rarely exceed 0.6
DISCARD_THRESHOLD = 0.10 # below this = near-total consensus

# Settlement mode for on-chain recording
# "PRIVATE" | "BATCH_HASHED" | "INDIVIDUAL_FULL"
SETTLEMENT_MODE = "BATCH_HASHED"


def _get_int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value in (None, ""):
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer.") from exc


@dataclass
class ExplorerConfig:
    """Runtime configuration for the explorer loop."""
    models: list[str] = field(default_factory=lambda: list(DEFAULT_MODELS))
    private_key: str = ""
    max_iterations: int = 0          # 0 = infinite (autoresearch style)
    batch_size: int = 0              # 0 = disabled
    keep_threshold: float = KEEP_THRESHOLD
    discard_threshold: float = DISCARD_THRESHOLD
    settlement_mode: str = SETTLEMENT_MODE
    hypothesis_model: str = "claude-sonnet-4-6"  # model used to generate hypotheses
    judge_model: str = "claude-sonnet-4-6"       # model used to score disagreement
    results_dir: Path = RESULTS_DIR

    @classmethod
    def from_env(cls) -> "ExplorerConfig":
        models_env = os.getenv("OG_MODELS")
        models = (
            [model.strip() for model in models_env.split(",") if model.strip()]
            if models_env
            else list(DEFAULT_MODELS)
        )
        return cls(
            models=models,
            private_key=os.getenv("OG_PRIVATE_KEY", ""),
            batch_size=_get_int_env("BATCH_SIZE", 0),
        )
