"""
Blink.World — PGC Content Batch Import

Parses .docx素材文件 and batch-imports stories into the database.
Supports both "ops" (明标 Blink.World 发行) and "ugc" (伪装用户) source types.
Images are extracted from the docx and uploaded to Cloudflare R2, with CDN URLs
stored as photo_file_id in the database.

Content format in docx:
  - Image (optional): ![IMG_xxx](media/imageN.ext) appears BEFORE its channel block
  - Channel name as a standalone line (e.g. "沙雕日常", "恋爱日记")
  - Story text follows on the next lines until the next channel name or image

Usage:
  # Import text only (no images)
  python -m scripts.import_content path/to/素材.docx

  # Import text + upload images to R2 CDN
  python -m scripts.import_content path/to/素材.docx --upload-images

  # Import as PGC (marked as ops — Blink.World official)
  python -m scripts.import_content path/to/素材.docx --source ops

  # Dry run (parse and show what would be imported, don't write to DB)
  python -m scripts.import_content path/to/素材.docx --dry-run --upload-images

  # Import with specific country tag
  python -m scripts.import_content path/to/素材.docx --country 中国

Requires: DATABASE_URL in .env, pandoc installed
For image upload: boto3 (pip install boto3)
"""

import asyncio
import argparse
import subprocess
import sys
import os
import re
import random
import logging
import zipfile
import uuid
import mimetypes
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("import_content")

# Channel name → channel_id mapping (must match models.py)
CHANNEL_NAME_MAP = {
    "环球旅行": 1,
    "今日头条": 2,
    "深夜树洞": 3,
    "沙雕日常": 4,
    "我吃什么": 5,
    "恋爱日记": 6,
    "人间真实": 7,
    "立个Flag": 8,
    "记录此刻": 9,
    "萌宠": 10,
    "我要搞钱": 11,
}

# Countries pool for fake UGC diversity
COUNTRIES = [
    "中国", "日本", "韩国", "美国", "英国", "法国", "德国",
    "巴西", "印度", "俄罗斯", "新加坡", "马来西亚", "泰国",
    "加拿大", "澳大利亚", "西班牙", "意大利", "越南", "菲律宾",
]

def get_r2_config() -> dict:
    """R2 参数来自 .env / app.config，默认值与 kissme_push/kiss-me-be/video_push/video_push.py 一致。"""
    from app.config import get_settings

    s = get_settings()
    if not s.R2_ACCESS_KEY_ID.strip() or not s.R2_SECRET_ACCESS_KEY.strip():
        raise RuntimeError(
            "R2_ACCESS_KEY_ID / R2_SECRET_ACCESS_KEY 未设置，请在项目根 .env 中配置（与 kissme video_push 相同）"
        )
    return {
        "endpoint": s.R2_ENDPOINT,
        "access_key_id": s.R2_ACCESS_KEY_ID.strip(),
        "secret_access_key": s.R2_SECRET_ACCESS_KEY.strip(),
        "bucket": s.R2_BUCKET,
        "region": s.R2_REGION,
        "cdn_url": s.R2_CDN_URL,
    }


def _get_r2_client(cfg: dict):
    import boto3

    return boto3.client(
        "s3",
        endpoint_url=cfg["endpoint"],
        aws_access_key_id=cfg["access_key_id"],
        aws_secret_access_key=cfg["secret_access_key"],
        region_name=cfg["region"],
    )


def upload_image_to_r2(data: bytes, original_filename: str) -> str:
    """
    Upload image bytes to Cloudflare R2, return public CDN URL.
    Uses a random prefix to avoid filename collisions.
    """
    ext = Path(original_filename).suffix.lower()
    unique_name = f"{uuid.uuid4().hex[:8]}_{original_filename}"
    object_key = f"blink/images/{unique_name}"

    content_type, _ = mimetypes.guess_type(original_filename)
    content_type = content_type or "image/png"

    cfg = get_r2_config()
    client = _get_r2_client(cfg)
    client.put_object(
        Bucket=cfg["bucket"],
        Key=object_key,
        Body=data,
        ContentType=content_type,
    )

    return f"{cfg['cdn_url'].rstrip('/')}/{object_key}"


def extract_image_bytes(docx_path: str, image_filename: str) -> bytes | None:
    """Extract a single image's bytes from the docx zip archive."""
    internal_path = f"word/media/{image_filename}"
    try:
        with zipfile.ZipFile(docx_path, "r") as z:
            if internal_path in z.namelist():
                return z.read(internal_path)
    except Exception as e:
        logger.warning("Failed to extract %s: %s", image_filename, e)
    return None


def parse_docx(filepath: str, upload_images: bool = False) -> list[dict]:
    """
    Parse a docx file into a list of story entries.

    Image association rule: an image appearing immediately before a channel-name
    line belongs to THAT channel's story (not the preceding entry).

    Returns list of:
      {
        "channel_id": int,
        "channel_name": str,
        "content": str,
        "photo_url": str | None,   # R2 CDN URL if uploaded, else None
        "image_filename": str | None,  # original docx media filename
      }
    """
    # Find pandoc: try PATH first, then common install locations
    pandoc_candidates = [
        "pandoc",
        "/opt/anaconda3/bin/pandoc",
        "/usr/local/bin/pandoc",
        "/opt/homebrew/bin/pandoc",
    ]
    pandoc_bin = None
    for candidate in pandoc_candidates:
        try:
            subprocess.run([candidate, "--version"], capture_output=True, check=True)
            pandoc_bin = candidate
            break
        except (FileNotFoundError, subprocess.CalledProcessError):
            continue
    if not pandoc_bin:
        logger.error("pandoc not found. Install with: brew install pandoc")
        sys.exit(1)

    result = subprocess.run(
        [pandoc_bin, filepath, "-t", "markdown"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        logger.error("pandoc failed: %s", result.stderr)
        sys.exit(1)

    lines = result.stdout.split("\n")
    entries = []
    current_channel = None
    current_content_lines = []
    # Image for the entry currently being built
    current_image_filename = None
    # Image seen in the markdown, waiting to be assigned to the NEXT channel block
    pending_image_filename = None

    # Cache: image_filename → CDN URL (avoid re-uploading the same image)
    image_url_cache: dict[str, str] = {}

    def resolve_image_url(image_filename: str | None) -> str | None:
        """Upload image to R2 if needed, return CDN URL."""
        if not image_filename or not upload_images:
            return None
        if image_filename in image_url_cache:
            return image_url_cache[image_filename]
        img_bytes = extract_image_bytes(filepath, image_filename)
        if not img_bytes:
            logger.warning("Image not found in docx: %s", image_filename)
            return None
        try:
            url = upload_image_to_r2(img_bytes, image_filename)
            image_url_cache[image_filename] = url
            logger.info("  ✓ R2 uploaded: %s → %s", image_filename, url)
            return url
        except Exception as e:
            logger.warning("R2 upload failed for %s: %s", image_filename, e)
            return None

    def flush_entry():
        nonlocal current_channel, current_content_lines, current_image_filename
        if current_channel and current_content_lines:
            content = "\n".join(current_content_lines).strip()
            # Clean up markdown artifacts: {width=... height=...}
            content = re.sub(r'\{[^}]*\}', '', content)
            content = content.strip()
            if len(content) >= 6:
                photo_url = resolve_image_url(current_image_filename)
                entries.append({
                    "channel_id": CHANNEL_NAME_MAP[current_channel],
                    "channel_name": current_channel,
                    "content": content,
                    "photo_url": photo_url,
                    "image_filename": current_image_filename,
                })
        current_content_lines = []
        current_image_filename = None

    for line in lines:
        stripped = line.strip()

        if not stripped:
            if current_content_lines:
                current_content_lines.append("")
            continue

        # ── Image line: ![IMG_xxx](media/imageN.ext){...}
        # The image belongs to the NEXT channel block, not the current one.
        if stripped.startswith("![IMG_"):
            img_match = re.search(r'\(media/([\w.\-]+)\)', stripped)
            if img_match:
                pending_image_filename = img_match.group(1)
            continue

        # Skip pandoc image attribute continuation lines
        if re.match(r'^(height|width)=', stripped):
            continue

        # ── Channel name line
        if stripped in CHANNEL_NAME_MAP:
            flush_entry()
            current_channel = stripped
            # Assign the pending image (if any) to this new entry
            current_image_filename = pending_image_filename
            pending_image_filename = None
            continue

        # ── Handle "ChannelName 内容" merged in one paragraph (edge case in docx)
        for ch_name in CHANNEL_NAME_MAP:
            if stripped.startswith(ch_name + " ") and len(stripped) > len(ch_name) + 1:
                flush_entry()
                current_channel = ch_name
                current_image_filename = pending_image_filename
                pending_image_filename = None
                # The rest of the line is the first content line
                rest = stripped[len(ch_name):].strip()
                if rest:
                    current_content_lines.append(rest)
                break
        else:
            # Normal content line
            if current_channel:
                current_content_lines.append(stripped)

    # Don't forget the last entry
    flush_entry()

    return entries


async def import_entries(
    entries: list[dict],
    source: str = "ugc",
    country: str = "",
    dry_run: bool = False,
    skip_translate: bool = False,
):
    """Import parsed entries into the database."""
    imported = 0
    skipped = 0

    for i, entry in enumerate(entries, 1):
        entry_country = country if country else random.choice(COUNTRIES)
        photo_url = entry.get("photo_url")
        image_filename = entry.get("image_filename")

        if dry_run:
            src_label = "OPS(官方)" if source == "ops" else "UGC(伪装)"
            if photo_url:
                img_info = f" 🖼 R2: {photo_url[:72]}{'…' if len(photo_url) > 72 else ''}"
            elif image_filename:
                img_info = f" 📎 docx 含图 {image_filename}（未传 R2，请加 --upload-images）"
            else:
                img_info = ""
            url_info = f"\n    URL: {photo_url}" if photo_url else ""
            logger.info(
                "[%d/%d] [DRY RUN] %s ch=%d(%s) country=%s len=%d%s",
                i, len(entries), src_label,
                entry["channel_id"], entry["channel_name"],
                entry_country, len(entry["content"]),
                img_info,
            )
            logger.info("  Preview: %s...", entry["content"][:80])
            if url_info:
                logger.info(url_info)
            imported += 1
            continue

        try:
            from app.services.post_service import create_post
            from app.services.translation_service import save_translation
            from app.ai_client import get_ai_client
            post_id = await create_post(
                channel_id=entry["channel_id"],
                content=entry["content"],
                original_lang="zh",
                source=source,
                author_id=None,
                country=entry_country,
                photo_file_id=photo_url,  # R2 CDN URL (Telegram supports URLs directly)
                group_only=None,
            )

            # Auto-translate to ALL supported languages
            translated_count = 0
            if not skip_translate:
                TRANSLATE_TARGETS = {
                    "en": "English",
                    "ru": "Russian",
                    "id": "Indonesian",
                    "pt": "Portuguese",
                }
                try:
                    ai = get_ai_client()
                    for lang_code, lang_name in TRANSLATE_TARGETS.items():
                        translated = await ai.translate(entry["content"], "Chinese", lang_name)
                        if translated and translated.strip():
                            await save_translation(post_id, lang_code, translated.strip())
                            translated_count += 1
                        await asyncio.sleep(0.3)
                except Exception as e:
                    logger.warning("Translation failed for post %s: %s", post_id, e)

            imported += 1
            if photo_url:
                short = photo_url if len(photo_url) <= 64 else photo_url[:61] + "…"
                img_tag = f" 🖼 R2: {short}"
            elif image_filename:
                img_tag = f" 📎 {image_filename}(未上传，需加 --upload-images)"
            else:
                img_tag = ""
            tl_info = f" [translated: {translated_count} langs]" if translated_count else ""
            logger.info(
                "[%d/%d] Imported post %s ch=%d(%s) country=%s%s%s",
                i, len(entries), post_id,
                entry["channel_id"], entry["channel_name"],
                entry_country, img_tag, tl_info,
            )

            if i % 5 == 0:
                await asyncio.sleep(1)

        except Exception as e:
            skipped += 1
            logger.error("[%d/%d] Failed: %s", i, len(entries), e)

    return imported, skipped


async def main():
    parser = argparse.ArgumentParser(description="Import PGC content from docx files")
    parser.add_argument("files", nargs="+", help="Path(s) to .docx content files")
    parser.add_argument("--source", choices=["ugc", "ops"], default="ugc",
                        help="Content source: ugc (fake user, default) or ops (official)")
    parser.add_argument("--country", default="",
                        help="Fixed country tag (default: random for UGC)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Parse and preview without importing")
    parser.add_argument("--skip-translate", action="store_true",
                        help="Skip AI translation (import Chinese text only)")
    parser.add_argument("--upload-images", action="store_true",
                        help="Extract images from docx and upload to Cloudflare R2 CDN")
    args = parser.parse_args()

    if args.upload_images:
        try:
            import boto3  # noqa: F401
        except ImportError:
            logger.error("boto3 not installed. Run: pip install boto3")
            sys.exit(1)
        try:
            r2 = get_r2_config()
        except RuntimeError as e:
            logger.error("%s", e)
            sys.exit(1)
        logger.info("Image upload enabled → R2 bucket: %s", r2["bucket"])
        logger.info("CDN base: %s", r2["cdn_url"])

    # Parse all files
    all_entries = []
    for filepath in args.files:
        if not os.path.exists(filepath):
            logger.error("File not found: %s", filepath)
            sys.exit(1)
        logger.info("Parsing %s (upload_images=%s)...", os.path.basename(filepath), args.upload_images)
        entries = parse_docx(filepath, upload_images=args.upload_images)
        logger.info("Parsed %d entries from %s", len(entries), os.path.basename(filepath))
        all_entries.extend(entries)

    if not all_entries:
        logger.warning("No content entries found. Check file format.")
        sys.exit(0)

    # Show summary
    from collections import Counter
    ch_counts = Counter(e["channel_name"] for e in all_entries)
    img_count = sum(1 for e in all_entries if e.get("photo_url"))
    no_img_count = sum(1 for e in all_entries if e.get("image_filename") and not e.get("photo_url"))

    logger.info("=== Content summary ===")
    for name, count in sorted(ch_counts.items(), key=lambda x: -x[1]):
        ch_id = CHANNEL_NAME_MAP[name]
        with_img = sum(1 for e in all_entries if e["channel_name"] == name and e.get("photo_url"))
        img_str = f" ({with_img} with image)" if with_img else ""
        logger.info("  Ch %2d %-8s: %d entries%s", ch_id, name, count, img_str)
    logger.info("  Total: %d entries", len(all_entries))
    if args.upload_images:
        logger.info("  Images uploaded to R2: %d", img_count)
        if no_img_count:
            logger.warning("  Images failed to upload: %d", no_img_count)
    logger.info("  Source: %s", "ops (官方发行)" if args.source == "ops" else "ugc (伪装用户)")

    if args.dry_run:
        logger.info("=== DRY RUN mode — nothing written to DB ===")
        await import_entries(all_entries, source=args.source,
                             country=args.country, dry_run=True)
        return

    # Initialize DB
    from app.config import get_settings
    from app.database import init_db, close_db
    from app.redis_client import init_redis, close_redis

    settings = get_settings()
    if not settings.DATABASE_URL:
        logger.error("DATABASE_URL not set in .env")
        sys.exit(1)

    await init_db(settings.DATABASE_URL, min_size=2, max_size=10)
    if settings.REDIS_URL:
        await init_redis(settings.REDIS_URL)

    imported, skipped = await import_entries(
        all_entries, source=args.source, country=args.country,
        skip_translate=args.skip_translate,
    )

    logger.info("=" * 50)
    logger.info("Import complete: %d imported, %d skipped", imported, skipped)

    await close_redis()
    await close_db()


if __name__ == "__main__":
    asyncio.run(main())
