-- 002_performance.sql
-- Performance indexes for 5-10万 DAU scale

-- Optimized feed query for "local pool" (same country)
-- Covers: WHERE is_active = TRUE AND group_only IS NULL AND country = $X ORDER BY created_at DESC
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_posts_feed_country
ON posts (country, created_at DESC)
WHERE is_active = TRUE AND group_only IS NULL;

-- Optimized feed query for "local pool" (same language)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_posts_feed_lang
ON posts (original_lang, created_at DESC)
WHERE is_active = TRUE AND group_only IS NULL;

-- Report rate check: quickly find high-report posts
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_posts_flagged
ON posts (report_count DESC, created_at ASC)
WHERE is_active = TRUE AND report_count > 0;

-- User favorites lookup (for profile page)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_favorites_user
ON post_favorites (user_id, created_at DESC);

-- Post reactions lookup (for reaction toggle)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_reactions_user_post
ON post_reactions (user_id, post_id);
