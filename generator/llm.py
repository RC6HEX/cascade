"""LLM client wrapper (Gemini direct / OpenRouter) with retry & token logging."""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

import httpx

from .config import Config

log = logging.getLogger("generator.llm")


@dataclass
class Usage:
    """Cumulative token usage."""

    input_tokens: int = 0
    output_tokens: int = 0
    calls: int = 0
    by_step: dict[str, dict[str, int]] = field(default_factory=dict)

    def add(self, step: str, in_tok: int, out_tok: int) -> None:
        self.input_tokens += in_tok
        self.output_tokens += out_tok
        self.calls += 1
        s = self.by_step.setdefault(step, {"in": 0, "out": 0, "calls": 0})
        s["in"] += in_tok
        s["out"] += out_tok
        s["calls"] += 1

    def summary(self) -> str:
        lines = [
            f"  Total calls : {self.calls}",
            f"  Input  tokens: {self.input_tokens:,}",
            f"  Output tokens: {self.output_tokens:,}",
            "  Per-step breakdown:",
        ]
        for step, s in self.by_step.items():
            lines.append(
                f"    {step:<12} calls={s['calls']:<2} in={s['in']:>6,} out={s['out']:>6,}"
            )
        return "\n".join(lines)


# Models in OpenRouter slug form (used only when provider=openrouter)
OPENROUTER_MODEL_MAP = {
    "gemini-2.5-flash": "google/gemini-2.5-flash",
    "gemini-2.5-pro": "google/gemini-2.5-pro",
}


class LLMClient:
    """Thin wrapper over Gemini REST API or OpenRouter."""

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.usage = Usage()
        self._client = httpx.Client(timeout=httpx.Timeout(180.0, connect=15.0))

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "LLMClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ---- public ----
    def generate(
        self,
        *,
        step: str,
        model: str,
        system: str,
        user: str,
        temperature: float = 0.4,
        max_output_tokens: int = 8192,
        retries: int = 4,
    ) -> str:
        """Generate a completion. Returns raw text.

        Retry strategy:
            - Network/timeout errors: exponential backoff (2, 4, 8, 16s)
            - HTTP 429 (rate limit): longer wait (15, 30, 60, 120s)
            - HTTP 5xx: medium wait (5, 10, 20, 40s)
            - Empty content: same as network error
        """
        last_err: Optional[Exception] = None
        for attempt in range(1, retries + 1):
            try:
                if self.cfg.provider == "gemini":
                    text, in_tok, out_tok = self._call_gemini(
                        model=model,
                        system=system,
                        user=user,
                        temperature=temperature,
                        max_output_tokens=max_output_tokens,
                    )
                else:
                    text, in_tok, out_tok = self._call_openrouter(
                        model=model,
                        system=system,
                        user=user,
                        temperature=temperature,
                        max_output_tokens=max_output_tokens,
                    )
                self.usage.add(step, in_tok, out_tok)
                log.info(
                    "[%s] model=%s in=%d out=%d", step, model, in_tok, out_tok
                )
                return text
            except (httpx.HTTPError, httpx.HTTPStatusError, RuntimeError) as e:
                last_err = e
                wait = self._compute_backoff(e, attempt)
                log.warning(
                    "LLM call failed (step=%s, attempt=%d/%d): %s. Retrying in %ds",
                    step, attempt, retries, e, wait,
                )
                time.sleep(wait)
        raise RuntimeError(f"LLM call failed after {retries} retries: {last_err}")

    @staticmethod
    def _compute_backoff(err: Exception, attempt: int) -> int:
        """Pick backoff duration based on error type. attempt is 1-indexed."""
        msg = str(err)
        # Rate limit — wait long
        if "HTTP 429" in msg or "rate limit" in msg.lower() or "rate-limit" in msg.lower():
            return min(15 * (2 ** (attempt - 1)), 120)
        # Server error — medium wait
        if any(f"HTTP 5{c}" in msg for c in ("00", "02", "03", "04", "20")):
            return min(5 * (2 ** (attempt - 1)), 40)
        # Default — exponential backoff
        return min(2 ** attempt, 16)

    # ---- providers ----
    def _call_gemini(
        self,
        *,
        model: str,
        system: str,
        user: str,
        temperature: float,
        max_output_tokens: int,
    ) -> tuple[str, int, int]:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/"
            f"models/{model}:generateContent?key={self.cfg.gemini_api_key}"
        )
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_output_tokens,
                "responseMimeType": "text/plain",
            },
        }
        r = self._client.post(url, json=payload)
        if r.status_code != 200:
            raise RuntimeError(f"Gemini HTTP {r.status_code}: {r.text[:500]}")
        data = r.json()

        candidates = data.get("candidates") or []
        if not candidates:
            raise RuntimeError(f"Gemini empty candidates: {json.dumps(data)[:500]}")
        cand = candidates[0]
        # Check finish reason for blocked content
        finish = cand.get("finishReason", "")
        parts = cand.get("content", {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts)
        if not text:
            raise RuntimeError(
                f"Gemini empty text (finishReason={finish}): {json.dumps(data)[:500]}"
            )
        usage = data.get("usageMetadata", {}) or {}
        return (
            text,
            int(usage.get("promptTokenCount", 0)),
            int(usage.get("candidatesTokenCount", 0)),
        )

    def _call_openrouter(
        self,
        *,
        model: str,
        system: str,
        user: str,
        temperature: float,
        max_output_tokens: int,
    ) -> tuple[str, int, int]:
        slug = OPENROUTER_MODEL_MAP.get(model, model)
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.cfg.openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/autonomous-team",
            "X-Title": "Autonomous Code Generator",
        }
        payload = {
            "model": slug,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_output_tokens,
        }
        r = self._client.post(url, headers=headers, json=payload)
        if r.status_code != 200:
            raise RuntimeError(f"OpenRouter HTTP {r.status_code}: {r.text[:500]}")
        data = r.json()
        choice = (data.get("choices") or [{}])[0]
        text = choice.get("message", {}).get("content", "") or ""
        if not text:
            raise RuntimeError(f"OpenRouter empty content: {json.dumps(data)[:500]}")
        usage = data.get("usage", {}) or {}
        return (
            text,
            int(usage.get("prompt_tokens", 0)),
            int(usage.get("completion_tokens", 0)),
        )
