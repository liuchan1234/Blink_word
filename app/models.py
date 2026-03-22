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
    name_zh: str
    name_en: str
    emoji: str
    is_user_channel: bool  # True = users can post to it


# Hard-coded channel definitions from PRD
CHANNELS: list[Channel] = [
    Channel(id=1, name_zh="环球风光", name_en="World Views", emoji="🌍", is_user_channel=False),
    Channel(id=2, name_zh="每日精选", name_en="Daily Picks", emoji="⭐", is_user_channel=False),
    Channel(id=3, name_zh="每日话题", name_en="Daily Topic", emoji="📮", is_user_channel=False),
    Channel(id=4, name_zh="深夜树洞", name_en="Late Night", emoji="🌙", is_user_channel=True),
    Channel(id=5, name_zh="恋爱日记", name_en="Love Diary", emoji="💕", is_user_channel=True),
    Channel(id=6, name_zh="人间真实", name_en="Real Talk", emoji="💬", is_user_channel=True),
    Channel(id=7, name_zh="萌宠", name_en="Cute Pets", emoji="🐾", is_user_channel=True),
    Channel(id=8, name_zh="校园", name_en="Campus", emoji="🎓", is_user_channel=True),
    Channel(id=9, name_zh="沙雕日常", name_en="Funny Daily", emoji="😂", is_user_channel=True),
    Channel(id=10, name_zh="我要搞钱", name_en="Money Talk", emoji="💰", is_user_channel=True),
]

USER_CHANNEL_IDS = [c.id for c in CHANNELS if c.is_user_channel]
ALL_CHANNEL_IDS = [c.id for c in CHANNELS]


def get_channel(channel_id: int) -> Channel | None:
    for c in CHANNELS:
        if c.id == channel_id:
            return c
    return None


def get_channel_name(channel_id: int, lang: str = "zh") -> str:
    c = get_channel(channel_id)
    if c is None:
        return "Unknown"
    return c.name_zh if lang == "zh" else c.name_en


def get_channel_display(channel_id: int, lang: str = "zh") -> str:
    c = get_channel(channel_id)
    if c is None:
        return "❓ Unknown"
    name = c.name_zh if lang == "zh" else c.name_en
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

REACTION_EMOJIS = ["🌸", "🤣", "💔", "🤗", "❓"]

REACTION_MEANINGS = {
    "🌸": {"zh": "送你一朵花", "en": "A flower for you"},
    "🤣": {"zh": "笑死", "en": "LOL"},
    "💔": {"zh": "心碎", "en": "Heartbreak"},
    "🤗": {"zh": "抱抱", "en": "Hugs"},
    "❓": {"zh": "离谱", "en": "WTF"},
}


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
