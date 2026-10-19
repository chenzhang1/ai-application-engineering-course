# EX-54-02 | 参数校验与权限分级：把"模型不能信任"写进代码
# 运行: python3 示例代码/ch54_tool_governance/ex_54_02_param_validation_permission.py
"""完整可运行（pydantic 2.14.1，无模型调用，确定性）：

ch39 讲过 args_schema 能拦住"参数类型不对"；本章把防线补全为两层：
    第一层 参数校验（Pydantic）：类型、范围、必填、业务规则（调整幅度 ≤ 20%）；
    第二层 权限分级（RBAC）：每个工具声明风险级别，每个角色声明可用级别，
          执行入口统一 enforce——工具函数内部永远不自己判断权限。

Java 对照：args_schema ≈ Bean Validation（@NotNull/@Max）；enforce ≈ 方法级
@PreAuthorize——区别是这里的"调用方"是概率模型，所以默认拒绝（deny by default）
必须落在代码里而不是提示词里（ch28 红线：提示词不是权限控制）。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

from pydantic import BaseModel, Field, field_validator


# ---- 第一层：参数校验（每个写操作工具一个 args schema） ---------------------------
class AdjustmentArgs(BaseModel):
    """提交计划调整的参数契约（工具的 inputSchema，模型生成的参数先过这里）。"""

    plan_id: str = Field(pattern=r"^P-\d{4}$", description="计划号，形如 P-1002")
    new_qty: int = Field(ge=0, le=100_000, description="调整后的数量")
    reason: str = Field(min_length=5, max_length=200, description="调整原因，必填")

    @field_validator("new_qty")
    @classmethod
    def qty_not_negative_step(cls, v: int) -> int:
        if v < 0:
            raise ValueError("数量不能为负")
        return v


# ---- 第二层：权限分级 --------------------------------------------------------------
class Risk(str, Enum):
    """工具风险级别（治理清单 54.3 里的定级表）。"""

    READ = "read"                    # 只读：任何角色
    LOW_RISK_WRITE = "low_risk"      # 低风险写：可撤销、幅度受限
    HIGH_RISK_WRITE = "high_risk"    # 高风险写：必须审批（ch48 interrupt）


class Role(str, Enum):
    VIEWER = "viewer"      # 只读
    OPERATOR = "operator"  # 只读 + 低风险写
    ADMIN = "admin"        # 全部（高风险写仍需人审批——admin≠免审）


ROLE_MATRIX: dict[Role, set[Risk]] = {
    Role.VIEWER: {Risk.READ},
    Role.OPERATOR: {Risk.READ, Risk.LOW_RISK_WRITE},
    Role.ADMIN: {Risk.READ, Risk.LOW_RISK_WRITE, Risk.HIGH_RISK_WRITE},
}


class PermissionDenied(Exception):
    """权限不足（对应 HTTP 403；审计里记 denied 事件）。"""


class BusinessRuleError(Exception):
    """参数合法但违反业务规则（对应 HTTP 422 语义）。"""


# ---- 工具注册表：名字 → 风险级别 + 参数 schema + 实现 ------------------------------
def _submit_adjustment_impl(args: AdjustmentArgs, plan_qty: int) -> dict[str, Any]:
    """工具实现：业务规则（幅度 ≤20% 才算低风险）在这里，权限不在这里。"""
    delta = abs(args.new_qty - plan_qty)
    if plan_qty and delta / plan_qty > 0.20:
        raise BusinessRuleError(
            f"调整幅度 {delta / plan_qty:.0%} 超过 20%，属高风险调整，须走人工审批")
    return {"accepted": True, "plan_id": args.plan_id, "new_qty": args.new_qty,
            "idempotency_key": f"adj:{args.plan_id}:{args.new_qty}:{hash(args.reason) % 10_000}"}


TOOL_RISK: dict[str, Risk] = {
    "query_plan": Risk.READ,
    "submit_adjustment": Risk.LOW_RISK_WRITE,
    "restart_line": Risk.HIGH_RISK_WRITE,
}


@dataclass
class ToolEntry:
    """工具注册表条目：治理的落点是这张表，不是散落各处的 if。"""

    risk: Risk
    args_schema: type[BaseModel] | None
    fn: Callable[..., dict[str, Any]]


def execute_tool(registry: dict[str, ToolEntry], name: str, role: Role,
                 raw_args: dict[str, Any], *, plan_qty: int = 1000,
                 approved: bool = False) -> dict[str, Any]:
    """统一执行入口：高风险闸门 → 权限 → 校验 → 业务规则 → 实现。

    高风险工具（restart_line）**任何角色都不能直调**：只能由审批流恢复后带着
    approved=True 进来（ch48 的 interrupt/Command(resume) 是唯一合法入口）——
    这就是"权限分级"与"人工审批"的分工：分级管"谁够格"，审批管"这次行不行"。
    任何一步不过都抛异常，由调用方翻译成协议响应（Agent 框架/FastAPI）。"""
    entry = registry.get(name)
    if entry is None:
        raise KeyError(f"未知工具 {name}")
    if entry.risk == Risk.HIGH_RISK_WRITE and not approved:
        raise PermissionDenied(
            f"{name} 是高风险工具，必须走人工审批入口（审批恢复后 approved=True 才能执行）")
    if entry.risk not in ROLE_MATRIX[role]:
        raise PermissionDenied(
            f"角色 {role.value} 无权调用 {name}（需要 {entry.risk.value} 级）")
    if entry.args_schema is not None:
        args = entry.args_schema.model_validate(raw_args)  # ValidationError → 422
    else:
        args = raw_args
    if name == "submit_adjustment":
        return _submit_adjustment_impl(args, plan_qty)
    return entry.fn(**raw_args)


def _query_plan_stub(plan_id: str) -> dict[str, Any]:
    return {"plan_id": plan_id, "qty": 1000, "status": "延期"}


REGISTRY: dict[str, ToolEntry] = {
    "query_plan": ToolEntry(Risk.READ, None, _query_plan_stub),
    "submit_adjustment": ToolEntry(Risk.LOW_RISK_WRITE, AdjustmentArgs, _submit_adjustment_impl),
    "restart_line": ToolEntry(Risk.HIGH_RISK_WRITE, None,
                              lambda **kw: {"restarted": kw.get("line_id")}),
}


def main() -> None:
    print("== 第一层：参数校验（Pydantic 拦在工具实现之前）==")
    from pydantic import ValidationError

    cases_bad = [
        {"plan_id": "P1002", "new_qty": 1200, "reason": "客户加急订单"},   # 计划号格式错
        {"plan_id": "P-1002", "new_qty": "abc", "reason": "客户加急订单"},  # 类型错
        {"plan_id": "P-1002", "new_qty": 1200},                            # 缺 reason
    ]
    for raw in cases_bad:
        try:
            execute_tool(REGISTRY, "submit_adjustment", Role.OPERATOR, raw)
            print(f"  ✗ 本应拦截：{raw}")
        except ValidationError as e:
            first = e.errors()[0]
            loc = ".".join(str(x) for x in first["loc"])
            print(f"  ✓ 拦截 {json.dumps(raw, ensure_ascii=False)}")
            print(f"      理由：ValidationError → {loc}: {first['msg'][:70]}")

    print("\n== 第二层：权限分级（deny by default）==")
    try:
        execute_tool(REGISTRY, "submit_adjustment", Role.VIEWER,
                     {"plan_id": "P-1002", "new_qty": 1100, "reason": "客户加急订单"})
    except PermissionDenied as e:
        print(f"  ✓ viewer 提交调整被拒：{e}")
    try:
        execute_tool(REGISTRY, "restart_line", Role.ADMIN, {"line_id": "L-3"})
    except PermissionDenied as e:
        print(f"  ✓ admin 直调 restart_line 也被拒（高风险工具任何角色不可直调）：{e}")
    print(f"  ✓ 审批流恢复后（approved=True）admin 执行："
          f"{execute_tool(REGISTRY, 'restart_line', Role.ADMIN, {'line_id': 'L-3'}, approved=True)}")

    print("\n== 业务规则：低风险放行、高风险改道审批 ==")
    ok = execute_tool(REGISTRY, "submit_adjustment", Role.OPERATOR,
                      {"plan_id": "P-1002", "new_qty": 1150, "reason": "客户加急订单5%以内"})
    print(f"  ✓ 幅度 15% 低风险放行：{json.dumps(ok, ensure_ascii=False)}")
    try:
        execute_tool(REGISTRY, "submit_adjustment", Role.OPERATOR,
                     {"plan_id": "P-1002", "new_qty": 2000, "reason": "客户要求翻倍交付"})
    except BusinessRuleError as e:
        print(f"  ✓ 幅度 100% 超限改道：{e}")
        print("     → 工程动作：返回结构化错误给模型，Agent 生成'建议+审批单'而非硬提交（ch48）")


if __name__ == "__main__":
    main()
