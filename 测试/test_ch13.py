# ch13 测试 | asyncio 并发收益、阻塞伤害、超时取消、信号量、异常传播
# 运行：cd /workspace/ai_application_course && python3 -m pytest 测试/test_ch13.py -v
import asyncio
import time

import pytest


async def n_async_sleeps(n: int, delay: float) -> float:
    started = time.perf_counter()
    await asyncio.gather(*(asyncio.sleep(delay) for _ in range(n)))
    return time.perf_counter() - started


async def test_gather_concurrent_sleeps():
    elapsed = await n_async_sleeps(5, 0.2)
    assert elapsed < 0.5  # 并发：5 个 0.2s 的任务 ≈ 0.2s，远小于串行的 1.0s
    assert elapsed >= 0.2  # 但不会快过单个任务


def test_time_sleep_blocks_event_loop():
    """对照实验的自动化版：事件循环内同步阻塞 0.3s，只需 0.05s 的任务被拖到 0.3s 后。"""

    async def main() -> float:
        async def quick() -> None:
            await asyncio.sleep(0.05)

        started = time.perf_counter()
        task = asyncio.create_task(quick())
        time.sleep(0.3)  # 同步阻塞：事件循环停摆
        await task
        return time.perf_counter() - started

    elapsed = asyncio.run(main())
    assert elapsed >= 0.3  # 任务实际完成时间被阻塞拖后（无阻塞时本应 ≈0.05s）


async def test_wait_for_timeout_cancels_inner():
    cancelled = False

    async def slow() -> None:
        nonlocal cancelled
        try:
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            cancelled = True
            raise

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(slow(), timeout=0.05)
    assert cancelled  # 超时触发内部协程的取消路径（清理逻辑有机会执行）


async def test_semaphore_caps_concurrency():
    running = 0
    max_seen = 0

    async def worker(sem: asyncio.Semaphore) -> None:
        nonlocal running, max_seen
        async with sem:
            running += 1
            max_seen = max(max_seen, running)
            await asyncio.sleep(0.05)
            running -= 1

    sem = asyncio.Semaphore(3)
    await asyncio.gather(*(worker(sem) for _ in range(10)))
    assert max_seen == 3  # 并发上限未被突破


async def test_gather_return_exceptions_collects():
    async def bad() -> None:
        raise ValueError("boom")

    results = await asyncio.gather(asyncio.sleep(0.01, "ok"), bad(), return_exceptions=True)
    assert results[0] == "ok"
    assert isinstance(results[1], ValueError)
    assert str(results[1]) == "boom"


async def test_manual_cancel_raises_cancelled_error():
    task = asyncio.create_task(asyncio.sleep(5))
    await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert task.cancelled()
