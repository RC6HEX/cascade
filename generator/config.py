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
        provider = os.getenv("LLM_PROVIDER", "openrouter").lower()
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

        # Sensible defaults per provider
        default_fast = (
            "qwen/qwen-2.5-72b-instruct" if provider == "openrouter" else "gemini-2.5-flash"
        )
        default_smart = (
            "deepseek/deepseek-chat-v3-0324" if provider == "openrouter" else "gemini-2.5-pro"
        )

        return cls(
            gemini_api_key=gemini_key,
            openrouter_api_key=openrouter_key,
            provider=provider,
            model_fast=os.getenv("MODEL_FAST", default_fast),
            model_smart=os.getenv("MODEL_SMART", default_smart),
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


# Curated list of models available via OpenRouter, surfaced in the UI's
# Settings panel. Tier is just a hint — the user can pick anything for any slot.
# Pricing is per 1M tokens (input / output), used only for UI display.
OPENROUTER_MODELS = [
    # === DeepSeek (cheap + capable) ===
    {"id": "deepseek/deepseek-chat-v3-0324", "label": "DeepSeek V3", "tier": "smart",
     "price_in": 0.27, "price_out": 1.10, "context": 64000,
     "note": "Очень капабельная и дешёвая модель. Дефолт для кода и ФТ."},
    {"id": "deepseek/deepseek-r1", "label": "DeepSeek R1 (reasoning)", "tier": "smart",
     "price_in": 0.55, "price_out": 2.19, "context": 64000,
     "note": "Reasoning-модель. Дороже, но сильнее в логике."},

    # === Qwen ===
    {"id": "qwen/qwen-2.5-72b-instruct", "label": "Qwen 2.5 72B", "tier": "fast",
     "price_in": 0.13, "price_out": 0.40, "context": 32000,
     "note": "Дёшево и стабильно. Дефолт для документации."},
    {"id": "qwen/qwen-2.5-7b-instruct", "label": "Qwen 2.5 7B (слабая)", "tier": "fast",
     "price_in": 0.04, "price_out": 0.10, "context": 32000,
     "note": "Самая дешёвая. Стресс-тест генератора на слабой модели."},
    {"id": "qwen/qwen-2.5-coder-32b-instruct", "label": "Qwen 2.5 Coder 32B", "tier": "smart",
     "price_in": 0.07, "price_out": 0.16, "context": 32000,
     "note": "Заточен под код."},

    # === Llama ===
    {"id": "meta-llama/llama-3.3-70b-instruct", "label": "Llama 3.3 70B", "tier": "fast",
     "price_in": 0.13, "price_out": 0.40, "context": 128000,
     "note": "Универсальная LLM от Meta."},
    {"id": "meta-llama/llama-3.2-3b-instruct", "label": "Llama 3.2 3B (free tier)", "tier": "fast",
     "price_in": 0.02, "price_out": 0.04, "context": 128000,
     "note": "Самая маленькая. Только для отладки пайплайна."},

    # === Mistral ===
    {"id": "mistralai/mistral-small-3.2-24b-instruct", "label": "Mistral Small 3.2", "tier": "fast",
     "price_in": 0.10, "price_out": 0.30, "context": 96000,
     "note": "Компактная и быстрая."},

    # === MiniMax ===
    {"id": "minimax/minimax-01", "label": "MiniMax-01 (1M context)", "tier": "fast",
     "price_in": 0.20, "price_out": 1.10, "context": 1000000,
     "note": "Длинный контекст до 1M токенов."},

    # === Gemini via OpenRouter ===
    {"id": "google/gemini-2.5-flash", "label": "Gemini 2.5 Flash", "tier": "fast",
     "price_in": 0.30, "price_out": 2.50, "context": 1000000,
     "note": "Хороший баланс цены и качества."},
    {"id": "google/gemini-2.5-pro", "label": "Gemini 2.5 Pro", "tier": "smart",
     "price_in": 1.25, "price_out": 10.00, "context": 1000000,
     "note": "Самое высокое качество, но дороже."},

    # === Anthropic ===
    {"id": "anthropic/claude-3.5-haiku", "label": "Claude 3.5 Haiku", "tier": "smart",
     "price_in": 0.80, "price_out": 4.00, "context": 200000,
     "note": "Стабильно для кода, но дорого."},
]


GEMINI_MODELS = [
    {"id": "gemini-2.5-flash", "label": "Gemini 2.5 Flash", "tier": "fast",
     "price_in": 0.30, "price_out": 2.50, "context": 1000000,
     "note": "Дефолт для документации."},
    {"id": "gemini-2.5-pro", "label": "Gemini 2.5 Pro", "tier": "smart",
     "price_in": 1.25, "price_out": 10.00, "context": 1000000,
     "note": "Дефолт для кода."},
]


def models_for_provider(provider: str) -> list[dict]:
    return OPENROUTER_MODELS if provider == "openrouter" else GEMINI_MODELS
