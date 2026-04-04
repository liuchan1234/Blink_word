"""
Blink.World — Seed Content Script
Generates initial content pool for all channels.

Usage:
  python -m scripts.seed_content

Requires .env with DATABASE_URL, REDIS_URL, AI_API_KEY set.

Target: 200-300 per channel × 8 channels = 2000+ stories
Channels 2 (每日精选) and 3 (每日话题) are curated, not seeded.
"""

import asyncio
import sys
import os
import logging

# Add parent dir to path so we can import app modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("seed")

# Per-channel target counts (V2 channel IDs — must match models.py)
SEED_PLAN = {
    1: 200,   # 环球旅行 — platform operated, high volume
    3: 250,   # 深夜树洞
    4: 250,   # 沙雕日常
    5: 150,   # 我吃什么
    6: 200,   # 恋爱日记
    7: 250,   # 人间真实
    8: 150,   # 立个Flag
    9: 150,   # 记录此刻
    10: 150,  # 萌宠
    11: 200,  # 我要搞钱
}
# Total: ~1700, plus some buffer for failures → 2000+ after retries


async def main():
    from app.config import get_settings
    from app.database import init_db, close_db
    from app.redis_client import init_redis, close_redis

    settings = get_settings()

    if not settings.DATABASE_URL:
        logger.error("DATABASE_URL not set. Create .env from .env.example first.")
        sys.exit(1)

    if not settings.AI_API_KEY:
        logger.error("AI_API_KEY not set. Need OpenRouter API key for content generation.")
        sys.exit(1)

    # Initialize connections
    logger.info("Connecting to database and Redis...")
    await init_db(settings.DATABASE_URL, min_size=2, max_size=10)

    if settings.REDIS_URL:
        await init_redis(settings.REDIS_URL)
    else:
        logger.warning("REDIS_URL not set — translations won't be cached in Redis")

    # Check current content counts
    from app.database import get_pool
    pool = get_pool()

    async with pool.acquire() as conn:
        for channel_id, target in SEED_PLAN.items():
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM posts WHERE channel_id = $1 AND source = 'ai'",
                channel_id,
            )
            logger.info("Channel %d: %d existing AI posts (target: %d)", channel_id, count, target)

    # Generate content
    from app.services.content_gen_service import batch_generate

    # Image ratio per channel: what % of posts get images
    # 环球旅行=80% (visual channel), 萌宠=60%, others=30%
    IMAGE_RATIOS = {
        1: 0.8,   # 环球旅行 — mostly visual
        3: 0.3,   # 深夜树洞
        4: 0.35,  # 沙雕日常
        5: 0.5,   # 我吃什么 — food is visual
        6: 0.3,   # 恋爱日记
        7: 0.25,  # 人间真实
        8: 0.25,  # 立个Flag
        9: 0.5,   # 记录此刻 — moments are visual
        10: 0.6,  # 萌宠 — visual channel
        11: 0.2,  # 我要搞钱
    }

    total_generated = 0

    for channel_id, target in SEED_PLAN.items():
        # Check how many we already have
        async with pool.acquire() as conn:
            existing = await conn.fetchval(
                "SELECT COUNT(*) FROM posts WHERE channel_id = $1 AND source = 'ai'",
                channel_id,
            )

        needed = max(0, target - existing)
        if needed == 0:
            logger.info("Channel %d: already at target (%d), skipping", channel_id, existing)
            continue

        image_ratio = IMAGE_RATIOS.get(channel_id, 0.3)
        logger.info("Channel %d: generating %d stories (have %d, need %d, image_ratio=%.0f%%)...",
                     channel_id, needed, existing, target, image_ratio * 100)

        post_ids = await batch_generate(channel_id, needed, image_ratio=image_ratio)
        total_generated += len(post_ids)

        logger.info("Channel %d: generated %d stories", channel_id, len(post_ids))

    # Final summary
    logger.info("=" * 50)
    logger.info("Seed complete! Generated %d total stories.", total_generated)

    async with pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM posts")
        ai_total = await conn.fetchval("SELECT COUNT(*) FROM posts WHERE source = 'ai'")
        logger.info("Total posts in DB: %d (AI: %d)", total, ai_total)

        for channel_id in sorted(SEED_PLAN.keys()):
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM posts WHERE channel_id = $1",
                channel_id,
            )
            from app.models import get_channel_name
            name = get_channel_name(channel_id, "zh")
            logger.info("  Channel %d (%s): %d posts", channel_id, name, count)

    # Cleanup
    await close_redis()
    await close_db()
    logger.info("Done!")


if __name__ == "__main__":
    asyncio.run(main())
