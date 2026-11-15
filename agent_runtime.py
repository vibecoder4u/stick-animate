from __future__ import annotations

"""Optional, free-tier-friendly OpenAI-compatible LLM adapter.

No paid dependency is required. Without GROQ_API_KEY the production agents use
their deterministic fallback and the renderer remains fully usable.
"""
import json
import os
import urllib.error
import urllib.request
from typing import Any


class AgentUnavailable(RuntimeError):
    pass


class FreeLLM:
    def __init__(self) -> None:
        self.api_key = os.getenv("GROQ_API_KEY", "").strip()
        self.model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        self.endpoint = os.getenv(
            "LLM_BASE_URL",
            "https://api.groq.com/openai/v1/chat/completions",
        )

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def json_completion(self, system: str, user: str, temperature: float = 0.35) -> dict[str, Any]:
        if not self.available:
            raise AgentUnavailable("No GROQ_API_KEY configured")
        payload = {
            "model": self.model,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": "Bearer " + self.api_key,
                "Content-Type": "application/json",
                "User-Agent": "stick-animate-free-agent-runtime/1.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=75) as response:
                result = json.loads(response.read().decode("utf-8"))
            content = result["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            if not isinstance(parsed, dict):
                raise ValueError("Model response must be a JSON object")
            return parsed
        except (urllib.error.URLError, TimeoutError, KeyError, IndexError, json.JSONDecodeError) as exc:
            raise AgentUnavailable(f"LLM request failed: {exc}") from exc
