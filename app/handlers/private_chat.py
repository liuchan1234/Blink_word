"""
Blink.World — Private Chat Handler (Round 2 Full Implementation)
Handles all private (1:1) messages:
  - /start onboarding (language → country → first card)
  - Menu navigation (browse / post / me / settings)
  - Browsing mode: reply keyboard 👍👎⭐⚠️
  - Onboarding state machine: new → choosing_country → typing_country → ready
"""

import logging

from app.services.user_service import get_or_create_user, update_user, get_user, add_points
from app.services.feed_service import get_next_card, get_current_post_id, get_swipe_count
from app.services.post_service import record_swipe, toggle_favorite, report_post, get_post, save_post_message
from app.i18n import t, detect_language, guess_country
from app.models import PointsConfig, ALL_CHANNEL_IDS
from app.telegram_helpers import send_message, send_photo, reply_keyboard
from app.handlers.card_builder import (
    build_card_text,
    build_card_inline_keyboard,
    build_private_browse_keyboard,
)

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════
# Keyboard Builders
# ══════════════════════════════════════════════

def _main_menu_keyboard(lang: str) -> dict:
    """Build the main menu reply keyboard."""
    return reply_keyboard([
        [t("menu_browse", lang), t("menu_post", lang)],
        [t("menu_me", lang), t("menu_settings", lang)],
    ])


def _browse_keyboard(lang: str) -> dict:
    """Reply keyboard during browsing mode (Layer 3)."""
    return build_private_browse_keyboard(lang)


# ══════════════════════════════════════════════
# Main Router
# ══════════════════════════════════════════════

async def handle_private_message(message: dict):
    """Route private messages by type and content."""
    user_tg = message.get("from", {})
    user_id = user_tg.get("id")
    chat_id = message.get("chat", {}).get("id")

    if not user_id or not chat_id:
        return

    text = message.get("text", "").strip()
    language_code = user_tg.get("language_code")

    # Get or create user
    user, is_new = await get_or_create_user(user_id, language_code)
    lang = user.lang

    # Fetch onboard_state from DB
    onboard_state = await _get_onboard_state(user_id)

    # ── Handle onboarding states ──
    if onboard_state in ("typing_country", "choosing_country") and text and not text.startswith("/"):
        # User typed a country name directly instead of using buttons
        await _finish_country_input(chat_id, user_id, text, lang)
        return

    # ── Handle publishing: waiting for content input ──
    if onboard_state == "writing_post":
        photo = message.get("photo")
        if text and not text.startswith("/"):
            await _handle_content_input(chat_id, user_id, user, text, None, lang)
            return
        elif photo:
            # Photo with optional caption
            photos = photo
            largest = photos[-1] if photos else None
            file_id = largest.get("file_id") if largest else None
            caption = message.get("caption", "").strip()
            await _handle_content_input(chat_id, user_id, user, caption, file_id, lang)
            return

    # ── Commands ──
    if text.startswith("/start"):
        await _handle_start(chat_id, user_id, text, user, is_new, language_code)
        return

    if text == "/help":
        await send_message(chat_id, t("welcome", lang), reply_markup=_main_menu_keyboard(lang))
        return

    if text == "/checkin":
        await _handle_checkin(chat_id, user_id, user, lang)
        return

    if text.startswith("/admin"):
        from app.handlers.admin_review import handle_admin_command
        await handle_admin_command(chat_id, user_id, text)
        return

    # ── Reply keyboard: Swipe actions (Layer 3) ──
    if text == "👍":
        await _handle_like(chat_id, user_id, lang)
        return

    if text == "👎":
        await _handle_dislike(chat_id, user_id, lang)
        return

    if text.startswith("⭐"):
        await _handle_fav(chat_id, user_id, lang)
        return

    if text.startswith("⚠️"):
        await _handle_report_action(chat_id, user_id, lang)
        return

    # ── Menu buttons ──
    menu_browse = t("menu_browse", lang)
    menu_post = t("menu_post", lang)
    menu_me = t("menu_me", lang)
    menu_settings = t("menu_settings", lang)

    if text == menu_browse:
        await _start_browsing(chat_id, user_id, user, lang)
        return

    if text == menu_post:
        await _start_publish(chat_id, user_id, user, lang)
        return

    if text == menu_me:
        await _show_profile(chat_id, user_id, user, lang)
        return

    if text == menu_settings:
        await _show_settings(chat_id, user_id, user, lang)
        return

    # ── Fallback: if in browsing state, treat as unrecognized ──
    current = await get_current_post_id(user_id)
    if current:
        # User is browsing; remind them of controls
        await send_message(chat_id, "👆", reply_markup=_browse_keyboard(lang))
    else:
        await send_message(chat_id, t("welcome", lang), reply_markup=_main_menu_keyboard(lang))


# ══════════════════════════════════════════════
# /start — Onboarding
# ══════════════════════════════════════════════

async def _handle_start(chat_id: int, user_id: int, text: str, user, is_new: bool, language_code: str | None):
    """Handle /start with optional referral payload."""
    lang = user.lang

    # Parse payload: /start ref_12345 or /start from_group_-123456
    payload = text.split(" ", 1)[1].strip() if " " in text else ""

    if payload.startswith("ref_") and is_new:
        try:
            inviter_id = int(payload[4:])
            if inviter_id != user_id and inviter_id > 0:
                await _process_referral(inviter_id, user_id)
        except (ValueError, TypeError):
            pass

    # Track group origin — user came from a group interaction prompt
    from_group = None
    if payload.startswith("from_group_"):
        try:
            from_group = int(payload.replace("from_group_", ""))
        except (ValueError, TypeError):
            pass

    onboard_state = await _get_onboard_state(user_id)

    if is_new or onboard_state == "new":
        # Fresh user: welcome → country input (free text + popular quick-picks)
        guessed = guess_country(language_code)
        await update_user(user_id, onboard_state="choosing_country")

        await send_message(chat_id, t("welcome", lang))

        # Show quick-pick buttons for common countries + free text hint
        from app.services.country_service import get_country_display as country_display
        hint = (
            "🌍 你在哪个国家？\n\n"
            "点击下方按钮快速选择，或者<b>直接输入你的国家名称</b>（支持任何语言）。"
        ) if lang == "zh" else (
            "🌍 What country are you in?\n\n"
            "Tap a button below, or <b>type your country name</b> in any language."
        )

        await send_message(
            chat_id,
            hint,
            reply_markup={"inline_keyboard": _country_quick_picks(lang, guessed)},
        )
    else:
        # Returning user: show main menu
        await send_message(chat_id, t("welcome", lang), reply_markup=_main_menu_keyboard(lang))

        # If user came from a group, remind them to go back
        if from_group:
            back_hint = "✅ 已激活！现在回到群里继续刷故事吧 👆" if lang == "zh" else "✅ Activated! Go back to the group to continue 👆"
            await send_message(chat_id, back_hint)


async def _finish_country_input(chat_id: int, user_id: int, country_text: str, lang: str):
    """Handle free-text country input — detect, normalize, confirm."""
    from app.services.country_service import detect_country

    info = await detect_country(country_text)

    # Save normalized country name (zh version for storage, display adapts to user lang)
    await update_user(user_id, country=info.name_zh, onboard_state="ready")

    display = f"{info.flag} {info.name_zh if lang == 'zh' else info.name_en}"
    await send_message(chat_id, t("country_set", lang, country=display))
    await send_message(
        chat_id,
        t("setup_complete", lang),
        reply_markup=_main_menu_keyboard(lang),
    )


async def _process_referral(inviter_id: int, invitee_id: int):
    """Process referral reward. Atomic, prevents duplicates."""
    from app.database import get_pool
    pool = get_pool()
    try:
        async with pool.acquire() as conn:
            result = await conn.execute(
                """
                INSERT INTO referrals (inviter_id, invitee_id)
                VALUES ($1, $2)
                ON CONFLICT (invitee_id) DO NOTHING
                """,
                inviter_id, invitee_id,
            )
            if "INSERT 0 1" in result:
                await add_points(inviter_id, PointsConfig.INVITE_USER, reason="invite")
                from app.services.user_service import increment_stat
                await increment_stat(inviter_id, "invited_count")
                # Notify inviter
                inviter = await get_user(inviter_id)
                if inviter:
                    try:
                        await send_message(
                            inviter_id,
                            t("invite_success", inviter.lang, points=PointsConfig.INVITE_USER),
                        )
                    except Exception:
                        pass
    except Exception as e:
        logger.error("Referral processing failed: %s", e)


# ══════════════════════════════════════════════
# Browsing — Send Next Card
# ══════════════════════════════════════════════

async def _start_browsing(chat_id: int, user_id: int, user, lang: str):
    """Enter browsing mode: switch keyboard and send first card."""
    await send_message(
        chat_id,
        "📖" if lang == "zh" else "📖",
        reply_markup=_browse_keyboard(lang),
    )
    await _send_next_card(chat_id, user_id, user, lang)


async def _send_next_card(chat_id: int, user_id: int, user, lang: str):
    """Fetch and send the next story card."""
    channel_ids = user.channel_prefs if user.channel_prefs else ALL_CHANNEL_IDS

    card = await get_next_card(
        user_id=user_id,
        channel_ids=channel_ids,
        viewer_country=user.country,
        viewer_lang=lang,
    )

    if card is None:
        await send_message(
            chat_id,
            t("no_more_content", lang),
            reply_markup=_main_menu_keyboard(lang),
        )
        return

    post_id = card["id"]

    # Translate content if needed
    from app.services.translation_service import get_translated_content
    translated = await get_translated_content(
        post_id=post_id,
        content=card.get("content", ""),
        original_lang=card.get("original_lang", "zh"),
        target_lang=lang,
    )

    # Build card content
    card_text = build_card_text(card, lang=lang, translated_content=translated)
    card_keyboard = build_card_inline_keyboard(
        post_id,
        reactions=card.get("reactions", {}),
        include_post_button=True,
        include_swipe_buttons=False,  # Private uses reply keyboard for Layer 3
    )

    # Send card (with or without photo)
    photo_file_id = card.get("photo_file_id")
    result = None

    if photo_file_id and photo_file_id.startswith("pending:"):
        # Deferred image: upload from Redis bytes
        result = await _send_pending_image(chat_id, photo_file_id, card_text, card_keyboard, post_id)
    elif photo_file_id:
        result = await send_photo(
            chat_id,
            photo=photo_file_id,
            caption=card_text,
            reply_markup=card_keyboard,
        )
    else:
        result = await send_message(
            chat_id,
            card_text,
            reply_markup=card_keyboard,
        )

    # Save message→post mapping (for native reactions tracking)
    if result and isinstance(result, dict):
        msg_id = result.get("message_id")
        if msg_id:
            await save_post_message(chat_id, msg_id, post_id)

    # Check points: every 10 swipes → +5 points
    swipe_count = await get_swipe_count(user_id)
    if swipe_count > 0 and swipe_count % 10 == 0:
        await add_points(user_id, PointsConfig.SWIPE_PER_10, reason="swipe_10")


# ══════════════════════════════════════════════
# Reply Keyboard Actions (Layer 3)
# ══════════════════════════════════════════════

async def _handle_like(chat_id: int, user_id: int, lang: str):
    """👍 — record like + send next card."""
    post_id = await get_current_post_id(user_id)
    if post_id:
        await record_swipe(user_id, post_id, "like")

    user = await get_user(user_id)
    if user:
        await _send_next_card(chat_id, user_id, user, lang)
    else:
        await send_message(chat_id, t("error_generic", lang))


async def _handle_dislike(chat_id: int, user_id: int, lang: str):
    """👎 — record dislike + send next card."""
    post_id = await get_current_post_id(user_id)
    if post_id:
        await record_swipe(user_id, post_id, "dislike")

    user = await get_user(user_id)
    if user:
        await _send_next_card(chat_id, user_id, user, lang)
    else:
        await send_message(chat_id, t("error_generic", lang))


async def _handle_fav(chat_id: int, user_id: int, lang: str):
    """⭐ — toggle favorite (no page turn)."""
    post_id = await get_current_post_id(user_id)
    if not post_id:
        await send_message(chat_id, t("error_not_found", lang))
        return

    is_fav = await toggle_favorite(user_id, post_id)
    if is_fav:
        await send_message(chat_id, t("favorited", lang), reply_markup=_browse_keyboard(lang))
    else:
        unfav_text = t("unfavorited", lang)
        await send_message(chat_id, f"⭐ {unfav_text}", reply_markup=_browse_keyboard(lang))


async def _handle_report_action(chat_id: int, user_id: int, lang: str):
    """⚠️ — report + send next card."""
    post_id = await get_current_post_id(user_id)
    if post_id:
        await report_post(user_id, post_id)
        await send_message(chat_id, t("reported", lang), reply_markup=_browse_keyboard(lang))

    user = await get_user(user_id)
    if user:
        await _send_next_card(chat_id, user_id, user, lang)


# ══════════════════════════════════════════════
# Profile
# ══════════════════════════════════════════════

async def _show_profile(chat_id: int, user_id: int, user, lang: str):
    """Show user profile with stats."""
    from app.config import get_settings
    settings = get_settings()

    stats = user.stats or {}
    invite_link = f"https://t.me/{settings.BOT_USERNAME}?start=ref_{user_id}"

    # Format country with flag
    from app.services.country_service import get_country_display as fmt_country
    country_display = fmt_country(user.country, lang) if user.country else ("未设置" if lang == "zh" else "Not set")

    if lang == "zh":
        text = (
            f"👤 <b>我的资料</b>\n\n"
            f"🆔 ID: <code>{user_id}</code>\n"
            f"📍 国家: {country_display}\n"
            f"🏆 积分: <b>{user.points}</b>\n\n"
            f"── 数据统计 ──\n"
            f"👁 累计浏览: {stats.get('views_total', 0)}\n"
            f"📝 累计发布: {stats.get('published_total', 0)}\n"
            f"❤️ 获得喜欢: {stats.get('likes_received', 0)}\n"
            f"👥 邀请人数: {stats.get('invited_count', 0)}\n\n"
            f"── 邀请好友 ──\n"
            f"🔗 {invite_link}\n"
            f"<i>每成功邀请一人 +{PointsConfig.INVITE_USER} 积分</i>"
        )
    else:
        text = (
            f"👤 <b>My Profile</b>\n\n"
            f"🆔 ID: <code>{user_id}</code>\n"
            f"📍 Country: {country_display}\n"
            f"🏆 Points: <b>{user.points}</b>\n\n"
            f"── Stats ──\n"
            f"👁 Total views: {stats.get('views_total', 0)}\n"
            f"📝 Published: {stats.get('published_total', 0)}\n"
            f"❤️ Likes received: {stats.get('likes_received', 0)}\n"
            f"👥 Invited: {stats.get('invited_count', 0)}\n\n"
            f"── Invite Friends ──\n"
            f"🔗 {invite_link}\n"
            f"<i>+{PointsConfig.INVITE_USER} points per invite</i>"
        )

    await send_message(chat_id, text, reply_markup=_main_menu_keyboard(lang))

    # Show sub-navigation buttons
    from app.telegram_helpers import inline_keyboard, inline_button
    sub_buttons = inline_keyboard([
        [
            inline_button(t("btn_my_stories", lang), "profile:stories"),
            inline_button(t("btn_my_favorites", lang), "profile:favorites"),
        ],
    ])
    await send_message(chat_id, "👇", reply_markup=sub_buttons)


# ══════════════════════════════════════════════
# Settings
# ══════════════════════════════════════════════

async def _show_settings(chat_id: int, user_id: int, user, lang: str):
    """Show settings menu with inline buttons."""
    from app.telegram_helpers import inline_keyboard, inline_button
    from app.services.country_service import get_country_display as fmt_country

    country_display = fmt_country(user.country, lang) if user.country else ("未设置" if lang == "zh" else "Not set")
    from app.i18n import LANGUAGE_NAMES
    lang_display = LANGUAGE_NAMES.get(user.lang, user.lang)
    location_display = "✅" if user.show_country else "❌"

    if lang == "zh":
        text = (
            f"⚙️ <b>设置</b>\n\n"
            f"🌐 语言: {lang_display}\n"
            f"📍 国家: {country_display}\n"
            f"📍 发帖显示位置: {location_display}"
        )
    else:
        text = (
            f"⚙️ <b>Settings</b>\n\n"
            f"🌐 Language: {lang_display}\n"
            f"📍 Country: {country_display}\n"
            f"📍 Show location on posts: {location_display}"
        )

    from app.i18n import LANGUAGE_NAMES

    # Language selector: show all available languages
    lang_buttons = []
    for lcode, lname in LANGUAGE_NAMES.items():
        if lcode == lang:
            lang_buttons.append(inline_button(f"✅ {lname}", f"set_lang:{lcode}"))
        else:
            lang_buttons.append(inline_button(lname, f"set_lang:{lcode}"))

    # Split into rows of 3
    lang_rows = [lang_buttons[i:i+3] for i in range(0, len(lang_buttons), 3)]

    keyboard = inline_keyboard([
        *lang_rows,
        [inline_button(t("settings_country", lang) + " ✏️", "settings:country")],
        [inline_button(t("settings_show_country", lang) + f" {location_display}", "settings:toggle_location")],
        [inline_button(t("settings_channels", lang), "settings:channels")],
    ])

    await send_message(chat_id, text, reply_markup=keyboard)


# ══════════════════════════════════════════════
# Publishing Flow
# ══════════════════════════════════════════════

async def _start_publish(chat_id: int, user_id: int, user, lang: str):
    """Start the publishing flow: show channel selection."""
    from app.telegram_helpers import inline_keyboard, inline_button
    from app.models import CHANNELS, get_channel_display

    rows = []
    for ch in CHANNELS:
        if not ch.is_user_channel:
            continue
        display = get_channel_display(ch.id, lang)
        rows.append([inline_button(display, f"chan:{ch.id}")])

    await send_message(chat_id, t("choose_channel", lang), reply_markup=inline_keyboard(rows))


async def _handle_content_input(
    chat_id: int, user_id: int, user, text: str | None, photo_file_id: str | None, lang: str,
):
    """Handle user's content input during publishing flow."""
    from app.services.publish_service import get_draft, save_draft
    from app.telegram_helpers import inline_keyboard, inline_button

    draft = await get_draft(user_id)
    if not draft:
        await send_message(chat_id, t("error_generic", lang), reply_markup=_main_menu_keyboard(lang))
        await update_user(user_id, onboard_state="ready")
        return

    content = text or ""

    # Validate length
    if len(content) < 30:
        await send_message(chat_id, t("content_too_short", lang))
        return
    if len(content) > 500:
        await send_message(chat_id, t("content_too_long", lang))
        return

    # Update draft with content
    draft["content"] = content
    if photo_file_id:
        draft["photo_file_id"] = photo_file_id
    draft["state"] = "preview"

    # Check if user was referred from a group (Round 3: group anonymous poster)
    from_group = draft.get("from_group_chat_id")

    await save_draft(user_id, draft)

    # Build preview
    from app.models import get_channel_display
    channel_name = get_channel_display(draft.get("channel_id", 0), lang)
    country = draft.get("country", "")
    anonymous = t("anonymous", lang)

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

    # If from group, show scope choice first
    if from_group:
        keyboard = inline_keyboard([
            [
                inline_button(t("publish_to_world", lang), "pub:global"),
                inline_button(t("publish_to_group", lang), "pub:group"),
            ],
            [inline_button(t("publish_cancel_btn", lang), "pub:cancel")],
        ])
    else:
        keyboard = inline_keyboard([
            [
                inline_button(t("publish_confirm_btn", lang), "pub:confirm"),
                inline_button(t("publish_cancel_btn", lang), "pub:cancel"),
            ],
        ])

    if photo_file_id:
        await send_photo(chat_id, photo=photo_file_id, caption=preview_text, reply_markup=keyboard)
    else:
        await send_message(chat_id, preview_text, reply_markup=keyboard)


# ══════════════════════════════════════════════
# Daily Check-in
# ══════════════════════════════════════════════

async def _handle_checkin(chat_id: int, user_id: int, user, lang: str):
    """Handle /checkin — daily sign in for points."""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)

    if user.last_checkin:
        last = user.last_checkin
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        if last.date() == now.date():
            await send_message(chat_id, t("checkin_already", lang), reply_markup=_main_menu_keyboard(lang))
            return

    new_total = await add_points(user_id, PointsConfig.DAILY_CHECKIN, reason="checkin")
    await update_user(user_id, last_checkin=now)

    await send_message(
        chat_id,
        t("checkin_success", lang, points=PointsConfig.DAILY_CHECKIN, total=new_total),
        reply_markup=_main_menu_keyboard(lang),
    )


# ══════════════════════════════════════════════
# Country Quick Picks (shared with callbacks)
# ══════════════════════════════════════════════

def _country_quick_picks(lang: str, highlighted: str = "") -> list[list[dict]]:
    """Build popular country quick-pick inline keyboard. User can also type freely."""
    picks = [
        ("🇨🇳", "中国", "China"),
        ("🇺🇸", "美国", "United States"),
        ("🇯🇵", "日本", "Japan"),
        ("🇰🇷", "韩国", "South Korea"),
        ("🇬🇧", "英国", "UK"),
        ("🇷🇺", "俄罗斯", "Russia"),
        ("🇩🇪", "德国", "Germany"),
        ("🇫🇷", "法国", "France"),
        ("🇧🇷", "巴西", "Brazil"),
        ("🇮🇳", "印度", "India"),
        ("🇸🇬", "新加坡", "Singapore"),
        ("🇲🇾", "马来西亚", "Malaysia"),
        ("🇹🇭", "泰国", "Thailand"),
        ("🇻🇳", "越南", "Vietnam"),
        ("🇮🇩", "印尼", "Indonesia"),
        ("🇨🇦", "加拿大", "Canada"),
        ("🇦🇺", "澳大利亚", "Australia"),
        ("🇪🇸", "西班牙", "Spain"),
    ]

    rows = []
    row = []
    for flag, name_zh, name_en in picks:
        name = name_zh if lang == "zh" else name_en
        marker = " ✓" if name_zh == highlighted or name_en == highlighted else ""
        btn = {"text": f"{flag} {name}{marker}", "callback_data": f"set_country:{name_zh}"}
        row.append(btn)
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    return rows


# ══════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════

async def _get_onboard_state(user_id: int) -> str:
    """Read onboard_state directly from DB."""
    from app.database import get_pool
    pool = get_pool()
    async with pool.acquire() as conn:
        val = await conn.fetchval(
            "SELECT onboard_state FROM users WHERE id = $1", user_id
        )
        return val or "new"


async def _send_pending_image(
    chat_id: int,
    pending_key: str,
    caption: str,
    reply_markup: dict,
    post_id: str,
) -> dict | None:
    """
    Upload a pending image from Redis and send it.
    On success, update the post's photo_file_id with the real Telegram file_id.
    """
    redis_key = pending_key.replace("pending:", "", 1)
    try:
        from app.redis_client import get_redis
        r = get_redis()
        img_bytes = await r.get(redis_key)

        if not img_bytes:
            # Image expired or missing — send as text
            return await send_message(chat_id, caption, reply_markup=reply_markup)

        # Ensure we have bytes
        if isinstance(img_bytes, str):
            img_bytes = img_bytes.encode("latin-1")

        from app.services.image_service import send_photo_bytes
        result = await send_photo_bytes(chat_id, img_bytes, caption=caption, reply_markup=reply_markup)

        if result and result.get("photo_file_id"):
            # Persist the real file_id so we never need to re-upload
            from app.database import get_pool
            pool = get_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE posts SET photo_file_id = $1 WHERE id = $2",
                    result["photo_file_id"], post_id,
                )
            # Clean up Redis
            await r.delete(redis_key)

        return result
    except Exception as e:
        logger.warning("Pending image send failed for %s: %s", pending_key, e)
        return await send_message(chat_id, caption, reply_markup=reply_markup)
