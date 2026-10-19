# EX-56-01 | 把已有 Java HTTP API 封装成 Agent 工具：@tool + httpx + Pydantic + 错误翻译
# 运行: python3 examples/ch56_java_bridge/ex_56_01_http_tool_wrapper.py
"""完整可运行（httpx 0.28.1 + 线程内 Java 替身，确定性）：

对接已有 Java 服务的第一步不是接框架，是把"HTTP 调用"包装成**干净的 Agent 工具**。
四件套缺一不可：
    1. 专用 httpx.Client（超时三件套 connect/read/pool，ch15 的规矩原样搬来）；
    2. 响应 → Pydantic 模型（契约在代码里，不在记忆里）；
    3. 错误翻译：404→"业务不存在"（返回工具结果，让模型知道）、5xx/超时→异常（让框架重试）；
       ——关键判断：**哪些错误是"数据"，哪些错误是"事故"**（56.5 展开）；
    4. docstring 写"何时用/何时不用"（EX-54-01 的描述纪律）。
把 STUB 换成 http://127.0.0.1:8080 即切到项目三的真 Java 服务（响应形状一致）。
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent))
from stub_java_service import StubJavaService  # noqa: E402

# ---- 契约模型：Java 响应的 Python 形状（契约即代码） -------------------------------


class Plan(BaseModel):
    """GET /plans 里单个计划的字段（与 PlanServer.java 的 PlanDTO 一致）。"""

    plan_id: str
    product: str
    qty: int = Field(ge=0)
    status: str


class PlansResponse(BaseModel):
    date: str
    count: int
    plans: list[Plan]


class WorkOrder(BaseModel):
    workorder_id: str
    plan_id: str
    status: str
    produced_qty: int
    target_qty: int


# ---- HTTP 客户端封装（Ch15 的工程纪律 + 错误翻译三层） -----------------------------


class JavaServiceError(Exception):
    """基础设施级错误（超时/5xx/连接失败）→ 让上层决定重试或熔断。"""


class ToolHTTPClient:
    """服务专用客户端：连接池 + 超时三件套（不要每次调用新建 Client）。"""

    def __init__(self, base_url: str) -> None:
        self._client = httpx.Client(
            base_url=base_url,
            timeout=httpx.Timeout(connect=2.0, read=5.0, write=2.0, pool=2.0),
        )

    def get_json(self, path: str, *, params: dict[str, str] | None = None) -> dict[str, Any]:
        try:
            r = self.client_get(path, params)
        except httpx.TimeoutException as e:
            raise JavaServiceError(f"上游超时（read=5s）：{type(e).__name__}") from e
        except httpx.HTTPError as e:
            raise JavaServiceError(f"上游连接失败：{type(e).__name__}") from e
        if r.status_code >= 500:
            raise JavaServiceError(f"上游 5xx：{r.status_code}")
        if r.status_code == 404:
            return {"_not_found": True}  # 业务性"不存在"是数据，不是事故 → 返回给模型
        r.raise_for_status()
        return r.json()

    def client_get(self, path: str, params: dict[str, str] | None) -> httpx.Response:
        return self._client.get(path, params=params)


# ---- Agent 工具层（docstring 遵守 EX-54-01 的描述纪律） ----------------------------
_CLIENT: ToolHTTPClient | None = None


def init_tools(base_url: str) -> None:
    global _CLIENT
    _CLIENT = ToolHTTPClient(base_url)


def tool_query_plans(date: str) -> dict[str, Any]:
    """查询指定日期(YYYY-MM-DD)的生产计划列表（计划号/产品/数量/状态）。只读。
    不知道具体计划号时先用本工具列出当日全部计划。"""
    resp = PlansResponse.model_validate(_CLIENT.get_json("/plans", params={"date": date}))
    return {"count": resp.count,
            "plans": [p.model_dump() for p in resp.plans]}


def tool_query_workorder(workorder_id: str) -> dict[str, Any]:
    """按工单号(WO-开头)查询单个工单的完成数量与状态。只读。
    仅在已知工单号时使用；不确定工单号先用 tool_query_plans。"""
    data = _CLIENT.get_json(f"/workorders/{workorder_id}")
    if data.get("_not_found"):
        return {"exists": False, "workorder_id": workorder_id,
                "hint": "工单不存在，请核对工单号（可用 tool_query_plans 反查）"}
    return WorkOrder.model_validate(data).model_dump() | {"exists": True}


def main() -> None:
    svc = StubJavaService()
    base = svc.start()
    init_tools(base)  # 真实环境：init_tools("http://127.0.0.1:8080")
    print(f"== HTTP → Agent 工具（目标服务 {base}）==\n")

    print("[1] 正常路径：query_plans('2026-03-18')")
    r = tool_query_plans("2026-03-18")
    print(f"    count={r['count']}，第一条：{r['plans'][0]}")

    print("\n[2] 正常路径：query_workorder('WO-2091')")
    print(f"    {tool_query_workorder('WO-2091')}")

    print("\n[3] 业务性 404（数据，不是事故）：query_workorder('WO-9999')")
    print(f"    {tool_query_workorder('WO-9999')}")

    print("\n[4] 基础设施错误（事故，交给上层重试/熔断）：关停服务后调用")
    svc.stop()
    try:
        tool_query_plans("2026-03-18")
    except JavaServiceError as e:
        print(f"    JavaServiceError: {e}")
        print("    → 模型收到的是框架层的重试/降级决策，不会把'连接失败'当成业务结论")

    print("\n四件套小结：专用 Client / 契约模型 / 错误翻译 / 描述纪律——")
    print("缺任何一件，'对接 Java 服务'都会在生产第三天变成排障地狱。")


if __name__ == "__main__":
    main()
