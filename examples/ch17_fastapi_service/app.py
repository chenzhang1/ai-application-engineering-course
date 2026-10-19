# EX-17-06 | 收束演练：完整 FastAPI 服务——订单查询 + 固定窗口限流 + trace_id 中间件
#            + /healthz + SSE 流式 + 后台任务（依赖 fastapi/uvicorn/pydantic-settings/fakeredis，均在 requirements.txt）
# 启动：cd examples/ch17_fastapi_service && uvicorn app:app --port 8917
# 验证：curl http://127.0.0.1:8917/healthz
#       curl -s -H "X-API-Key: demo-key-123" http://127.0.0.1:8917/orders/ORD-10001
#       curl -N -H "X-API-Key: demo-key-123" http://127.0.0.1:8917/orders/ORD-10001/stream
"""架构要点（与 ch13~ch19 各章呼应）：
- pydantic-settings 管配置（ch16），无硬编码密钥；
- contextvars 存 trace_id（ch17 中间件），日志过滤器自动带上下文；
- Depends 组合鉴权与限流（鉴权先行，限流按调用方计数）；
- fakeredis 做固定窗口限流（ch19 的算法；Redis 可用时可换真实 Redis，接口一致）；
- SSE 用异步生成器 + is_disconnected 断连兜底（ch13 的取消语义在这里落地）。

注意：本文件刻意不写 `from __future__ import annotations`——
工厂函数闭包里定义依赖时，字符串化注解会让 FastAPI 解析不到依赖对象（见 ch17 排错节）。
"""
import asyncio
import json
import logging
import pathlib
import time
import uuid
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import Annotated, Any

import redis as redis_py
from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Path,
    Request,
)
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# ── 配置（ch16）：默认值 < 环境变量；测试用 ORDER_SVC_* 覆盖 ──────────────────
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ORDER_SVC_", extra="ignore")

    api_key: str = "demo-key-123"            # 演示用；生产从密钥管理系统注入
    rate_limit_per_minute: int = 60          # 固定窗口限流阈值
    redis_url: str = ""                      # 为空则使用 fakeredis（离线可运行）
    audit_log_path: str = "_audit.log"       # 后台任务写审计日志的位置


# ── trace_id（contextvars）：一个请求一个上下文，asyncio 安全 ─────────────────
trace_id_var: ContextVar[str] = ContextVar("trace_id", default="-")


class TraceIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = trace_id_var.get()
        return True


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("order_service")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s [trace=%(trace_id)s] %(message)s"))
        handler.addFilter(TraceIdFilter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


log = setup_logging()


# ── 限流器（ch19 固定窗口）：INCR + EXPIRE，窗口按分钟取整对齐 ────────────────
class FixedWindowLimiter:
    def __init__(self, client: Any, limit: int, window_seconds: int = 60) -> None:
        self.client = client
        self.limit = limit
        self.window = window_seconds

    def hit(self, caller: str) -> dict[str, Any]:
        window_id = int(time.time()) // self.window
        key = f"rl:{caller}:{window_id}"
        count = int(self.client.incr(key))
        if count == 1:
            self.client.expire(key, self.window + 1)  # 只在首个请求设置过期，防止计数残留
        allowed = count <= self.limit
        ttl = max(1, int(self.client.ttl(key))) if self.client.ttl(key) > 0 else self.window
        return {"allowed": allowed, "count": count,
                "remaining": max(0, self.limit - count), "retry_after": ttl}


def build_redis_client(settings: Settings) -> Any:
    if settings.redis_url:
        return redis_py.Redis.from_url(settings.redis_url, decode_responses=True,
                                       socket_connect_timeout=2.0)
    import fakeredis  # 默认离线后端：接口与真实 Redis 一致
    return fakeredis.FakeRedis(decode_responses=True)


# ── 业务模型（ch16）与假数据库 ────────────────────────────────────────────────
class OrderOut(BaseModel):
    order_id: str = Field(pattern=r"^ORD-\d{5}$")
    user: str
    amount: float = Field(gt=0)
    status: str


_ORDERS: dict[str, dict[str, Any]] = {
    "ORD-10001": {"order_id": "ORD-10001", "user": "alice", "amount": 129.0, "status": "paid"},
    "ORD-10002": {"order_id": "ORD-10002", "user": "bob", "amount": 59.5, "status": "shipped"},
    "ORD-10003": {"order_id": "ORD-10003", "user": "carol", "amount": 899.0, "status": "paid"},
}


class OrderNotFound(Exception):
    def __init__(self, order_id: str) -> None:
        self.order_id = order_id


# ── 应用工厂：测试可以注入低阈值配置，生产用模块级 app ────────────────────────
def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    limiter = FixedWindowLimiter(build_redis_client(settings), settings.rate_limit_per_minute)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        log.info("服务启动：rate_limit=%d/分钟, redis=%s",
                 settings.rate_limit_per_minute, settings.redis_url or "fakeredis(内存)")
        yield
        log.info("服务关闭")

    app = FastAPI(title="订单查询服务（ch17 收束演练）", lifespan=lifespan)

    # 中间件：trace_id（沿用调用方的或生成新的）→ 响应头 + 访问日志
    @app.middleware("http")
    async def trace_middleware(request: Request, call_next):
        tid = request.headers.get("X-Trace-Id") or uuid.uuid4().hex[:16]
        token = trace_id_var.set(tid)
        started = time.perf_counter()
        try:
            response = await call_next(request)
            response.headers["X-Trace-Id"] = tid
            log.info("%s %s -> %d (%.1fms)", request.method, request.url.path,
                     response.status_code, (time.perf_counter() - started) * 1000)
            return response
        finally:
            trace_id_var.reset(token)

    # 依赖一：鉴权（ex_17_02）
    def verify_api_key(x_api_key: Annotated[str, Header()]) -> str:
        if x_api_key != settings.api_key:
            raise HTTPException(status_code=401, detail="无效的 API Key")
        return x_api_key

    # 依赖二：限流（依赖一的返回值作为计数主体：先鉴权后限流）
    def rate_limit(api_key: Annotated[str, Depends(verify_api_key)]) -> dict[str, Any]:
        verdict = limiter.hit(api_key)
        if not verdict["allowed"]:
            raise HTTPException(status_code=429, detail="请求过于频繁，请稍后重试",
                                headers={"Retry-After": str(verdict["retry_after"]),
                                         "X-RateLimit-Limit": str(settings.rate_limit_per_minute),
                                         "X-RateLimit-Remaining": "0"})
        return verdict

    # 异常处理器：业务异常 → 结构化 404（带 trace_id，方便拿着日志单对单排查）
    @app.exception_handler(OrderNotFound)
    async def order_not_found_handler(_request: Request, exc: OrderNotFound) -> JSONResponse:
        return JSONResponse(status_code=404,
                            content={"detail": f"订单 {exc.order_id} 不存在",
                                     "trace_id": trace_id_var.get()})

    @app.get("/healthz")
    def healthz() -> dict[str, Any]:
        """存活探针：进程活着即可返回 200；依赖不可用属于"就绪/外部依赖"问题（ch20 讨论）。"""
        return {"status": "ok", "backend": "redis" if settings.redis_url else "fakeredis",
                "rate_limit_per_minute": settings.rate_limit_per_minute}

    @app.get("/orders/{order_id}", response_model=OrderOut)
    def get_order(order_id: Annotated[str, Path(pattern=r"^ORD-\d{5}$")],
                  _verdict: Annotated[dict, Depends(rate_limit)]) -> OrderOut:
        order = _ORDERS.get(order_id)
        if order is None:
            log.info("订单未命中：%s", order_id)
            raise OrderNotFound(order_id)
        return OrderOut(**order)

    @app.post("/orders", status_code=201)
    def create_order(order: OrderOut, background_tasks: BackgroundTasks,
                     _verdict: Annotated[dict, Depends(rate_limit)]) -> dict:
        _ORDERS[order.order_id] = order.model_dump()
        background_tasks.add_task(append_audit, settings.audit_log_path, order.order_id)
        return {"accepted": True, "order_id": order.order_id}

    @app.get("/orders/{order_id}/stream")
    async def stream_order_progress(order_id: Annotated[str, Path(pattern=r"^ORD-\d{5}$")],
                                    request: Request,
                                    _verdict: Annotated[dict, Depends(rate_limit)]) -> StreamingResponse:
        if order_id not in _ORDERS:
            raise OrderNotFound(order_id)

        async def events():
            try:
                stages = ["已支付", "已发货", "运输中", "派送中", "已签收"]
                for i, stage in enumerate(stages, start=1):
                    if await request.is_disconnected():
                        log.info("SSE 客户端断连，停止生成")
                        break
                    payload = json.dumps({"order_id": order_id, "percent": i * 20, "stage": stage},
                                         ensure_ascii=False)
                    yield f"event: progress\ndata: {payload}\n\n"
                    await asyncio.sleep(0.05)
                yield "event: done\ndata: {}\n\n"
            finally:
                log.info("SSE 生成器退出（完成/断连/异常统一清理）")

        return StreamingResponse(events(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    return app


def append_audit(path: str, order_id: str) -> None:
    """后台任务（ex_17_05）：响应已返回，审计随后落盘。"""
    with pathlib.Path(path).open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": time.time(), "order_id": order_id,
                            "trace_id": trace_id_var.get()}) + "\n")


app = create_app()  # uvicorn app:app 使用这个实例
