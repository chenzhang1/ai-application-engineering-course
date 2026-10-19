# EX-19-04 | Redis 固定窗口限流：INCR+EXPIRE 的完整实现（fakeredis 可跑，接口与真实 Redis 一致）
# 运行：python3 examples/ch19_data_cache/ex_19_04_rate_limit_fixed_window.py
import time
from typing import Any

import fakeredis


class FixedWindowLimiter:
    """固定窗口计数器：把时间轴切成 window 秒的窗口，窗口内计数超过 limit 就拒绝。

    与 ch17 收束演练 app.py 中的实现一致（那里限的是 HTTP 调用方，这里直接演示算法）。
    """

    def __init__(self, client: Any, limit: int, window_seconds: int = 1) -> None:
        self.client = client
        self.limit = limit
        self.window = window_seconds

    def hit(self, caller: str) -> tuple[bool, int]:
        """返回 (是否放行, 窗口内已计数)。"""
        window_id = int(time.time()) // self.window
        key = f"rl:{caller}:{window_id}"
        count = int(self.client.incr(key))          # 原子自增：多进程/多实例共享同一计数
        if count == 1:
            self.client.expire(key, self.window + 1)  # 首次计数才设过期，窗口结束自动清零
        return count <= self.limit, count


def main() -> None:
    client = fakeredis.FakeRedis(decode_responses=True)
    limiter = FixedWindowLimiter(client, limit=5, window_seconds=1)

    allowed = 0
    blocked = 0
    for i in range(8):  # 同一秒内打 8 发
        ok, count = limiter.hit("alice")
        allowed += ok
        blocked += not ok
        print(f"  第 {i + 1} 发：{'放行' if ok else '拒绝(429)'}（窗口计数 {count}/5）")
    print(f"[窗口内] 放行 {allowed} / 拒绝 {blocked}——阈值 5 之外的请求全部 429")

    print("…等待窗口翻页（1.1s）…")
    time.sleep(1.1)
    ok, count = limiter.hit("alice")
    print(f"[新窗口] 第 1 发：{'放行' if ok else '拒绝'}（计数重新从 {count} 开始——固定窗口自动复位）")

    # 不同调用方互不影响（Redis key 按 caller 隔离）
    ok_bob, count_bob = limiter.hit("bob")
    print(f"[隔离] bob 的首次请求：{'放行' if ok_bob else '拒绝'}（计数 {count_bob}，与 alice 无关）")
    client.close()


if __name__ == "__main__":
    main()
