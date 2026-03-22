"""
Blink.World — AI Client (OpenRouter abstraction)
Unified interface for translation, content generation, and moderation.
Supports multi-provider fallback, retry, concurrency control.
"""

import json
import asyncio
import logging
from datetime import date
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from app.config import get_settings
from app.redis_client import incr_with_ttl, cache_get

logger = logging.getLogger(__name__)


class AIClient:
    """Unified AI interface with retry + fallback + concurrency control."""

    def __init__(self):
        settings = get_settings()
        self._providers = [
            {
                "name": "primary",
                "base_url": settings.AI_API_BASE_URL,
                "api_key": settings.AI_API_KEY,
                "model": settings.AI_MODEL,
            },
            {
                "name": "fallback",
                "base_url": settings.AI_API_BASE_URL,
                "api_key": settings.AI_API_KEY,
                "model": settings.AI_FALLBACK_MODEL,
            },
        ]
        self._daily_limit = settings.AI_DAILY_LIMIT
        self._semaphores: dict[str, asyncio.Semaphore] = {
            p["name"]: asyncio.Semaphore(settings.AI_CONCURRENCY)
            for p in self._providers
        }
        self._http: httpx.AsyncClient | None = None

    async def _get_http(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(timeout=60)
        return self._http

    async def close(self):
        if self._http and not self._http.is_closed:
            await self._http.aclose()

    # ── Public API ──

    async def generate_text(
        self,
        system: str,
        prompt: str,
        max_tokens: int = 1024,
        timeout_s: float = 45.0,
        temperature: float = 0.7,
    ) -> str | None:
        """Generate free-form text. Returns None on total failure."""
        for provider in self._providers:
            for attempt in range(3):
                try:
                    return await self._call(
                        provider, system, prompt, max_tokens, timeout_s, temperature
                    )
                except Exception as e:
                    logger.warning(
                        "AI %s attempt %d failed: %s", provider["name"], attempt + 1, e
                    )
                    if attempt < 2:
                        await asyncio.sleep(1 * (attempt + 1))
        logger.error("All AI providers failed for generate_text")
        return None

    async def generate_json(
        self,
        system: str,
        prompt: str,
        schema: type[BaseModel],
        max_tokens: int = 1024,
        timeout_s: float = 45.0,
        temperature: float = 0.5,
    ) -> dict | None:
        """Generate structured JSON validated against a Pydantic schema."""
        for provider in self._providers:
            for attempt in range(3):
                try:
                    raw = await self._call(
                        provider, system, prompt, max_tokens, timeout_s, temperature
                    )
                    if raw is None:
                        continue
                    cleaned = self._clean_json(raw)
                    validated = schema(**json.loads(cleaned))
                    return validated.model_dump()
                except (json.JSONDecodeError, ValidationError) as e:
                    logger.warning(
                        "AI %s JSON parse attempt %d failed: %s",
                        provider["name"], attempt + 1, e,
                    )
                    if attempt < 2:
                        await asyncio.sleep(1 * (attempt + 1))
                except Exception as e:
                    logger.warning(
                        "AI %s attempt %d failed: %s", provider["name"], attempt + 1, e
                    )
                    if attempt < 2:
                        await asyncio.sleep(1 * (attempt + 1))
        logger.error("All AI providers failed for generate_json")
        return None

    async def translate(
        self, text: str, source_lang: str, target_lang: str
    ) -> str | None:
        """Translate text preserving conversational tone."""
        settings = get_settings()
        system = (
            "You are a translator. Translate the following text naturally, "
            "as if a regular person is chatting with friends. "
            "Preserve emotions, slang, and cultural flavor. "
            "Keep local terms with transliteration + brief explanation in parentheses. "
            "Output ONLY the translated text, nothing else."
        )
        prompt = (
            f"Translate from {source_lang} to {target_lang}:\n\n{text}"
        )
        return await self.generate_text(
            system=system,
            prompt=prompt,
            max_tokens=1024,
            timeout_s=settings.AI_TIMEOUT_TRANSLATE,
            temperature=0.3,
        )

    async def moderate(self, text: str) -> dict | None:
        """Check content for policy violations. Returns {safe: bool, reason: str}."""

        class ModerationResult(BaseModel):
            safe: bool
            reason: str = ""

        settings = get_settings()
        system = (
            "You are a content moderator. Evaluate if the text violates any policies "
            "(hate speech, violence, illegal content, spam, NSFW). "
            "Respond in JSON: {\"safe\": true/false, \"reason\": \"...\"}"
        )
        result = await self.generate_json(
            system=system,
            prompt=f"Evaluate this content:\n\n{text}",
            schema=ModerationResult,
            max_tokens=256,
            timeout_s=settings.AI_TIMEOUT_MODERATE,
            temperature=0.1,
        )
        if result is None:
            # Fail-open: allow content if moderation fails, flag for manual review
            return {"safe": True, "reason": "moderation_unavailable"}
        return result

    # ── Internal ──

    async def _call(
        self,
        provider: dict,
        system: str,
        prompt: str,
        max_tokens: int,
        timeout_s: float,
        temperature: float,
    ) -> str | None:
        """Make a single API call to a provider."""
        # Check daily limit
        today = date.today().isoformat()
        count_key = f"ai_daily:{provider['name']}:{today}"
        count = await incr_with_ttl(count_key, ttl=86400)
        if count > self._daily_limit:
            logger.warning("AI daily limit reached for %s", provider["name"])
            raise RuntimeError(f"Daily limit reached for {provider['name']}")

        sem = self._semaphores[provider["name"]]
        async with sem:
            http = await self._get_http()
            response = await http.post(
                f"{provider['base_url']}/chat/completions",
                headers={
                    "Authorization": f"Bearer {provider['api_key']}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": provider["model"],
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
                timeout=timeout_s,
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            logger.debug(
                "AI %s call success, tokens used: %s",
                provider["name"],
                data.get("usage", {}),
            )
            return content

    @staticmethod
    def _clean_json(raw: str) -> str:
        """Extract JSON from markdown fences or raw text."""
        text = raw.strip()
        # Remove markdown code fences
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first and last line if they are fences
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        # Try to extract {...} or [...]
        for start_char, end_char in [("{", "}"), ("[", "]")]:
            start = text.find(start_char)
            end = text.rfind(end_char)
            if start != -1 and end != -1 and end > start:
                return text[start : end + 1]
        return text


# ── Singleton ──

_ai_client: AIClient | None = None


def get_ai_client() -> AIClient:
    global _ai_client
    if _ai_client is None:
        _ai_client = AIClient()
    return _ai_client


async def close_ai_client():
    global _ai_client
    if _ai_client:
        await _ai_client.close()
        _ai_client = None
