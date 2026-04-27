"""Configuration: env vars, model selection, paths."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Config:
    """Runtime configuration."""

    gemini_api_key: str
    openrouter_api_key: str
    provider: str  # "gemini" | "openrouter"
    model_fast: str
    model_smart: str
    project_root: Path

    @classmethod
    def load(cls) -> "Config":
        provider = os.getenv("LLM_PROVIDER", "gemini").lower()
        gemini_key = os.getenv("GEMINI_API_KEY", "")
        openrouter_key = os.getenv("OPENROUTER_API_KEY", "")

        if provider == "gemini" and not gemini_key:
            raise RuntimeError(
                "GEMINI_API_KEY is missing. Set it in .env or change LLM_PROVIDER."
            )
        if provider == "openrouter" and not openrouter_key:
            raise RuntimeError(
                "OPENROUTER_API_KEY is missing. Set it in .env or change LLM_PROVIDER."
            )

        return cls(
            gemini_api_key=gemini_key,
            openrouter_api_key=openrouter_key,
            provider=provider,
            model_fast=os.getenv("MODEL_FAST", "gemini-2.5-flash"),
            model_smart=os.getenv("MODEL_SMART", "gemini-2.5-pro"),
            project_root=PROJECT_ROOT,
        )


# Per-step model assignment.
# `fast` — light, cheap (use for docs).
# `smart` — heavier, used where quality matters (code, FR with traceability).
STEP_MODELS = {
    "use_cases": "fast",
    "nfr": "fast",
    "fr": "smart",
    "code": "smart",
    "tests": "fast",
    "readme": "fast",
}
