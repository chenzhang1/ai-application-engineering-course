# EX-13-06 | Semaphore 并发限制：10 个任务最多同时 3 个（对端保护）
# 运行：python3 示例代码/ch13_asyncio/ex_13_06_semaphore.py
import asyncio
import time

MAX_CONCURRENCY = 3
_running = 0          # 当前并发数（演示用全局计数，工程代码请用上下文隔离）
_max_seen = 0


async def call_remote_api(task_id: int, sem: asyncio.Semaphore) -> int:
    global _running, _max_seen
    async with sem:  # 进入信号量：拿不到许可的协程在此挂起，不会占用事件循环
        _running += 1
        _max_seen = max(_max_seen, _running)
        await asyncio.sleep(0.2)  # 模拟一次 200ms 的远程调用
        _running -= 1
    return task_id


async def main() -> None:
    sem = asyncio.Semaphore(MAX_CONCURRENCY)
    started = time.perf_counter()
    ids = await asyncio.gather(*(call_remote_api(i, sem) for i in range(10)))
    elapsed = time.perf_counter() - started
    print(f"10 个任务全部完成：{ids}")
    print(f"实际观测到的最大并发 = {_max_seen}（信号量上限 {MAX_CONCURRENCY}，未被突破）")
    print(f"总耗时 {elapsed:.2f}s（理论下限 = ceil(10/3)×0.2 = 0.8s）")


if __name__ == "__main__":
    asyncio.run(main())
