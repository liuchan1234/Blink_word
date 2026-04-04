-- 004_v2_channels.sql
-- Migrate user channel_prefs from V1 channel IDs to V2 channel IDs
--
-- V1 IDs: 1(环球风光) 2(每日精选) 3(每日话题) 4(深夜树洞) 5(恋爱日记)
--         6(人间真实) 7(萌宠) 8(校园) 9(沙雕日常) 10(我要搞钱)
--
-- V2 IDs: 1(环球旅行) 2(今日头条) 3(深夜树洞) 4(沙雕日常) 5(我吃什么)
--         6(恋爱日记) 7(人间真实) 8(立个Flag) 9(记录此刻) 10(萌宠) 11(我要搞钱)
--
-- Strategy: Reset all users to "all channels selected" (V2 default)
-- This is the safest approach since channel meanings changed completely.

UPDATE users
SET channel_prefs = '[1,2,3,4,5,6,7,8,9,10,11]'::jsonb
WHERE channel_prefs IS NOT NULL;

-- Also update any posts with old channel IDs to map to V2 IDs
-- V1 channel 1 (环球风光) → V2 channel 1 (环球旅行) — same concept, keep
-- V1 channel 2 (每日精选) → no direct equivalent, map to channel 2 (今日头条)
-- V1 channel 3 (每日话题) → removed, map to channel 3 (深夜树洞) as closest
-- V1 channel 4 (深夜树洞) → V2 channel 3
-- V1 channel 5 (恋爱日记) → V2 channel 6
-- V1 channel 6 (人间真实) → V2 channel 7
-- V1 channel 7 (萌宠)     → V2 channel 10
-- V1 channel 8 (校园)     → V2 channel 9 (记录此刻)
-- V1 channel 9 (沙雕日常) → V2 channel 4
-- V1 channel 10(我要搞钱) → V2 channel 11

-- Use a temp column to avoid conflicts during remapping
ALTER TABLE posts ADD COLUMN IF NOT EXISTS channel_id_new INT;

UPDATE posts SET channel_id_new = CASE channel_id
    WHEN 1 THEN 1    -- 环球风光 → 环球旅行
    WHEN 2 THEN 2    -- 每日精选 → 今日头条
    WHEN 3 THEN 3    -- 每日话题 → 深夜树洞
    WHEN 4 THEN 3    -- 深夜树洞 → 深夜树洞
    WHEN 5 THEN 6    -- 恋爱日记 → 恋爱日记
    WHEN 6 THEN 7    -- 人间真实 → 人间真实
    WHEN 7 THEN 10   -- 萌宠 → 萌宠
    WHEN 8 THEN 9    -- 校园 → 记录此刻
    WHEN 9 THEN 4    -- 沙雕日常 → 沙雕日常
    WHEN 10 THEN 11  -- 我要搞钱 → 我要搞钱
    ELSE channel_id
END;

UPDATE posts SET channel_id = channel_id_new WHERE channel_id_new IS NOT NULL;
ALTER TABLE posts DROP COLUMN IF EXISTS channel_id_new;
