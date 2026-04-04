"""
Blink.World — pytest shared fixtures
Provides mock DB pool, mock Redis, and common test data.
"""

import sys
import os
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

# Ensure app is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── Fake Redis ──

class FakeRedis:
    """In-memory async Redis mock for tests."""

    def __init__(self):
        self._data: dict[str, str] = {}
        self._sets: dict[str, set] = {}
        self._ttls: dict[str, int] = {}

    async def get(self, key: str) -> str | None:
        return self._data.get(key)

    async def set(self, key: str, value, ex: int | None = None, nx: bool = False):
        if nx and key in self._data:
            return None
        self._data[key] = str(value)
        if ex:
            self._ttls[key] = ex
        return True

    async def delete(self, *keys):
        for k in keys:
            self._data.pop(k, None)
            self._sets.pop(k, None)

    async def incr(self, key: str) -> int:
        val = int(self._data.get(key, "0")) + 1
        self._data[key] = str(val)
        return val

    async def expire(self, key: str, ttl: int):
        self._ttls[key] = ttl

    async def ttl(self, key: str) -> int:
        return self._ttls.get(key, -1)

    async def sadd(self, key: str, *members) -> int:
        if key not in self._sets:
            self._sets[key] = set()
        added = 0
        for m in members:
            if m not in self._sets[key]:
                self._sets[key].add(m)
                added += 1
        return added

    async def smembers(self, key: str) -> set:
        return self._sets.get(key, set())

    async def sismember(self, key: str, member: str) -> bool:
        return member in self._sets.get(key, set())

    async def eval(self, script, num_keys, *args):
        # Simple rate limit stub: always allow
        return 1

    async def ping(self):
        return True

    def pipeline(self):
        return FakePipeline(self)


class FakePipeline:
    def __init__(self, redis: FakeRedis):
        self._redis = redis
        self._commands = []

    def incr(self, key):
        self._commands.append(("incr", key))
        return self

    def expire(self, key, ttl):
        self._commands.append(("expire", key, ttl))
        return self

    async def execute(self):
        results = []
        for cmd in self._commands:
            if cmd[0] == "incr":
                r = await self._redis.incr(cmd[1])
                results.append(r)
            elif cmd[0] == "expire":
                await self._redis.expire(cmd[1], cmd[2])
                results.append(True)
        return results


@pytest.fixture
def fake_redis():
    """Provide a fresh FakeRedis instance."""
    return FakeRedis()


@pytest.fixture
def mock_redis(fake_redis):
    """Patch redis_client.get_redis to return FakeRedis."""
    with patch("app.redis_client.get_redis", return_value=fake_redis):
        yield fake_redis


# ── Fake DB Pool ──

class FakeConnection:
    """Minimal async DB connection mock."""

    def __init__(self, rows=None, fetchval_result=None):
        self._rows = rows or []
        self._fetchval_result = fetchval_result
        self.executed = []

    async def fetch(self, query, *args):
        self.executed.append(("fetch", query, args))
        return self._rows

    async def fetchrow(self, query, *args):
        self.executed.append(("fetchrow", query, args))
        return self._rows[0] if self._rows else None

    async def fetchval(self, query, *args):
        self.executed.append(("fetchval", query, args))
        return self._fetchval_result

    async def execute(self, query, *args):
        self.executed.append(("execute", query, args))
        return "INSERT 0 1"


class FakePool:
    """Minimal async pool mock with context manager."""

    def __init__(self, conn: FakeConnection | None = None):
        self._conn = conn or FakeConnection()

    def acquire(self):
        return _FakePoolAcquire(self._conn)


class _FakePoolAcquire:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *args):
        pass


@pytest.fixture
def fake_pool():
    """Provide a FakePool factory."""
    def _factory(rows=None, fetchval_result=None):
        conn = FakeConnection(rows=rows, fetchval_result=fetchval_result)
        pool = FakePool(conn)
        return pool, conn
    return _factory


# ── Common test data ──

@pytest.fixture
def sample_post():
    """A typical post dict as returned from DB."""
    return {
        "id": "abc123",
        "channel_id": 4,
        "country": "中国",
        "content": "这是一个测试故事，已经超过三十个字了吧应该是的。",
        "photo_file_id": None,
        "original_lang": "zh",
        "source": "ugc",
        "author_id": 12345,
        "group_only": None,
        "created_at": datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc),
        "reactions": {"🌸": 5, "🤣": 2, "💔": 10, "🤗": 3, "❓": 0},
        "like_count": 15,
        "dislike_count": 3,
        "favorite_count": 4,
        "report_count": 0,
        "view_count": 50,
        "is_active": True,
    }


@pytest.fixture
def sample_user():
    """A UserProfile-like dict."""
    from app.models import UserProfile
    return UserProfile(
        id=12345,
        lang="zh",
        country="中国",
        channel_prefs=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        points=100,
        show_country=True,
        created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        last_checkin=None,
        stats={"views_total": 50, "published_total": 3, "likes_received": 10, "invited_count": 1},
    )
