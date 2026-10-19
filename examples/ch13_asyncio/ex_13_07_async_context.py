# EX-13-07 | 异步上下文管理器：__aenter__/__aexit__ 与 asynccontextmanager 两种写法
# 运行：python3 examples/ch13_asyncio/ex_13_07_async_context.py
import asyncio
from contextlib import asynccontextmanager


class AsyncDbConn:
    """模拟一个异步数据库连接：进入时建连，退出时归还连接池。"""

    def __init__(self, dsn: str) -> None:
        self.dsn = dsn
        self.closed = True

    async def __aenter__(self) -> "AsyncDbConn":
        await asyncio.sleep(0.05)  # 模拟异步建连（真实驱动如 asyncpg 连接就是 await 的）
        self.closed = False
        print(f"[类写法] 已连接 {self.dsn}")
        return self

    async def __aexit__(self, exc_type: type[BaseException] | None,
                        exc: BaseException | None, tb: object) -> None:
        await asyncio.sleep(0.01)  # 模拟异步归还
        self.closed = True
        print(f"[类写法] 连接已归还（异常信息：{exc_type.__name__ if exc_type else '无'}）")


@asynccontextmanager
async def request_span(name: str):
    """装饰器写法：yield 之前=进入逻辑，之后=退出逻辑，8 行顶一个类。"""
    print(f"[装饰器写法] span {name} 开始")
    try:
        yield name
    finally:
        print(f"[装饰器写法] span {name} 结束（即使内部抛异常也会走到这里）")


async def main() -> None:
    async with AsyncDbConn("postgres://demo") as conn:
        print(f"[类写法] 使用连接：closed={conn.closed}")
    assert conn.closed

    try:
        async with request_span("批量摘要") as span:
            await asyncio.sleep(0.05)
            raise RuntimeError("模拟业务异常")
    except RuntimeError as exc:
        print(f"[装饰器写法] 外层捕获到异常：{exc}——但 span 的清理已经先执行了")


if __name__ == "__main__":
    asyncio.run(main())
