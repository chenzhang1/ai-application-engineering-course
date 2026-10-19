# EX-13-02 | 对照实验：time.sleep 阻塞事件循环 vs asyncio.sleep 让出控制权
# 运行：python3 示例代码/ch13_asyncio/ex_13_02_sleep_compare.py
import asyncio
import time


# [B] 并发版任务：asyncio.sleep 只"登记"一个 0.2s 后的回调，随后立刻让出控制权
async def async_task(name: str, delay: float) -> str:
    await asyncio.sleep(delay)
    return f"{name}完成"


async def demo_async_concurrent() -> None:
    started = time.perf_counter()
    results = await asyncio.gather(*(async_task(f"任务{i}", 0.2) for i in range(5)))
    elapsed = time.perf_counter() - started
    print(f"[B] asyncio.sleep 并发 5 个任务：总耗时 {elapsed:.2f}s（近似单个任务的时长），结果 {len(results)} 个")


# [C] 阻塞伤害演示：一个只需要 0.1s 的任务，因为事件循环被同步代码卡住 0.5s，
#     实际完成时间被推迟——这是同步库混入 async 代码时最经典的线上事故。
async def demo_blocking_harm() -> None:
    async def should_finish_fast() -> str:
        await asyncio.sleep(0.1)  # 本任务只需求 0.1s
        return "我本应在 0.1s 后完成"

    started = time.perf_counter()
    task = asyncio.create_task(should_finish_fast())  # 已被调度，等 0.1s 就该完成
    time.sleep(0.5)  # 同步阻塞：事件循环整个被卡住 0.5s，谁也无法被调度
    result = await task
    elapsed = time.perf_counter() - started
    print(f"[C] 事件循环内调用 time.sleep(0.5)：任务实际 {elapsed:.2f}s 后才返回（需求 0.1s）→ {result}")


def main() -> None:
    # [A] 顺序阻塞版：每次 time.sleep 都真的占用线程干等
    started = time.perf_counter()
    for i in range(5):
        time.sleep(0.2)
    print(f"[A] time.sleep 顺序睡 5 次：总耗时 {time.perf_counter() - started:.2f}s（0.2×5=1.0s）")

    asyncio.run(demo_async_concurrent())
    asyncio.run(demo_blocking_harm())


if __name__ == "__main__":
    main()
