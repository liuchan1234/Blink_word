"""
Blink.World — Card Builder
Builds Telegram message text and inline keyboards for story cards.
Shared between private chat and group chat handlers.

PRD Card Layout (Private):
  [图片（如有）]

  🌙 深夜树洞 · 📍 中国

  已经连续三个月在公司厕所里哭了...

  — 匿名

  inline keyboard:
  [🌸 47] [🤣 3] [💔 89] [🤗 124] [❓ 2]   ← Layer 1
  [📝 我也说一个]                             ← Layer 2

  reply keyboard（常驻）:
  [👍]  [👎]                                  ← Layer 3
  [⭐ 收藏]  [⚠️ 举报]

Group layout has Layer 3 in inline keyboard instead.
"""

from app.models import REACTION_EMOJIS, get_channel_display
from app.telegram_helpers import inline_keyboard, inline_button, reply_keyboard
from app.i18n import t


def build_card_text(
    post: dict,
    lang: str = "zh",
    translated_content: str | None = None,
) -> str:
    """Build the text/caption for a story card."""
    channel_display = get_channel_display(post.get("channel_id", 0), lang)
    country = post.get("country", "")
    content = translated_content or post.get("content", "")
    anonymous = t("anonymous", lang)

    lines = []

    # Header: channel · location (with flag emoji)
    header_parts = [channel_display]
    if country:
        from app.services.country_service import get_country_display as fmt_country
        header_parts.append(fmt_country(country, lang))
    lines.append(" · ".join(header_parts))
    lines.append("")

    # Content body
    lines.append(content)
    lines.append("")

    # Author
    lines.append(f"— {anonymous}")

    return "\n".join(lines)


def build_card_inline_keyboard(
    post_id: str,
    reactions: dict | None = None,
    include_post_button: bool = True,
    include_swipe_buttons: bool = False,
) -> dict:
    """
    Build inline keyboard for a card.

    Layer 1: Emoji reaction row (always present)
    Layer 2: "📝 我也说一个" (always present)
    Layer 3: 👍 👎 ⭐ ⚠️ (group mode only; private uses reply keyboard)
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

    # ── Layer 2: "我也说一个" ──
    if include_post_button:
        rows.append([inline_button("📝 我也说一个", "post_also")])

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
    PRD Layout:
      [👍]  [👎]
      [⭐ 收藏]  [⚠️ 举报]
    """
    fav_label = "⭐" + (" 收藏" if lang == "zh" else " Save")
    report_label = "⚠️" + (" 举报" if lang == "zh" else " Report")

    return reply_keyboard([
        ["👍", "👎"],
        [fav_label, report_label],
    ])


def build_group_card_inline_keyboard(
    post_id: str,
    reactions: dict | None = None,
) -> dict:
    """
    Build inline keyboard for group cards.
    All 3 layers in inline keyboard (group has no reply keyboard).

    PRD Group Layout:
      [🌸 47] [🤣 3] [💔 89] [🤗 124] [❓ 2]     ← Layer 1
      [📝 我也说一个]                               ← Layer 2
      [👍] [👎] [⭐] [⚠️]                          ← Layer 3
    """
    return build_card_inline_keyboard(
        post_id=post_id,
        reactions=reactions,
        include_post_button=True,
        include_swipe_buttons=True,
    )
