-- 003_migrate_emojis.sql
-- Migrate reaction emojis: 🤗→😭, ❓→💀
-- Merges old emoji counts into new ones, then removes old keys from JSONB

-- Step 1: Add 🤗 counts to 😭 (for posts that had 🤗 reactions)
UPDATE posts
SET reactions = jsonb_set(
    reactions,
    '{😭}',
    (COALESCE((reactions->>'😭')::int, 0) + COALESCE((reactions->>'🤗')::int, 0))::text::jsonb
)
WHERE reactions ? '🤗' AND (reactions->>'🤗')::int > 0;

-- Step 2: Add ❓ counts to 💀
UPDATE posts
SET reactions = jsonb_set(
    reactions,
    '{💀}',
    (COALESCE((reactions->>'💀')::int, 0) + COALESCE((reactions->>'❓')::int, 0))::text::jsonb
)
WHERE reactions ? '❓' AND (reactions->>'❓')::int > 0;

-- Step 3: Remove old keys
UPDATE posts SET reactions = reactions - '🤗' WHERE reactions ? '🤗';
UPDATE posts SET reactions = reactions - '❓' WHERE reactions ? '❓';

-- Step 4: Migrate individual reaction records
UPDATE post_reactions SET emoji = '😭' WHERE emoji = '🤗';
UPDATE post_reactions SET emoji = '💀' WHERE emoji = '❓';
