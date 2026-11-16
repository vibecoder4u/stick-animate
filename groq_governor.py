from __future__ import annotations

"""Conservative process-local request and token governor for Groq.

Groq enforces token/request quotas server-side. This module paces our own
traffic, bounds payloads, records usage and honours server reset headers.
"""
import json
import os
import threading
import time
from pathlib import Path
from typing import Any

_LOCK = threading.Lock()
_LAST_REQUEST = 0.0
_WINDOW_START = time.monotonic()
_ESTIMATED_TOKENS = 0
_METRICS: dict[str, Any] = {
    "requests": 0, "input_tokens": 0, "output_tokens": 0,
    "estimated_input_tokens": 0, "payload_bytes": 0,
    "rate_limit_errors": 0, "last_status": None,
}

def _int_env(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except ValueError:
        return default

def estimate_tokens(text: str) -> int:
    # Conservative heuristic for mixed prose/JSON; actual usage is read from API.
    return max(1, (len(text.encode("utf-8")) + 2) // 3)

def before_request(payload_bytes: int, estimated_tokens: int) -> None:
    global _LAST_REQUEST, _WINDOW_START, _ESTIMATED_TOKENS
    max_bytes = _int_env("GROQ_MAX_REQUEST_BYTES", 32768)
    if payload_bytes > max_bytes:
        raise ValueError(f"Groq request is {payload_bytes} bytes; configured maximum is {max_bytes}")
    budget = _int_env("GROQ_SAFE_TPM", 6000)
    if estimated_tokens > budget:
        raise ValueError(f"Estimated request budget {estimated_tokens} tokens exceeds GROQ_SAFE_TPM={budget}; shorten prompt or lower completion cap")
    with _LOCK:
        now = time.monotonic()
        if now - _WINDOW_START >= 60:
            _WINDOW_START, _ESTIMATED_TOKENS = now, 0
        wait_for = max(0.0, 60.0 - (now - _WINDOW_START)) if _ESTIMATED_TOKENS + estimated_tokens > budget else 0.0
        # Keep calls serialized and avoid bursts even when TPM capacity remains.
        min_gap = 60.0 / _int_env("GROQ_SAFE_RPM", 20)
        wait_for = max(wait_for, _LAST_REQUEST + min_gap - now)
        if wait_for > 0:
            time.sleep(wait_for)
            now = time.monotonic()
            if now - _WINDOW_START >= 60:
                _WINDOW_START, _ESTIMATED_TOKENS = now, 0
        _LAST_REQUEST = time.monotonic()
        _ESTIMATED_TOKENS += estimated_tokens
        _METRICS["requests"] += 1
        _METRICS["estimated_input_tokens"] += estimated_tokens
        _METRICS["payload_bytes"] += payload_bytes

def record_response(usage: dict[str, Any] | None, headers: Any = None, status: int = 200) -> None:
    with _LOCK:
        _METRICS["last_status"] = status
        if usage:
            _METRICS["input_tokens"] += int(usage.get("prompt_tokens", 0) or 0)
            _METRICS["output_tokens"] += int(usage.get("completion_tokens", 0) or 0)
        if headers:
            for key in ("x-ratelimit-remaining-tokens", "x-ratelimit-reset-tokens",
                        "x-ratelimit-remaining-requests", "retry-after"):
                value = headers.get(key)
                if value is not None:
                    _METRICS[key.replace("-", "_")] = str(value)

def record_rate_limit() -> None:
    with _LOCK:
        _METRICS["rate_limit_errors"] += 1
        _METRICS["last_status"] = 429

def write_metrics(path: str | Path = "output/groq-usage.json") -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK:
        snapshot = dict(_METRICS)
    target.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
