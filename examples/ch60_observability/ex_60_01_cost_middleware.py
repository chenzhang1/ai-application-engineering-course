# EX-60-01 | token/延迟/成本统计中间件（FastAPI） | 运行: python3 examples/ch60_observability/ex_60_01_cost_middleware.py
"""完整可运行（fastapi + 共享 MockLLM，离线）：每个 AI 请求记一行结构化日志——
trace_id、路径、状态码、延迟、prompt/completion tokens、估算成本、token 计数方式。

设计要点（正文 60.3 展开）：
  - 日志是 JSONL（每行一个 JSON 对象）：文本日志没法聚合，结构化日志才能进监控；
  - usage 由端点写到 request.state（scope 共享），中间件统一记账——业务代码只管调模型；
  - 成本 = tokens × 单价。价目表里的数字是**演示占位**，生产必须从厂商定价页核对
    并放进配置中心（价格会变，代码常量会腐烂）；
  - usage 缺失按 0 记并让 count_method 显示 unavailable——绝不能把"没统计到"当"没花钱"。
"""
from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from examples.common.llm_client import get_llm  # noqa: E402

# ── 演示价目表（占位数字，非任何厂商的真实定价！生产从定价页核对进配置中心）──
PRICE_TABLE: dict[str, dict[str, float]] = {
    "demo-model": {"prompt_per_1k": 0.0015, "completion_per_1k": 0.002},  # 单位：元/千token
}

# 结构化日志：JSONL 格式器（Java 对照：Logback JsonEncoder + MDC.put("trace_id",...)）
logger = logging.getLogger("cost")
if not logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(message)s"))   # 消息本身就是 JSON 行
    logger.addHandler(_h)
logger.setLevel(logging.INFO)


class AskIn(BaseModel):
    question: str


def create_app() -> FastAPI:
    app = FastAPI()

    @app.middleware("http")
    async def cost_middleware(request: Request, call_next):
        trace_id = request.headers.get("X-Trace-Id") or uuid.uuid4().hex[:16]
        start = time.perf_counter()
        response = await call_next(request)            # 端点在 scope 里留下 usage
        latency_ms = (time.perf_counter() - start) * 1000

        usage: dict = getattr(request.state, "usage", {}) or {}
        price = PRICE_TABLE["demo-model"]
        prompt_t = usage.get("prompt_tokens", 0)
        comp_t = usage.get("completion_tokens", 0)
        cost = (prompt_t / 1000 * price["prompt_per_1k"]
                + comp_t / 1000 * price["completion_per_1k"])
        logger.info(json.dumps({
            "ts": round(time.time(), 3),
            "trace_id": trace_id,
            "path": request.url.path,
            "status": response.status_code,
            "latency_ms": round(latency_ms, 1),
            "prompt_tokens": prompt_t,
            "completion_tokens": comp_t,
            "count_method": usage.get("count_method", "unavailable"),
            "cost_est_yuan": round(cost, 6),
        }, ensure_ascii=False))
        response.headers["X-Trace-Id"] = trace_id
        return response

    @app.post("/v1/ask")
    def ask(body: AskIn, request: Request) -> dict:
        """业务端点：只管调模型，把 usage 交给请求作用域，记账是中间件的职责。"""
        result = get_llm().chat([
            {"role": "system", "content": "你是制度问答助手，只依据给定制度回答。"},
            {"role": "user", "content": body.question},
        ])
        request.state.usage = result.usage
        return {"answer": result.content}

    return app


def main() -> None:
    client = TestClient(create_app())
    print("── 两个请求（下面的 JSON 行 = 中间件真实输出的日志）──")
    for tid, q in (("t-demo-001", "年假有几天？"), ("t-demo-002", "报销流程是什么？")):
        r = client.post("/v1/ask", json={"question": q}, headers={"X-Trace-Id": tid})
        print(f"    HTTP {r.status_code}  X-Trace-Id={r.headers['X-Trace-Id']}")
    print("\n（日志行里 latency_ms 每次不同是正常现象——延迟不是确定性数据。）")
    print("\n[接入提示] 生产把 logger.info 换成日志管道客户端（ELK/Loki/云日志服务）；")
    print("  trace_id 由网关透传（Spring Cloud Gateway 注入 X-Trace-Id）；")
    print("  异步任务把 trace_id 存进任务记录（与 ch57 的 job_id 配对），长任务才能从头查到尾。")


if __name__ == "__main__":
    main()
