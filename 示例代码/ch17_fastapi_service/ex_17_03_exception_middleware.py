# EX-17-03 | 异常处理器 + contextvars 中间件：trace_id 贯穿日志与响应头
# 运行：python3 示例代码/ch17_fastapi_service/ex_17_03_exception_middleware.py
import logging
import uuid
from contextvars import ContextVar

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

# ── trace_id 用 contextvars 保存：协程安全（每个请求一个独立上下文），
#    Java 对照：ThreadLocal 存 MDC——但 asyncio 下多协程共用一个线程，必须用 contextvars。
trace_id_var: ContextVar[str] = ContextVar("trace_id", default="-")


class TraceIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = trace_id_var.get()
        return True


_handler = logging.StreamHandler()
_handler.setFormatter(logging.Formatter("%(levelname)s [trace=%(trace_id)s] %(message)s"))
_handler.addFilter(TraceIdFilter())
log = logging.getLogger("demo")
log.handlers = [_handler]
log.setLevel(logging.INFO)
log.propagate = False


class BillingUnavailable(Exception):
    """业务自定义异常：携带结构化信息，交给专门处理器转成 HTTP 响应。"""


app = FastAPI(title="异常与trace演示")


@app.middleware("http")
async def trace_middleware(request: Request, call_next):
    tid = request.headers.get("X-Trace-Id") or uuid.uuid4().hex[:16]
    token = trace_id_var.set(tid)
    try:
        response = await call_next(request)
        response.headers["X-Trace-Id"] = tid
        # 注意时序：先打访问日志（此刻上下文里还有 trace_id），再在 finally 里 reset
        log.info("%s %s -> %d", request.method, request.url.path, response.status_code)
        return response
    finally:
        trace_id_var.reset(token)


@app.exception_handler(BillingUnavailable)
async def billing_handler(request: Request, exc: BillingUnavailable) -> JSONResponse:
    # 异常处理器里能拿到 contextvars 的当前值——同一请求的所有环节共享一个 trace_id
    return JSONResponse(status_code=503,
                        content={"detail": "计费服务暂不可用，请稍后重试", "trace_id": trace_id_var.get()})


@app.get("/pay")
def pay(amount: float) -> dict:
    log.info("发起扣款 amount=%.2f", amount)
    if amount > 1000:
        raise BillingUnavailable(f"计费超时 amount={amount}")
    return {"ok": True, "amount": amount}


def main() -> None:
    with TestClient(app) as client:
        r = client.get("/pay", params={"amount": 9.9})
        print(f"[正常]   status={r.status_code}  body={r.json()}  X-Trace-Id={r.headers['X-Trace-Id'][:8]}…")

        r = client.get("/pay", params={"amount": 5000})
        print(f"[业务异常] status={r.status_code}  body={r.json()}（trace_id 与日志中的相同）")

        # 客户端透传 trace_id（Java 网关把 MDC 的 traceId 放进请求头，是同样的链路协议）
        r = client.get("/pay", params={"amount": 1}, headers={"X-Trace-Id": "my-trace-42"})
        print(f"[透传]   status={r.status_code}  X-Trace-Id={r.headers['X-Trace-Id']}（服务端沿用调用方的）")


if __name__ == "__main__":
    main()
