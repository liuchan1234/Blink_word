"""
Blink.World — Native Reaction Handler
Silently records Telegram's built-in message reactions.
These are tracked separately from our custom inline button reactions.
"""

import logging

from app.database import get_pool
from app.services.post_service import get_post_by_message

logger = logging.getLogger(__name__)


async def handle_native_reaction(reaction_update: dict):
    """
    Handle message_reaction update from Telegram.
    Structure:
    {
        "chat": {"id": ...},
        "message_id": ...,
        "user": {"id": ...},
        "date": ...,
        "old_reaction": [...],
        "new_reaction": [{"type": "emoji", "emoji": "👍"}, ...]
    }
    """
    chat_id = reaction_update.get("chat", {}).get("id")
    message_id = reaction_update.get("message_id")
    new_reactions = reaction_update.get("new_reaction", [])

    if not chat_id or not message_id:
        return

    # Find which post this message belongs to
    post_id = await get_post_by_message(chat_id, message_id)
    if not post_id:
        logger.debug("Native reaction on unknown message %d in chat %d", message_id, chat_id)
        return

    # Aggregate all current reactions on this message
    # Telegram sends the full new_reaction list for the user, not a delta.
    # We store aggregate counts per emoji per post.
    pool = get_pool()
    async with pool.acquire() as conn:
        for reaction in new_reactions:
            if reaction.get("type") != "emoji":
                continue
            emoji = reaction.get("emoji", "")
            if not emoji:
                continue

            await conn.execute(
                """
                INSERT INTO native_reactions (post_id, message_id, chat_id, emoji, count, updated_at)
                VALUES ($1, $2, $3, $4, 1, NOW())
                ON CONFLICT (post_id, emoji)
                DO UPDATE SET count = native_reactions.count + 1, updated_at = NOW()
                """,
                post_id, message_id, chat_id, emoji,
            )

    logger.debug("Recorded %d native reactions for post %s", len(new_reactions), post_id)
