# ch19 测试 | SQL 注入防护、只读防线、缓存命中/TTL、固定窗口限流
# 运行：cd /workspace/ai_application_course && python3 -m pytest 测试/test_ch19.py -v
import sqlite3
import time

import fakeredis
import pytest

from 示例代码.ch19_data_cache.ex_19_04_rate_limit_fixed_window import FixedWindowLimiter


def _seed_users() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, password TEXT)")
    conn.executemany("INSERT INTO users (name, password) VALUES (?, ?)",
                     [("alice", "s3cret!"), ("bob", "hunter2")])
    conn.commit()
    return conn


def test_parameterized_query_blocks_injection():
    conn = _seed_users()
    evil = "' OR '1'='1' --"

    # 拼接：被注入，全表泄露（先看见漏洞，再验证防线）
    rows_vuln = conn.execute(
        f"SELECT id FROM users WHERE name = '{evil}' AND password = 'x'").fetchall()
    assert len(rows_vuln) == 2

    # 参数化：输入只是数据
    rows_safe = conn.execute(
        "SELECT id FROM users WHERE name = ? AND password = ?", (evil, "x")).fetchall()
    assert rows_safe == []
    conn.close()


def test_query_only_connection_blocks_writes():
    conn = _seed_users()
    conn.execute("PRAGMA query_only = ON")
    with pytest.raises(sqlite3.OperationalError):
        conn.execute("DELETE FROM users")
    assert conn.execute("SELECT count(*) FROM users").fetchone()[0] == 2  # 数据完好
    conn.close()


def test_cache_aside_hit_and_expiry():
    client = fakeredis.FakeRedis(decode_responses=True)
    calls: list[str] = []

    def source(key: str) -> str:
        calls.append(key)  # 记录"回源"次数
        return f"value-of-{key}"

    def get(key: str, ttl: int) -> str:
        cached = client.get(key)
        if cached is not None:
            return cached
        value = source(key)
        client.set(key, value, ex=ttl)
        return value

    assert get("k", 1) == "value-of-k"   # 未命中 → 回源
    assert get("k", 1) == "value-of-k"   # 命中
    assert get("k", 1) == "value-of-k"   # 命中
    assert calls == ["k"]                # 只回源了 1 次

    time.sleep(1.05)                     # TTL=1s 过期
    assert client.get("k") is None
    get("k", 1)
    assert calls == ["k", "k"]           # 过期后重新回源
    client.close()


def test_fixed_window_limiter_limit_and_rollover():
    limiter = FixedWindowLimiter(fakeredis.FakeRedis(decode_responses=True),
                                 limit=3, window_seconds=1)
    verdicts = [limiter.hit("u1")[0] for _ in range(5)]
    assert verdicts == [True, True, True, False, False]  # 前 3 放行，后 2 拒绝

    time.sleep(1.05)  # 窗口翻页
    ok, count = limiter.hit("u1")
    assert ok and count == 1  # 新窗口计数复位

    ok_bob, _ = limiter.hit("u2")
    assert ok_bob  # 不同调用方 key 隔离
