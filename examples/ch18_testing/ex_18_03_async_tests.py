# EX-18-03 | pytest-asyncio 异步测试：async def test_ 直接写（asyncio_mode=auto）
# 运行：cd /workspace/ai_application_course && python3 -m pytest examples/ch18_testing/ex_18_03_async_tests.py -v
"""根目录 pytest.ini 已配置 asyncio_mode=auto：async 测试无需装饰器。
Java 对照：没有 main 线程阻塞 join 的样板，await 直接写在测试里。"""
from __future__ import annotations

import asyncio

import pytest


async def fetch_batch(ids: list[int], delay: float = 0.05) -> list[str]:
    async def one(i: int) -> str:
        await asyncio.sleep(delay)
        return f"id-{i}"

    return await asyncio.gather(*(one(i) for i in ids))


async def slow_but_cancelable(delay: float) -> str:
    try:
        await asyncio.sleep(delay)
        return "done"
    except asyncio.CancelledError:
        raise


async def test_fetch_batch_concurrent() -> None:
    started = asyncio.get_running_loop().time()
    results = await fetch_batch([1, 2, 3])
    elapsed = asyncio.get_running_loop().time() - started
    assert results == ["id-1", "id-2", "id-3"]  # gather 保序
    assert elapsed < 0.15  # 并发执行：3×0.05s 的任务总耗时 ≈ 0.05s


async def test_timeout_wraps_slow_task() -> None:
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(slow_but_cancelable(1.0), timeout=0.05)


@pytest.fixture
async def event_loop_probe() -> list[str]:
    """异步 fixture 也可以 yield：先 await 一段再交付。"""
    await asyncio.sleep(0.01)
    yield ["from-async-fixture"]


async def test_async_fixture(event_loop_probe: list[str]) -> None:
    assert event_loop_probe == ["from-async-fixture"]
    assert asyncio.get_running_loop() is not None  # 测试运行在真实的事件循环里
