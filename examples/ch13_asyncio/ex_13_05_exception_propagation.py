# EX-13-05 | gather 的异常传播：默认策略 vs return_exceptions=True（关键差异）
# 运行：python3 examples/ch13_asyncio/ex_13_05_exception_propagation.py
import asyncio


async def ok_task(name: str, seconds: float) -> str:
    await asyncio.sleep(seconds)
    return f"{name}成功"


async def bad_task(seconds: float) -> None:
    await asyncio.sleep(seconds)
    raise ValueError(f"业务处理失败（{seconds}s 后）")


async def main() -> None:
    # 场景一：默认 return_exceptions=False——第一个异常立刻抛给调用方，
    # 但注意：其他兄弟任务不会被自动取消，它们会继续跑完！
    async def gather_pair() -> list[object]:
        # gather 返回的是 Future 而非协程，要用 Task 包一层需先再包一个 async 函数
        return await asyncio.gather(ok_task("先成功的", 0.05), bad_task(0.05))

    survivor = asyncio.create_task(ok_task("幸存者", 0.3))
    results_bad = asyncio.create_task(gather_pair())
    try:
        await results_bad
    except ValueError as exc:
        print(f"[场景一] 默认策略：await gather 处抛出 ValueError: {exc}")
    print(f"[场景一] 兄弟任务没有被自动取消，仍可继续等待：{await survivor}")

    # 场景二：return_exceptions=True——异常作为"值"出现在结果列表的对应位置，
    # 所有任务都跑完才返回；适合"部分失败可接受"的批量调用（如批量摘要）。
    mixed = await asyncio.gather(
        ok_task("A", 0.05),
        bad_task(0.05),
        ok_task("B", 0.05),
        return_exceptions=True,
    )
    print(f"[场景二] return_exceptions=True：{mixed}")
    for i, item in enumerate(mixed):
        if isinstance(item, Exception):
            print(f"  位置 {i} 是异常：{type(item).__name__}: {item}")
        else:
            print(f"  位置 {i} 是正常值：{item}")


if __name__ == "__main__":
    asyncio.run(main())
