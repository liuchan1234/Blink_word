"""
Blink.World — Callback Query Handler (Round 3 Full Implementation)
Routes all inline keyboard button presses.
Now includes: publishing flow, group swipe/fav/report, settings.
"""

import logging

from app.telegram_helpers import (
    answer_callback_query, send_message, send_photo,
    edit_message_text, edit_message_reply_markup,
    inline_keyboard, inline_button,
)
from app.services.user_service import get_or_create_user, update_user, get_user
from app.services.publish_service import save_draft, get_draft, clear_draft, publish_draft
from app.i18n import t
from app.models import (
    CHANNELS, USER_CHANNEL_IDS, ALL_CHANNEL_IDS,
    get_channel, get_channel_display,
)

logger = logging.getLogger(__name__)


async def handle_callback(callback_query: dict):
    """Main callback dispatcher."""
    cb_id = callback_query.get("id", "")
    data = callback_query.get("data", "")
    user_tg = callback_query.get("from", {})
    user_id = user_tg.get("id")
    message = callback_query.get("message", {})
    chat = message.get("chat", {})
    chat_id = chat.get("id")
    chat_type = chat.get("type", "private")
    message_id = message.get("message_id")

    if not user_id or not chat_id or not data:
        await answer_callback_query(cb_id)
        return

    is_group = chat_type in ("group", "supergroup")

    # ── Group activation gate ──
    # In groups, user must have /start'd the Bot before interacting.
    # This is both a product decision (grow main Bot user base) and
    # a technical necessity (Bot can't send DMs to non-started users).
    if is_group:
        from app.services.user_service import get_user
        existing_user = await get_user(user_id)
        if existing_user is None:
            # User hasn't started the Bot → prompt them
            from app.config import get_settings
            settings = get_settings()
            bot_link = f"https://t.me/{settings.BOT_USERNAME}?start=from_group_{chat_id}"
            await answer_callback_query(
                cb_id,
                text="Please start the Bot first / 请先启动 Bot 👇",
                show_alert=True,
            )
            # Send a message with a direct link to start the Bot
            await send_message(
                chat_id,
                f"👆 <a href=\"{bot_link}\">Click here to start Blink.World Bot</a> first, then come back!",
                reply_markup=inline_keyboard([[
                    inline_button("🚀 Start Bot", url=bot_link),
                ]]),
            )
            return

    user, _ = await get_or_create_user(user_id, user_tg.get("language_code"))
    lang = user.lang

    try:
        # ── Onboarding ──
        if data.startswith("set_country:"):
            await _handle_set_country(cb_id, chat_id, user_id, data, lang)
        elif data.startswith("set_lang:"):
            await _handle_set_lang(cb_id, chat_id, user_id, data)

        # ── Reactions (Layer 1) ──
        elif data.startswith("react:"):
            await _handle_reaction(cb_id, chat_id, message_id, user_id, data, lang)

        # ── Swipe (Layer 3) ──
        elif data.startswith("swipe:"):
            await _handle_swipe(cb_id, chat_id, message_id, user_id, data, lang, is_group)

        # ── Favorite ──
        elif data.startswith("fav:"):
            if is_group:
                post_id = data.split(":", 1)[1] if ":" in data else ""
                from app.handlers.group_chat import handle_group_favorite
                await handle_group_favorite(cb_id, user_id, post_id, lang)
            else:
                await _handle_favorite(cb_id, user_id, data, lang)

        # ── Report ──
        elif data.startswith("report:"):
            await _handle_report(cb_id, chat_id, message_id, user_id, data, lang, is_group)

        # ── "我也说一个" → start publishing ──
        elif data == "post_also":
            await answer_callback_query(cb_id)
            # Redirect to private chat for publishing
            if is_group:
                from app.config import get_settings
                settings = get_settings()
                hint = "📝 私聊我来投稿吧！" if lang == "zh" else "📝 DM me to share your story!"
                await send_message(
                    chat_id,
                    f"{hint}\n👉 @{settings.BOT_USERNAME}",
                )
            else:
                await _start_publish_flow(chat_id, user_id, user, lang)

        # ── Publishing flow ──
        elif data.startswith("chan:"):
            await _handle_channel_select(cb_id, chat_id, user_id, user, data, lang)
        elif data.startswith("pub:"):
            await _handle_publish_action(cb_id, chat_id, user_id, user, data, lang)

        # ── Admin review ──
        elif data.startswith("adm:"):
            from app.handlers.admin_review import handle_admin_callback
            await handle_admin_callback(cb_id, chat_id, user_id, data)

        # ── Profile sub-pages ──
        elif data.startswith("profile:"):
            await _handle_profile(cb_id, chat_id, user_id, data, lang)

        # ── Settings ──
        elif data.startswith("settings:"):
            await _handle_settings(cb_id, chat_id, message_id, user_id, user, data, lang)
        elif data.startswith("toggle_ch:"):
            await _handle_toggle_channel(cb_id, chat_id, message_id, user_id, user, data, lang)

        else:
            logger.debug("Unknown callback_data: %s", data)
            await answer_callback_query(cb_id)

    except Exception as e:
        logger.error("Callback error data=%s: %s", data, e, exc_info=True)
        await answer_callback_query(cb_id)


# ══════════════════════════════════════════════
# Country Selection
# ══════════════════════════════════════════════

async def _handle_set_country(cb_id: str, chat_id: int, user_id: int, data: str, lang: str):
    country_raw = data.split(":", 1)[1]

    # Use country service to normalize and get flag
    from app.services.country_service import detect_country
    info = await detect_country(country_raw)

    await update_user(user_id, country=info.name_zh, onboard_state="ready")

    display = f"{info.flag} {info.name_zh if lang == 'zh' else info.name_en}"
    await answer_callback_query(cb_id, text=t("country_set", lang, country=display))

    from app.handlers.private_chat import _main_menu_keyboard
    await send_message(chat_id, t("setup_complete", lang), reply_markup=_main_menu_keyboard(lang))


# ══════════════════════════════════════════════
# Language Switch
# ══════════════════════════════════════════════

async def _handle_set_lang(cb_id: str, chat_id: int, user_id: int, data: str):
    from app.i18n import SUPPORTED_LANGUAGES
    new_lang = data.split(":", 1)[1]
    if new_lang not in SUPPORTED_LANGUAGES:
        new_lang = "en"

    await update_user(user_id, lang=new_lang)
    await answer_callback_query(cb_id, text=t("lang_changed", new_lang))

    from app.handlers.private_chat import _main_menu_keyboard
    await send_message(chat_id, t("welcome", new_lang), reply_markup=_main_menu_keyboard(new_lang))


# ══════════════════════════════════════════════
# Emoji Reactions (Layer 1)
# ══════════════════════════════════════════════

async def _handle_reaction(cb_id: str, chat_id: int, message_id: int, user_id: int, data: str, lang: str):
    parts = data.split(":", 2)
    if len(parts) < 3:
        await answer_callback_query(cb_id)
        return

    post_id, emoji = parts[1], parts[2]

    from app.services.post_service import add_reaction, remove_reaction, get_user_reactions, get_post

    existing = await get_user_reactions(user_id, post_id)
    if emoji in existing:
        await remove_reaction(user_id, post_id, emoji)
        await answer_callback_query(cb_id)
    else:
        added = await add_reaction(user_id, post_id, emoji)
        if not added:
            max_text = "每条内容最多 3 个表情" if lang == "zh" else "Max 3 reactions per post"
            await answer_callback_query(cb_id, text=max_text, show_alert=False)
            return
        await answer_callback_query(cb_id)
        # Milestone check is handled inside add_reaction — no duplicate needed

    # Refresh keyboard with updated counts
    post = await get_post(post_id)
    if post and message_id:
        from app.handlers.card_builder import build_card_inline_keyboard, build_group_card_inline_keyboard
        chat_msg = (await _get_chat_type(chat_id))
        if chat_msg in ("group", "supergroup"):
            new_markup = build_group_card_inline_keyboard(post_id, post.get("reactions", {}))
        else:
            new_markup = build_card_inline_keyboard(post_id, post.get("reactions", {}))
        await edit_message_reply_markup(chat_id, message_id, reply_markup=new_markup)


# ══════════════════════════════════════════════
# Swipe (Layer 3) — handles both private and group
# ══════════════════════════════════════════════

async def _handle_swipe(cb_id: str, chat_id: int, message_id: int, user_id: int, data: str, lang: str, is_group: bool):
    parts = data.split(":", 2)
    if len(parts) < 3:
        await answer_callback_query(cb_id)
        return

    post_id, action = parts[1], parts[2]

    if is_group:
        from app.handlers.group_chat import handle_group_swipe
        await handle_group_swipe(cb_id, chat_id, message_id, user_id, post_id, action, lang)
    else:
        # Private inline swipe (shouldn't normally happen — private uses reply keyboard)
        from app.services.post_service import record_swipe
        await record_swipe(user_id, post_id, action)
        await answer_callback_query(cb_id)


# ══════════════════════════════════════════════
# Favorite
# ══════════════════════════════════════════════

async def _handle_favorite(cb_id: str, user_id: int, data: str, lang: str):
    post_id = data.split(":", 1)[1] if ":" in data else ""
    if not post_id:
        await answer_callback_query(cb_id)
        return

    from app.services.post_service import toggle_favorite
    is_fav = await toggle_favorite(user_id, post_id)
    text = t("favorited", lang) if is_fav else ("已取消收藏" if lang == "zh" else "Unsaved")
    await answer_callback_query(cb_id, text=text)


# ══════════════════════════════════════════════
# Report
# ══════════════════════════════════════════════

async def _handle_report(cb_id: str, chat_id: int, message_id: int, user_id: int, data: str, lang: str, is_group: bool):
    post_id = data.split(":", 1)[1] if ":" in data else ""
    if not post_id:
        await answer_callback_query(cb_id)
        return

    if is_group:
        from app.handlers.group_chat import handle_group_swipe
        await handle_group_swipe(cb_id, chat_id, message_id, user_id, post_id, "report", lang)
    else:
        from app.services.post_service import report_post
        await report_post(user_id, post_id)
        await answer_callback_query(cb_id, text=t("reported", lang))


# ══════════════════════════════════════════════
# Publishing Flow
# ══════════════════════════════════════════════

async def _start_publish_flow(chat_id: int, user_id: int, user, lang: str):
    """Show channel selection for publishing."""
    rows = []
    for ch in CHANNELS:
        if not ch.is_user_channel:
            continue
        display = get_channel_display(ch.id, lang)
        rows.append([inline_button(display, f"chan:{ch.id}")])

    title = t("choose_channel", lang)
    await send_message(chat_id, title, reply_markup=inline_keyboard(rows))


async def _handle_channel_select(cb_id: str, chat_id: int, user_id: int, user, data: str, lang: str):
    """User selected a channel → save to draft, ask for content."""
    try:
        channel_id = int(data.split(":", 1)[1])
    except (ValueError, IndexError):
        await answer_callback_query(cb_id)
        return

    ch = get_channel(channel_id)
    if not ch or not ch.is_user_channel:
        await answer_callback_query(cb_id, text="Invalid channel", show_alert=True)
        return

    # Save draft with channel selection
    draft = {
        "channel_id": channel_id,
        "country": user.country if user.show_country else "",
        "lang": lang,
        "state": "waiting_content",
    }

    # Check for daily topic
    daily_topic = await _get_daily_topic(lang)
    if daily_topic:
        draft["daily_topic"] = daily_topic

    await save_draft(user_id, draft)
    await answer_callback_query(cb_id)

    # Show content input prompt
    channel_name = get_channel_display(channel_id, lang)
    prompt = t("enter_content", lang)

    # If there's a daily topic, show it as hint
    if daily_topic:
        prompt = t("daily_topic_hint", lang, topic=daily_topic) + "\n\n" + prompt

    await send_message(chat_id, f"{channel_name}\n\n{prompt}")
    await update_user(user_id, onboard_state="writing_post")


async def _handle_publish_action(cb_id: str, chat_id: int, user_id: int, user, data: str, lang: str):
    """Handle publish confirm / cancel / scope selection."""
    action = data.split(":", 1)[1] if ":" in data else ""

    if action == "confirm":
        draft = await get_draft(user_id)
        if not draft:
            await answer_callback_query(cb_id, text=t("error_generic", lang), show_alert=True)
            return

        post_id = await publish_draft(user_id, draft)
        await answer_callback_query(cb_id)

        if post_id:
            await send_message(chat_id, t("published_success", lang))
        else:
            await send_message(chat_id, t("error_generic", lang))

        await update_user(user_id, onboard_state="ready")

        from app.handlers.private_chat import _main_menu_keyboard
        await send_message(chat_id, "👆", reply_markup=_main_menu_keyboard(lang))

    elif action == "cancel":
        await clear_draft(user_id)
        await answer_callback_query(cb_id, text=t("publish_cancelled", lang))
        await update_user(user_id, onboard_state="ready")

        from app.handlers.private_chat import _main_menu_keyboard
        await send_message(chat_id, t("publish_cancelled", lang), reply_markup=_main_menu_keyboard(lang))

    elif action == "global":
        # Publish to global feed
        draft = await get_draft(user_id)
        if draft:
            draft["group_only"] = None
            await save_draft(user_id, draft)
        await _show_publish_preview(cb_id, chat_id, user_id, user, lang)

    elif action == "group":
        # Publish to group only (🔒)
        draft = await get_draft(user_id)
        if draft and draft.get("from_group_chat_id"):
            draft["group_only"] = draft["from_group_chat_id"]
            await save_draft(user_id, draft)
        await _show_publish_preview(cb_id, chat_id, user_id, user, lang)

    else:
        await answer_callback_query(cb_id)


async def _show_publish_preview(cb_id: str, chat_id: int, user_id: int, user, lang: str):
    """Show preview of the post before confirming."""
    await answer_callback_query(cb_id)
    draft = await get_draft(user_id)
    if not draft:
        await send_message(chat_id, t("error_generic", lang))
        return

    channel_name = get_channel_display(draft.get("channel_id", 0), lang)
    country = draft.get("country", "")
    content = draft.get("content", "")
    anonymous = t("anonymous", lang)

    # Build preview
    lines = [channel_name]
    if country:
        lines[0] += f" · 📍 {country}"
    lines.append("")
    lines.append(content)
    lines.append("")
    lines.append(f"— {anonymous}")
    lines.append("")
    lines.append(t("preview_confirm", lang))

    preview_text = "\n".join(lines)

    keyboard = inline_keyboard([
        [
            inline_button(t("publish_confirm_btn", lang), "pub:confirm"),
            inline_button(t("publish_cancel_btn", lang), "pub:cancel"),
        ],
    ])

    photo = draft.get("photo_file_id")
    if photo:
        await send_photo(chat_id, photo=photo, caption=preview_text, reply_markup=keyboard)
    else:
        await send_message(chat_id, preview_text, reply_markup=keyboard)


# ══════════════════════════════════════════════
# Profile Sub-pages (Creator Panel + Favorites)
# ══════════════════════════════════════════════

async def _handle_profile(cb_id: str, chat_id: int, user_id: int, data: str, lang: str):
    """Handle profile:stories and profile:favorites."""
    action = data.split(":", 1)[1] if ":" in data else ""
    await answer_callback_query(cb_id)

    if action == "stories":
        await _show_creator_panel(chat_id, user_id, lang)
    elif action == "favorites":
        await _show_favorites(chat_id, user_id, lang)


async def _show_creator_panel(chat_id: int, user_id: int, lang: str):
    """Show creator's published stories with stats."""
    from app.database import get_pool
    pool = get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, channel_id, content, like_count, view_count, reactions,
                   created_at
            FROM posts
            WHERE author_id = $1 AND is_active = TRUE
            ORDER BY created_at DESC
            LIMIT 10
            """,
            user_id,
        )

    if not rows:
        await send_message(chat_id, f"📊 {t('no_stories_yet', lang)}")
        return

    lines = [t("my_stories_title", lang)]

    for i, row in enumerate(rows, 1):
        import json as _json
        reactions = row["reactions"]
        if isinstance(reactions, str):
            reactions = _json.loads(reactions)
        total_reactions = sum(reactions.values()) if isinstance(reactions, dict) else 0

        channel_name = get_channel_display(row["channel_id"], lang)
        content_preview = row["content"][:40] + ("..." if len(row["content"]) > 40 else "")

        stats_line = f"👁{row['view_count']} · 👍{row['like_count']}"

        if reactions and isinstance(reactions, dict):
            emoji_parts = [f"{e}{c}" for e, c in reactions.items() if c > 0]
            if emoji_parts:
                stats_line += " · " + " ".join(emoji_parts[:5])

        lines.append(f"\n<b>{i}.</b> {channel_name}")
        lines.append(f"   {content_preview}")
        lines.append(f"   {stats_line}")

    await send_message(chat_id, "\n".join(lines))


async def _show_favorites(chat_id: int, user_id: int, lang: str):
    """Show user's saved/favorited stories."""
    from app.database import get_pool
    pool = get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT p.id, p.channel_id, p.content, p.country
            FROM post_favorites pf
            JOIN posts p ON p.id = pf.post_id
            WHERE pf.user_id = $1 AND p.is_active = TRUE
            ORDER BY pf.created_at DESC
            LIMIT 10
            """,
            user_id,
        )

    if not rows:
        await send_message(chat_id, f"⭐ {t('no_favorites_yet', lang)}")
        return

    lines = [t("my_favorites_title", lang)]

    for i, row in enumerate(rows, 1):
        channel_name = get_channel_display(row["channel_id"], lang)
        content_preview = row["content"][:50] + ("..." if len(row["content"]) > 50 else "")
        country = row["country"]

        lines.append(f"\n<b>{i}.</b> {channel_name}")
        if country:
            from app.services.country_service import get_country_display as fmt_country
            lines[-1] += f" · {fmt_country(country, lang)}"
        lines.append(f"   {content_preview}")

    await send_message(chat_id, "\n".join(lines))


# ══════════════════════════════════════════════
# Settings
# ══════════════════════════════════════════════

async def _handle_settings(cb_id: str, chat_id: int, message_id: int, user_id: int, user, data: str, lang: str):
    action = data.split(":", 1)[1] if ":" in data else ""

    if action == "country":
        await answer_callback_query(cb_id)
        from app.handlers.private_chat import _country_quick_picks
        await update_user(user_id, onboard_state="choosing_country")
        hint = (
            "🌍 选择或输入你的国家（支持任何语言）："
        ) if lang == "zh" else (
            "🌍 Pick or type your country (any language):"
        )
        await send_message(
            chat_id, hint,
            reply_markup={"inline_keyboard": _country_quick_picks(lang, user.country)},
        )
    elif action == "toggle_location":
        new_val = not user.show_country
        await update_user(user_id, show_country=new_val)
        status = "✅" if new_val else "❌"
        await answer_callback_query(cb_id, text=f"📍 → {status}")
        from app.handlers.private_chat import _show_settings
        refreshed = await get_user(user_id)
        if refreshed:
            await _show_settings(chat_id, user_id, refreshed, lang)
    elif action == "channels":
        await answer_callback_query(cb_id)
        await _show_channel_settings(chat_id, user_id, user, lang)
    elif action == "channels_done":
        await answer_callback_query(cb_id)
        from app.handlers.private_chat import _main_menu_keyboard
        done_text = "✅ 频道设置已保存" if lang == "zh" else "✅ Channel settings saved"
        await send_message(chat_id, done_text, reply_markup=_main_menu_keyboard(lang))
    else:
        await answer_callback_query(cb_id)


async def _show_channel_settings(chat_id: int, user_id: int, user, lang: str):
    prefs = set(user.channel_prefs) if user.channel_prefs else set(ALL_CHANNEL_IDS)
    title = "📺 频道订阅\n\n点击切换：" if lang == "zh" else "📺 Channel Subscriptions\n\nTap to toggle:"

    rows = []
    for ch in CHANNELS:
        is_on = ch.id in prefs
        mark = "✅" if is_on else "⬜"
        name = get_channel_display(ch.id, lang)
        rows.append([inline_button(f"{mark} {name}", f"toggle_ch:{ch.id}")])

    done_text = "✅ 完成" if lang == "zh" else "✅ Done"
    rows.append([inline_button(done_text, "settings:channels_done")])
    await send_message(chat_id, title, reply_markup=inline_keyboard(rows))


async def _handle_toggle_channel(cb_id: str, chat_id: int, message_id: int, user_id: int, user, data: str, lang: str):
    try:
        channel_id = int(data.split(":", 1)[1])
    except (ValueError, IndexError):
        await answer_callback_query(cb_id)
        return

    prefs = set(user.channel_prefs) if user.channel_prefs else set(ALL_CHANNEL_IDS)
    if channel_id in prefs:
        prefs.discard(channel_id)
    else:
        prefs.add(channel_id)

    if not prefs:
        no_empty = "至少选一个频道" if lang == "zh" else "Select at least 1 channel"
        await answer_callback_query(cb_id, text=no_empty)
        return

    await update_user(user_id, channel_prefs=sorted(prefs))
    await answer_callback_query(cb_id)

    # Refresh inline keyboard
    rows = []
    for ch in CHANNELS:
        is_on = ch.id in prefs
        mark = "✅" if is_on else "⬜"
        name = get_channel_display(ch.id, lang)
        rows.append([inline_button(f"{mark} {name}", f"toggle_ch:{ch.id}")])

    done_text = "✅ 完成" if lang == "zh" else "✅ Done"
    rows.append([inline_button(done_text, "settings:channels_done")])
    await edit_message_reply_markup(chat_id, message_id, reply_markup=inline_keyboard(rows))


# ══════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════

async def _get_daily_topic(lang: str) -> str | None:
    """Get today's daily topic if available."""
    from app.database import get_pool
    pool = get_pool()
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT question_zh, question_en FROM daily_topics WHERE topic_date = CURRENT_DATE"
            )
            if row:
                return row["question_zh"] if lang == "zh" else row["question_en"]
    except Exception:
        pass
    return None


async def _get_chat_type(chat_id: int) -> str:
    """Determine chat type. For now, infer from chat_id sign (groups are negative)."""
    return "group" if chat_id < 0 else "private"
