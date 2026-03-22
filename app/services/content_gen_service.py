"""
Blink.World — Content Generation Service
Per-channel AI content generation with distinct voice and tone.
Generates multi-language versions directly (zh + en).

PRD §17: AI 60-70%, each channel has independent tone prompt.
AI content is generated directly in all supported languages — no translation needed.
"""

import json
import logging
import random
from pydantic import BaseModel, Field

from app.ai_client import get_ai_client
from app.services.post_service import create_post

logger = logging.getLogger(__name__)

# ── Countries pool for realistic diversity ──
COUNTRIES_ZH = [
    "中国", "日本", "韩国", "美国", "英国", "法国", "德国",
    "巴西", "印度", "俄罗斯", "新加坡", "马来西亚", "泰国",
    "加拿大", "澳大利亚", "西班牙", "意大利", "荷兰", "瑞典",
    "墨西哥", "阿根廷", "土耳其", "波兰", "越南", "菲律宾",
]


# ── Generated content schema ──

class GeneratedStory(BaseModel):
    content_zh: str = Field(description="中文版故事内容，80-300字")
    content_en: str = Field(description="English version, natural and conversational")
    content_ru: str = Field(default="", description="Russian version")
    content_id: str = Field(default="", description="Indonesian version")
    content_pt: str = Field(default="", description="Portuguese version")
    country: str = Field(description="发帖人的国家")


# ══════════════════════════════════════════════
# Per-Channel Prompt Definitions
# ══════════════════════════════════════════════

CHANNEL_PROMPTS: dict[int, dict] = {
    1: {
        "name": "环球风光 / World Views",
        "system": (
            "你是一个热爱旅行的人，在匿名社交平台上分享自己在世界各地的见闻。\n"
            "写作风格：感性、有画面感、带点小情绪（感叹、怀念、震撼）。\n"
            "内容：描述某个地方的风景、人文、食物，文案需要牵动情绪，不要干巴巴的介绍。\n"
            "像是朋友圈里最会拍照的那个朋友发的配文。"
        ),
        "examples": [
            "在冰岛看到极光的那一刻，突然觉得之前加班到凌晨三点也值了。零下十度，风吹得脸疼，但那片绿色的光幕在头顶跳舞的时候，我哭了。",
            "京都的秋天，随便走进一个小巷子，脚下全是金色的银杏叶。一个老奶奶在门口扫落叶，看到我在拍照，笑着朝我鞠了一躬。",
        ],
    },
    4: {
        "name": "深夜树洞 / Late Night",
        "system": (
            "你是一个普通人，在深夜无法入睡时，在匿名平台上倾诉心事。\n"
            "写作风格：真实、脆弱、口语化，像是凌晨两点发的朋友圈（但朋友看不到的那种）。\n"
            "内容：秘密、confession、压力、孤独、迷茫、对过去的遗憾、不敢跟身边人说的话。\n"
            "不要鸡汤，不要正能量，要真实的人间情绪。"
        ),
        "examples": [
            "已经连续三个月在公司厕所里哭了。不是因为工作，是因为下班后回家也没人说话。",
            "今天是我和前任分手一年整。我以为我已经放下了，但刚才在街上看到一个背影很像他的人，还是鬼使神差地跟了两步。",
        ],
    },
    5: {
        "name": "恋爱日记 / Love Diary",
        "system": (
            "你是一个正在经历各种恋爱状态的人（暗恋、热恋、分手、暧昧、复合）。\n"
            "写作风格：甜蜜或扎心，充满细节，让人共鸣或心碎。\n"
            "内容：恋爱中的小事、暗恋的忐忑、分手后的余震、暧昧期的患得患失。\n"
            "要有具体的场景和对话，不要泛泛而谈。"
        ),
        "examples": [
            "他说「到家了记得说一声」的时候，我其实已经到家二十分钟了。但我没说，因为想多聊一会儿。",
            "分手后第一次在共同好友的聚会上碰到，她换了发型，笑起来还是那个样子。我假装在看手机，其实屏幕早就黑了。",
        ],
    },
    6: {
        "name": "人间真实 / Real Talk",
        "system": (
            "你是一个打工人/社会观察者，在匿名平台上说出真实想法。\n"
            "写作风格：犀利、真实、吐槽但不戾气，有点黑色幽默。\n"
            "内容：职场潜规则、社会观察、成年人才懂的无奈、阶层差异、消费主义吐槽。\n"
            "既有不满，也有自嘲和豁达。"
        ),
        "examples": [
            "今天领导跟我说「你要把公司当成自己的家」。我说好的，那我先躺沙发上睡个午觉。",
            "月薪八千的时候觉得月薪两万就能财务自由，月薪两万的时候发现只是换了个焦虑的方式活着。",
        ],
    },
    7: {
        "name": "萌宠 / Cute Pets",
        "system": (
            "你是一个养宠物的人，在匿名平台分享和毛孩子的日常。\n"
            "写作风格：温馨、搞笑、拟人化，充满对宠物的爱。\n"
            "内容：猫狗的搞笑行为、感人瞬间、养宠趣事、动物的迷惑行为。\n"
            "可以从宠物视角写，也可以从主人视角写。"
        ),
        "examples": [
            "我家猫每天早上五点准时坐在我胸口上，用爪子轻轻拍我的脸。不是因为饿了，纯粹就是想看我痛苦的表情。",
            "带狗去看病，在医院门口死活不进去。回家的时候跑得比谁都快。演技比我还好。",
        ],
    },
    8: {
        "name": "校园 / Campus",
        "system": (
            "你是一个学生（高中或大学），在匿名平台分享校园生活。\n"
            "写作风格：青春、有趣、有点中二但很真实。\n"
            "内容：上课趣事、室友关系、考试焦虑、社团生活、毕业感言、食堂吐槽。\n"
            "抓住那种「只有学生才懂」的共鸣点。"
        ),
        "examples": [
            "高数课上老师说「这个很简单」的时候，我看了看周围，大家的表情告诉我并不简单。",
            "大学四年最后悔的事就是没早点认识我现在的室友。明天就毕业了，四个人哭成了一团。",
        ],
    },
    9: {
        "name": "沙雕日常 / Funny Daily",
        "system": (
            "你是一个社死达人/段子手，在匿名平台分享离谱经历。\n"
            "写作风格：搞笑、荒诞、自嘲，节奏感要好，要有一个出其不意的反转或笑点。\n"
            "内容：社死瞬间、离谱经历、神回复、迷惑行为、搞笑误会。\n"
            "关键是要让人「笑死」而不是「尬笑」。"
        ),
        "examples": [
            "今天上班发消息吐槽领导，结果发到了工作群。更离谱的是，领导回了一句：写得不错，但有几处事实不太准确。",
            "点外卖备注了「多放辣」，骑手打电话问我：你确定吗？我说确定。结果打开一看，里面放了三根完整的干辣椒，没切。",
        ],
    },
    10: {
        "name": "我要搞钱 / Money Talk",
        "system": (
            "你是一个在搞钱路上的人（副业/创业/理财/求职），分享真实经验和感悟。\n"
            "写作风格：实在、有干货、不装逼，可以有失败经历。\n"
            "内容：副业尝试、理财踩坑、创业心得、面试经历、行业观察。\n"
            "真实比成功更重要，失败的教训比成功的鸡汤更有价值。"
        ),
        "examples": [
            "裸辞创业三个月，还没赚到一分钱，但我知道了：自由职业的重点不是自由，是职业。",
            "搞了个小红书账号卖手工饰品，第一个月营收 87 块，成本 200。但第三个月突然爆了一条，一天卖了五千。",
        ],
    },
}


# ══════════════════════════════════════════════
# Generation Pipeline
# ══════════════════════════════════════════════

async def generate_story(channel_id: int) -> dict | None:
    """
    Generate a single story for a given channel.
    Returns {content_zh, content_en, country} or None on failure.
    """
    prompt_config = CHANNEL_PROMPTS.get(channel_id)
    if not prompt_config:
        logger.warning("No prompt config for channel %d", channel_id)
        return None

    country = random.choice(COUNTRIES_ZH)

    system = (
        f"{prompt_config['system']}\n\n"
        f"要求：\n"
        f"1. 生成一条匿名故事，发帖人来自「{country}」\n"
        f"2. 同时给出 5 种语言版本：中文、英文、俄文、印尼文、葡萄牙文\n"
        f"3. 中文 80-300 字，其他语言对应翻译要自然（像当地人说话，不是机翻）\n"
        f"4. 像普通人和朋友聊天时说的话，不要文学腔\n"
        f"5. 每种语言都是母语者的表达方式，不是逐字直译\n"
        f"6. 返回 JSON:\n"
        f"   {{\"content_zh\": \"...\", \"content_en\": \"...\", \"content_ru\": \"...\", "
        f"\"content_id\": \"...\", \"content_pt\": \"...\", \"country\": \"{country}\"}}"
    )

    examples_text = ""
    if prompt_config.get("examples"):
        examples_text = "\n\n参考风格（不要照抄）：\n" + "\n---\n".join(prompt_config["examples"])

    prompt = f"Generate a story for the channel. {examples_text}"

    ai = get_ai_client()
    result = await ai.generate_json(
        system=system,
        prompt=prompt,
        schema=GeneratedStory,
        max_tokens=2048,  # More tokens needed for 5 languages
        timeout_s=45.0,
        temperature=0.85,
    )

    return result


async def generate_and_save_story(
    channel_id: int,
    image_mode: str = "none",
) -> str | None:
    """
    Generate a story and save both language versions to the database.

    image_mode:
      "none"   — pure text, no image
      "ai"     — generate AI atmosphere image (DALL-E / Stability)
      "poster" — render text as a styled poster image (大字报)
    """
    result = await generate_story(channel_id)
    if not result:
        return None

    photo_file_id = None

    # Generate image based on mode
    if image_mode == "ai":
        from app.services.image_service import generate_atmosphere_image
        img_bytes = await generate_atmosphere_image(channel_id, result["content_zh"][:80])
        if img_bytes:
            # We'll store bytes temporarily; actual file_id comes when first sent to a user
            # For seed content, we store a marker and generate on first display
            # Better approach: save bytes to a temp store, but simplest is to skip file_id
            # and let the card builder handle bytes → upload on first send.
            # For now, store as a special key in Redis for the seed script to process.
            photo_file_id = await _upload_seed_image(img_bytes)

    elif image_mode == "poster":
        from app.services.image_service import generate_poster_image
        img_bytes = generate_poster_image(result["content_zh"], channel_id)
        if img_bytes:
            photo_file_id = await _upload_seed_image(img_bytes)

    # Save post
    post_id = await create_post(
        channel_id=channel_id,
        content=result["content_zh"],
        original_lang="zh",
        source="ai",
        author_id=None,
        country=result.get("country", ""),
        photo_file_id=photo_file_id,
    )

    # Pre-save all translations (AI generated directly — no extra translation cost)
    from app.services.translation_service import save_translation
    lang_fields = {"en": "content_en", "ru": "content_ru", "id": "content_id", "pt": "content_pt"}
    for lang_code, field in lang_fields.items():
        text = result.get(field, "")
        if text:
            await save_translation(post_id, lang_code, text)

    return post_id


async def _upload_seed_image(img_bytes: bytes) -> str | None:
    """
    Upload image bytes to Telegram to get a reusable file_id.
    Uses a dedicated 'image upload' channel/chat if configured,
    otherwise stores bytes in Redis for deferred upload.
    """
    from app.services.image_service import send_photo_bytes
    from app.config import get_settings
    settings = get_settings()

    # We need a chat_id to send to. Use ADMIN chat or a staging channel.
    # For seed script, caller should set IMAGE_UPLOAD_CHAT_ID env var
    upload_chat_id = getattr(settings, "IMAGE_UPLOAD_CHAT_ID", None)
    if not upload_chat_id:
        # Fallback: store raw bytes in Redis, defer upload to first display
        from app.redis_client import get_redis
        import uuid
        key = f"img_pending:{uuid.uuid4().hex[:12]}"
        try:
            r = get_redis()
            await r.set(key, img_bytes, ex=86400 * 30)  # 30 day TTL
            return f"pending:{key}"
        except Exception as e:
            logger.warning("Failed to store pending image: %s", e)
            return None

    result = await send_photo_bytes(int(upload_chat_id), img_bytes)
    if result and result.get("photo_file_id"):
        return result["photo_file_id"]
    return None


async def batch_generate(channel_id: int, count: int = 10, image_ratio: float = 0.4) -> list[str]:
    """
    Generate multiple stories for a channel. Returns list of post_ids.

    image_ratio: fraction of posts that get images (split between AI and poster).
      e.g. 0.4 means 40% get images → 20% AI atmosphere + 20% poster.
      Remaining 60% are pure text.
    """
    import asyncio

    # Pre-decide image mode for each story
    modes = []
    for i in range(count):
        r = random.random()
        if r < image_ratio / 2:
            modes.append("ai")
        elif r < image_ratio:
            modes.append("poster")
        else:
            modes.append("none")

    post_ids = []
    # Run in batches of 5 to respect rate limits
    for i in range(0, count, 5):
        batch_size = min(5, count - i)
        batch_modes = modes[i:i + batch_size]
        tasks = [
            generate_and_save_story(channel_id, image_mode=m)
            for m in batch_modes
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for r in results:
            if isinstance(r, str):
                post_ids.append(r)
            elif isinstance(r, Exception):
                logger.warning("Batch generate failed for one story: %s", r)

        # Brief pause between batches
        if i + batch_size < count:
            await asyncio.sleep(2)

    logger.info("Batch generated %d/%d stories for channel %d (image_ratio=%.0f%%)",
                len(post_ids), count, channel_id, image_ratio * 100)
    return post_ids
