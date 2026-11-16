from __future__ import annotations

"""Single-call Groq adapter with payload limits, pacing and usage telemetry."""
import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

from groq_governor import before_request, record_response, record_rate_limit, write_metrics

class AgentUnavailable(RuntimeError):
    pass

class FreeLLM:
    def __init__(self) -> None:
        self.api_key = os.getenv("GROQ_API_KEY", "").strip()
        self.model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
        self.endpoint = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1/chat/completions")
        self.max_completion_tokens = max(256, int(os.getenv("GROQ_MAX_COMPLETION_TOKENS", "2500")))

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def json_completion(self, system: str, user: str, temperature: float = 0.35) -> dict[str, Any]:
        if not self.available:
            raise AgentUnavailable("No GROQ_API_KEY configured")
        payload = {
            "model": self.model,
            "temperature": temperature,
            "max_completion_tokens": self.max_completion_tokens,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        try:
            before_request(len(body), max(1, (len(body) + 2) // 3) + self.max_completion_tokens)
            # Retry only transient throttling/server errors, respecting server guidance.
            for attempt in range(3):
                request = urllib.request.Request(
                    self.endpoint, data=body,
                    headers={"Authorization": "Bearer " + self.api_key,
                             "Content-Type": "application/json",
                             "User-Agent": "stick-animate-groq-governor/1.0"},
                    method="POST",
                )
                try:
                    with urllib.request.urlopen(request, timeout=90) as response:
                        result = json.loads(response.read().decode("utf-8"))
                        record_response(result.get("usage"), response.headers, response.status)
                    write_metrics()
                    content = result["choices"][0]["message"]["content"]
                    parsed = json.loads(content)
                    if not isinstance(parsed, dict):
                        raise ValueError("Model response must be a JSON object")
                    return parsed
                except urllib.error.HTTPError as exc:
                    detail = exc.read(2000).decode("utf-8", errors="replace").strip()
                    if exc.code == 429:
                        record_rate_limit()
                    if exc.code in (429, 500, 502, 503, 504) and attempt < 2:
                        retry = exc.headers.get("retry-after")
                        delay = float(retry) if retry and retry.replace(".", "", 1).isdigit() else min(30, 5 * (attempt + 1))
                        time.sleep(max(1, delay))
                        continue
                    record_response(None, exc.headers, exc.code)
                    write_metrics()
                    raise AgentUnavailable(f"LLM request failed: HTTP {exc.code} {exc.reason}: {detail[:1200]}")
            raise AgentUnavailable("LLM request exhausted retry attempts")
        except (urllib.error.URLError, TimeoutError, KeyError, IndexError, json.JSONDecodeError, ValueError) as exc:
            write_metrics()
            if isinstance(exc, AgentUnavailable):
                raise
            raise AgentUnavailable(f"LLM request failed: {exc}") from exc
