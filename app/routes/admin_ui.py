"""
Blink.World — Admin Management UI

Routes:
  GET  /admin                     首页 / 数据总览
  GET  /admin/personas            虚拟用户列表
  GET  /admin/personas/new        新建虚拟用户
  POST /admin/personas/new        提交新建
  POST /admin/personas/{id}/delete 删除虚拟用户
  GET  /admin/posts/new           手动新增故事
  POST /admin/posts/new           提交单篇
  GET  /admin/posts/bulk          批量上传（CSV / XLSX）
  POST /admin/posts/bulk          处理上传文件
  GET  /admin/posts/template      下载 CSV 模板
  GET  /admin/posts               帖子列表
  POST /admin/posts/{id}/toggle   上架 / 下架
  POST /admin/posts/{id}/delete   永久删除
  POST /admin/api/import          JSON 批量导入 API
"""

from __future__ import annotations

import csv
import html
import io
import logging
import random
import time
from secrets import compare_digest
from urllib.parse import quote_plus

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from app.config import get_settings
from app.database import get_pool
from app.models import CHANNELS, ContentSource, Limits
from app.services.post_service import create_post

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin-ui"], include_in_schema=False)
security = HTTPBasic(auto_error=False)

# ── Persona ID range (won't clash with real Telegram IDs) ──
PERSONA_ID_MIN = 9_000_000_000
PERSONA_ID_MAX = 9_999_999_999

CHANNEL_NAME_MAP: dict[str, int] = {
    "环球旅行": 1, "今日头条": 2, "深夜树洞": 3,
    "沙雕日常": 4, "我吃什么": 5, "恋爱日记": 6,
    "人间真实": 7, "立个Flag": 8, "记录此刻": 9,
    "萌宠": 10, "我要搞钱": 11,
    # English aliases
    "travel": 1, "news": 2, "confessions": 3,
    "wtf": 4, "food": 5, "love": 6,
    "nofilter": 7, "goals": 8, "moments": 9,
    "pets": 10, "money": 11,
}

SAMPLE_COUNTRIES = [
    "中国", "日本", "韩国", "美国", "英国", "法国", "德国",
    "巴西", "印度", "俄罗斯", "新加坡", "马来西亚", "泰国",
]


# ══════════════════════════════════════════════
# HTML helpers
# ══════════════════════════════════════════════

def _nav() -> str:
    return """
<nav>
  <a href="/admin">🏠 首页</a>
  <a href="/admin/personas">👤 虚拟用户</a>
  <a href="/admin/posts/new">✏️ 新增故事</a>
  <a href="/admin/posts/bulk">📤 批量上传</a>
  <a href="/admin/posts">📋 帖子列表</a>
</nav>"""


def _page(title: str, inner: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} — Blink Admin</title>
<style>
:root {{
  --bg:#0f0d14; --card:#1a1625; --text:#e8e4f0; --muted:#8b8498;
  --accent:#a78bfa; --ok:#22c55e; --err:#ef4444;
  --border:rgba(255,255,255,.08);
}}
* {{ box-sizing:border-box; margin:0; padding:0; }}
body {{ font-family:system-ui,-apple-system,sans-serif; background:var(--bg); color:var(--text); padding:24px; line-height:1.6; }}
a {{ color:var(--accent); text-decoration:none; }}
a:hover {{ text-decoration:underline; }}

/* layout */
header {{ margin-bottom:24px; }}
header h1 {{ font-size:1.3rem; margin-bottom:10px; }}
nav {{ display:flex; flex-wrap:wrap; gap:6px; margin-bottom:4px; }}
nav a {{ padding:5px 12px; border-radius:20px; background:var(--card); border:1px solid var(--border); font-size:13px; }}
nav a:hover {{ border-color:var(--accent); text-decoration:none; }}

/* cards & forms */
.card {{ background:var(--card); border:1px solid var(--border); border-radius:12px; padding:20px; max-width:760px; margin-bottom:20px; }}
.card-wide {{ max-width:100%; overflow-x:auto; }}
label {{ display:block; font-size:12px; color:var(--muted); margin:14px 0 5px; }}
input[type=text], input[type=number], input[type=file], textarea, select {{
  width:100%; padding:9px 12px; border-radius:8px; border:1px solid var(--border);
  background:#12101a; color:var(--text); font-size:14px;
}}
input[type=file] {{ padding:6px; cursor:pointer; }}
textarea {{ min-height:130px; resize:vertical; }}
.textarea-wrap {{ border:1px solid var(--border); border-radius:8px; background:#12101a; overflow:hidden; }}
.textarea-wrap textarea {{ width:100%; border:none; border-radius:0; padding:10px 12px; display:block; min-height:130px; resize:vertical; }}
.textarea-wrap textarea:focus {{ outline:none; }}
.textarea-wrap:focus-within {{ box-shadow:0 0 0 1px rgba(167,139,250,.35); }}
.emoji-bar {{ display:flex; gap:6px; flex-wrap:wrap; padding:8px 10px; border-top:1px solid var(--border); background:rgba(0,0,0,.18); }}
.emoji-btn {{ padding:7px 13px; border-radius:8px; border:none; cursor:pointer; background:#2e8b57; color:#fff; font-size:1.05rem; }}

/* buttons */
button, .btn {{
  display:inline-block; margin-top:14px; padding:9px 18px; border-radius:8px;
  border:none; background:linear-gradient(135deg,#7c3aed,#6366f1); color:#fff;
  font-weight:600; cursor:pointer; font-size:14px; text-decoration:none;
}}
.btn-sm {{ padding:4px 10px; font-size:12px; margin-top:0; border-radius:6px; }}
.btn-danger {{ background:linear-gradient(135deg,#dc2626,#b91c1c) !important; }}
.btn-warn {{ background:linear-gradient(135deg,#d97706,#b45309) !important; }}
.btn-ok {{ background:linear-gradient(135deg,#059669,#047857) !important; }}
.btn-ghost {{ background:#2a2535 !important; border:1px solid var(--border); }}

/* messages */
.msg {{ padding:11px 15px; border-radius:8px; margin-bottom:16px; font-size:14px; }}
.msg.ok {{ background:rgba(34,197,94,.12); border:1px solid rgba(34,197,94,.3); color:#4ade80; }}
.msg.err {{ background:rgba(239,68,68,.12); border:1px solid rgba(239,68,68,.3); color:#fca5a5; }}
.msg.info {{ background:rgba(167,139,250,.1); border:1px solid rgba(167,139,250,.25); }}

/* table */
table {{ width:100%; border-collapse:collapse; font-size:13px; }}
th, td {{ text-align:left; padding:8px 10px; border-bottom:1px solid var(--border); vertical-align:middle; }}
th {{ color:var(--muted); font-weight:600; white-space:nowrap; }}
td {{ word-break:break-word; }}
tr:last-child td {{ border-bottom:none; }}

/* stats row */
.stats {{ display:flex; gap:16px; flex-wrap:wrap; margin-bottom:24px; }}
.stat {{ background:var(--card); border:1px solid var(--border); border-radius:10px; padding:14px 20px; min-width:110px; }}
.stat small {{ display:block; font-size:11px; color:var(--muted); }}
.stat b {{ font-size:1.4rem; }}

/* badges */
.badge {{ display:inline-block; padding:2px 8px; border-radius:20px; font-size:11px; font-weight:600; white-space:nowrap; }}
.badge-ops {{ background:rgba(167,139,250,.18); color:#a78bfa; }}
.badge-ugc {{ background:rgba(34,197,94,.13); color:#22c55e; }}
.badge-persona {{ background:rgba(251,191,36,.13); color:#fbbf24; }}
.badge-on {{ background:rgba(34,197,94,.13); color:#22c55e; }}
.badge-off {{ background:rgba(239,68,68,.13); color:#fca5a5; }}

/* hint box */
.hint {{ background:rgba(167,139,250,.07); border:1px solid rgba(167,139,250,.18); border-radius:8px; padding:12px 16px; font-size:13px; color:var(--muted); margin-bottom:16px; }}
.hint code {{ color:var(--accent); background:rgba(167,139,250,.1); padding:1px 5px; border-radius:4px; }}
</style>
</head>
<body>
{inner}
</body>
</html>"""


# ══════════════════════════════════════════════
# Auth
# ══════════════════════════════════════════════

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


# ══════════════════════════════════════════════
# HOME
# ══════════════════════════════════════════════

@router.get("", response_class=HTMLResponse)
async def admin_home(_: None = Depends(require_admin)):
    pool = get_pool()
    async with pool.acquire() as conn:
        n_posts   = await conn.fetchval("SELECT COUNT(*) FROM posts")
        n_active  = await conn.fetchval("SELECT COUNT(*) FROM posts WHERE is_active = TRUE")
        n_users   = await conn.fetchval("SELECT COUNT(*) FROM users")
        n_persona = await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE id BETWEEN $1 AND $2",
            PERSONA_ID_MIN, PERSONA_ID_MAX,
        )
        n_today   = await conn.fetchval(
            "SELECT COUNT(*) FROM posts WHERE created_at > NOW() - INTERVAL '24 hours'"
        )

    body = f"""
<header>
  <h1>🌍 Blink.World 内容管理后台</h1>
  {_nav()}
</header>
<div class="stats">
  <div class="stat"><small>帖子总数</small><b>{n_posts}</b></div>
  <div class="stat"><small>上架中</small><b>{n_active}</b></div>
  <div class="stat"><small>今日新增</small><b>{n_today}</b></div>
  <div class="stat"><small>用户总数</small><b>{n_users}</b></div>
  <div class="stat"><small>虚拟用户</small><b>{n_persona}</b></div>
</div>
<div class="hint">
  认证方式：HTTP Basic，用户名任意，密码 = 环境变量 <code>ADMIN_SECRET</code>。
</div>
"""
    return HTMLResponse(_page("首页", body))


# ══════════════════════════════════════════════
# PERSONAS — 虚拟用户管理
# ══════════════════════════════════════════════

@router.get("/personas", response_class=HTMLResponse)
async def admin_personas(request: Request, _: None = Depends(require_admin)):
    msg_ok  = request.query_params.get("ok")
    msg_err = request.query_params.get("err")

    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, lang, country, points, stats, created_at
            FROM users
            WHERE id BETWEEN $1 AND $2
            ORDER BY created_at DESC
            """,
            PERSONA_ID_MIN, PERSONA_ID_MAX,
        )

    import json as _json
    rows_html = []
    for r in rows:
        stats = r["stats"]
        if isinstance(stats, (str, bytes)):
            stats = _json.loads(stats)
        label = (stats or {}).get("persona_label", "—")
        rows_html.append(
            "<tr>"
            f"<td><code>{r['id']}</code></td>"
            f"<td>{html.escape(label)}</td>"
            f"<td>{html.escape(r['lang'])}</td>"
            f"<td>{html.escape(r['country'] or '—')}</td>"
            f"<td>{r['points']}</td>"
            f"<td><small>{r['created_at'].strftime('%Y-%m-%d')}</small></td>"
            f"<td>"
            f"<form method='post' action='/admin/personas/{r['id']}/delete' style='display:inline'>"
            f"<button class='btn btn-sm btn-danger' onclick=\"return confirm('确认删除该虚拟用户？')\">删除</button>"
            f"</form>"
            f"</td>"
            "</tr>"
        )

    table_body = "\n".join(rows_html) if rows_html else "<tr><td colspan='7'>暂无虚拟用户</td></tr>"
    msg = ""
    if msg_ok:
        msg = f'<div class="msg ok">{html.escape(msg_ok)}</div>'
    if msg_err:
        msg += f'<div class="msg err">{html.escape(msg_err)}</div>'

    inner = f"""
<header>
  <h1>👤 虚拟用户管理</h1>
  {_nav()}
</header>
{msg}
<div style="margin-bottom:16px;">
  <a href="/admin/personas/new" class="btn btn-sm">＋ 新建虚拟用户</a>
</div>
<div class="card card-wide">
<table>
  <thead>
    <tr><th>ID</th><th>备注名</th><th>语言</th><th>国家</th><th>积分</th><th>创建时间</th><th>操作</th></tr>
  </thead>
  <tbody>{table_body}</tbody>
</table>
<p style="margin-top:12px;"><small>虚拟用户 ID 范围：{PERSONA_ID_MIN} – {PERSONA_ID_MAX}，不会与真实 Telegram 用户冲突。</small></p>
</div>
"""
    return HTMLResponse(_page("虚拟用户", inner))


@router.get("/personas/new", response_class=HTMLResponse)
async def admin_new_persona_form(request: Request, _: None = Depends(require_admin)):
    err = request.query_params.get("err", "")
    err_block = f'<div class="msg err">{html.escape(err)}</div>' if err else ""

    lang_opts = "".join(
        f'<option value="{l}">{l}</option>' for l in ["zh", "en", "ru", "id", "pt"]
    )
    country_opts = "".join(
        f'<option value="{c}">{c}</option>' for c in SAMPLE_COUNTRIES
    )

    inner = f"""
<header>
  <h1>＋ 新建虚拟用户</h1>
  {_nav()}
</header>
{err_block}
<div class="card">
<div class="hint">
  虚拟用户会被写入 <code>users</code> 表，ID 自动分配在 {PERSONA_ID_MIN}–{PERSONA_ID_MAX} 范围内。
  创建后可在「新增故事」中选择其作为作者，让内容看起来像真实用户发布。
</div>
<form method="post" action="/admin/personas/new">
  <label>备注名（仅后台显示，不对用户可见）</label>
  <input type="text" name="label" placeholder="例如：中国用户_01" required />

  <label>语言</label>
  <select name="lang">{lang_opts}</select>

  <label>国家/地区</label>
  <select name="country">{country_opts}</select>

  <label>初始积分（可选，默认 0）</label>
  <input type="number" name="points" value="0" min="0" max="99999" />

  <button type="submit">创建虚拟用户</button>
</form>
</div>
"""
    return HTMLResponse(_page("新建虚拟用户", inner))


@router.post("/personas/new")
async def admin_new_persona_submit(
    _: None = Depends(require_admin),
    label: str = Form(...),
    lang: str = Form("zh"),
    country: str = Form("中国"),
    points: int = Form(0),
):
    import json as _json
    pool = get_pool()
    async with pool.acquire() as conn:
        # Find an unused ID in the persona range
        existing = {r["id"] for r in await conn.fetch(
            "SELECT id FROM users WHERE id BETWEEN $1 AND $2",
            PERSONA_ID_MIN, PERSONA_ID_MAX,
        )}
        new_id = None
        for _ in range(100):
            candidate = random.randint(PERSONA_ID_MIN, PERSONA_ID_MAX)
            if candidate not in existing:
                new_id = candidate
                break
        if new_id is None:
            q = quote_plus("无法分配 ID，请稍后重试")
            return RedirectResponse(url=f"/admin/personas/new?err={q}", status_code=303)

        stats = _json.dumps({
            "views_total": 0, "published_total": 0,
            "likes_received": 0, "invited_count": 0,
            "persona_label": label.strip(),
        })
        await conn.execute(
            """
            INSERT INTO users (id, lang, country, points, onboard_state, stats)
            VALUES ($1, $2, $3, $4, 'ready', $5::jsonb)
            ON CONFLICT DO NOTHING
            """,
            new_id, lang, country, points, stats,
        )

    q = quote_plus(f"虚拟用户已创建，ID: {new_id}")
    return RedirectResponse(url=f"/admin/personas?ok={q}", status_code=303)


@router.post("/personas/{persona_id}/delete")
async def admin_delete_persona(
    persona_id: int,
    _: None = Depends(require_admin),
):
    pool = get_pool()
    async with pool.acquire() as conn:
        # Anonymise their posts before deleting
        await conn.execute("UPDATE posts SET author_id = NULL WHERE author_id = $1", persona_id)
        await conn.execute("DELETE FROM post_swipes    WHERE user_id = $1", persona_id)
        await conn.execute("DELETE FROM post_favorites WHERE user_id = $1", persona_id)
        await conn.execute("DELETE FROM post_reactions WHERE user_id = $1", persona_id)
        await conn.execute("DELETE FROM referrals WHERE inviter_id=$1 OR invitee_id=$1", persona_id)
        await conn.execute("DELETE FROM users WHERE id = $1", persona_id)

    q = quote_plus(f"虚拟用户 {persona_id} 已删除")
    return RedirectResponse(url=f"/admin/personas?ok={q}", status_code=303)


# ══════════════════════════════════════════════
# SINGLE POST — 手动新增
# ══════════════════════════════════════════════

def _channel_options(selected: int | None = None) -> str:
    opts = []
    for ch in CHANNELS:
        sel = " selected" if selected == ch.id else ""
        label = f"{ch.emoji} {ch.names.get('zh', str(ch.id))} (id={ch.id})"
        opts.append(f'<option value="{ch.id}"{sel}>{html.escape(label)}</option>')
    return "\n".join(opts)


@router.get("/posts/new", response_class=HTMLResponse)
async def admin_new_post_form(request: Request, _: None = Depends(require_admin)):
    err = request.query_params.get("err", "")
    err_block = f'<div class="msg err">{html.escape(err)}</div>' if err else ""

    # Load personas for the dropdown
    pool = get_pool()
    import json as _json
    async with pool.acquire() as conn:
        persona_rows = await conn.fetch(
            "SELECT id, stats FROM users WHERE id BETWEEN $1 AND $2 ORDER BY created_at DESC",
            PERSONA_ID_MIN, PERSONA_ID_MAX,
        )

    persona_opts = '<option value="">— 平台内容（无作者）—</option>'
    for p in persona_rows:
        st = p["stats"]
        if isinstance(st, (str, bytes)):
            st = _json.loads(st)
        lbl = (st or {}).get("persona_label", str(p["id"]))
        persona_opts += f'<option value="{p["id"]}">{html.escape(lbl)} ({p["id"]})</option>'

    sources = "".join(
        f'<option value="{s.value}"{"  selected" if s.value == "ops" else ""}>{s.name} ({s.value})</option>'
        for s in ContentSource
    )

    inner = f"""
<header>
  <h1>✏️ 手动新增故事</h1>
  {_nav()}
</header>
{err_block}
<div class="card">
<form method="post" action="/admin/posts/new">
  <label>频道</label>
  <select name="channel_id" required>{_channel_options(3)}</select>

  <label>正文（{Limits.CONTENT_MIN_LENGTH}–{Limits.CONTENT_MAX_LENGTH} 字）</label>
  <div class="textarea-wrap">
    <textarea id="post-content" name="content" required
      minlength="{Limits.CONTENT_MIN_LENGTH}" maxlength="{Limits.CONTENT_MAX_LENGTH}"
      placeholder="故事正文…"></textarea>
    <div class="emoji-bar">
      <button type="button" class="emoji-btn" data-emoji="😂">😂</button>
      <button type="button" class="emoji-btn" data-emoji="😭">😭</button>
      <button type="button" class="emoji-btn" data-emoji="🥹">🥹</button>
      <button type="button" class="emoji-btn" data-emoji="💔">💔</button>
      <button type="button" class="emoji-btn" data-emoji="🔥">🔥</button>
      <button type="button" class="emoji-btn" data-emoji="👀">👀</button>
      <button type="button" class="emoji-btn" data-emoji="…">…</button>
    </div>
  </div>
  <script>
  (function(){{
    var ta=document.getElementById("post-content");
    document.querySelectorAll(".emoji-btn").forEach(function(b){{
      b.addEventListener("click",function(){{
        var s=ta.selectionStart,e=ta.selectionEnd,em=b.getAttribute("data-emoji");
        ta.value=ta.value.slice(0,s)+em+ta.value.slice(e);
        ta.selectionStart=ta.selectionEnd=s+em.length; ta.focus();
      }});
    }});
  }})();
  </script>

  <label>语言</label>
  <select name="original_lang">
    <option value="zh">zh 中文</option>
    <option value="en">en English</option>
    <option value="ru">ru Русский</option>
    <option value="id">id Bahasa</option>
    <option value="pt">pt Português</option>
  </select>

  <label>来源</label>
  <select name="source">{sources}</select>

  <label>国家/地区（显示在卡片上，可空）</label>
  <input type="text" name="country" placeholder="例如：中国" />

  <label>虚拟用户作者</label>
  <select name="author_id">{persona_opts}</select>

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
        q = quote_plus(f"正文长度不符合要求（{Limits.CONTENT_MIN_LENGTH}–{Limits.CONTENT_MAX_LENGTH} 字）")
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

    return RedirectResponse(url=f"/admin/posts?ok=已创建帖子+{post_id}", status_code=303)


# ══════════════════════════════════════════════
# BULK UPLOAD — CSV / XLSX from Lark
# ══════════════════════════════════════════════

@router.get("/posts/template")
async def admin_download_template(_: None = Depends(require_admin)):
    """Download a CSV template compatible with Lark export."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["频道", "内容", "国家", "语言", "来源", "虚拟用户ID"])
    writer.writerow(["深夜树洞", "示例故事正文，替换成真实内容。", "中国", "zh", "ugc", ""])
    writer.writerow(["恋爱日记", "Another example story.", "美国", "en", "ops", ""])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue().encode("utf-8-sig")]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=blink_template.csv"},
    )


def _parse_channel(raw: str) -> int | None:
    raw = str(raw).strip()
    if raw.isdigit():
        ch_id = int(raw)
        if any(c.id == ch_id for c in CHANNELS):
            return ch_id
        return None
    # Try name map (strip emoji prefix)
    clean = raw.lstrip("🌍📰🌙🤪🍳💖💬😈📷🐾💰 ")
    return CHANNEL_NAME_MAP.get(clean) or CHANNEL_NAME_MAP.get(raw)


def _parse_rows_csv(data: bytes) -> tuple[list[dict], str]:
    """Parse CSV bytes → list of row dicts. Returns (rows, error_msg)."""
    try:
        text = data.decode("utf-8-sig", errors="replace")
        reader = csv.DictReader(io.StringIO(text))
        rows = list(reader)
        if not rows:
            return [], "CSV 文件为空"
        return rows, ""
    except Exception as e:
        return [], f"CSV 解析失败：{e}"


def _parse_rows_xlsx(data: bytes) -> tuple[list[dict], str]:
    """Parse XLSX bytes → list of row dicts."""
    try:
        import openpyxl
    except ImportError:
        return [], "服务器未安装 openpyxl，请上传 CSV 格式"
    try:
        wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        ws = wb.active
        rows_iter = iter(ws.iter_rows(values_only=True))
        header = [str(c or "").strip() for c in next(rows_iter, [])]
        if not header:
            return [], "XLSX 表头为空"
        result = []
        for row in rows_iter:
            result.append({header[i]: str(v or "").strip() for i, v in enumerate(row) if i < len(header)})
        return result, ""
    except Exception as e:
        return [], f"XLSX 解析失败：{e}"


# Column name aliases (Lark may export with different headers)
_COL_CHANNEL = {"频道", "channel", "channel_id", "频道id"}
_COL_CONTENT = {"内容", "正文", "content", "故事"}
_COL_COUNTRY = {"国家", "国家/地区", "country"}
_COL_LANG    = {"语言", "lang", "language", "original_lang"}
_COL_SOURCE  = {"来源", "source"}
_COL_AUTHOR  = {"虚拟用户id", "虚拟用户", "author_id", "persona_id", "persona"}


def _find_col(row: dict, aliases: set[str]) -> str | None:
    for k in row:
        if k.strip().lower() in aliases or k.strip() in aliases:
            return k
    return None


@router.get("/posts/bulk", response_class=HTMLResponse)
async def admin_bulk_form(request: Request, _: None = Depends(require_admin)):
    ok  = request.query_params.get("ok", "")
    err = request.query_params.get("err", "")
    msg = ""
    if ok:
        msg = f'<div class="msg ok">{html.escape(ok)}</div>'
    if err:
        msg += f'<div class="msg err">{html.escape(err)}</div>'

    channel_rows = "".join(
        f"<tr><td>{ch.id}</td><td>{ch.emoji} {ch.names.get('zh','')}</td></tr>"
        for ch in CHANNELS
    )

    inner = f"""
<header>
  <h1>📤 批量上传内容</h1>
  {_nav()}
</header>
{msg}
<div class="card">
  <div class="hint">
    支持从 <b>飞书（Lark）</b> 导出的 <code>.csv</code> 或 <code>.xlsx</code> 文件。<br>
    表格必须包含列：<code>频道</code>、<code>内容</code>；可选列：<code>国家</code>、<code>语言</code>、<code>来源</code>、<code>虚拟用户ID</code>。<br>
    列名顺序不限，首行为标题行。
  </div>
  <a href="/admin/posts/template" class="btn btn-sm btn-ghost" style="margin-bottom:12px;display:inline-block;">⬇ 下载 CSV 模板</a>
  <form method="post" action="/admin/posts/bulk" enctype="multipart/form-data">
    <label>上传文件（.csv 或 .xlsx）</label>
    <input type="file" name="file" accept=".csv,.xlsx" required />

    <label>默认来源（文件中未指定时使用）</label>
    <select name="default_source">
      <option value="ugc">ugc（模拟用户）</option>
      <option value="ops">ops（平台官方）</option>
    </select>

    <label>默认语言（文件中未指定时使用）</label>
    <select name="default_lang">
      <option value="zh">zh 中文</option>
      <option value="en">en English</option>
      <option value="ru">ru Русский</option>
      <option value="id">id Bahasa</option>
      <option value="pt">pt Português</option>
    </select>

    <label>默认国家（文件中未指定时随机）</label>
    <input type="text" name="default_country" placeholder="留空则随机分配" />

    <button type="submit">开始导入</button>
  </form>
</div>

<div class="card" style="max-width:400px;">
  <b style="font-size:13px;color:var(--muted);">频道 ID 对照表</b>
  <table style="margin-top:8px;">
    <thead><tr><th>ID</th><th>频道名</th></tr></thead>
    <tbody>{channel_rows}</tbody>
  </table>
</div>
"""
    return HTMLResponse(_page("批量上传", inner))


@router.post("/posts/bulk")
async def admin_bulk_submit(
    _: None = Depends(require_admin),
    file: UploadFile = File(...),
    default_source: str = Form("ugc"),
    default_lang: str = Form("zh"),
    default_country: str = Form(""),
):
    data = await file.read()
    fname = (file.filename or "").lower()

    if fname.endswith(".xlsx"):
        rows, parse_err = _parse_rows_xlsx(data)
    else:
        rows, parse_err = _parse_rows_csv(data)

    if parse_err:
        q = quote_plus(parse_err)
        return RedirectResponse(url=f"/admin/posts/bulk?err={q}", status_code=303)

    imported, errors = 0, []

    for i, row in enumerate(rows, 1):
        try:
            col_ch = _find_col(row, _COL_CHANNEL)
            col_ct = _find_col(row, _COL_CONTENT)
            if not col_ch or not col_ct:
                errors.append(f"行 {i}：找不到「频道」或「内容」列")
                continue

            ch_id = _parse_channel(row.get(col_ch, ""))
            if not ch_id:
                errors.append(f"行 {i}：未知频道「{row.get(col_ch)}」")
                continue

            content = (row.get(col_ct) or "").strip()
            if len(content) < Limits.CONTENT_MIN_LENGTH:
                errors.append(f"行 {i}：内容过短（{len(content)} 字）")
                continue
            if len(content) > Limits.CONTENT_MAX_LENGTH:
                content = content[:Limits.CONTENT_MAX_LENGTH]

            col_country = _find_col(row, _COL_COUNTRY)
            col_lang    = _find_col(row, _COL_LANG)
            col_source  = _find_col(row, _COL_SOURCE)
            col_author  = _find_col(row, _COL_AUTHOR)

            country = (row.get(col_country) if col_country else None) or default_country or random.choice(SAMPLE_COUNTRIES)
            lang    = (row.get(col_lang)    if col_lang    else None) or default_lang
            source  = (row.get(col_source)  if col_source  else None) or default_source
            if source not in ("ugc", "ops", "ai"):
                source = default_source

            aid: int | None = None
            if col_author:
                raw_aid = (row.get(col_author) or "").strip()
                if raw_aid:
                    try:
                        aid = int(raw_aid)
                    except ValueError:
                        pass

            await create_post(
                channel_id=ch_id,
                content=content,
                original_lang=lang,
                source=source,
                author_id=aid,
                country=country.strip(),
                photo_file_id=None,
                group_only=None,
            )
            imported += 1

        except Exception as e:
            errors.append(f"行 {i}：{str(e)[:120]}")

    summary = f"成功导入 {imported} 条"
    if errors:
        summary += f"，{len(errors)} 条失败：" + " | ".join(errors[:5])
        if len(errors) > 5:
            summary += f" …（共 {len(errors)} 个错误）"

    logger.info("Bulk import: %d ok, %d errors", imported, len(errors))
    param = "ok" if not errors else "err"
    q = quote_plus(summary)
    return RedirectResponse(url=f"/admin/posts/bulk?{param}={q}", status_code=303)


# ══════════════════════════════════════════════
# POST LIST + TOGGLE + DELETE
# ══════════════════════════════════════════════

@router.get("/posts", response_class=HTMLResponse)
async def admin_list_posts(request: Request, _: None = Depends(require_admin)):
    ok  = request.query_params.get("ok", "")
    err = request.query_params.get("err", "")
    ch_filter = request.query_params.get("ch", "")

    pool = get_pool()
    where = f"AND channel_id = {int(ch_filter)}" if ch_filter.isdigit() else ""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT id, channel_id, LEFT(content, 80) AS preview,
                   source, is_active, country, author_id, created_at
            FROM posts
            WHERE TRUE {where}
            ORDER BY created_at DESC
            LIMIT 100
            """
        )

    ch_filter_opts = '<option value="">全部频道</option>' + "".join(
        f'<option value="{ch.id}"{"  selected" if str(ch.id)==ch_filter else ""}>'
        f'{ch.emoji} {ch.names.get("zh","")}</option>'
        for ch in CHANNELS
    )

    rows_html = []
    for r in rows:
        prev  = html.escape((r["preview"] or "").replace("\n", " "))
        aid   = r["author_id"]
        aid_s = str(aid) if aid is not None else "—"
        badge_src = f'<span class="badge badge-{"ugc" if r["source"]=="ugc" else "ops"}">{r["source"]}</span>'
        badge_on  = f'<span class="badge badge-{"on" if r["is_active"] else "off"}">{"上架" if r["is_active"] else "下架"}</span>'
        toggle_label = "下架" if r["is_active"] else "上架"
        toggle_cls   = "btn-warn" if r["is_active"] else "btn-ok"
        pid = html.escape(r["id"])
        rows_html.append(
            "<tr>"
            f"<td><code style='font-size:11px'>{pid[:12]}…</code></td>"
            f"<td>{r['channel_id']}</td>"
            f"<td>{badge_src}</td>"
            f"<td>{badge_on}</td>"
            f"<td>{prev}</td>"
            f"<td>{html.escape(r['country'] or '—')}</td>"
            f"<td>{aid_s}</td>"
            f"<td><small>{r['created_at'].strftime('%m-%d %H:%M')}</small></td>"
            f"<td style='white-space:nowrap'>"
            f"<form method='post' action='/admin/posts/{pid}/toggle' style='display:inline'>"
            f"<button class='btn btn-sm {toggle_cls}'>{toggle_label}</button></form> "
            f"<form method='post' action='/admin/posts/{pid}/delete' style='display:inline'"
            f" onsubmit=\"return confirm('永久删除？')\">"
            f"<button class='btn btn-sm btn-danger'>删除</button></form>"
            f"</td>"
            "</tr>"
        )

    msg = ""
    if ok:
        msg = f'<div class="msg ok">{html.escape(ok)}</div>'
    if err:
        msg += f'<div class="msg err">{html.escape(err)}</div>'

    table_body = "\n".join(rows_html) if rows_html else "<tr><td colspan='9'>暂无数据</td></tr>"

    inner = f"""
<header>
  <h1>📋 帖子列表</h1>
  {_nav()}
</header>
{msg}
<form method="get" style="margin-bottom:16px;display:flex;gap:10px;align-items:center;">
  <select name="ch" style="width:auto;padding:7px 12px;">{ch_filter_opts}</select>
  <button type="submit" style="margin-top:0;">筛选</button>
  <a href="/admin/posts" class="btn btn-sm btn-ghost" style="margin-top:0;">重置</a>
</form>
<div class="card card-wide">
<table>
  <thead>
    <tr>
      <th>ID</th><th>频道</th><th>来源</th><th>状态</th>
      <th>预览</th><th>国家</th><th>作者</th><th>时间</th><th>操作</th>
    </tr>
  </thead>
  <tbody>{table_body}</tbody>
</table>
<p style="margin-top:12px;"><small>最多显示 100 条，按创建时间倒序。</small></p>
</div>
"""
    return HTMLResponse(_page("帖子列表", inner))


@router.post("/posts/{post_id}/toggle")
async def admin_toggle_post(post_id: str, _: None = Depends(require_admin)):
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT is_active FROM posts WHERE id = $1", post_id)
        if not row:
            q = quote_plus(f"帖子 {post_id} 不存在")
            return RedirectResponse(url=f"/admin/posts?err={q}", status_code=303)
        new_state = not row["is_active"]
        await conn.execute("UPDATE posts SET is_active = $1 WHERE id = $2", new_state, post_id)
    label = "上架" if new_state else "下架"
    q = quote_plus(f"帖子已{label}")
    return RedirectResponse(url=f"/admin/posts?ok={q}", status_code=303)


@router.post("/posts/{post_id}/delete")
async def admin_delete_post(post_id: str, _: None = Depends(require_admin)):
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM posts WHERE id = $1", post_id)
    q = quote_plus(f"帖子 {post_id} 已永久删除")
    return RedirectResponse(url=f"/admin/posts?ok={q}", status_code=303)


# ══════════════════════════════════════════════
# JSON Batch Import API
# ══════════════════════════════════════════════

@router.post("/api/import")
async def admin_batch_import(
    _: None = Depends(require_admin),
    stories: list[dict] = Body(..., embed=True),
):
    """
    JSON batch import.
    POST /admin/api/import  (HTTP Basic, password = ADMIN_SECRET)
    Body: {"stories": [{"channel":"深夜树洞","content":"...","country":"中国","lang":"zh","source":"ugc"}]}
    """
    imported_ids, errors = [], []

    for i, story in enumerate(stories):
        try:
            ch_id = story.get("channel_id") or _parse_channel(str(story.get("channel", "")))
            if not ch_id:
                errors.append({"index": i, "error": f"Unknown channel: {story.get('channel')}"})
                continue

            content = str(story.get("content", "")).strip()
            if len(content) < Limits.CONTENT_MIN_LENGTH:
                errors.append({"index": i, "error": "Content too short"})
                continue

            source = story.get("source", "ugc")
            if source not in ("ugc", "ops", "ai"):
                source = "ugc"

            country = story.get("country") or random.choice(SAMPLE_COUNTRIES)
            lang    = story.get("lang", "zh")
            aid     = story.get("author_id")
            if aid:
                try:
                    aid = int(aid)
                except (ValueError, TypeError):
                    aid = None

            post_id = await create_post(
                channel_id=ch_id, content=content,
                original_lang=lang, source=source,
                author_id=aid, country=country,
                photo_file_id=None, group_only=None,
            )
            imported_ids.append(post_id)
        except Exception as e:
            errors.append({"index": i, "error": str(e)[:200]})

    logger.info("API batch import: %d ok, %d errors", len(imported_ids), len(errors))
    return {"imported": len(imported_ids), "post_ids": imported_ids, "errors": errors}
