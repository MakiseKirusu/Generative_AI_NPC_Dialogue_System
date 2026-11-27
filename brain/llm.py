"""Talks to the language model (Google Gemini) over its REST API, and times every call.

Same idea as M.IKU's "model cascade": several API keys and several models. If a call fails or takes too long, the
next key is tried, then the next model. A key that answers "too many requests" (HTTP 429) rests for REST_SECONDS for
that model, and one that answers "no such model" (404) is never asked for that model again, so later lines do not
wait on them. If everything fails, LLMError is raised and the dialogue code uses a ready-made fallback line, so the
game never freezes or crashes because of the network.

Keys come from the environment or a .env file next to this project:  GEMINI_API_KEYS=key1,key2
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import httpx

URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
# Measured 25 Nov (median reply, one Bram line): 3.5-flash-lite 0.6 s, 3.1-flash-lite 1.1 s, flash-lite-latest 0.7 s.
# Left out: gemini-3.5-flash (17-19 s, it thinks before answering) and gemini-2.5-flash (no longer offered to new keys).
DEFAULT_MODELS = "gemini-3.5-flash-lite,gemini-3.1-flash-lite,gemini-flash-lite-latest"
REST_SECONDS = 30.0


class LLMError(Exception):
    pass


def _env(name: str, default: str = "") -> str:
    if os.environ.get(name):
        return os.environ[name]
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            key, _, value = line.partition("=")
            if key.strip() == name:
                return value.strip().strip('"').strip("'")
    return default


class GeminiLLM:
    def __init__(self, keys: list[str] | None = None, models: list[str] | None = None, timeout: float = 4.0, budget: float = 9.0):
        self.keys = keys or [k.strip() for k in (_env("GEMINI_API_KEYS") or _env("GEMINI_API_KEY")).split(",") if k.strip()]
        self.models = models or [m.strip() for m in _env("NPC_MODELS", DEFAULT_MODELS).split(",") if m.strip()]
        self.timeout = timeout  # the longest one request may take
        self.budget = budget    # the longest the player waits for one answer, all tries together
        self.http = httpx.Client()  # one connection, kept open between lines
        self._next_key = 0  # keys take turns, so one key's limit is not hit while the others rest
        self._resting: dict[tuple[str, str], float] = {}  # (model, key) → left alone until then ("too many requests", "no such model")

    def _keys_for(self, model: str) -> list[str]:
        """Up to two keys to try this model with, in turn, skipping keys that were just told "too many requests"."""
        now, n = time.monotonic(), len(self.keys)
        order = [self.keys[(self._next_key + i) % n] for i in range(n)]
        self._next_key += 1
        return [k for k in order if self._resting.get((model, k), 0) <= now][:2]

    def generate(self, system: str, prompt: str, temperature: float = 0.7, max_tokens: int = 300) -> dict:
        """Returns {"text", "model", "latency_ms", "tokens_in", "tokens_out", "attempts"} or raises LLMError."""
        if not self.keys:
            raise LLMError("no API key set (GEMINI_API_KEYS)")
        started, problems = time.perf_counter(), []
        config = {"temperature": temperature, "maxOutputTokens": max_tokens, "responseMimeType": "application/json"}
        body = {"systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": prompt}]}], "generationConfig": config}
        for model in self.models:
            keys = self._keys_for(model)
            if not keys:
                problems.append(f"{model}: every key is resting")
            for key in keys:
                left = self.budget - (time.perf_counter() - started)
                if left < 1.0:  # out of time: the dialogue code answers with a fallback line
                    raise LLMError("; ".join(problems) + "; out of time")
                try:
                    if model.startswith("gemini-3"):  # no "thinking" before answering: seconds of waiting for a 3-sentence line
                        body["generationConfig"] = {**config, "thinkingConfig": {"thinkingLevel": "minimal"}}
                    else:
                        body["generationConfig"] = config
                    r = self.http.post(URL.format(model=model), json=body, headers={"x-goog-api-key": key}, timeout=min(self.timeout, left))
                    if r.status_code != 200:
                        problems.append(f"{model}: HTTP {r.status_code}")
                        if r.status_code == 404:  # this model is not offered to this key: never ask it again
                            self._resting[(model, key)] = float("inf")
                            break  # try the next model, not the next key
                        if r.status_code == 429:  # this key's limit for this model: let it rest
                            self._resting[(model, key)] = time.monotonic() + REST_SECONDS
                        continue
                    data = r.json()
                    text = "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"])
                    usage = data.get("usageMetadata", {})
                    return {"text": text, "model": model, "latency_ms": round((time.perf_counter() - started) * 1000),
                            "tokens_in": usage.get("promptTokenCount", 0), "tokens_out": usage.get("candidatesTokenCount", 0),
                            "attempts": len(problems) + 1}
                except (httpx.HTTPError, KeyError, IndexError, ValueError) as e:  # timeouts, no network, an empty or odd answer
                    problems.append(f"{model}: {type(e).__name__}")
        raise LLMError("; ".join(problems))
