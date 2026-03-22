"""
Blink.World — Translation Service

Three translation paths (from PRD §5.2):
1. Hot pre-translate: posts with high engagement in first hour → auto-translate to all langs
2. On-demand: user sees uncached content → real-time translate → cache for reuse
3. AI content: generated directly in multiple languages at creation time

Cache: Redis translate:{post_id}:{lang} TTL 7d (primary) + DB translations table (persistent)
"""

import logging

from app.ai_client import get_ai_client
from app.redis_client import cache_get, cache_set
from app.database import get_pool

logger = logging.getLogger(__name__)

TRANSLATE_CACHE_TTL = 7 * 86400  # 7 days
SUPPORTED_LANGS = ("zh", "en", "ru", "id", "pt")
LANG_NAMES = {
    "zh": "Chinese",
    "en": "English",
    "ru": "Russian",
    "id": "Indonesian",
    "pt": "Portuguese",
}


async def get_translated_content(post_id: str, content: str, original_lang: str, target_lang: str) -> str:
    """
    Get translated content. Lookup: same lang → Redis → DB → AI → fallback original.
    """
    if original_lang == target_lang or target_lang not in SUPPORTED_LANGS:
        return content

    cache_key = f"translate:{post_id}:{target_lang}"

    # 1. Redis cache
    cached = await cache_get(cache_key)
    if cached:
        return cached

    # 2. DB fallback
    db_text = await _get_from_db(post_id, target_lang)
    if db_text:
        await cache_set(cache_key, db_text, ttl=TRANSLATE_CACHE_TTL)
        return db_text

    # 3. AI translate
    ai = get_ai_client()
    source_name = LANG_NAMES.get(original_lang, original_lang)
    target_name = LANG_NAMES.get(target_lang, target_lang)
    translated = await ai.translate(content, source_name, target_name)

    if translated and translated.strip():
        translated = translated.strip()
        await cache_set(cache_key, translated, ttl=TRANSLATE_CACHE_TTL)
        await _save_to_db(post_id, target_lang, translated)
        logger.info("Translated post %s: %s→%s (%d chars)", post_id, original_lang, target_lang, len(translated))
        return translated

    # 4. Fallback
    logger.warning("Translation failed for post %s (%s→%s)", post_id, original_lang, target_lang)
    return content


async def pre_translate_hot_post(post_id: str, content: str, original_lang: str):
    """Pre-translate a hot post to all supported languages."""
    for lang in SUPPORTED_LANGS:
        if lang == original_lang:
            continue
        cache_key = f"translate:{post_id}:{lang}"
        if await cache_get(cache_key):
            continue
        await get_translated_content(post_id, content, original_lang, lang)


async def check_hot_post_for_pretranslate(post_id: str):
    """If post < 1 hour old and >= 5 interactions, pre-translate to all languages."""
    from app.database import get_pool
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT content, original_lang,
                   COALESCE((SELECT SUM((value)::int) FROM jsonb_each_text(reactions)), 0) + like_count as total
            FROM posts
            WHERE id = $1 AND created_at > NOW() - INTERVAL '1 hour'
            """,
            post_id,
        )
        if not row or row["total"] < 5:
            return

        await pre_translate_hot_post(post_id, row["content"], row["original_lang"])
        logger.info("Hot post %s pre-translated (interactions=%d)", post_id, row["total"])


# ── DB operations ──

async def _get_from_db(post_id: str, lang: str) -> str | None:
    pool = get_pool()
    try:
        async with pool.acquire() as conn:
            return await conn.fetchval(
                "SELECT translated_text FROM translations WHERE post_id = $1 AND lang = $2",
                post_id, lang,
            )
    except Exception as e:
        logger.warning("DB translation lookup failed: %s", e)
        return None


async def _save_to_db(post_id: str, lang: str, translated_text: str):
    pool = get_pool()
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO translations (post_id, lang, translated_text)
                VALUES ($1, $2, $3)
                ON CONFLICT (post_id, lang) DO UPDATE SET translated_text = $3, created_at = NOW()
                """,
                post_id, lang, translated_text,
            )
    except Exception as e:
        logger.warning("DB translation save failed: %s", e)


async def save_translation(post_id: str, lang: str, translated_text: str):
    """Public API: save a pre-generated translation to both cache and DB."""
    await cache_set(f"translate:{post_id}:{lang}", translated_text, ttl=TRANSLATE_TTL)
    await _save_to_db(post_id, lang, translated_text)
