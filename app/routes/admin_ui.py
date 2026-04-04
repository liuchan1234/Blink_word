"""
Blink.World — Developer admin UI (HTML)

Protected by HTTP Basic: any username, password = ADMIN_SECRET.
Requires DATABASE_URL + ADMIN_SECRET. Not for public exposure.
"""

from __future__ import annotations

import html
import logging
from secrets import compare_digest
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from app.config import get_settings
from app.database import get_pool
from app.models import CHANNELS, Limits, ContentSource
from app.services.post_service import create_post

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin-ui"], include_in_schema=False)
security = HTTPBasic(auto_error=False)


def _page(title: str, inner: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
:root {{ --bg:#0f0d14; --card:#1a1625; --text:#e8e4f0; --muted:#8b8498; --accent:#a78bfa; --ok:#22c55e; --border:rgba(255,255,255,.08); }}
* {{ box-sizing:border-box; }}
body {{ font-family: system-ui, -apple-system, sans-serif; background:var(--bg); color:var(--text); margin:0; padding:24px; line-height:1.5; }}
a {{ color:var(--accent); }}
header {{ margin-bottom:24px; }}
header h1 {{ font-size:1.25rem; margin:0 0 8px; }}
nav a {{ margin-right:16px; }}
.card {{ background:var(--card); border:1px solid var(--border); border-radius:12px; padding:20px; max-width:720px; }}
label {{ display:block; font-size:12px; color:var(--muted); margin:12px 0 6px; }}
input[type=text], input[type=number], textarea, select {{
  width:100%; padding:10px 12px; border-radius:8px; border:1px solid var(--border);
  background:#12101a; color:var(--text); font-size:14px;
}}
textarea {{ min-height:140px; resize:vertical; }}
.textarea-wrap {{
  border:1px solid var(--border); border-radius:8px; background:#12101a; overflow:hidden;
}}
.textarea-wrap textarea {{
  width:100%; min-height:140px; resize:vertical; border:none; border-radius:0;
  padding:10px 12px; display:block;
}}
.textarea-wrap textarea:focus {{ outline:none; }}
.textarea-wrap:focus-within {{ box-shadow:0 0 0 1px rgba(167,139,250,.35); }}
.textarea-toolbar {{
  display:flex; gap:8px; flex-wrap:wrap; align-items:center;
  padding:8px 10px; border-top:1px solid var(--border); background:rgba(0,0,0,.18);
}}
.emoji-toolbar-btn {{
  margin:0; padding:8px 14px; border-radius:8px; border:none; cursor:pointer;
  background:#2e8b57; color:#fff; font-size:1.15rem; line-height:1;
  min-width:44px; transition:filter .15s;
}}
.emoji-toolbar-btn:hover {{ filter:brightness(1.08); }}
.emoji-toolbar-btn:active {{ filter:brightness(.92); }}
button, .btn {{
  display:inline-block; margin-top:16px; padding:10px 20px; border-radius:8px;
  border:none; background:linear-gradient(135deg,#7c3aed,#6366f1); color:#fff;
  font-weight:600; cursor:pointer; text-decoration:none; font-size:14px;
}}
.msg {{ padding:12px 16px; border-radius:8px; margin-bottom:16px; }}
.msg.ok {{ background:rgba(34,197,94,.12); border:1px solid rgba(34,197,94,.25); }}
.msg.err {{ background:rgba(239,68,68,.12); border:1px solid rgba(239,68,68,.25); }}
table {{ width:100%; border-collapse:collapse; font-size:13px; }}
th, td {{ text-align:left; padding:8px 10px; border-bottom:1px solid var(--border); vertical-align:top; }}
th {{ color:var(--muted); font-weight:600; }}
small {{ color:var(--muted); }}
.stats {{ display:flex; gap:20px; flex-wrap:wrap; margin-bottom:20px; }}
.stat {{ background:var(--card); border:1px solid var(--border); border-radius:10px; padding: 16px 20px; }}
.stat b {{ font-size:1.25rem; display:block; }}
</style>
</head>
<body>
{inner}
</body>
</html>"""


async def require_admin(credentials: HTTPBasicCredentials | None = Depends(security)) -> None:
    settings = get_settings()
    if not settings.ADMIN_SECRET:
        raise HTTPException(status_code=503, detail="ADMIN_SECRET not configured")
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": 'Basic realm="Blink Admin"'},
        )
    if not compare_digest(credentials.password, settings.ADMIN_SECRET):
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": 'Basic realm="Blink Admin"'},
        )


@router.get("", response_class=HTMLResponse)
async def admin_home(_: None = Depends(require_admin)):
    pool = get_pool()
    async with pool.acquire() as conn:
        n_posts = await conn.fetchval("SELECT COUNT(*) FROM posts")
        n_users = await conn.fetchval("SELECT COUNT(*) FROM users")
        n_active = await conn.fetchval("SELECT COUNT(*) FROM posts WHERE is_active = TRUE")

    body = f"""
<header>
  <h1>Blink.World 开发后台</h1>
  <nav>
    <a href="/admin">首页</a>
    <a href="/admin/posts/new">新增故事</a>
    <a href="/admin/posts">最近帖子</a>
  </nav>
</header>
<div class="stats">
  <div class="stat"><small>posts 总数</small><b>{n_posts}</b></div>
  <div class="stat"><small>is_active</small><b>{n_active}</b></div>
  <div class="stat"><small>users</small><b>{n_users}</b></div>
</div>
<p><small>使用 HTTP Basic：用户名任意，密码为环境变量 <code>ADMIN_SECRET</code>。</small></p>
"""
    return HTMLResponse(_page("Admin", body))


def _channel_options(selected: int | None = None) -> str:
    opts = []
    for ch in CHANNELS:
        sel = " selected" if selected == ch.id else ""
        label = f"{ch.emoji} {ch.names.get('zh', ch.id)} (id={ch.id})"
        opts.append(f'<option value="{ch.id}"{sel}>{html.escape(label)}</option>')
    return "\n".join(opts)


@router.get("/posts/new", response_class=HTMLResponse)
async def admin_new_post_form(request: Request, _: None = Depends(require_admin)):
    err = request.query_params.get("err")
    err_block = f'<div class="msg err">{html.escape(err)}</div>' if err else ""

    opts = _channel_options(3)
    sources = "".join(
        f'<option value="{s.value}">{s.name} ({s.value})</option>'
        for s in ContentSource
    )
    inner = f"""
<header>
  <h1>手动新增故事</h1>
  <nav><a href="/admin">← 后台首页</a></nav>
</header>
{err_block}
<div class="card">
<form method="post" action="/admin/posts/new">
  <label>频道</label>
  <select name="channel_id" required>{opts}</select>

  <label>正文（{Limits.CONTENT_MIN_LENGTH}–{Limits.CONTENT_MAX_LENGTH} 字，与 Bot 投稿一致）</label>
  <div class="textarea-wrap">
    <textarea id="post-content" name="content" required minlength="{Limits.CONTENT_MIN_LENGTH}" maxlength="{Limits.CONTENT_MAX_LENGTH}" placeholder="故事正文…"></textarea>
    <div class="textarea-toolbar" role="toolbar" aria-label="快捷表情">
      <button type="button" class="emoji-toolbar-btn" data-emoji="👍" title="插入 👍" aria-label="插入点赞">👍</button>
      <button type="button" class="emoji-toolbar-btn" data-emoji="👎" title="插入 👎" aria-label="插入点踩">👎</button>
      <button type="button" class="emoji-toolbar-btn" data-emoji="⭐" title="插入 ⭐" aria-label="插入星标">⭐</button>
      <button type="button" class="emoji-toolbar-btn" data-emoji="⚠️" title="插入 ⚠️" aria-label="插入警告">⚠️</button>
    </div>
  </div>
  <script>
  (function() {{
    var ta = document.getElementById("post-content");
    if (!ta) return;
    document.querySelectorAll(".emoji-toolbar-btn").forEach(function(btn) {{
      btn.addEventListener("click", function() {{
        var sym = btn.getAttribute("data-emoji") || "";
        var start = ta.selectionStart, end = ta.selectionEnd;
        var v = ta.value;
        ta.value = v.slice(0, start) + sym + v.slice(end);
        var pos = start + sym.length;
        ta.selectionStart = ta.selectionEnd = pos;
        ta.focus();
      }});
    }});
  }})();
  </script>

  <label>语言 original_lang</label>
  <select name="original_lang">
    <option value="zh">zh</option>
    <option value="en">en</option>
    <option value="ru">ru</option>
    <option value="id">id</option>
    <option value="pt">pt</option>
  </select>

  <label>来源 source</label>
  <select name="source">{sources}</select>

  <label>国家/地区（可空，显示在卡片上）</label>
  <input type="text" name="country" placeholder="例如：中国" />

  <label>作者 Telegram user_id（可空；空 = 平台内容）</label>
  <input type="text" name="author_id" placeholder="纯数字，留空则 author_id 为 NULL" />

  <button type="submit">写入数据库</button>
</form>
</div>
"""
    return HTMLResponse(_page("新增故事", inner))


@router.post("/posts/new")
async def admin_new_post_submit(
    _: None = Depends(require_admin),
    channel_id: int = Form(...),
    content: str = Form(...),
    original_lang: str = Form("zh"),
    source: str = Form("ops"),
    country: str = Form(""),
    author_id: str = Form(""),
):
    content = content.strip()
    if len(content) < Limits.CONTENT_MIN_LENGTH or len(content) > Limits.CONTENT_MAX_LENGTH:
        q = quote_plus("正文长度不符合要求")
        return RedirectResponse(url=f"/admin/posts/new?err={q}", status_code=303)

    if source not in {s.value for s in ContentSource}:
        source = ContentSource.OPS.value

    aid: int | None = None
    if author_id.strip():
        try:
            aid = int(author_id.strip())
        except ValueError:
            q = quote_plus("author_id 必须是数字")
            return RedirectResponse(url=f"/admin/posts/new?err={q}", status_code=303)

    try:
        post_id = await create_post(
            channel_id=channel_id,
            content=content,
            original_lang=original_lang or "zh",
            source=source,
            author_id=aid,
            country=country.strip(),
            photo_file_id=None,
            group_only=None,
        )
    except Exception as e:
        logger.exception("Admin create post failed: %s", e)
        q = quote_plus(str(e)[:200])
        return RedirectResponse(url=f"/admin/posts/new?err={q}", status_code=303)

    logger.info("Admin created post %s channel=%s", post_id, channel_id)
    return RedirectResponse(url=f"/admin/posts?created={post_id}", status_code=303)


@router.get("/posts", response_class=HTMLResponse)
async def admin_list_posts(request: Request, _: None = Depends(require_admin)):
    created = request.query_params.get("created")
    err = request.query_params.get("err")

    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, channel_id, LEFT(content, 80) AS preview, source, is_active,
                   country, author_id, created_at
            FROM posts
            ORDER BY created_at DESC
            LIMIT 80
            """
        )

    rows_html = []
    for r in rows:
        prev = html.escape((r["preview"] or "").replace("\n", " "))
        aid = r["author_id"]
        aid_s = str(aid) if aid is not None else "—"
        rows_html.append(
            "<tr>"
            f"<td><code>{html.escape(r['id'])}</code></td>"
            f"<td>{r['channel_id']}</td>"
            f"<td>{html.escape(r['source'])}</td>"
            f"<td>{'✓' if r['is_active'] else '✗'}</td>"
            f"<td>{prev}</td>"
            f"<td>{html.escape(r['country'] or '')}</td>"
            f"<td>{aid_s}</td>"
            f"<td><small>{r['created_at']}</small></td>"
            "</tr>"
        )

    msg = ""
    if created:
        msg = f'<div class="msg ok">已创建帖子 <code>{html.escape(created)}</code></div>'
    if err:
        msg += f'<div class="msg err">{html.escape(err)}</div>'

    table_body = "\n".join(rows_html) if rows_html else "<tr><td colspan='8'>暂无数据</td></tr>"

    inner = f"""
<header>
  <h1>最近帖子</h1>
  <nav><a href="/admin">← 后台首页</a> · <a href="/admin/posts/new">新增故事</a></nav>
</header>
{msg}
<div class="card" style="max-width:100%; overflow:auto;">
<table>
  <thead>
    <tr>
      <th>id</th><th>ch</th><th>src</th><th>on</th><th>preview</th><th>country</th><th>author</th><th>created</th>
    </tr>
  </thead>
  <tbody>
    {table_body}
  </tbody>
</table>
<p><small>最多显示 80 条，按创建时间倒序。</small></p>
</div>
"""
    return HTMLResponse(_page("帖子列表", inner))


# ══════════════════════════════════════════════
# Batch Import API (JSON) — for programmatic content injection
# ══════════════════════════════════════════════

from fastapi import Body


@router.post("/api/import")
async def admin_batch_import(
    _: None = Depends(require_admin),
    stories: list[dict] = Body(..., embed=True),
):
    """
    Batch import PGC/fake-UGC content via JSON API.

    POST /admin/api/import
    Authorization: HTTP Basic (password = ADMIN_SECRET)
    Body:
    {
      "stories": [
        {
          "channel": "深夜树洞",       // or channel_id: 3
          "content": "故事正文...",
          "source": "ugc",            // "ugc" (fake user) or "ops" (official)
          "country": "中国",           // optional, random if omitted
          "lang": "zh"                // optional, default "zh"
        }
      ]
    }

    Returns: {"imported": N, "errors": [...]}
    """
    import random

    CHANNEL_NAME_MAP = {
        "环球旅行": 1, "今日头条": 2, "深夜树洞": 3,
        "沙雕日常": 4, "我吃什么": 5, "恋爱日记": 6,
        "人间真实": 7, "立个Flag": 8, "记录此刻": 9,
        "萌宠": 10, "我要搞钱": 11,
    }
    COUNTRIES = [
        "中国", "日本", "韩国", "美国", "英国", "法国", "德国",
        "巴西", "印度", "俄罗斯", "新加坡", "马来西亚", "泰国",
    ]

    imported_ids = []
    errors = []

    for i, story in enumerate(stories):
        try:
            # Resolve channel
            ch_id = story.get("channel_id")
            if not ch_id:
                ch_name = story.get("channel", "")
                ch_id = CHANNEL_NAME_MAP.get(ch_name)
            if not ch_id:
                errors.append({"index": i, "error": f"Unknown channel: {story.get('channel')}"})
                continue

            content = story.get("content", "").strip()
            if not content or len(content) < Limits.CONTENT_MIN_LENGTH:
                errors.append({"index": i, "error": "Content too short"})
                continue

            source = story.get("source", "ugc")
            if source not in ("ugc", "ops"):
                source = "ugc"

            country = story.get("country") or random.choice(COUNTRIES)
            lang = story.get("lang", "zh")

            post_id = await create_post(
                channel_id=ch_id,
                content=content,
                original_lang=lang,
                source=source,
                author_id=None,
                country=country,
                photo_file_id=None,
                group_only=None,
            )
            imported_ids.append(post_id)

        except Exception as e:
            errors.append({"index": i, "error": str(e)[:200]})

    logger.info("Batch import: %d imported, %d errors", len(imported_ids), len(errors))

    return {
        "imported": len(imported_ids),
        "post_ids": imported_ids,
        "errors": errors,
    }

