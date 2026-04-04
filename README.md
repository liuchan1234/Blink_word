# Blink.World Backend

Anonymous real story platform on Telegram.

## Quick Start

```bash
# Requirements: Python 3.12+, PostgreSQL, Redis

# Install dependencies
pip install -r requirements.txt

# Copy and fill env vars
cp .env.example .env
# Edit .env with your values

# Run locally
uvicorn app.main:app --reload --port 8000

# Check health
curl http://localhost:8000/health
```

## Project Structure

```
app/
  main.py              # FastAPI entry + lifespan
  config.py            # Environment variables (pydantic-settings)
  database.py          # asyncpg pool + auto-migration
  redis_client.py      # Redis wrapper (cache/lock/rate-limit)
  ai_client.py         # OpenRouter AI abstraction
  telegram_helpers.py  # Telegram Bot API calls
  models.py            # Data models + channels + constants
  algorithm.py         # Recommendation (pure functions, no I/O)
  i18n.py              # 5 languages × 59 keys
  tasks.py             # Background tasks (daily topic, pre-translate, milestones)
  handlers/            # Telegram message/callback handlers
  services/            # Business logic + DB operations
  routes/              # HTTP routes (webhook, health)
migrations/            # SQL migration files (idempotent)
scripts/               # Seed content generation
```

## Environment Variables

See `.env.example` for full list. Required:
- `BOT_TOKEN` — from @BotFather
- `DATABASE_URL` — PostgreSQL connection string
- `REDIS_URL` — Redis connection string
- `AI_API_KEY` — OpenRouter API key
- `WEBHOOK_HOST` — public HTTPS URL
- `WEBHOOK_SECRET` — random string for webhook verification
- `ADMIN_SECRET` — random string for admin API
- `ADMIN_USER_IDS` — comma-separated Telegram user IDs for Bot admin

## Deployment

See `DEPLOY.md` for full Railway deployment guide.

## Seed Content

```bash
# Generate 1700+ AI stories across all channels
python -m scripts.seed_content
```
