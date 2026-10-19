# EX-19-03 | Redis 缓存（cache-aside）：fakeredis 默认全程可跑；配置 REDIS_URL 可切真实 Redis
# 运行：python3 示例代码/ch19_data_cache/ex_19_03_redis_cache.py
# 切真实 Redis：REDIS_URL=redis://127.0.0.1:6379/5 python3 示例代码/ch19_data_cache/ex_19_03_redis_cache.py
import json
import os
import time
from typing import Any

import fakeredis

_miss = 0
_hit = 0


def build_client() -> Any:
    url = os.environ.get("REDIS_URL", "")
    if url:
        import redis  # redis-py（fakeredis 的传递依赖）
        client = redis.Redis.from_url(url, decode_responses=True, socket_connect_timeout=2.0)
        client.ping()
        print(f"[后端] 真实 Redis：{url}")
        return client
    print("[后端] fakeredis（未配置 REDIS_URL，离线可运行）")
    return fakeredis.FakeRedis(decode_responses=True)


def expensive_query(order_id: str) -> dict[str, Any]:
    """模拟昂贵调用：查库/调模型，耗时 100ms。"""
    time.sleep(0.1)
    return {"order_id": order_id, "status": "paid", "amount": 129.0}


def get_order_cached(client: Any, order_id: str, ttl: int = 2) -> dict[str, Any]:
    """cache-aside 模式：先查缓存 → 未命中回源 → 写回缓存（带 TTL）。"""
    global _miss, _hit
    key = f"order:{order_id}"
    cached = client.get(key)
    if cached is not None:
        _hit += 1
        return {"data": json.loads(cached), "from": "cache"}
    _miss += 1
    data = expensive_query(order_id)
    client.set(key, json.dumps(data), ex=ttl)  # ex=TTL 秒
    return {"data": data, "from": "db"}


def main() -> None:
    client = build_client()
    started = time.perf_counter()
    r1 = get_order_cached(client, "ORD-10001")          # 未命中 → 回源
    t1 = time.perf_counter() - started
    r2 = get_order_cached(client, "ORD-10001")          # 命中
    r3 = get_order_cached(client, "ORD-10001")          # 命中
    print(f"[首次]  {r1['from']}  耗时 {t1 * 1000:.0f}ms（含 100ms 回源）")
    print(f"[第2次] {r2['from']}  [第3次] {r3['from']}（同一进程内 ~0ms）")

    # TTL 过期：ttl=2s，睡 2.1s 后再次未命中
    time.sleep(2.1)
    r4 = get_order_cached(client, "ORD-10001")
    print(f"[过期后] {r4['from']}（TTL 到期，重新回源）")
    print(f"[统计] 命中 {_hit} 次 / 未命中 {_miss} 次——命中率是缓存有效性的唯一裁判")
    client.close()


if __name__ == "__main__":
    main()
