"""LLM client wrapper (Gemini direct / OpenRouter) with retry & token logging."""
from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Iterator, Optional

import httpx

from .config import Config

log = logging.getLogger("generator.llm")


@dataclass
class Usage:
    """Cumulative token usage. Thread-safe via internal Lock."""

    input_tokens: int = 0
    output_tokens: int = 0
    calls: int = 0
    by_step: dict[str, dict[str, int]] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    def add(self, step: str, in_tok: int, out_tok: int) -> None:
        with self._lock:
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

    def generate_stream(
        self,
        *,
        step: str,
        model: str,
        system: str,
        user: str,
        on_chunk,  # Callable[[str], None] — called for each text chunk
        temperature: float = 0.4,
        max_output_tokens: int = 16384,
        retries: int = 3,
    ) -> str:
        """Generate a completion, streaming chunks to `on_chunk`.

        Returns the final concatenated text once the stream completes.
        Falls back to non-streaming on errors. Token usage is accumulated.
        """
        last_err: Optional[Exception] = None
        for attempt in range(1, retries + 1):
            try:
                if self.cfg.provider == "openrouter":
                    text, in_tok, out_tok = self._stream_openrouter(
                        model=model, system=system, user=user,
                        temperature=temperature, max_output_tokens=max_output_tokens,
                        on_chunk=on_chunk,
                    )
                else:
                    text, in_tok, out_tok = self._stream_gemini(
                        model=model, system=system, user=user,
                        temperature=temperature, max_output_tokens=max_output_tokens,
                        on_chunk=on_chunk,
                    )
                self.usage.add(step, in_tok, out_tok)
                log.info("[%s] (stream) model=%s in=%d out=%d", step, model, in_tok, out_tok)
                return text
            except (httpx.HTTPError, RuntimeError) as e:
                last_err = e
                wait = self._compute_backoff(e, attempt)
                log.warning(
                    "Streaming LLM call failed (step=%s, attempt=%d/%d): %s. Retrying in %ds",
                    step, attempt, retries, e, wait,
                )
                time.sleep(wait)
        # After exhausted streaming retries, fall back to regular non-streaming call
        log.warning("[%s] streaming exhausted retries, falling back to non-streaming", step)
        return self.generate(step=step, model=model, system=system, user=user,
                             temperature=temperature, max_output_tokens=max_output_tokens)

    def _stream_openrouter(
        self, *, model, system, user, temperature, max_output_tokens, on_chunk
    ) -> tuple[str, int, int]:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.cfg.openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/RC6HEX/cascade",
            "X-Title": "Cascade",
        }
        slug = OPENROUTER_MODEL_MAP.get(model, model)
        payload = {
            "model": slug,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_output_tokens,
            "stream": True,
            "usage": {"include": True},  # OpenRouter: ask for usage in final SSE event
        }
        chunks: list[str] = []
        in_tok = 0
        out_tok = 0
        with self._client.stream("POST", url, headers=headers, json=payload) as r:
            if r.status_code != 200:
                raise RuntimeError(f"OpenRouter HTTP {r.status_code}: {r.read()[:500]!r}")
            for line in r.iter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    obj = json.loads(data)
                except json.JSONDecodeError:
                    continue
                # Token usage is in the final chunks
                if obj.get("usage"):
                    u = obj["usage"]
                    in_tok = int(u.get("prompt_tokens", in_tok))
                    out_tok = int(u.get("completion_tokens", out_tok))
                choices = obj.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta", {}) or {}
                piece = delta.get("content") or ""
                if piece:
                    chunks.append(piece)
                    try:
                        on_chunk(piece)
                    except Exception:
                        log.exception("on_chunk callback failed — ignoring")
        text = "".join(chunks)
        if not text:
            raise RuntimeError("OpenRouter stream returned empty content")
        return text, in_tok, out_tok

    def _stream_gemini(
        self, *, model, system, user, temperature, max_output_tokens, on_chunk
    ) -> tuple[str, int, int]:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/"
            f"models/{model}:streamGenerateContent?alt=sse&key={self.cfg.gemini_api_key}"
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
        chunks: list[str] = []
        in_tok = 0
        out_tok = 0
        with self._client.stream("POST", url, json=payload) as r:
            if r.status_code != 200:
                raise RuntimeError(f"Gemini stream HTTP {r.status_code}: {r.read()[:500]!r}")
            for line in r.iter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if not data:
                    continue
                try:
                    obj = json.loads(data)
                except json.JSONDecodeError:
                    continue
                cand = (obj.get("candidates") or [{}])[0]
                parts = (cand.get("content") or {}).get("parts") or []
                for part in parts:
                    piece = part.get("text") or ""
                    if piece:
                        chunks.append(piece)
                        try:
                            on_chunk(piece)
                        except Exception:
                            log.exception("on_chunk callback failed — ignoring")
                u = obj.get("usageMetadata") or {}
                if u:
                    in_tok = int(u.get("promptTokenCount", in_tok))
                    out_tok = int(u.get("candidatesTokenCount", out_tok))
        text = "".join(chunks)
        if not text:
            raise RuntimeError("Gemini stream returned empty content")
        return text, in_tok, out_tok

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
