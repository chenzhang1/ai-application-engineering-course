# EX-15-01 | httpx.Client 连接池与超时三件套（connect/read/pool）的真实验证
# 运行：python3 示例代码/ch15_http_client/ex_15_01_client_pool_timeout.py
import threading
import time

import httpx
from server_stub import make_server


def main() -> None:
    server = make_server()  # 本地测试服务器（见 server_stub.py）
    base = f"http://127.0.0.1:{server.server_address[1]}"
    threading.Thread(target=server.serve_forever, daemon=True).start()

    # ── 1. 连接复用：共享 Client vs 每次新建 Client ─────────────────────────
    # 超时三件套：connect=建连、read=等响应、pool=排队等连接池里的空闲连接
    timeout = httpx.Timeout(connect=1.0, read=2.0, write=1.0, pool=1.0)
    shared = httpx.Client(base_url=base, timeout=timeout)
    started = time.perf_counter()
    for _ in range(10):
        shared.get("/ok")
    shared_time = time.perf_counter() - started
    shared.close()

    started = time.perf_counter()
    for _ in range(10):
        with httpx.Client(base_url=base, timeout=timeout) as one_shot:  # 每次重新 TCP 建连
            one_shot.get("/ok")
    fresh_time = time.perf_counter() - started
    print(f"[1] 10 次请求，共享 Client（keep-alive 复用连接）：{shared_time * 1000:.0f}ms")
    print(f"[1] 10 次请求，每次新建 Client（重新 TCP 建连）：  {fresh_time * 1000:.0f}ms")

    # ── 2. read 超时：服务端睡 2s，客户端 read=0.3s 先超时 ──────────────────
    with httpx.Client(base_url=base, timeout=httpx.Timeout(connect=1.0, read=0.3, write=1.0, pool=1.0)) as c:
        started = time.perf_counter()
        try:
            c.get("/slow", params={"ms": 2000})
            print("[2] 意外：没超时（不应发生）")
        except httpx.ReadTimeout:
            elapsed = time.perf_counter() - started
            print(f"[2] read 超时：{elapsed * 1000:.0f}ms 后抛出 httpx.ReadTimeout（服务端要 2000ms）")

    # ── 3. pool 超时：连接池只有 1 条连接，两个慢请求并发，第二个排队超时 ──
    limits = httpx.Limits(max_connections=1, max_keepalive_connections=1)
    with httpx.Client(base_url=base, timeout=httpx.Timeout(connect=1.0, read=2.0, write=1.0, pool=0.3),
                      limits=limits) as c:
        started = time.perf_counter()
        try:
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=2) as pool:
                f1 = pool.submit(c.get, "/slow", params={"ms": 800})
                f2 = pool.submit(c.get, "/slow", params={"ms": 800})  # 只能排队等那条连接
                f1.result()
                f2.result()
            print("[3] 意外：没超时（不应发生）")
        except httpx.PoolTimeout:
            elapsed = time.perf_counter() - started
            print(f"[3] pool 超时：{elapsed * 1000:.0f}ms 后抛出 httpx.PoolTimeout（排队等连接超过 0.3s）")

    server.shutdown()


if __name__ == "__main__":
    main()
