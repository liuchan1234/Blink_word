-- Blink.World V1 — Initial Schema
-- All statements are idempotent (IF NOT EXISTS / DO $$ ... $$)

-- ══════════════════════════════════════════════
-- 1. Users
-- ══════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS users (
    id              BIGINT PRIMARY KEY,              -- Telegram user ID
    lang            VARCHAR(5)  NOT NULL DEFAULT 'zh',
    country         VARCHAR(64) NOT NULL DEFAULT '',
    channel_prefs   JSONB       NOT NULL DEFAULT '[1,2,3,4,5,6,7,8,9,10]',
    points          INT         NOT NULL DEFAULT 0,
    show_country    BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_checkin    TIMESTAMPTZ,
    stats           JSONB       NOT NULL DEFAULT '{"views_total":0,"published_total":0,"likes_received":0,"invited_count":0}',
    -- Onboarding state: 'new' → 'choosing_country' → 'ready'
    onboard_state   VARCHAR(32) NOT NULL DEFAULT 'new'
);

CREATE INDEX IF NOT EXISTS idx_users_country ON users (country);
CREATE INDEX IF NOT EXISTS idx_users_lang    ON users (lang);

-- ══════════════════════════════════════════════
-- 2. Posts
-- ══════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS posts (
    id              VARCHAR(64)  PRIMARY KEY,         -- UUID string
    channel_id      SMALLINT     NOT NULL,
    country         VARCHAR(64)  NOT NULL DEFAULT '',
    content         TEXT         NOT NULL,
    photo_file_id   TEXT,
    original_lang   VARCHAR(5)   NOT NULL DEFAULT 'zh',
    source          VARCHAR(10)  NOT NULL DEFAULT 'ugc',  -- ai / ops / ugc
    author_id       BIGINT       REFERENCES users(id) ON DELETE SET NULL,
    group_only      BIGINT,                           -- group chat_id if 🔒, NULL = global
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    reactions       JSONB        NOT NULL DEFAULT '{}', -- {"🌸": 47, "🤣": 3, ...}
    like_count      INT          NOT NULL DEFAULT 0,
    dislike_count   INT          NOT NULL DEFAULT 0,
    favorite_count  INT          NOT NULL DEFAULT 0,
    report_count    INT          NOT NULL DEFAULT 0,
    view_count      INT          NOT NULL DEFAULT 0,
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE  -- soft delete / moderation
);

CREATE INDEX IF NOT EXISTS idx_posts_channel     ON posts (channel_id, is_active);
CREATE INDEX IF NOT EXISTS idx_posts_created      ON posts (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_posts_author       ON posts (author_id);
CREATE INDEX IF NOT EXISTS idx_posts_country      ON posts (country);
CREATE INDEX IF NOT EXISTS idx_posts_source       ON posts (source);
CREATE INDEX IF NOT EXISTS idx_posts_group_only   ON posts (group_only) WHERE group_only IS NOT NULL;
-- For recommendation queries: active global posts sorted by creation
CREATE INDEX IF NOT EXISTS idx_posts_feed ON posts (is_active, group_only, channel_id, created_at DESC)
    WHERE is_active = TRUE AND group_only IS NULL;

-- ══════════════════════════════════════════════
-- 3. Post Reactions (emoji reactions, per user per post)
-- ══════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS post_reactions (
    user_id         BIGINT      NOT NULL,
    post_id         VARCHAR(64) NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    emoji           VARCHAR(8)  NOT NULL,             -- e.g. "🌸"
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, post_id, emoji)
);

-- Max 3 reactions per user per post enforced at application level

-- ══════════════════════════════════════════════
-- 4. Post Swipes (like / dislike)
-- ══════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS post_swipes (
    user_id         BIGINT      NOT NULL,
    post_id         VARCHAR(64) NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    action          VARCHAR(10) NOT NULL,              -- 'like' or 'dislike'
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, post_id)
);

-- ══════════════════════════════════════════════
-- 5. Post Favorites
-- ══════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS post_favorites (
    user_id         BIGINT      NOT NULL,
    post_id         VARCHAR(64) NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, post_id)
);

-- ══════════════════════════════════════════════
-- 6. Post Reports
-- ══════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS post_reports (
    user_id         BIGINT      NOT NULL,
    post_id         VARCHAR(64) NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, post_id)
);

-- ══════════════════════════════════════════════
-- 7. Post Milestones (prevent duplicate pushes)
-- ══════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS post_milestones (
    post_id         VARCHAR(64) NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    milestone_level INT         NOT NULL,              -- 10, 30, 100, 300, 1000
    triggered_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (post_id, milestone_level)
);

-- ══════════════════════════════════════════════
-- 8. Native Reactions (Telegram built-in reactions)
-- ══════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS native_reactions (
    post_id         VARCHAR(64) NOT NULL,
    message_id      BIGINT,                            -- Telegram message ID
    chat_id         BIGINT,                            -- Where the reaction happened
    emoji           VARCHAR(16) NOT NULL,
    count           INT         NOT NULL DEFAULT 0,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (post_id, emoji)
);

-- ══════════════════════════════════════════════
-- 9. Translations cache (DB-level, Redis is primary cache)
-- ══════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS translations (
    post_id         VARCHAR(64) NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    lang            VARCHAR(5)  NOT NULL,
    translated_text TEXT        NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (post_id, lang)
);

-- ══════════════════════════════════════════════
-- 10. Groups
-- ══════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS groups (
    chat_id         BIGINT      PRIMARY KEY,
    title           VARCHAR(256) DEFAULT '',
    settings        JSONB       NOT NULL DEFAULT '{}',
    added_by        BIGINT,                            -- User who added bot
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_active     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ══════════════════════════════════════════════
-- 11. Referrals
-- ══════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS referrals (
    inviter_id      BIGINT NOT NULL,
    invitee_id      BIGINT NOT NULL UNIQUE,            -- Each user can only be invited once
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (inviter_id, invitee_id)
);

CREATE INDEX IF NOT EXISTS idx_referrals_inviter ON referrals (inviter_id);

-- ══════════════════════════════════════════════
-- 12. Daily Topics
-- ══════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS daily_topics (
    topic_date      DATE        PRIMARY KEY,
    question_zh     TEXT        NOT NULL DEFAULT '',
    question_en     TEXT        NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ══════════════════════════════════════════════
-- 13. Post-to-Message mapping (track which Telegram message shows which post)
-- ══════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS post_messages (
    chat_id         BIGINT      NOT NULL,
    message_id      BIGINT      NOT NULL,
    post_id         VARCHAR(64) NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (chat_id, message_id)
);

CREATE INDEX IF NOT EXISTS idx_post_messages_post ON post_messages (post_id);
