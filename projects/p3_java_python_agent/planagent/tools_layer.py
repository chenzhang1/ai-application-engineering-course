# projects/p3_java_python_agent/planagent/tools_layer.py
"""工具层：Agent 与 Java 服务之间的"治理关卡"（教材 ch54/ch56 的工程落地）。

四道关卡按序执行，全部通过才触达 Java：
    ① 取消检查（协作式取消：任务被 DELETE 后工具入口立即拒绝）；
    ② 参数校验（Pydantic args schema：类型/格式/范围——模型给的参数不可信）；
    ③ 权限分级（viewer 只读；operator 才能低风险写；高风险工具唯一入口是审批流）；
    ④ 业务规则（调整幅度 ≤20% 才算低风险——对照 Java 侧权威数据核验，不信模型转述）。

幂等：写操作一律生成确定性幂等键（同一次分析内重试同 key），Java 侧按 key 去重。
审计：每次调用（含被拒的）写一条 JSONL。
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import httpx
from langchain_core.tools import tool
from pydantic import BaseModel, Field, ValidationError

from planagent.audit import AuditLog

# ---- 契约模型：Java 响应的 Python 形状（与 data/*.json 逐字段一致） ----------------


class Plan(BaseModel):
    plan_id: str
    product: str
    qty: int = Field(ge=0)
    status: str


class WorkOrder(BaseModel):
    workorder_id: str
    plan_id: str
    status: str
    produced_qty: int
    target_qty: int


# ---- 工具参数 schema（模型的参数先过这里， ValidationError → 结构化错误给模型） ------


class QueryPlansArgs(BaseModel):
    """GET /plans 的参数契约。"""

    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$", description="生产日期 YYYY-MM-DD")


class QueryWorkOrderArgs(BaseModel):
    workorder_id: str = Field(pattern=r"^WO-\d+$", description="工单号，形如 WO-2091")


class AdjustmentArgs(BaseModel):
    """低风险调整参数：date 用于到 Java 侧核验计划现量（不信模型转述）。"""

    plan_id: str = Field(pattern=r"^P-\d{4}$")
    new_qty: int = Field(ge=0, le=100_000)
    reason: str = Field(min_length=5, max_length=200)
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$", description="计划所属生产日")


class EmergencyAdjustmentArgs(BaseModel):
    """高风险调整参数（翻倍/急单插单）。无 date：直提，靠审批拦截参数风险。"""

    plan_id: str = Field(pattern=r"^P-\d{4}$")
    new_qty: int = Field(ge=0, le=100_000)
    reason: str = Field(min_length=5, max_length=200)


# ---- 权限分级 ----------------------------------------------------------------------


class Role(str, Enum):
    VIEWER = "viewer"      # 只读
    OPERATOR = "operator"  # 只读 + 低风险写（高风险一律走审批，operator/admin 皆然）


READ_TOOLS = {"query_plans", "query_workorder"}
LOW_RISK_TOOLS = {"submit_adjustment"}
HIGH_RISK_TOOLS = {"submit_emergency_adjustment"}  # 只能由审批流恢复后执行


class ToolPermissionError(PermissionError):
    """权限不足（审计记 denied；HTTP 语义 403）。"""


class ToolValidationError(ValueError):
    """参数校验失败（HTTP 语义 422；错误信息回传模型供其纠正参数）。"""


class BusinessRuleError(ValueError):
    """业务规则不满足：超幅度调整应改走审批，而不是硬提交。"""


class TaskCancelled(Exception):
    """任务已被取消：工具入口的协作式取消检查点抛出。"""


# ---- Java HTTP 客户端（ch56 EX-56-01 的工程版：超时三件套 + 重试白名单） ------------


class JavaServiceError(Exception):
    """基础设施级错误（超时/连接失败/5xx）→ 上层决定重试或任务失败。"""


RETRYABLE = (httpx.TimeoutException, httpx.TransportError)


class JavaClient:
    """服务专用客户端：连接池复用 + 超时三件套 + 有限重试（写操作靠幂等键安全重试）。"""

    def __init__(self, base_url: str, *, connect_s: float = 2.0, read_s: float = 5.0,
                 max_attempts: int = 3, base_backoff_s: float = 0.05) -> None:
        self._client = httpx.Client(
            base_url=base_url,
            timeout=httpx.Timeout(connect=connect_s, read=read_s, write=2.0, pool=2.0),
        )
        self.max_attempts = max_attempts
        self.base_backoff_s = base_backoff_s

    def get_json(self, path: str, *, params: dict[str, str] | None = None) -> dict[str, Any]:
        """GET：天然幂等 → 可自动重试；404 返回 {"_not_found": True}（业务数据非事故）。"""
        last_exc: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                r = self._client.get(path, params=params)
            except RETRYABLE as e:
                last_exc = e
            else:
                if r.status_code >= 500:
                    last_exc = JavaServiceError(f"上游 5xx：{r.status_code}")
                elif r.status_code == 404:
                    return {"_not_found": True}
                else:
                    r.raise_for_status()
                    return r.json()
            if attempt < self.max_attempts:
                time.sleep(self.base_backoff_s * (2 ** (attempt - 1)))
        self._raise_exhausted(last_exc)

    def post_adjustment(self, payload: dict[str, Any], idempotency_key: str) -> dict[str, Any]:
        """POST /adjustments：携带 Idempotency-Key → 重试安全（Java 按 key 去重）。"""
        last_exc: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                r = self._client.post("/adjustments", json=payload,
                                      headers={"Idempotency-Key": idempotency_key})
            except RETRYABLE as e:
                last_exc = e
            else:
                if r.status_code >= 500:
                    last_exc = JavaServiceError(f"上游 5xx：{r.status_code}")
                else:
                    r.raise_for_status()  # 4xx（业务校验失败）原样抛 → 上层翻译
                    return r.json()
            if attempt < self.max_attempts:
                time.sleep(self.base_backoff_s * (2 ** (attempt - 1)))
        self._raise_exhausted(last_exc)

    @staticmethod
    def _raise_exhausted(last_exc: Exception | None) -> None:
        """重试耗尽：网络层异常统一包装为 JavaServiceError（上层只需捕获一种基础设施错误）。"""
        if last_exc is None:
            raise JavaServiceError("未知错误")
        if isinstance(last_exc, JavaServiceError):
            raise last_exc
        raise JavaServiceError(f"{type(last_exc).__name__}: {last_exc}") from last_exc

    def call_slow(self, ms: int) -> dict[str, Any]:
        """GET /slow：超时/重试演示专用（对齐 Java 服务的慢端点）。"""
        return self.get_json("/slow", params={"ms": str(ms)})


def idempotency_key(plan_id: str, new_qty: int, reason: str, trace_id: str) -> str:
    """确定性幂等键：同一次分析（trace）内对同一计划的同一次调整，重试同 key。"""
    digest = hashlib.sha1(f"{plan_id}|{new_qty}|{reason}|{trace_id}".encode("utf-8")).hexdigest()
    return f"adj-{plan_id}-{new_qty}-{digest[:10]}"


# ---- 工具上下文与执行入口 -----------------------------------------------------------


@dataclass
class ToolContext:
    """一次分析任务的工具上下文：客户端/审计/身份/取消标志（工具闭包共享）。

    approved_tools：审批凭证集合——高风险工具只有审批流恢复（approve）后
    才把工具名加进来；绕过 Agent 直调工具时集合为空，闸门拒绝（defense in depth）。
    """

    client: JavaClient
    audit: AuditLog
    task_id: str
    trace_id: str
    role: Role = Role.OPERATOR
    cancel_event: threading.Event = field(default_factory=threading.Event)
    demo_date: str = "2026-03-18"  # 教学固定演示日（Java 种子数据所在日期）
    max_adjust_ratio: float = 0.20  # 低风险调整幅度上限
    approved_tools: set[str] = field(default_factory=set)

    def check_cancel(self) -> None:
        if self.cancel_event.is_set():
            raise TaskCancelled(f"任务 {self.task_id} 已被取消")


def _audited(ctx: ToolContext, tool: str, args: dict[str, Any], fn_name: str,
             exec_fn: Any) -> dict[str, Any]:
    """统一执行入口：取消 → 权限 → 校验 → 实现，全分支写审计。"""
    t0 = time.monotonic()
    ctx.check_cancel()
    if tool in HIGH_RISK_TOOLS:
        # 高风险工具不在此入口执行——审批流恢复后的专门路径才带 approved=True
        ctx.audit.record(trace_id=ctx.trace_id, actor="agent-p3", role=ctx.role.value,
                         tool=tool, args=args, outcome="denied",
                         detail="高风险工具必须经人工审批（HITL）执行", duration_ms=0)
        raise ToolPermissionError(f"{tool} 是高风险工具，必须经人工审批")
    if tool not in READ_TOOLS and ctx.role is not Role.OPERATOR:
        ctx.audit.record(trace_id=ctx.trace_id, actor="agent-p3", role=ctx.role.value,
                         tool=tool, args=args, outcome="denied",
                         detail=f"角色 {ctx.role.value} 无权调用 {tool}", duration_ms=0)
        raise ToolPermissionError(f"角色 {ctx.role.value} 无权调用 {tool}")
    try:
        result = exec_fn()
    except (BusinessRuleError, JavaServiceError) as e:
        ctx.audit.record(trace_id=ctx.trace_id, actor="agent-p3", role=ctx.role.value,
                         tool=tool, args=args, outcome="error",
                         detail=f"{type(e).__name__}: {e}",
                         duration_ms=(time.monotonic() - t0) * 1000)
        raise
    ctx.audit.record(trace_id=ctx.trace_id, actor="agent-p3", role=ctx.role.value,
                     tool=tool, args=args, outcome="ok",
                     detail=json.dumps(result, ensure_ascii=False, default=str)[:280],
                     duration_ms=(time.monotonic() - t0) * 1000)
    return result


def _validate(schema: type[BaseModel], raw: dict[str, Any]) -> BaseModel:
    try:
        return schema.model_validate(raw)
    except ValidationError as e:
        first = e.errors()[0]
        loc = ".".join(str(x) for x in first["loc"])
        raise ToolValidationError(f"参数校验失败 {loc}: {first['msg']}") from e


def build_tools(ctx: ToolContext) -> list[Any]:
    """为一次任务构造工具闭包（@tool 列表；create_agent 直接可用）。"""

    @tool
    def query_plans(date: str) -> dict[str, Any]:
        """查询指定日期(YYYY-MM-DD)的生产计划列表（计划号/产品/数量/状态）。只读。
        不知道计划号时先用本工具列出当日全部计划；延期计划以 status 字段判断。"""
        args = _validate(QueryPlansArgs, {"date": date})

        def run() -> dict[str, Any]:
            data = ctx.client.get_json("/plans", params={"date": args.date})
            plans = [Plan.model_validate(p) for p in data.get("plans", [])]
            return {"date": args.date, "count": len(plans),
                    "plans": [p.model_dump() for p in plans]}

        return _audited(ctx, "query_plans", args.model_dump(), "query_plans", run)

    @tool
    def query_workorder(workorder_id: str) -> dict[str, Any]:
        """按工单号(WO-开头)查询单个工单的完成数量与状态。只读。
        仅在已知工单号时使用；不确定工单号先用 query_plans 反查。"""
        args = _validate(QueryWorkOrderArgs, {"workorder_id": workorder_id})

        def run() -> dict[str, Any]:
            data = ctx.client.get_json(f"/workorders/{args.workorder_id}")
            if data.get("_not_found"):
                return {"exists": False, "workorder_id": args.workorder_id,
                        "hint": "工单不存在，请核对工单号"}
            return WorkOrder.model_validate(data).model_dump() | {"exists": True}

        return _audited(ctx, "query_workorder", args.model_dump(), "query_workorder", run)

    @tool
    def submit_adjustment(plan_id: str, new_qty: int, reason: str, date: str) -> dict[str, Any]:
        """提交低风险生产计划调整（写操作）：把 plan_id 在 date 当日的数量调整为 new_qty。
        前置条件：调整幅度 ≤ 计划现量的 20%（超出会被拒绝，应改走审批）；
        date 必须提供（服务端按当日计划核验现量，不接受转述）。"""
        args = _validate(AdjustmentArgs, {"plan_id": plan_id, "new_qty": new_qty,
                                          "reason": reason, "date": date})

        def run() -> dict[str, Any]:
            # ① 到 Java 侧取权威现量（不信模型转述的 qty）
            data = ctx.client.get_json("/plans", params={"date": args.date})
            plan = next((Plan.model_validate(p) for p in data.get("plans", [])
                         if p["plan_id"] == args.plan_id), None)
            if plan is None:
                raise BusinessRuleError(f"计划 {args.plan_id} 在 {args.date} 不存在")
            delta = abs(args.new_qty - plan.qty)
            if plan.qty and delta / plan.qty > ctx.max_adjust_ratio:
                raise BusinessRuleError(
                    f"调整幅度 {delta / plan.qty:.0%} 超过 {ctx.max_adjust_ratio:.0%} 上限，"
                    "属高风险调整，应改走 submit_emergency_adjustment（人工审批）")
            # ② 幂等键（同 trace 内重试同 key → Java 去重）
            key = idempotency_key(args.plan_id, args.new_qty, args.reason, ctx.trace_id)
            resp = ctx.client.post_adjustment(
                {"plan_id": args.plan_id, "new_qty": args.new_qty, "reason": args.reason}, key)
            return {"submitted": True, "idempotency_key": key, **resp}

        return _audited(ctx, "submit_adjustment", args.model_dump(), "submit_adjustment", run)

    @tool
    def submit_emergency_adjustment(plan_id: str, new_qty: int, reason: str) -> dict[str, Any]:
        """提交高风险生产计划调整（翻倍/急单插单）：必须经人工审批后才会执行。
        本工具由 HumanInTheLoopMiddleware 拦截：审批 approve 才真正提交，reject 则记录拒绝。"""
        args = _validate(EmergencyAdjustmentArgs,
                         {"plan_id": plan_id, "new_qty": new_qty, "reason": reason})

        def run() -> dict[str, Any]:
            key = idempotency_key(args.plan_id, args.new_qty, args.reason, ctx.trace_id)
            resp = ctx.client.post_adjustment(
                {"plan_id": args.plan_id, "new_qty": args.new_qty, "reason": args.reason}, key)
            return {"submitted": True, "via": "approved_high_risk",
                    "idempotency_key": key, **resp}

        # 高风险工具的第二道闸门（第一道是 HITL 中间件拦截工具调用）：
        # 只有审批恢复路径（approve）把工具名放进 approved_tools 才放行，
        # 绕过 Agent 直调工具（含测试/调试）一律拒绝并留痕。
        if "submit_emergency_adjustment" not in ctx.approved_tools:
            ctx.audit.record(trace_id=ctx.trace_id, actor="agent-p3", role=ctx.role.value,
                             tool="submit_emergency_adjustment", args=args.model_dump(),
                             outcome="denied", detail="高风险工具未经人工审批不可执行")
            raise ToolPermissionError(
                "submit_emergency_adjustment 是高风险工具，必须经人工审批后执行")
        ctx.check_cancel()
        result = run()
        ctx.audit.record(trace_id=ctx.trace_id, actor="agent-p3", role=ctx.role.value,
                         tool="submit_emergency_adjustment", args=args.model_dump(),
                         outcome="ok", detail=json.dumps(result, ensure_ascii=False)[:280])
        return result

    return [query_plans, query_workorder, submit_adjustment, submit_emergency_adjustment]
