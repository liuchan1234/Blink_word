"""
Blink.World — Recommendation Algorithm
Pure functions for scoring and selecting content. No I/O, no database calls.
"""

import random
import math
from datetime import datetime, timezone


def compute_exposure_weight(
    like_count: int,
    dislike_count: int,
    reactions_total: int,
    view_count: int,
    created_at: datetime,
    viewer_country: str,
    viewer_lang: str,
    post_country: str,
    post_lang: str,
    channel_id: int,
    now: datetime | None = None,
) -> float:
    """
    Compute exposure weight for a post.

    Formula: quality × (1 + emotion) × freshness × affinity

    quality   = like_count / (like_count + dislike_count)
    emotion   = total_emoji / views_count
    freshness = 1 / (1 + hours_since_publish / 24)
    affinity  = 同国家 2.0 / 同语言 1.5 / 其他 1.0

    Channel 1 (环球风光) is exempt from affinity bonus.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    # Ensure created_at is timezone-aware
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    # Quality: like ratio (default 0.5 if no votes)
    total_votes = like_count + dislike_count
    quality = like_count / total_votes if total_votes > 0 else 0.5

    # Emotion: reaction engagement rate
    emotion = reactions_total / view_count if view_count > 0 else 0.0

    # Freshness: 24h half-life decay
    hours_since = max(0, (now - created_at).total_seconds() / 3600)
    freshness = 1.0 / (1.0 + hours_since / 24.0)

    # Affinity (channel 1 exempt)
    if channel_id == 1:
        affinity = 1.0
    elif post_country and viewer_country and post_country == viewer_country:
        affinity = 2.0
    elif post_lang and viewer_lang and post_lang == viewer_lang:
        affinity = 1.5
    else:
        affinity = 1.0

    weight = quality * (1.0 + emotion) * freshness * affinity
    return max(weight, 0.001)  # Floor to prevent zero-weight


def select_post_pool_strategy() -> str:
    """
    50/50 strategy: randomly decide whether to draw from
    local (same country/language) pool or global pool.
    Returns "local" or "global".
    """
    return "local" if random.random() < 0.5 else "global"


def weighted_random_select(
    posts: list[dict],
    viewer_country: str,
    viewer_lang: str,
    now: datetime | None = None,
) -> dict | None:
    """
    Select one post from a list using weighted random selection.
    Each post dict must have: like_count, dislike_count, reactions (dict),
    view_count, created_at, country, original_lang, channel_id.
    """
    if not posts:
        return None

    if now is None:
        now = datetime.now(timezone.utc)

    weights = []
    for post in posts:
        reactions_total = sum(post.get("reactions", {}).values()) if isinstance(post.get("reactions"), dict) else 0
        w = compute_exposure_weight(
            like_count=post.get("like_count", 0),
            dislike_count=post.get("dislike_count", 0),
            reactions_total=reactions_total,
            view_count=max(post.get("view_count", 1), 1),
            created_at=post["created_at"],
            viewer_country=viewer_country,
            viewer_lang=viewer_lang,
            post_country=post.get("country", ""),
            post_lang=post.get("original_lang", ""),
            channel_id=post.get("channel_id", 0),
            now=now,
        )
        weights.append(w)

    # Weighted random selection
    total = sum(weights)
    if total <= 0:
        return random.choice(posts)

    r = random.random() * total
    cumulative = 0.0
    for i, w in enumerate(weights):
        cumulative += w
        if r <= cumulative:
            return posts[i]

    return posts[-1]


def should_auto_remove(report_count: int, view_count: int) -> str:
    """
    Check if post should be demoted or removed based on report rate.
    Returns: "normal" | "demoted" | "removed"
    """
    if view_count < 10:
        return "normal"

    report_rate = report_count / view_count

    if report_rate > 0.10:
        return "removed"    # >10% → auto remove, manual review
    elif report_rate > 0.05:
        return "demoted"    # >5% → weight to zero
    else:
        return "normal"


def compute_group_rate_limit(today_swipe_count: int) -> int:
    """
    Returns minimum seconds between group swipes.
    < 50: 0 (no limit)
    50-100: 5s
    > 100: 15s
    """
    if today_swipe_count < 50:
        return 0
    elif today_swipe_count <= 100:
        return 5
    else:
        return 15
