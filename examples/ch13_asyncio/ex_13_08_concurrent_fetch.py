# EX-13-08 | 真实网络并发实验：本地 HTTP 服务 20 个请求，顺序 vs asyncio 并发
# 运行：python3 examples/ch13_asyncio/ex_13_08_concurrent_fetch.py
import asyncio
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx


class SlowServer(ThreadingHTTPServer):
    # 默认 request_queue_size（backlog）只有 5：20 个并发连接会溢出并触发 1s 的 SYN 重传，
    # 这本身就是一条真实的排障经验——并发压测时服务端吞吐异常，先查 backlog。
    daemon_threads = True
    request_queue_size = 128


class SlowHandler(BaseHTTPRequestHandler):
    """每个 /work 请求睡眠 100ms 再返回——模拟一次 100ms 的真实网络调用。"""

    def do_GET(self) -> None:  # noqa: N802（http.server 的方法名约定）
        if self.path.startswith("/work"):
            time.sleep(0.1)  # 注意：服务端这里是 time.sleep，ThreadingHTTPServer 每请求一线程，能并发
            body = b'{"ok": true}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404)

    def log_message(self, *args: object) -> None:  # 静音默认访问日志
        pass


async def fetch_sequential(client: httpx.AsyncClient, n: int) -> float:
    started = time.perf_counter()
    for i in range(n):
        r = await client.get("/work")
        assert r.status_code == 200
    return time.perf_counter() - started


async def fetch_concurrent(client: httpx.AsyncClient, n: int) -> float:
    started = time.perf_counter()
    rs = await asyncio.gather(*(client.get("/work") for _ in range(n)))
    assert all(r.status_code == 200 for r in rs)
    return time.perf_counter() - started


async def main(base_url: str) -> None:
    async with httpx.AsyncClient(base_url=base_url) as client:
        seq = await fetch_sequential(client, 20)
        conc = await fetch_concurrent(client, 20)
    print(f"20 个请求、单个 100ms：顺序 await 总耗时 {seq:.2f}s")
    print(f"20 个请求、单个 100ms：gather 并发 总耗时 {conc:.2f}s（理论下限≈0.1s）")
    print(f"加速比 ≈ {seq / conc:.1f} 倍——并发瓶颈从'总睡眠时间'变成'单次最慢请求'")


if __name__ == "__main__":
    server = SlowServer(("127.0.0.1", 0), SlowHandler)  # 端口 0=系统分配空闲端口
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        asyncio.run(main(f"http://127.0.0.1:{port}"))
    finally:
        server.shutdown()
