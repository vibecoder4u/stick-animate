from __future__ import annotations

"""Search, download, attribute and mix scene-matched open-licensed sound effects.

Openverse is queried for commercially usable audio. Failed searches never stop a
render: the existing procedural audio remains as a deterministic fallback.
"""
import json
import os
import random
import subprocess
import tempfile
import urllib.parse
import urllib.request
import wave
from array import array
from pathlib import Path
from typing import Any

RATE = 22050
MAX_DOWNLOAD = 20 * 1024 * 1024
EVENT_SEARCH = {
    "forest_ambience": "forest birds insects ambience",
    "flowing_water": "gentle river stream flowing water",
    "birds": "forest birds chirping song",
    "footsteps": "soft footsteps dirt gravel walking",
    "jump_whoosh": "cartoon jump whoosh air swoosh",
    "wood_creak": "large tree wood creaking groaning",
    "wood_impact": "heavy wood branch rolling thud",
    "water_splash": "shallow water splash footsteps",
    "turtle_shuffle": "small animal movement rustling leaves",
    "bear_effort": "bear grunt animal low grunt",
    "metal_clang": "metal clang impact",
    "rain": "rain forest ambience",
    "wind": "wind blowing through trees",
    "door_open": "heavy wooden door creak open",
    "heartbeat": "low heartbeat sound effect",
    "bird_wings": "bird wings flapping",
}

def _request_json(url: str) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": "stick-animate/1.0 (open audio search)"})
    with urllib.request.urlopen(req, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))

def _download(url: str, target: Path) -> bool:
    req = urllib.request.Request(url, headers={"User-Agent": "stick-animate/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=25) as response, target.open("wb") as out:
            total = 0
            while True:
                chunk = response.read(256 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_DOWNLOAD:
                    raise ValueError("sound file exceeds 20 MB safety limit")
                out.write(chunk)
        return target.exists() and target.stat().st_size > 1024
    except Exception:
        target.unlink(missing_ok=True)
        return False

def search_openverse(event: str, cache_dir: Path) -> dict[str, Any] | None:
    """Return one validated, commercially licensed sound, cached as mono WAV."""
    query = EVENT_SEARCH.get(event)
    if not query:
        return None
    cache_dir.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() else "-" for c in event).strip("-")
    wav_path = cache_dir / (safe + ".wav")
    metadata_path = cache_dir / (safe + ".json")
    if wav_path.exists() and wav_path.stat().st_size > 1024 and metadata_path.exists():
        return json.loads(metadata_path.read_text(encoding="utf-8"))
    params = urllib.parse.urlencode({"q": query, "page_size": 8, "license_type": "commercial"})
    endpoint = "https://api.openverse.org/v1/audio/?" + params
    try:
        payload = _request_json(endpoint)
        results = payload.get("results", [])
    except Exception:
        return None
    candidates = []
    for item in results:
        url = item.get("url")
        license_code = str(item.get("license", "")).lower()
        if not url or license_code not in {"cc0", "by", "by-sa"}:
            continue
        title = str(item.get("title", "")).lower()
        tags = " ".join(str(tag.get("name", "")) for tag in item.get("tags", []) if isinstance(tag, dict)).lower()
        words = set(query.lower().split())
        score = sum(2 for word in words if word in title) + sum(1 for word in words if word in tags)
        candidates.append((score, item))
    candidates.sort(key=lambda pair: pair[0], reverse=True)
    for _, item in candidates:
        source = cache_dir / (safe + ".download")
        if not _download(str(item["url"]), source):
            continue
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-v", "error", "-i", str(source), "-vn", "-ac", "1",
                 "-ar", str(RATE), "-t", "30", "-c:a", "pcm_s16le", str(wav_path)],
                check=True, capture_output=True, timeout=35,
            )
        except Exception:
            source.unlink(missing_ok=True)
            wav_path.unlink(missing_ok=True)
            continue
        source.unlink(missing_ok=True)
        metadata = {
            "event": event, "title": item.get("title", "Untitled sound"),
            "creator": item.get("creator", "Unknown creator"),
            "source_url": item.get("foreign_landing_url"),
            "download_url": item.get("url"),
            "license": item.get("license"),
            "license_version": item.get("license_version"),
            "license_url": item.get("license_url"),
            "attribution": item.get("attribution"),
            "local_file": wav_path.name,
        }
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        return metadata
    return None

def find_and_mix_effects(base_wav: Path, cues: list[dict[str, Any]], duration: float,
                         cache_dir: Path, attribution_path: Path) -> list[dict[str, Any]]:
    """Find unique cue sounds and mix them into the existing dialogue/foley WAV."""
    manifest: list[dict[str, Any]] = []
    assets: dict[str, dict[str, Any] | None] = {}
    for cue in cues:
        event = str(cue.get("event", ""))
        if event not in assets:
            assets[event] = search_openverse(event, cache_dir)
        asset = assets[event]
        if asset:
            manifest.append({**asset, "start": cue["start"], "duration": cue["duration"],
                             "gain": cue.get("gain", 0.32)})
    attribution_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    if not manifest:
        return manifest
    try:
        with wave.open(str(base_wav), "rb") as base:
            if base.getnchannels() != 2 or base.getsampwidth() != 2 or base.getframerate() != RATE:
                return manifest
            frame_count = base.getnframes()
            mixed = array("h")
            mixed.frombytes(base.readframes(frame_count))
        for item in manifest:
            path = cache_dir / item["local_file"]
            with wave.open(str(path), "rb") as src:
                if src.getnchannels() != 1 or src.getsampwidth() != 2 or src.getframerate() != RATE:
                    continue
                samples = array("h")
                samples.frombytes(src.readframes(src.getnframes()))
            if not samples:
                continue
            start = max(0, int(float(item["start"]) * RATE))
            limit = min(frame_count, start + int(float(item["duration"]) * RATE))
            if start >= limit:
                continue
            looping = item["event"] in {"forest_ambience", "flowing_water", "birds", "rain", "wind"}
            gain = float(item.get("gain", 0.32))
            for frame in range(start, limit):
                index = frame - start
                if index >= len(samples):
                    if not looping:
                        break
                    index %= len(samples)
                value = int(samples[index] * gain)
                left = frame * 2
                mixed[left] = max(-32768, min(32767, mixed[left] + value))
                mixed[left + 1] = max(-32768, min(32767, mixed[left + 1] + value))
        temp = base_wav.with_suffix(".mixed.wav")
        with wave.open(str(temp), "wb") as out:
            out.setnchannels(2)
            out.setsampwidth(2)
            out.setframerate(RATE)
            out.writeframes(mixed.tobytes())
        temp.replace(base_wav)
    except Exception:
        # Keep the deterministic base mix if an optional downloaded clip is malformed.
        return manifest
    return manifest
