"""
Blink.World — Card Builder
Builds Telegram message text and inline keyboards for story cards.
Shared between private chat and group chat handlers.

V2 Layout (Private):
  [图片（如有）]

  🌙 深夜树洞 · 🇨🇳 中国

  已经连续三个月在公司厕所里哭了...

  — 匿名

  inline keyboard:
  [🌸 47] [🤣 3] [💔 89] [😭 124] [💀 2]   ← Layer 1
  [📝 我也说一个] [↗️ 分享]                   ← Layer 2

  reply keyboard（常驻）:
  [👍]  [👎]                                  ← Layer 3
  [⭐ 收藏]  [⚠️ 举报]

Group layout: same reply keyboard for Layer 3 (no inline swipe buttons).
"""

from app.config import get_settings
from app.models import REACTION_EMOJIS, PGC_CHANNEL_IDS, get_channel_display
from app.telegram_helpers import inline_keyboard, inline_button, reply_keyboard
from app.i18n import t

# PGC channel signatures
_PGC_SIGNATURES = {
    1: "— Blink.World 🌍",   # 环球旅行
    2: "— Blink.World 📰",   # 今日头条
}


def _share_url(post_id: str, user_id: int | None = None) -> str:
    """Build share deep link URL — uses Telegram native share sheet.
    Shares the card content text (not just a link) via switch_inline_query.
    Falls back to URL share for the button itself."""
    settings = get_settings()
    # Include referral in the bot link so new users who open it count as invites
    if user_id:
        bot_link = f"https://t.me/{settings.BOT_USERNAME}?start=share_{post_id}_ref_{user_id}"
    else:
        bot_link = f"https://t.me/{settings.BOT_USERNAME}?start=share_{post_id}"
    return f"https://t.me/share/url?url={bot_link}"


def _write_url(channel_id: int) -> str:
    """Build deep link URL to start writing in a specific channel (for group → Bot jump)."""
    settings = get_settings()
    return f"https://t.me/{settings.BOT_USERNAME}?start=write_{channel_id}"


def build_card_text(
    post: dict,
    lang: str = "zh",
    translated_content: str | None = None,
) -> str:
    """Build the text/caption for a story card."""
    channel_display = get_channel_display(post.get("channel_id", 0), lang)
    country = post.get("country", "")
    content = translated_content or post.get("content", "")
    channel_id = post.get("channel_id", 0)

    # PGC channels use Blink.World signature, UGC uses "匿名"
    signature = _PGC_SIGNATURES.get(channel_id, f"— {t('anonymous', lang)}")

    lines = []

    # Header: channel · location (with flag emoji) — bold
    header_parts = [channel_display]
    if country:
        from app.services.country_service import get_country_display as fmt_country
        header_parts.append(fmt_country(country, lang))
    lines.append("<b>" + " · ".join(header_parts) + "</b>")
    lines.append("")

    # Content body
    lines.append(content)
    lines.append("")

    # Signature
    lines.append(signature)

    return "\n".join(lines)


def build_card_inline_keyboard(
    post_id: str,
    channel_id: int = 0,
    reactions: dict | None = None,
    include_post_button: bool = True,
    include_swipe_buttons: bool = False,
    is_group: bool = False,
    lang: str = "zh",
    viewer_user_id: int | None = None,
) -> dict:
    """
    Build inline keyboard for a card.

    Layer 1: Emoji reaction row
    Layer 2: "📝 我也说一个" + "↗️"
      - Private: callback (post_also:{channel_id})
      - Group: URL (jumps to Bot, no message in group)
    Layer 3: 👍 👎 ⭐ ⚠️ (only if include_swipe_buttons=True)
    """
    if reactions is None:
        reactions = {}

    rows = []

    # ── Layer 1: Emoji reactions ──
    reaction_row = []
    for emoji in REACTION_EMOJIS:
        count = reactions.get(emoji, 0)
        label = f"{emoji} {count}" if count > 0 else emoji
        reaction_row.append(inline_button(label, f"react:{post_id}:{emoji}"))
    rows.append(reaction_row)

    # ── Layer 2: "我也说一个" + "分享" ──
    if include_post_button:
        post_also_text = t("post_also", lang)
        # Share button: use switch_inline_query_chosen_chat to share card content natively
        share_btn = {"text": "↗️", "switch_inline_query_chosen_chat": {
            "query": f"share:{post_id}",
            "allow_user_chats": True,
            "allow_group_chats": True,
            "allow_channel_chats": False,
            "allow_bot_chats": False,
        }}
        if is_group:
            # Group: URL button → jumps directly to Bot private chat
            rows.append([
                inline_button(post_also_text, url=_write_url(channel_id)),
                share_btn,
            ])
        else:
            # Private: callback button → stays in chat, starts publishing
            rows.append([
                inline_button(post_also_text, f"post_also:{channel_id}"),
                share_btn,
            ])

    # ── Layer 3: Swipe actions (group mode only) ──
    if include_swipe_buttons:
        rows.append([
            inline_button("👍", f"swipe:{post_id}:like"),
            inline_button("👎", f"swipe:{post_id}:dislike"),
            inline_button("⭐", f"fav:{post_id}"),
            inline_button("⚠️", f"report:{post_id}"),
        ])

    return inline_keyboard(rows)


def build_private_browse_keyboard(lang: str = "zh") -> dict:
    """
    Reply keyboard for private chat browsing mode.
    Layout:
      [👍 赞]  [👎 下一个]
      [⭐ 收藏]  [⚠️ 举报]
      [↩️ 返回]
    """
    return reply_keyboard([
        [t("browse_like_btn", lang), t("browse_next_btn", lang)],
        [t("browse_favorite_btn", lang), t("browse_report_btn", lang)],
        [t("browse_back_btn", lang)],
    ])


def build_group_browse_keyboard(lang: str = "zh") -> dict:
    """
    Reply keyboard for group browsing mode.
    Layout:
      [👍 赞]  [👎 下一个]
      [⭐ 收藏]  [⚠️ 举报]
      [🎯 主题]
    """
    return reply_keyboard([
        [t("browse_like_btn", lang), t("browse_next_btn", lang)],
        [t("browse_favorite_btn", lang), t("browse_report_btn", lang)],
        [t("browse_topics_btn", lang)],
    ])


def build_group_card_inline_keyboard(
    post_id: str,
    channel_id: int = 0,
    reactions: dict | None = None,
    lang: str = "zh",
) -> dict:
    """
    Build inline keyboard for group cards.
    No swipe buttons — group uses reply keyboard for swipe actions.
    """
    return build_card_inline_keyboard(
        post_id=post_id,
        channel_id=channel_id,
        reactions=reactions,
        include_post_button=True,
        include_swipe_buttons=False,
        is_group=True,
        lang=lang,
    )
