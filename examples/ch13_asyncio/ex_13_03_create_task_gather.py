# EX-13-03 | create_task 并发调度 + gather 收集结果（结果按提交顺序返回）
# 运行：python3 examples/ch13_asyncio/ex_13_03_create_task_gather.py
import asyncio
import time


async def fetch(url: str, delay: float) -> str:
    await asyncio.sleep(delay)  # 模拟网络 IO
    return f"{url}@{delay}"


async def main() -> None:
    started = time.perf_counter()

    # 方式一：create_task 立刻把协程包装成 Task 排入事件循环，不等 await 就开始跑
    t_fast = asyncio.create_task(fetch("fast-api", 0.1))
    t_slow = asyncio.create_task(fetch("slow-api", 0.4))
    print(f"create_task 之后、await 之前，任务已在调度中：fast.done={t_fast.done()}")

    # 方式二：gather 接收协程/Task 列表，全部完成后按"提交顺序"返回结果列表
    results = await asyncio.gather(t_slow, t_fast)  # 先提交的 slow 排在前面
    elapsed = time.perf_counter() - started

    print(f"gather 结果（按提交顺序）：{results}")
    print(f"总耗时 {elapsed:.2f}s（取最慢任务的 0.4s，而不是 0.1+0.4=0.5s）")
    print(f"fast.done={t_fast.done()}，slow.done={t_slow.done()}")


if __name__ == "__main__":
    asyncio.run(main())
