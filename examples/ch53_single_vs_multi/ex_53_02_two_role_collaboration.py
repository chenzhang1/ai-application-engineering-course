# EX-53-02 | 最小两角色协作：主 Agent 拆解派工，子 Agent 各自闭环，失败按策略处理
# 运行: python3 examples/ch53_single_vs_multi/ex_53_02_two_role_collaboration.py
"""完整可运行（LLM_MODE=mock，确定性）：

"主 Agent + 子任务 Agent"的最小协作（ch53 的演示核心）：
    主 Agent（orchestrator）：拆解目标 → 派工（结构化 SubTask）→ 汇总；
    子 Agent（sub-agent）  ：只领一个子任务，**独立上下文 + 领域工具 + 独立脚本**，
                             产出统一形状的 SubResult（通信靠结构化消息，不靠共享内存）。
失败处理三策略全部演示：
    retry（同参数重试一次）→ degrade（降级为部分结果）→ escalate（上报主 Agent，写入缺口）。
关键不变量：子 Agent 之间互不可见；主 Agent 只看 SubResult 摘要——
这就是 53.3"共享状态最小化"的代码形态。
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # 仓库根
from examples.common.llm_client import chat_structured
from pydantic import BaseModel, Field


# ---- 角色间通信协议（结构化消息 = 多 Agent 世界的"接口契约"） ---------------------
class SubTask(BaseModel):
    """主 Agent 派工单：子 Agent 只看这张单子，不看主 Agent 的对话历史。"""

    subtask_id: str
    domain: str = "order"          # 领域路由：order / logistics / invoice
    instruction: str = "查询计划状态"
    must_include: list[str] = Field(default_factory=list)  # 结果必须覆盖的要点


@dataclass
class SubResult:
    """子 Agent 回执：status ∈ ok / degraded / failed；主 Agent 只按这个形状消费。"""

    subtask_id: str
    status: str
    summary: str
    attempts: int = 1
    gaps: list[str] = field(default_factory=list)


# ---- 领域工具（每个子 Agent 只有自己的工具，互相不可见） --------------------------
def order_query(plan_or_order: str) -> str:
    return "订单 A1001：已发货，物流单号 SF-8899"


def logistics_query(order_no: str) -> str:
    raise ConnectionError("物流服务超时（教学剧本：该子任务要失败）")


def invoice_query(order_no: str) -> str:
    return "发票已开具：电子票，金额 12,800 元"


def run_sub_agent(task: SubTask) -> SubResult:
    """子 Agent：独立上下文 + 领域工具 + 最多 2 次尝试，失败按策略收口。

    策略（与 53.3 失败处理表一一对应）：
      第 1 次失败 → retry（原样重试一次——对瞬态故障有效）；
      第 2 次失败 → degrade（换一个退路工具/口径再试，能给出部分结果也算成果）；
      仍失败     → failed + gaps（主 Agent 决定升级或放弃，子 Agent 不擅自编造）。
    """
    tools: dict[str, Callable[..., Any]] = {
        "order": {"query": order_query, "arg": "A1001"},
        "logistics": {"query": logistics_query, "arg": "A1001"},
        "invoice": {"query": invoice_query, "arg": "A1001"},
    }[task.domain]
    attempts = 0
    last_err: str = ""
    while attempts < 2:
        attempts += 1
        try:
            out = str(tools["query"](tools["arg"]))
            covered = [k for k in task.must_include if k in out]
            status = "ok" if len(covered) == len(task.must_include) else "degraded"
            gaps = [k for k in task.must_include if k not in out]
            return SubResult(task.subtask_id, status, out, attempts, gaps)
        except Exception as exc:  # noqa: BLE001
            last_err = f"{type(exc).__name__}: {exc}"
    return SubResult(task.subtask_id, "failed", f"两次尝试均失败（{last_err}）",
                     attempts, gaps=["物流轨迹不可得"])


def orchestrate(goal: str) -> dict[str, Any]:
    """主 Agent：拆解（chat_structured 走 schema 校验）→ 派工 → 汇总。"""
    _ = chat_structured(  # Mock 下解析 goal/要点；派工单按教学脚本回填保持确定性
        [{"role": "system", "content": "你是主协调器，把目标拆成子任务单。"},
         {"role": "user", "content": f"goal={goal} subtask_id=T1 域=order,logistics,invoice"}],
        SubTask)
    tasks = [
        SubTask(subtask_id="T1", domain="order", instruction="查订单状态",
                must_include=["已发货"]),
        SubTask(subtask_id="T2", domain="logistics", instruction="查物流轨迹",
                must_include=["轨迹", "预计送达"]),
        SubTask(subtask_id="T3", domain="invoice", instruction="查发票",
                must_include=["电子票"]),
    ]
    results = [run_sub_agent(t) for t in tasks]
    ok = [r for r in results if r.status == "ok"]
    degraded = [r for r in results if r.status == "degraded"]
    failed = [r for r in results if r.status == "failed"]
    return {
        "goal": goal,
        "summary": f"{len(ok)} 成功 / {len(degraded)} 降级 / {len(failed)} 失败",
        "report_parts": [r.summary for r in results if r.status != "failed"],
        "gaps": [g for r in failed for g in r.gaps],
        "attempts": {r.subtask_id: r.attempts for r in results},
    }


def main() -> None:
    print("== 主 Agent + 子任务 Agent 最小协作（Mock 驱动）==")
    out = orchestrate("客户 A1001 的履约情况总览")
    for r_desc in [f"  {k}: 尝试 {v} 次" for k, v in out["attempts"].items()]:
        print(r_desc)
    print(f"\n汇总：{out['summary']}")
    print("报告可用部分：")
    for p in out["report_parts"]:
        print(f"  - {p}")
    print(f"缺口（如实上报，不编造）：{out['gaps']}")
    print("\n通信=结构化 SubTask/SubResult；共享状态=无（子 Agent 互不可见）；"
          "失败=retry→degrade→escalate 三级收口")


if __name__ == "__main__":
    main()
