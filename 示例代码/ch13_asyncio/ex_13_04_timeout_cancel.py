# EX-13-04 | wait_for 超时与取消：TimeoutError、CancelledError 与清理逻辑
# 运行：python3 示例代码/ch13_asyncio/ex_13_04_timeout_cancel.py
import asyncio


async def slow_query(seconds: float) -> str:
    try:
        print(f"  开始一个需要 {seconds}s 的查询…")
        await asyncio.sleep(seconds)
        return "查询结果"
    except asyncio.CancelledError:
        # 取消不是异常"事故"，而是协程间协作的常规机制：收到后应尽快清理并重新抛出
        print("  收到取消信号：回滚事务/关闭游标，然后重新抛出 CancelledError")
        raise
    finally:
        print("  finally：无论正常完成还是被取消都会执行（清理资源的好位置）")


async def main() -> None:
    # 场景一：wait_for 超时 → 内部协程被取消，调用方拿到 TimeoutError
    try:
        await asyncio.wait_for(slow_query(1.0), timeout=0.2)
    except asyncio.TimeoutError:
        print("[场景一] wait_for 超时：调用方捕获 TimeoutError（Java 对照：Future.get(timeout) 抛 TimeoutException）")

    # 场景二：任务能在超时前完成 → 正常返回
    result = await asyncio.wait_for(slow_query(0.1), timeout=0.5)
    print(f"[场景二] 未超时：正常拿到 {result}")

    # 场景三：手动取消
    task = asyncio.create_task(slow_query(1.0))
    await asyncio.sleep(0.1)  # 让任务先跑起来
    task.cancel()
    try:
        await task  # 取消的异常在 await task 处浮出
    except asyncio.CancelledError:
        print("[场景三] 手动 task.cancel()：await task 处收到 CancelledError")


if __name__ == "__main__":
    asyncio.run(main())
