# Blink.World V1 — 部署上线清单

> 按顺序执行，每完成一步打 ✅

---

## 第一步：注册账号和 API Key（约 30 分钟）

### 1.1 创建 Telegram Bot
- [ ] 打开 Telegram，搜索 @BotFather
- [ ] 发送 `/newbot`
- [ ] 输入 Bot 显示名称：`Blink.World`
- [ ] 输入 Bot username：`BlinkWorldBot`（如果被占用换一个，记下来）
- [ ] 复制 BotFather 给你的 **BOT_TOKEN**（格式：`123456:ABC-DEF...`）
- [ ] 发送 `/setdescription` → 设置 Bot 描述
- [ ] 发送 `/setabouttext` → 设置 "关于" 文本
- [ ] 发送 `/setuserpic` → 上传 Bot 头像

### 1.2 注册 OpenRouter（AI 内容生成 + 翻译）
- [ ] 访问 https://openrouter.ai/ 注册账号
- [ ] 进入 Dashboard → Keys → Create Key
- [ ] 复制 **AI_API_KEY**
- [ ] 充值至少 $10（种子内容生成约 $3-8，后续运营约 $3-6/天）

### 1.3 注册 OpenAI（AI 配图，可选）
- [ ] 如果要用 DALL-E 配图：访问 https://platform.openai.com/ 注册
- [ ] API Keys → Create → 复制 **OPENAI_API_KEY**
- [ ] 充值至少 $10（每张图 $0.04，500 张约 $20）
- [ ] 如果暂时不用配图，跳过此步，设置 `IMAGE_GEN_ENABLED=false`

### 1.4 生成安全密钥
- [ ] 生成 **WEBHOOK_SECRET**（随机字符串，用于验证 Telegram 请求）
  ```bash
  python3 -c "import secrets; print(secrets.token_urlsafe(32))"
  ```
- [ ] 生成 **ADMIN_SECRET**（用于管理 API 认证）
  ```bash
  python3 -c "import secrets; print(secrets.token_urlsafe(32))"
  ```

---

## 第二步：Railway 部署（约 20 分钟）

### 2.1 创建 Railway 项目
- [ ] 访问 https://railway.app/ 注册/登录
- [ ] New Project → 选择 "Deploy from GitHub repo"
- [ ] 连接你的 GitHub 账号，选择 blink-world 仓库
- [ ] Railway 会自动检测到 Dockerfile

### 2.2 添加 PostgreSQL
- [ ] 在 Railway 项目中 → New → Database → PostgreSQL
- [ ] 点击 PostgreSQL 实例 → Variables → 复制 **DATABASE_URL**
  （格式：`postgresql://postgres:xxx@xxx.railway.internal:5432/railway`）

### 2.3 添加 Redis
- [ ] New → Database → Redis
- [ ] 点击 Redis 实例 → Variables → 复制 **REDIS_URL**
  （格式：`redis://default:xxx@xxx.railway.internal:6379`）

### 2.4 配置环境变量
- [ ] 点击你的 backend 服务 → Variables → Add Variable
- [ ] 逐个添加：

| 变量名 | 值 | 说明 |
|--------|-----|------|
| `BOT_TOKEN` | 从 BotFather 复制 | 必填 |
| `BOT_USERNAME` | 你的 bot username（不带 @） | 必填 |
| `WEBHOOK_HOST` | `https://你的服务名.up.railway.app` | 部署后看 Settings → Domains |
| `WEBHOOK_SECRET` | 上面生成的随机串 | 必填 |
| `DATABASE_URL` | Railway 自动提供，用 `${{Postgres.DATABASE_URL}}` 引用 | 必填 |
| `REDIS_URL` | Railway 自动提供，用 `${{Redis.REDIS_URL}}` 引用 | 必填 |
| `AI_API_KEY` | OpenRouter API Key | 必填 |
| `AI_API_BASE_URL` | `https://openrouter.ai/api/v1` | 默认值 |
| `AI_MODEL` | `openai/gpt-4o` | 默认值 |
| `AI_FALLBACK_MODEL` | `openai/gpt-4o-mini` | 默认值 |
| `ADMIN_SECRET` | 上面生成的随机串 | 必填 |
| `IMAGE_GEN_ENABLED` | `true` 或 `false` | 是否启用 AI 配图 |
| `OPENAI_API_KEY` | OpenAI Key（如果配图） | 可选 |
| `APP_ENV` | `production` | 必填 |
| `LOG_LEVEL` | `INFO` | 默认值 |

### 2.5 部署
- [ ] 设置完环境变量后，Railway 会自动触发部署
- [ ] 等待 Build + Deploy 完成（约 2-3 分钟）
- [ ] 查看 Deployments 日志，确认看到：
  ```
  Database initialized, pool size 5-50
  Redis connected
  Telegram webhook registered: https://xxx.up.railway.app/webhook/telegram
  Blink.World started successfully
  ```

### 2.6 获取部署域名
- [ ] 点击服务 → Settings → Networking → Generate Domain
- [ ] 复制域名（例如 `blink-world-production.up.railway.app`）
- [ ] 回到 Variables，更新 `WEBHOOK_HOST` 为 `https://你的域名`
- [ ] Railway 会自动重新部署

---

## 第三步：验证基础功能（约 10 分钟）

### 3.1 健康检查
- [ ] 浏览器访问 `https://你的域名/health`
- [ ] 应返回 `{"status": "ok", ...}`
- [ ] 如果返回 `degraded`，检查 DB 和 Redis 连接

### 3.2 测试 Bot 基础交互
- [ ] 打开 Telegram，搜索你的 Bot
- [ ] 发送 `/start`
- [ ] 应该看到欢迎消息 + 国家选择
- [ ] 选择一个国家（或输入一个）
- [ ] 应该看到 "设置完成" + 主菜单键盘
- [ ] 点 "📖 刷故事" → 应该看到 "没有更多内容"（因为还没灌种子数据）

### 3.3 测试设置
- [ ] 点 "⚙️ 设置" → 检查语言切换、国家修改、频道订阅都能用
- [ ] 切换到 English → 界面变英文
- [ ] `/checkin` → 签到成功 +10 积分

---

## 第四步：灌入种子内容（约 30-60 分钟）

### 4.1 准备本地环境
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
```

### 4.2 填写 .env
- [ ] 填入和 Railway 一样的 `AI_API_KEY`
- [ ] **DATABASE_URL** 用 Railway 的公网地址（不是 internal 地址）
  → Railway PostgreSQL → Settings → Public Networking → Enable → 复制公网 URL
- [ ] **REDIS_URL** 同理，启用 Redis 公网访问并复制 URL
- [ ] `IMAGE_GEN_ENABLED=true`（如果有 OpenAI key）或 `false`

### 4.3 运行种子脚本
```bash
python -m scripts.seed_content
```
- [ ] 观察日志输出，确认每个频道在生成内容
- [ ] 预计耗时 30-60 分钟，取决于 API 速度
- [ ] 完成后应看到 "Total posts in DB: 1700+" 的总结

### 4.4 关闭公网数据库访问
- [ ] 种子脚本跑完后，回到 Railway 关闭 PostgreSQL 和 Redis 的公网访问
  （安全起见，生产环境只用内网通信）

---

## 第五步：完整功能验证（约 15 分钟）

### 5.1 私聊刷卡
- [ ] 回到 Telegram Bot，点 "📖 刷故事"
- [ ] 应该开始看到故事卡片（带频道标签 + 国旗 + 内容）
- [ ] 点 👍 → 翻到下一张
- [ ] 点 👎 → 翻到下一张
- [ ] 点 ⭐ → 提示"已收藏"，不翻页
- [ ] 点 ⚠️ → 提示"已举报"，翻到下一张
- [ ] 点卡片上的表情按钮（🌸🤣💔🤗❓）→ 计数变化

### 5.2 投稿
- [ ] 点 "📝 说一个" → 选频道 → 输入 30 字以上内容
- [ ] 预览 → 确认发布 → 应提示"发布成功"
- [ ] 点 "👤 我的" → 检查积分和发布数量增加
- [ ] 点 "📊 我的故事" → 能看到刚发布的内容

### 5.3 群组功能
- [ ] 把 Bot 拉入一个测试群
- [ ] 在群里发送 `/blink`
- [ ] 应该出现故事卡片（带群组模式的 inline 按钮）
- [ ] 点 👍 → 群里弹出下一张卡（旧卡保留）
- [ ] 快速连续点 → 验证防并发（不会出现两张卡）

### 5.4 邀请机制
- [ ] 在 "👤 我的" 里复制邀请链接
- [ ] 用另一个 Telegram 账号点击链接
- [ ] 新用户完成注册后，原用户应收到 "+50 积分" 通知

### 5.5 签到
- [ ] 发送 `/checkin` → "+10 积分"
- [ ] 再发一次 → "今天已经签到过了"

---

## 第六步：上线前调优（可选）

### 6.1 Railway 资源配置
- [ ] PostgreSQL：建议 Starter 或 Pro plan（至少 1GB RAM）
- [ ] Redis：建议 256MB-512MB 内存（种子图片缓存需要空间）
- [ ] Backend 服务：建议 512MB+ RAM

### 6.2 监控
- [ ] 定期检查 `https://你的域名/health`
- [ ] Railway 自带日志监控，关注 ERROR 级别日志
- [ ] 如需详细监控：`https://你的域名/health/detailed`（需 Admin Secret header）

### 6.3 内容补充
- [ ] 每周可以再跑一次种子脚本补充新内容
- [ ] 或设置定时任务自动生成（tasks.py 已有框架）
- [ ] 运营频道（环球风光、每日精选、每日话题）需要人工策划内容

---

## 环境变量速查表

| 变量 | 必填 | 从哪里获取 |
|------|------|-----------|
| BOT_TOKEN | ✅ | Telegram @BotFather |
| BOT_USERNAME | ✅ | 你创建 Bot 时的 username |
| WEBHOOK_HOST | ✅ | Railway 部署域名 |
| WEBHOOK_SECRET | ✅ | 自己生成的随机串 |
| DATABASE_URL | ✅ | Railway PostgreSQL |
| REDIS_URL | ✅ | Railway Redis |
| AI_API_KEY | ✅ | OpenRouter |
| ADMIN_SECRET | ✅ | 自己生成的随机串 |
| OPENAI_API_KEY | 可选 | OpenAI（配图用） |
| IMAGE_GEN_ENABLED | 可选 | `true` / `false` |
| APP_ENV | ✅ | `production` |

---

## 预估成本（月）

| 项目 | 费用 |
|------|------|
| Railway（Backend + DB + Redis）| $5-20/月 |
| OpenRouter（翻译 + 内容生成）| $90-180/月（1000条/天） |
| OpenAI DALL-E（配图，可选）| $20-60/月 |
| **总计** | **$115-260/月** |

> 以上基于 5-10 万 DAU 的初期估算。随用户量增长，主要成本增长点是 AI 翻译。

---

*完成以上所有步骤后，Bot 即可对外运营。*
