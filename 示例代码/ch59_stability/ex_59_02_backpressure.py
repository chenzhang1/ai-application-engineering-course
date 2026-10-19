# EX-59-02 | 背压：并发闸门 + 队列深度上限 + 快速拒绝 | 运行: python3 示例代码/ch59_stability/ex_59_02_backpressure.py
"""完整可运行（标准库 asyncio，离线）：限流保护的是"速率"（每分钟几个），
背压保护的是"在途量"（同时压在系统里几个）。两者都要有。

设计：asyncio.Semaphore 做并发闸门（最多 N 个在途），显式队列做等待位
（最多 M 个排队），两者都满 → 立即拒绝（对应 HTTP 503 + Retry-After），
而不是无限排队把延迟拖到雪崩。

对比 ch13：ch13 的 Semaphore 只演示"限并发"；本示例补齐"排队上限 + 快速拒绝"
这两个生产必备件（ch13 的写法在洪峰下会让所有请求无限等待）。
"""
from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field


class QueueFull(Exception):
    """队列已满：快速拒绝（HTTP 语义：503 + Retry-After 头）。"""


@dataclass
class BackpressureGate:
    """背压闸门：并发上限 N + 排队上限 M。"""

    concurrency: int
    queue_depth: int
    _sem: asyncio.Semaphore = field(init=False)
    _waiting: deque[int] = field(default_factory=deque, init=False)
    stats: dict[str, int] = field(default_factory=lambda: {"accepted": 0, "rejected": 0})

    def __post_init__(self) -> None:
        self._sem = asyncio.Semaphore(self.concurrency)

    async def run(self, req_id: int, work_ms: int) -> str:
        """带背压的请求执行：抢不到位置就立刻拒绝，绝不无限等。"""
        if len(self._waiting) >= self.queue_depth:
            self.stats["rejected"] += 1
            raise QueueFull(f"req-{req_id}：并发与队列已满（{self.concurrency}+{self.queue_depth}），快速拒绝")
        self._waiting.append(req_id)
        try:
            async with self._sem:                      # 闸门：最多 concurrency 个同时过
                self._waiting.remove(req_id)
                self.stats["accepted"] += 1
                await asyncio.sleep(work_ms / 1000)    # 模拟 LLM 调用耗时
                return f"req-{req_id} done"
        finally:
            if req_id in self._waiting:                # 异常路径兜底：别把占位留在队列里
                self._waiting.remove(req_id)


async def main_async() -> tuple[int, int, int, int]:
    gate = BackpressureGate(concurrency=3, queue_depth=2)
    # 洪峰：10 个请求几乎同时到达，每个"调用"耗时 20ms
    results = await asyncio.gather(
        *(gate.run(i, work_ms=20) for i in range(10)), return_exceptions=True)
    done = sum(1 for r in results if isinstance(r, str))
    rejected = sum(1 for r in results if isinstance(r, QueueFull))
    return done, rejected, gate.stats["accepted"], gate.stats["rejected"]


def main() -> None:
    done, rejected, acc, rej = asyncio.run(main_async())
    print("── 洪峰实验：并发上限 3 + 队列上限 2，10 个请求同时到达 ──")
    print(f"    成功完成：{done} 个（3 个在跑 + 2 个排队，跑完一个进一个）")
    print(f"    快速拒绝：{rejected} 个（排队位已满，立即 503 + Retry-After，而不是等 30s 再超时）")
    print(f"    闸门统计：accepted={acc} rejected={rej}")
    print("\n── 为什么'无限排队'是事故配置 ──")
    print("    没有队列上限时，洪峰下第 200 个请求要等前 199 个跑完——")
    print("    客户端超时断开后服务端还在算（token 白烧），重试再来一波，系统进入雪崩。")
    print("    背压三板斧：并发上限（Semaphore）+ 队列上限（快速拒绝）+ 降级（拒绝时给缓存/兜底话术）。")
    print("\n[部署注意] asyncio.Semaphore 是进程内存——uvicorn --workers 2 时每个 worker")
    print("    各有一份，总在途量 = 2×N。跨进程的并发控制要用 Redis（ch19 限流同款思路）")
    print("    或 uvicorn --limit-concurrency（ch20，进程级总闸）。")


if __name__ == "__main__":
    main()
