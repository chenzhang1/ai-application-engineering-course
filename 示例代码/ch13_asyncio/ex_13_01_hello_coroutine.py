# EX-13-01 | 第一个协程：async def / await 的执行时序
# 运行：python3 示例代码/ch13_asyncio/ex_13_01_hello_coroutine.py
import asyncio
import time


async def fetch_order(order_id: str) -> str:
    """模拟一次异步 IO：await 处挂起，事件循环转去跑别人，到期回来续跑。"""
    print(f"[{time.perf_counter():.3f}] 开始查询订单 {order_id}")
    await asyncio.sleep(0.3)  # 挂起点：不是睡眠，而是"交还控制权，0.3s 后再叫我"
    print(f"[{time.perf_counter():.3f}] 查询订单 {order_id} 完成")
    return f"订单{order_id}"


async def main() -> None:
    started = time.perf_counter()
    # await 会等协程跑完才继续，所以两个查询是"顺序"的
    r1 = await fetch_order("A001")
    r2 = await fetch_order("A002")
    print(f"结果：{r1} / {r2}，总耗时 {time.perf_counter() - started:.2f}s（0.3+0.3=0.6s）")


if __name__ == "__main__":
    asyncio.run(main())  # 事件循环入口：程序退出前它负责调度所有协程
