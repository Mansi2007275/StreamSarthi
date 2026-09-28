"""AI Second Opinion. The ONLY file that knows which AI provider we use.

Switch provider with env vars:
  AI_PROVIDER=gemini             AI_MODEL=gemini-2.5-flash (check current model list)
  AI_PROVIDER=openai_compatible  AI_BASE_URL=https://api.groq.com/openai/v1  AI_MODEL=<a Groq vision model>
"""

import base64
import json
import logging
import re
import time

import httpx
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.core.logging import log_event
from app.models.schemas import AIOpinion, Indicator

logger = logging.getLogger("streamsaathi")

PROMPT = """You help citizen scientists assess urban stream health.
You give a SECOND OPINION only. A human makes the final decision.

Indicator: {label}
Question: {help}
Scale: {lo}-{hi}. Labels (in order): {labels}

Judge ONLY what is visible in the photo. If the photo is unclear, not of water,
or this indicator cannot be judged from it, set can_assess=false and confidence low.

Return ONLY JSON, no markdown:
{{"suggested_score": int|null, "confidence": 0-1,
  "visible_evidence": ["...", "..."], "reason": "one simple sentence",
  "can_assess": true|false, "retake_tip": ""}}"""

FALLBACK = AIOpinion(reason="AI opinion unavailable right now", can_assess=False)


def build_prompt(ind: Indicator) -> str:
    lo, hi = ind.scale
    labels = ", ".join(f"{lo + i}={lbl}" for i, lbl in enumerate(ind.scale_labels))
    return PROMPT.format(label=ind.label, help=ind.help.get("en", ""), lo=lo, hi=hi, labels=labels)


def parse_opinion(raw: str, ind: Indicator) -> AIOpinion:
    """Turn raw model text into a validated AIOpinion. Raises on garbage."""
    clean = raw.replace("```json", "").replace("```", "").strip()
    if not clean.startswith("{"):
        m = re.search(r"\{.*\}", clean, re.DOTALL)
        if not m:
            raise ValueError("no JSON object in model output")
        clean = m.group(0)
    op = AIOpinion.model_validate(json.loads(clean))
    lo, hi = ind.scale
    if op.suggested_score is not None and not lo <= op.suggested_score <= hi:
        op.suggested_score, op.can_assess = None, False
    if not op.can_assess:
        op.suggested_score = None
    return op


async def _call_gemini(image: bytes, prompt: str, s: Settings) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{s.ai_model}:generateContent"
    body = {
        "contents": [
            {
                "parts": [
                    {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(image).decode()}},
                    {"text": prompt},
                ]
            }
        ],
        "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"},
    }
    async with httpx.AsyncClient(timeout=s.ai_timeout_seconds) as client:
        r = await client.post(url, json=body, headers={"x-goog-api-key": s.ai_api_key})
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]


async def _call_openai_compatible(image: bytes, prompt: str, s: Settings) -> str:
    url = f"{s.ai_base_url.rstrip('/')}/chat/completions"
    data_uri = "data:image/jpeg;base64," + base64.b64encode(image).decode()
    body = {
        "model": s.ai_model,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_uri}},
                ],
            }
        ],
    }
    async with httpx.AsyncClient(timeout=s.ai_timeout_seconds) as client:
        r = await client.post(url, json=body, headers={"Authorization": f"Bearer {s.ai_api_key}"})
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


async def call_vision_model(image: bytes, prompt: str, s: Settings) -> str:
    if s.ai_provider == "openai_compatible":
        return await _call_openai_compatible(image, prompt, s)
    return await _call_gemini(image, prompt, s)


async def get_opinion(image_bytes: bytes, ind: Indicator, settings: Settings | None = None) -> AIOpinion:
    """Never raises. On any failure returns FALLBACK so the user flow is never blocked."""
    s = settings or get_settings()
    if not s.ai_api_key:
        return FALLBACK.model_copy(update={"reason": "AI not configured (AI_API_KEY missing)"})
    start = time.perf_counter()
    try:
        raw = await call_vision_model(image_bytes, build_prompt(ind), s)
        op = parse_opinion(raw, ind)
        log_event("ai_opinion", ok=True, indicator=ind.id, ms=round((time.perf_counter() - start) * 1000))
        return op
    except (httpx.HTTPError, KeyError, IndexError, ValueError, ValidationError, json.JSONDecodeError):
        logger.exception("ai_opinion_failed")
        log_event("ai_opinion", ok=False, indicator=ind.id, ms=round((time.perf_counter() - start) * 1000))
        return FALLBACK.model_copy()
