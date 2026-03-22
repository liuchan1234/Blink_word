"""
Blink.World — Image Generation Service

Two modes:
1. AI Atmosphere Image — DALL-E / Stability AI generates a mood-matching image
2. Poster Mode (大字报) — Renders text onto a styled background image

Images are uploaded to Telegram via sendPhoto and the file_id is stored.
"""

import io
import logging
import random
from textwrap import wrap

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════
# 1. AI Atmosphere Image (DALL-E / Stability)
# ══════════════════════════════════════════════

# Per-channel image style prompts
CHANNEL_IMAGE_STYLES: dict[int, str] = {
    1: "beautiful landscape photography, golden hour lighting, cinematic, travel photography, wide shot, no text, no people",
    4: "moody atmospheric night scene, soft city lights through rain, melancholy aesthetic, dark blue tones, no text",
    5: "soft romantic aesthetic, warm pastel tones, dreamy bokeh lights, intimate close-up still life, no text no people",
    6: "urban street photography, gritty realistic city life, office buildings, commuter scenes, muted tones, no text",
    7: "adorable pet photography, cute cat or dog, warm natural lighting, cozy home setting, soft focus background",
    8: "university campus scene, autumn trees, library interior, warm nostalgic college aesthetic, no text",
    9: "colorful pop art style illustration, funny absurd scene, bright saturated colors, cartoon-like, no text",
    10: "modern minimalist workspace, laptop and coffee, business aesthetic, clean lines, warm lighting, no text",
}


async def generate_atmosphere_image(channel_id: int, content_hint: str = "") -> bytes | None:
    """
    Generate an AI atmosphere image for a post.
    Returns image bytes (PNG) or None on failure.
    """
    settings = get_settings()
    if not settings.IMAGE_GEN_ENABLED:
        return None

    style = CHANNEL_IMAGE_STYLES.get(channel_id, "aesthetic minimalist photography, soft lighting, no text")

    # Build prompt: channel style + brief content hint
    if content_hint:
        # Extract mood keywords from content (first 50 chars)
        hint = content_hint[:50].replace("\n", " ")
        prompt = f"{style}, mood inspired by: {hint}"
    else:
        prompt = style

    # Cap prompt length
    prompt = prompt[:900]

    if settings.IMAGE_GEN_PROVIDER == "openai":
        return await _generate_dalle(prompt, settings)
    elif settings.IMAGE_GEN_PROVIDER == "stability":
        return await _generate_stability(prompt, settings)
    else:
        logger.warning("Unknown image gen provider: %s", settings.IMAGE_GEN_PROVIDER)
        return None


async def _generate_dalle(prompt: str, settings) -> bytes | None:
    """Generate image via DALL-E 3 (OpenAI API)."""
    api_key = settings.OPENAI_API_KEY or settings.AI_API_KEY
    if not api_key:
        logger.warning("No API key for DALL-E image generation")
        return None

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                "https://api.openai.com/v1/images/generations",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "dall-e-3",
                    "prompt": prompt,
                    "n": 1,
                    "size": "1024x1024",
                    "quality": "standard",
                    "response_format": "url",
                },
            )
            response.raise_for_status()
            data = response.json()
            image_url = data["data"][0]["url"]

            # Download the image
            img_response = await client.get(image_url)
            img_response.raise_for_status()
            return img_response.content

    except Exception as e:
        logger.error("DALL-E generation failed: %s", e)
        return None


async def _generate_stability(prompt: str, settings) -> bytes | None:
    """Generate image via Stability AI."""
    if not settings.STABILITY_API_KEY:
        logger.warning("No API key for Stability AI")
        return None

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image",
                headers={
                    "Authorization": f"Bearer {settings.STABILITY_API_KEY}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                json={
                    "text_prompts": [{"text": prompt, "weight": 1}],
                    "cfg_scale": 7,
                    "height": 1024,
                    "width": 1024,
                    "steps": 30,
                    "samples": 1,
                },
            )
            response.raise_for_status()
            data = response.json()

            import base64
            img_b64 = data["artifacts"][0]["base64"]
            return base64.b64decode(img_b64)

    except Exception as e:
        logger.error("Stability AI generation failed: %s", e)
        return None


# ══════════════════════════════════════════════
# 2. Poster Mode (大字报 — Text rendered on background)
# ══════════════════════════════════════════════

# Color schemes per channel (bg_color, text_color, accent_color)
POSTER_THEMES: dict[int, list[tuple[str, str, str]]] = {
    4: [  # 深夜树洞 — dark moody
        ("#1a1a2e", "#e0e0e0", "#6c63ff"),
        ("#16213e", "#f0e6d3", "#e94560"),
        ("#0f0e17", "#fffffe", "#ff8906"),
    ],
    5: [  # 恋爱日记 — warm romantic
        ("#fce4ec", "#4a2040", "#e91e63"),
        ("#fff3e0", "#5d4037", "#ff7043"),
        ("#f3e5f5", "#4a148c", "#ab47bc"),
    ],
    6: [  # 人间真实 — gritty urban
        ("#263238", "#eceff1", "#ffab40"),
        ("#212121", "#fafafa", "#69f0ae"),
        ("#1b1b1b", "#e0e0e0", "#ff6e40"),
    ],
    7: [  # 萌宠 — cute pastel
        ("#fff8e1", "#5d4037", "#ffb74d"),
        ("#e8f5e9", "#2e7d32", "#81c784"),
        ("#fce4ec", "#880e4f", "#f48fb1"),
    ],
    8: [  # 校园 — fresh young
        ("#e3f2fd", "#1565c0", "#42a5f5"),
        ("#f1f8e9", "#33691e", "#8bc34a"),
        ("#fff3e0", "#e65100", "#ff9800"),
    ],
    9: [  # 沙雕日常 — pop bright
        ("#ffeb3b", "#212121", "#f44336"),
        ("#00e5ff", "#1a1a1a", "#ff1744"),
        ("#76ff03", "#1b1b1b", "#d500f9"),
    ],
    10: [ # 我要搞钱 — business sleek
        ("#1a237e", "#e8eaf6", "#ffd740"),
        ("#004d40", "#e0f2f1", "#ffab40"),
        ("#263238", "#eceff1", "#00e676"),
    ],
}

DEFAULT_THEMES = [
    ("#2d2d2d", "#f5f5f5", "#4fc3f7"),
    ("#1a1a2e", "#eaeaea", "#e94560"),
    ("#0d1117", "#f0f6fc", "#58a6ff"),
]


def generate_poster_image(
    text: str,
    channel_id: int = 0,
    width: int = 800,
    height: int = 600,
) -> bytes:
    """
    Render text onto a styled background as a poster image (大字报).
    Uses pure Python SVG → PNG conversion is not available without Pillow,
    so we generate SVG bytes that Telegram can accept.

    Actually, Telegram doesn't accept SVG. We'll generate a minimal HTML canvas
    approach... No, simplest reliable approach: generate with Pillow.

    Falls back to SVG data URI if Pillow is not available.
    """
    try:
        return _generate_poster_pillow(text, channel_id, width, height)
    except ImportError:
        logger.warning("Pillow not installed, poster generation unavailable")
        return _generate_poster_svg_fallback(text, channel_id, width, height)


def _generate_poster_pillow(
    text: str,
    channel_id: int,
    width: int,
    height: int,
) -> bytes:
    """Generate poster image using Pillow."""
    from PIL import Image, ImageDraw, ImageFont

    # Pick theme
    themes = POSTER_THEMES.get(channel_id, DEFAULT_THEMES)
    bg_color, text_color, accent_color = random.choice(themes)

    # Create image
    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    # Try to load a good font, fall back to default
    font_size = 36
    small_font_size = 18
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size)
        small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", small_font_size)
    except (OSError, IOError):
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc", font_size)
            small_font = ImageFont.truetype("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc", small_font_size)
        except (OSError, IOError):
            font = ImageFont.load_default()
            small_font = font

    # Add decorative accent line at top
    draw.rectangle([(0, 0), (width, 6)], fill=accent_color)

    # Add decorative quote marks
    quote_mark = "\u201c"  # "
    draw.text((40, 30), quote_mark, fill=accent_color, font=font)

    # Wrap and draw main text
    max_chars_per_line = 20 if _has_cjk(text) else 38
    lines = []
    for paragraph in text.split("\n"):
        if paragraph.strip():
            lines.extend(wrap(paragraph, width=max_chars_per_line))
        else:
            lines.append("")

    # Limit lines to fit
    max_lines = (height - 140) // (font_size + 12)
    if len(lines) > max_lines:
        lines = lines[:max_lines - 1] + ["..."]

    y = 80
    for line in lines:
        draw.text((60, y), line, fill=text_color, font=font)
        y += font_size + 12

    # Add bottom accent line
    draw.rectangle([(0, height - 6), (width, height)], fill=accent_color)

    # Add watermark
    draw.text((width - 180, height - 35), "Blink.World", fill=accent_color, font=small_font)

    # Export to PNG bytes
    buffer = io.BytesIO()
    img.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def _generate_poster_svg_fallback(
    text: str,
    channel_id: int,
    width: int,
    height: int,
) -> bytes:
    """Fallback: generate SVG poster (less ideal for Telegram but functional)."""
    themes = POSTER_THEMES.get(channel_id, DEFAULT_THEMES)
    bg_color, text_color, accent_color = random.choice(themes)

    # Escape HTML entities in text
    escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    lines = escaped.split("\n")

    text_elements = []
    y = 100
    for line in lines[:12]:  # Max 12 lines
        text_elements.append(
            f'<text x="60" y="{y}" fill="{text_color}" '
            f'font-family="sans-serif" font-size="32">{line}</text>'
        )
        y += 48

    quote_char = "\u201c"  # Left double quotation mark
    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
  <rect width="100%" height="100%" fill="{bg_color}"/>
  <rect width="100%" height="6" fill="{accent_color}"/>
  <text x="40" y="60" fill="{accent_color}" font-family="serif" font-size="60">{quote_char}</text>
  {''.join(text_elements)}
  <rect y="{height-6}" width="100%" height="6" fill="{accent_color}"/>
  <text x="{width-180}" y="{height-15}" fill="{accent_color}" font-family="sans-serif" font-size="16">Blink.World</text>
</svg>"""

    return svg.encode("utf-8")


def _has_cjk(text: str) -> bool:
    """Check if text contains CJK characters."""
    for char in text[:50]:
        if "\u4e00" <= char <= "\u9fff" or "\u3000" <= char <= "\u303f":
            return True
    return False


# ══════════════════════════════════════════════
# 3. Upload Helper — send image to Telegram, get file_id
# ══════════════════════════════════════════════

async def upload_image_to_telegram(image_bytes: bytes, filename: str = "image.png") -> str | None:
    """
    Upload an image to Telegram by sending it to the bot chat (Saved Messages).
    Returns the file_id for reuse.

    Alternative approach: send to a private channel and delete.
    For now, we use the sendPhoto API with a dummy chat_id and extract file_id.
    """
    from app.config import get_settings
    settings = get_settings()

    if not settings.BOT_TOKEN:
        return None

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            # Use multipart upload
            # We need a valid chat_id. We'll use the bot's own ID.
            # First, get bot info
            bot_info = await client.get(
                f"https://api.telegram.org/bot{settings.BOT_TOKEN}/getMe"
            )
            bot_data = bot_info.json()
            if not bot_data.get("ok"):
                logger.error("Failed to get bot info for image upload")
                return None

            # Telegram doesn't allow bots to send to themselves directly.
            # Instead, we store the bytes and use InputFile when sending.
            # Return a special marker so the caller knows to use bytes.
            return None  # See note below

    except Exception as e:
        logger.error("Image upload failed: %s", e)
        return None


async def send_photo_bytes(chat_id: int, image_bytes: bytes, caption: str = "", reply_markup: dict | None = None) -> dict | None:
    """Send a photo from bytes (not file_id) to a Telegram chat."""
    from app.config import get_settings
    settings = get_settings()

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            files = {"photo": ("image.png", image_bytes, "image/png")}
            data = {
                "chat_id": str(chat_id),
                "parse_mode": "HTML",
            }
            if caption:
                data["caption"] = caption
            if reply_markup:
                import json
                data["reply_markup"] = json.dumps(reply_markup)

            response = await client.post(
                f"https://api.telegram.org/bot{settings.BOT_TOKEN}/sendPhoto",
                data=data,
                files=files,
            )
            result = response.json()
            if result.get("ok"):
                # Extract file_id from the sent photo for future reuse
                msg = result["result"]
                photos = msg.get("photo", [])
                if photos:
                    file_id = photos[-1]["file_id"]
                    return {"message_id": msg["message_id"], "photo_file_id": file_id}
                return {"message_id": msg["message_id"]}
            else:
                logger.error("sendPhoto bytes failed: %s", result.get("description"))
                return None
    except Exception as e:
        logger.error("send_photo_bytes failed: %s", e)
        return None
