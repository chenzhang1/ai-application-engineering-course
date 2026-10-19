# EX-15-02 | 指数退避 + 抖动重试的完整实现（对本地服务"失败 2 次后成功"做真实重试）
# 运行：python3 示例代码/ch15_http_client/ex_15_02_retry_backoff.py
import logging
import random
import time
from typing import Any

import httpx

try:  # 直接运行本文件时生效（脚本目录自动在 sys.path）
    from server_stub import make_server
except ImportError:  # 作为 examples.ch15_http_client.* 被导入时生效（如 pytest）
    from 示例代码.ch15_http_client.server_stub import make_server

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)  # 静音 httpx 的 INFO 访问日志，突出重试日志
log = logging.getLogger("retry")


def request_with_retry(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    max_attempts: int = 4,
    base_delay: float = 0.1,
    max_delay: float = 1.0,
    retry_status: tuple[int, ...] = (502, 503, 504),
    retry_on: tuple[type[Exception], ...] = (httpx.TransportError,),
    **kwargs: Any,
) -> httpx.Response:
    """可复用的同步重试封装：指数退避 + 完全抖动（full jitter）。

    指数退避：第 n 次重试的等待上限 = min(max_delay, base_delay * 2**(n-1))
    完全抖动：真实等待 = random.uniform(0, 上限)，避免失败后所有客户端同一时刻再撞一次
    """
    for attempt in range(1, max_attempts + 1):
        try:
            resp = client.request(method, url, **kwargs)
            if resp.status_code in retry_status and attempt < max_attempts:
                log.warning("第 %d 次：%d，准备退避重试", attempt, resp.status_code)
            else:
                return resp
        except retry_on as exc:  # 网络层错误（超时/连接拒绝/断连）才重试；4xx 参数错误不重试
            if attempt >= max_attempts:
                raise
            log.warning("第 %d 次：%s，准备退避重试", attempt, exc.__class__.__name__)
        ceiling = min(max_delay, base_delay * 2 ** (attempt - 1))
        delay = random.uniform(0, ceiling)
        log.info("退避 %.0f ms（上限 %.0f ms）", delay * 1000, ceiling * 1000)
        time.sleep(delay)
    raise AssertionError("不可达")  # 循环内要么 return 要么 raise


def main() -> None:
    server = make_server()
    import threading
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"

    with httpx.Client(base_url=base, timeout=httpx.Timeout(connect=1.0, read=2.0, write=1.0, pool=1.0)) as client:
        client.post("/reset")  # 清零失败计数，保证演示从"新 key"开始
        started = time.perf_counter()
        resp = request_with_retry(client, "GET", "/flaky", params={"fail": 2, "key": "demo"})
        elapsed = time.perf_counter() - started
        print(f"最终结果：{resp.status_code} {resp.json()}，总耗时 {elapsed * 1000:.0f}ms（含两次退避）")

        # 对比：4xx 参数错误不该重试——服务端对未知路径直接 404，一次就返回
        resp404 = request_with_retry(client, "GET", "/no-such-path")
        print(f"404 不重试：{resp404.status_code}（若错误地重试 4xx，只会放大数据库压力并拉长尾延迟）")

    server.shutdown()


if __name__ == "__main__":
    main()
