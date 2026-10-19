# EX-17-04 | SSE 流式响应：StreamingResponse + 客户端断连处理思想
# 运行：python3 示例代码/ch17_fastapi_service/ex_17_04_sse_stream.py
import asyncio
import json

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient

app = FastAPI(title="SSE 演示")


async def progress_events(order_id: str, request: Request):
    """异步生成器：像挤牙膏一样每次产出一条 SSE 消息（Java 对照：SseEmitter.send 循环）。"""
    try:
        for pct in (20, 40, 60, 80, 100):
            # 断连检测：客户端关掉了连接就立刻停止生成，别再白算
            if await request.is_disconnected():
                print("[服务端] 检测到客户端断连，停止生成事件")
                break
            payload = json.dumps({"order_id": order_id, "percent": pct}, ensure_ascii=False)
            yield f"event: progress\ndata: {payload}\n\n"
            await asyncio.sleep(0.05)
        else:
            yield "event: done\ndata: {}\n\n"
    finally:
        # 无论正常结束、断连还是异常，生成器关闭时都会执行——在这里释放资源
        print("[服务端] SSE 生成器已退出（finally 兜底清理）")


@app.get("/stream/{order_id}")
async def stream(order_id: str, request: Request) -> StreamingResponse:
    return StreamingResponse(
        progress_events(order_id, request),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},  # 禁缓存/禁代理缓冲
    )


def main() -> None:
    with TestClient(app) as client:
        # 场景一：完整消费整条流
        events: list[str] = []
        with client.stream("GET", "/stream/ORD-10001") as resp:
            print(f"[完整消费] content-type={resp.headers['content-type']}")
            for line in resp.iter_lines():
                if line.startswith("data:"):
                    events.append(line[5:].strip())
        print(f"[完整消费] 收到 {len(events)} 条 data：最后一条={events[-1]}")

        # 场景二：客户端读 2 条就关连接（模拟用户关闭页面）
        with client.stream("GET", "/stream/ORD-10001") as resp:
            for i, line in enumerate(resp.iter_lines()):
                if line.startswith("data:"):
                    print(f"[提前断连] 读到第 {i // 2 + 1} 条：{line[5:].strip()}")
                if i >= 1:
                    break  # 提前退出 with 块 → 连接关闭 → 服务端生成器被终止
        print("[提前断连] 客户端已关闭，未报错（服务端靠 is_disconnected + finally 兜底）")


if __name__ == "__main__":
    main()
