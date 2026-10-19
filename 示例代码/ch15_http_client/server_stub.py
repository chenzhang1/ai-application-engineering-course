# ch15 共用测试服务器 | 用标准库 http.server 模拟慢端点/不稳定端点/幂等接口
# 运行：python3 示例代码/ch15_http_client/server_stub.py [port]   （默认 8931，Ctrl+C 停止）
"""提供以下端点（供 ch15 各示例与 测试/test_ch15.py 使用）：
GET  /ok                 → 200 {"ok": true}
GET  /slow?ms=N          → 等 N 毫秒再返回 200（默认 200ms）
GET  /flaky?fail=N&key=K → 对同一个 key 前 N 次返回 503，之后返回 200（模拟"先失败后成功"）
POST /pay                → 读 JSON body；带 Idempotency-Key 头时同一 key 只扣款一次，重复请求回放首次响应
POST /reset              → 清空计数与幂等账本（测试隔离用）
"""
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

_lock = threading.Lock()
_fail_counter: dict[str, int] = {}   # key → 已失败次数
_idempotency: dict[str, dict] = {}   # idempotency key → 首次响应内容


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"  # 支持 keep-alive，便于演示连接复用

    def _send(self, status: int, payload: dict, headers: dict[str, str] | None = None) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        url = urlparse(self.path)
        qs = parse_qs(url.query)
        if url.path == "/ok":
            self._send(200, {"ok": True})
        elif url.path == "/slow":
            ms = int(qs.get("ms", ["200"])[0])
            time.sleep(ms / 1000)
            self._send(200, {"ok": True, "slept_ms": ms})
        elif url.path == "/flaky":
            key = qs.get("key", ["default"])[0]
            fail_n = int(qs.get("fail", ["2"])[0])
            with _lock:
                _fail_counter[key] = _fail_counter.get(key, 0) + 1
                failed_so_far = _fail_counter[key]
            if failed_so_far <= fail_n:
                self._send(503, {"error": "upstream unavailable", "attempt": failed_so_far})
            else:
                self._send(200, {"ok": True, "attempt": failed_so_far})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self) -> None:
        url = urlparse(self.path)
        if url.path == "/reset":
            with _lock:
                _fail_counter.clear()
                _idempotency.clear()
            self._send(200, {"reset": True})
            return
        if url.path == "/pay":
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            idem_key = self.headers.get("Idempotency-Key")
            if idem_key:
                with _lock:
                    if idem_key in _idempotency:
                        # 同一 Idempotency-Key：不重复扣款，回放首次响应
                        self._send(200, _idempotency[idem_key], {"X-Idempotent-Replay": "true"})
                        return
                    # 真实业务：这里应该有事务、扣款、落库……本例用订单号代替
                    resp = {"order_id": f"ORD-{abs(hash((idem_key, payload.get('amount')))) % 100000:05d}",
                            "amount": payload.get("amount"), "charged": True}
                    _idempotency[idem_key] = resp
                self._send(200, resp)
            else:
                # 没有幂等键：每次请求都被当作新订单（重复提交 = 重复扣款风险）
                resp = {"order_id": f"ORD-{abs(hash((time.time_ns(), payload.get('amount')))) % 100000:05d}",
                        "amount": payload.get("amount"), "charged": True}
                self._send(200, resp)
            return
        self._send(404, {"error": "not found"})

    def log_message(self, *args: object) -> None:
        pass  # 静音访问日志


def make_server(port: int = 0) -> ThreadingHTTPServer:
    """port=0 表示系统分配空闲端口（示例与测试都用这种方式避免端口冲突）。"""
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    server.request_queue_size = 128
    return server


if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8931
    server = make_server(port)
    print(f"ch15 测试服务器已启动：http://127.0.0.1:{server.server_address[1]}（Ctrl+C 停止）")
    server.serve_forever()
