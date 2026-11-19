"""Talks to the language model (Google Gemini) over its REST API, and times every call.

Same idea as M.IKU's "model cascade": several API keys and several models. If a call fails or takes too long, the
next key is tried, then the next model. If everything fails, LLMError is raised and the dialogue code uses a
ready-made fallback line, so the game never freezes or crashes because of the network.

Keys come from the environment or a .env file next to this project:  GEMINI_API_KEYS=key1,key2
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import httpx

URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DEFAULT_MODELS = "gemini-3.5-flash-lite,gemini-3.5-flash,gemini-2.5-flash"


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
    def __init__(self, keys: list[str] | None = None, models: list[str] | None = None, timeout: float = 7.0, budget: float = 12.0):
        self.keys = keys or [k.strip() for k in (_env("GEMINI_API_KEYS") or _env("GEMINI_API_KEY")).split(",") if k.strip()]
        self.models = models or [m.strip() for m in _env("NPC_MODELS", DEFAULT_MODELS).split(",") if m.strip()]
        self.timeout = timeout  # the longest one request may take
        self.budget = budget    # the longest the player waits for one answer, all tries together
        self.http = httpx.Client()  # one connection, kept open between lines
        self._next_key = 0  # keys take turns, so one key's limit is not hit while the others rest

    def generate(self, system: str, prompt: str, temperature: float = 0.7, max_tokens: int = 300) -> dict:
        """Returns {"text", "model", "latency_ms", "tokens_in", "tokens_out", "attempts"} or raises LLMError."""
        if not self.keys:
            raise LLMError("no API key set (GEMINI_API_KEYS)")
        started, problems = time.perf_counter(), []
        body = {"systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens, "responseMimeType": "application/json"}}
        for model in self.models:
            for _ in range(min(2, len(self.keys))):  # at most two keys per model
                left = self.budget - (time.perf_counter() - started)
                if left < 1.0:  # out of time: the dialogue code answers with a fallback line
                    raise LLMError("; ".join(problems) + "; out of time")
                key = self.keys[self._next_key % len(self.keys)]
                self._next_key += 1
                try:
                    r = self.http.post(URL.format(model=model), json=body, headers={"x-goog-api-key": key}, timeout=min(self.timeout, left))
                    if r.status_code != 200:
                        problems.append(f"{model}: HTTP {r.status_code}")
                        if r.status_code == 404:
                            break  # this model does not exist for us: try the next model, not the next key
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
