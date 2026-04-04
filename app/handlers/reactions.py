"""
Blink.World — Native Reaction Handler
Silently records Telegram's built-in message reactions.
These are tracked separately from our custom inline button reactions.
"""

import logging

from app.services.post_service import get_post_by_message, save_native_reaction

logger = logging.getLogger(__name__)


async def handle_native_reaction(reaction_update: dict):
    """Handle message_reaction update from Telegram."""
    chat_id = reaction_update.get("chat", {}).get("id")
    message_id = reaction_update.get("message_id")
    new_reactions = reaction_update.get("new_reaction", [])

    if not chat_id or not message_id:
        return

    post_id = await get_post_by_message(chat_id, message_id)
    if not post_id:
        logger.debug("Native reaction on unknown message %d in chat %d", message_id, chat_id)
        return

    for reaction in new_reactions:
        if reaction.get("type") != "emoji":
            continue
        emoji = reaction.get("emoji", "")
        if not emoji:
            continue
        await save_native_reaction(post_id, message_id, chat_id, emoji)

    logger.debug("Recorded %d native reactions for post %s", len(new_reactions), post_id)
