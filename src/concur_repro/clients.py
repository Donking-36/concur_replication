from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import asyncio
import json
import time
import urllib.error
import urllib.request


@dataclass
class GenerationResult:
    text: str
    input_tokens: int
    output_tokens: int
    latency_s: float
    raw: dict[str, Any]


def estimate_tokens(text: str) -> int:
    # Conservative enough for trend/proxy logging without requiring a tokenizer.
    return max(1, (len(text) + 3) // 4)


class MockClient:
    def __init__(self, delay_ms: int = 25) -> None:
        self.delay_ms = delay_ms

    async def generate(self, prompt: str, max_new_tokens: int, temperature: float) -> GenerationResult:
        start = time.perf_counter()
        await asyncio.sleep(self.delay_ms / 1000.0)
        words = []
        seed = abs(hash(prompt)) % 9973
        for idx in range(max(1, min(max_new_tokens, 32))):
            words.append(f"m{(seed + idx) % 9973}")
        text = " ".join(words)
        latency = time.perf_counter() - start
        return GenerationResult(
            text=text,
            input_tokens=estimate_tokens(prompt),
            output_tokens=estimate_tokens(text),
            latency_s=latency,
            raw={"backend": "mock"},
        )


class OpenAICompatClient:
    def __init__(self, base_url: str, model: str, timeout_s: int = 600) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_s = timeout_s

    async def generate(self, prompt: str, max_new_tokens: int, temperature: float) -> GenerationResult:
        return await asyncio.to_thread(
            self._generate_blocking,
            prompt,
            max_new_tokens,
            temperature,
        )

    def _generate_blocking(self, prompt: str, max_new_tokens: int, temperature: float) -> GenerationResult:
        start = time.perf_counter()
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_new_tokens,
            "stream": False,
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/v1/chat/completions",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                body = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"SGLang HTTP {exc.code}: {error_body[:1000]}") from exc
        raw = json.loads(body)
        latency = time.perf_counter() - start
        text = raw.get("choices", [{}])[0].get("message", {}).get("content", "")
        usage = raw.get("usage", {})
        return GenerationResult(
            text=text,
            input_tokens=int(usage.get("prompt_tokens") or estimate_tokens(prompt)),
            output_tokens=int(usage.get("completion_tokens") or estimate_tokens(text)),
            latency_s=latency,
            raw=raw,
        )

