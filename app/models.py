"""
Blink.World — Pydantic data models
Mirrors database schema. Used for validation, serialization, type safety.
"""

from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


# ── Enums ──

class Language(str, Enum):
    ZH = "zh"
    EN = "en"
    RU = "ru"
    ID = "id"
    PT = "pt"


class ContentSource(str, Enum):
    AI = "ai"
    OPS = "ops"      # platform operations
    UGC = "ugc"      # user generated


class SwipeAction(str, Enum):
    LIKE = "like"
    DISLIKE = "dislike"


# ── Channel ──

class Channel(BaseModel):
    id: int
    names: dict[str, str]    # {"zh": "...", "en": "...", "ru": "...", "id": "...", "pt": "..."}
    emoji: str
    is_user_channel: bool    # True = users can post to it


# V2 channel definitions: 2 PGC (front) + 9 UGC
# Browsing: all 11 visible, default all selected
# Creating: only UGC channels (is_user_channel=True)
CHANNELS: list[Channel] = [
    # ── PGC (platform-operated, listed first) ──
    Channel(id=1, names={"zh": "环球旅行", "en": "World Travel", "ru": "Путешествия", "id": "Keliling Dunia", "pt": "Viagem Mundial"}, emoji="🌍", is_user_channel=False),
    Channel(id=2, names={"zh": "今日头条", "en": "Headlines", "ru": "Новости дня", "id": "Berita Hari Ini", "pt": "Manchetes"}, emoji="📰", is_user_channel=False),
    # ── UGC (user-generated) ──
    Channel(id=3, names={"zh": "深夜树洞", "en": "Confessions", "ru": "Признания", "id": "Curhat", "pt": "Confissões"}, emoji="🌙", is_user_channel=True),
    Channel(id=4, names={"zh": "沙雕日常", "en": "WTF Moments", "ru": "Жесть дня", "id": "Kok Bisa", "pt": "Que Isso"}, emoji="🤪", is_user_channel=True),
    Channel(id=5, names={"zh": "我吃什么", "en": "What I Ate", "ru": "Что я ем", "id": "Aku Makan Apa", "pt": "O Que Eu Comi"}, emoji="🍳", is_user_channel=True),
    Channel(id=6, names={"zh": "恋爱日记", "en": "Love Stories", "ru": "Про любовь", "id": "Soal Cinta", "pt": "Sobre Amor"}, emoji="💖", is_user_channel=True),
    Channel(id=7, names={"zh": "人间真实", "en": "No Filter", "ru": "Без фильтра", "id": "Tanpa Filter", "pt": "Sem Filtro"}, emoji="💬", is_user_channel=True),
    Channel(id=8, names={"zh": "立个Flag", "en": "Mark My Words", "ru": "Зуб даю", "id": "Tantang Aku", "pt": "Pode Cobrar"}, emoji="😈", is_user_channel=True),
    Channel(id=9, names={"zh": "记录此刻", "en": "Moments", "ru": "Моменты", "id": "Momen", "pt": "Momentos"}, emoji="📷", is_user_channel=True),
    Channel(id=10, names={"zh": "萌宠", "en": "Pet Moments", "ru": "Мой питомец", "id": "Peliharaanku", "pt": "Meu Pet"}, emoji="🐾", is_user_channel=True),
    Channel(id=11, names={"zh": "我要搞钱", "en": "Money Talk", "ru": "Про деньги", "id": "Cari Cuan", "pt": "Falar de Grana"}, emoji="💰", is_user_channel=True),
]

USER_CHANNEL_IDS = [c.id for c in CHANNELS if c.is_user_channel]
ALL_CHANNEL_IDS = [c.id for c in CHANNELS]

# PGC channel IDs (for signature logic)
PGC_CHANNEL_IDS = [c.id for c in CHANNELS if not c.is_user_channel]


def get_channel(channel_id: int) -> Channel | None:
    for c in CHANNELS:
        if c.id == channel_id:
            return c
    return None


def get_channel_name(channel_id: int, lang: str = "zh") -> str:
    c = get_channel(channel_id)
    if c is None:
        return "Unknown"
    return c.names.get(lang) or c.names.get("en") or "Unknown"


def get_channel_display(channel_id: int, lang: str = "zh") -> str:
    c = get_channel(channel_id)
    if c is None:
        return "❓ Unknown"
    name = c.names.get(lang) or c.names.get("en") or "Unknown"
    return f"{c.emoji} {name}"


# ── User ──

class UserProfile(BaseModel):
    id: int                                         # Telegram user ID
    lang: str = "zh"                                # language preference
    country: str = ""                               # user's country
    channel_prefs: list[int] = Field(default_factory=lambda: list(ALL_CHANNEL_IDS))
    points: int = 0
    show_country: bool = True
    created_at: datetime | None = None
    last_checkin: datetime | None = None
    stats: dict = Field(default_factory=lambda: {
        "views_total": 0,
        "published_total": 0,
        "likes_received": 0,
        "invited_count": 0,
    })


# ── Post ──

class Post(BaseModel):
    id: str                                         # UUID
    channel_id: int
    country: str = ""
    content: str
    photo_file_id: str | None = None
    original_lang: str = "zh"
    source: ContentSource = ContentSource.UGC
    author_id: int | None = None                    # None for AI/ops content
    group_only: int | None = None                   # group chat_id if 🔒
    created_at: datetime | None = None
    reactions: dict = Field(default_factory=dict)    # {emoji: count}
    like_count: int = 0
    dislike_count: int = 0
    favorite_count: int = 0
    report_count: int = 0
    view_count: int = 0


# ── Reaction Emojis ──

REACTION_EMOJIS = ["🌸", "🤣", "💔", "😭", "💀"]

REACTION_MEANINGS = {
    "🌸": {"zh": "送你一朵花", "en": "A flower for you"},
    "🤣": {"zh": "笑死", "en": "LOL"},
    "💔": {"zh": "心碎", "en": "Heartbreak"},
    "😭": {"zh": "哭死", "en": "Crying"},
    "💀": {"zh": "人没了", "en": "I'm dead"},
}

# Legacy emojis that may exist in DB from older versions
LEGACY_REACTION_EMOJIS = {"🤗", "❓"}


# ── Milestone Levels ──

MILESTONE_LEVELS = [
    {"threshold": 10, "points": 10, "emoji": "🎉"},
    {"threshold": 30, "points": 30, "emoji": "🔥"},
    {"threshold": 100, "points": 100, "emoji": "🔥"},
    {"threshold": 300, "points": 300, "emoji": "🏆"},
    {"threshold": 1000, "points": 1000, "emoji": "👑"},
]


# ── Points Config ──

class PointsConfig:
    DAILY_CHECKIN = 10
    SWIPE_PER_10 = 5
    PUBLISH_STORY = 20
    DAILY_TOPIC_BONUS = 10
    LIKED_PER_10 = 5
    INVITE_USER = 50
    ADD_BOT_TO_GROUP = 100
    GROUP_PARTICIPATE = 2


class Limits:
    """All business rule thresholds in one place."""
    # Content
    CONTENT_MIN_LENGTH = 6               # Global minimum (used by admin UI)
    CONTENT_MIN_LENGTH_ZH = 6            # Chinese: 6 characters
    CONTENT_MIN_LENGTH_DEFAULT = 10      # Other languages: 10 characters
    CONTENT_MAX_LENGTH = 500
    REACTIONS_PER_POST = 3           # Max emoji reactions per user per post
    REPORT_MIN_VIEWS = 10            # Min views before report rate is calculated
    REPORT_DEMOTE_RATE = 0.05        # >5% → weight to zero
    REPORT_REMOVE_RATE = 0.10        # >10% → auto remove

    # Translation
    HOT_POST_THRESHOLD = 5           # Min interactions to trigger pre-translation

    # Private chat rate limiting (anti-script abuse)
    PRIVATE_SWIPE_PER_MINUTE = 20    # Max swipes per window
    PRIVATE_SWIPE_WINDOW = 60        # Window in seconds

    # Feed
    FEED_CANDIDATE_LIMIT = 30        # Max candidates fetched per recommendation
    FEED_CANDIDATE_MULTIPLIER = 3    # Overfetch multiplier for post-filter dedup

    # Profile / list pagination
    PROFILE_STORIES_LIMIT = 10       # Max stories shown in creator panel
    PROFILE_FAVORITES_LIMIT = 10     # Max favorites shown in favorites list

    # Group
    GROUP_RATE_TIER1_COUNT = 50      # Swipes before tier-1 cooldown kicks in
    GROUP_RATE_TIER2_COUNT = 100     # Swipes before tier-2 cooldown kicks in
    GROUP_RATE_TIER1_SECONDS = 5     # Cooldown seconds for tier 1
    GROUP_RATE_TIER2_SECONDS = 15    # Cooldown seconds for tier 2

    # Group invite soft reminder
    GROUP_INVITE_REMINDER_INTERVAL = 20  # Show reminder every N swipes

    # Redis TTLs (seconds)
    VIEWED_TTL = 7 * 86400           # 7 days
    CURRENT_POST_TTL = 3600          # 1 hour
    SWIPE_COUNT_TTL = 86400          # 24 hours
    TRANSLATE_TTL = 7 * 86400        # 7 days
    DRAFT_TTL = 1800                 # 30 minutes
    GROUP_STATE_TTL = 86400          # 24 hours
    GROUP_SEEN_TTL = 86400           # 24 hours
    FLIP_LOCK_TTL = 10               # Safety net TTL; normally released immediately after card sent
    PENDING_IMAGE_TTL = 30 * 86400   # 30 days


def get_min_content_length(lang: str) -> int:
    """Get minimum content length based on user language."""
    if lang == "zh":
        return Limits.CONTENT_MIN_LENGTH_ZH
    return Limits.CONTENT_MIN_LENGTH_DEFAULT
