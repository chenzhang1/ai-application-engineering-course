# projects/p3_java_python_agent/planagent/agent_core.py
"""Agent 核心：规则模型 + create_agent（checkpointer + HITL 审批中间件）。

模型说明（重要，README 同步声明）：
    沙箱无 OPENAI_API_KEY，Agent 的"模型"用 RuleChatModel（BaseChatModel 子类，
    按对话状态确定性产出 tool_calls/回答）。它与真实模型的契约完全一致：
    bind_tools 接收工具 schema、_generate 产出 AIMessage——生产替换为
    ChatOpenAI(model=...) 即可（ch42 的标准接线），控制流与工具层零改动。
    LLM_MODE=real 且设置 OPENAI_API_KEY 时自动切换真实模型。

审批链路（ch42 中间件 + ch48 恢复语义的衔接）：
    HumanInTheLoopMiddleware(interrupt_on={"submit_emergency_adjustment": ...})
    → 高风险工具调用被拦截，invoke 返回 __interrupt__
    → 人工 POST /analysis/{id}/approval
    → agent.invoke(Command(resume={"decisions": [...]}), 同 config) 恢复执行
"""
from __future__ import annotations

import json
import os
from collections.abc import Sequence
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import BaseTool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from planagent.tools_layer import ToolContext, build_tools

SYSTEM_PROMPT = (
    "你是生产计划分析助手。分析延期等异常时：先 query_plans 查当日计划，"
    "需要时 query_workorder 看工单进度；小幅度恢复性调整用 submit_adjustment（低风险，直提）；"
    "翻倍/急单插单等大幅调整用 submit_emergency_adjustment（高风险，会转人工审批）。"
    "回答给出结论与依据，不编造数据。"
)

HIGH_RISK_TOOL = "submit_emergency_adjustment"
APPROVABLE_TOOLS = {HIGH_RISK_TOOL}


class RuleChatModel(BaseChatModel):
    """确定性规则模型：按对话状态产出下一步（Mock 基座精神，离线可复现）。

    剧本（与 README 的"正常与失败路径"一一对应）：
        轮 1（最后是 HumanMessage）：发起 query_plans(date)；
        轮 2（最后是 query_plans 的 ToolMessage）：
            有延期计划 → 按问题是否含"紧急/翻倍"决定走低风险调整（+5%）或高风险调整（×2）；
            无延期计划 → 直接给"无延期"结论；
        轮 3（最后是 submit_* 的 ToolMessage）：整合结果给出最终分析结论；
        被 reject（ToolMessage 以 "User rejected" 开头）：结论=调整被拒绝，不执行。
    """

    seq: int = 0  # tool_call id 计数器（声明为 pydantic 字段，实例级递增）

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

    @property
    def _llm_type(self) -> str:
        return "rule-chat"

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> Any:
        return self  # 规则模型不读 schema（剧本内固定调用），但必须声明契约支持

    # -- 剧本本体 -------------------------------------------------------------
    def _generate(self, messages: list[BaseMessage], stop: Any = None,
                  run_manager: Any = None, **kwargs: Any) -> ChatResult:
        last = messages[-1]
        question = next((str(m.content) for m in messages
                         if isinstance(m, HumanMessage)), "")
        if isinstance(last, ToolMessage):
            return ChatResult(generations=[ChatGeneration(
                message=self._after_tool(last, question))])
        if isinstance(last, HumanMessage):
            date = self._extract_date(question)
            return ChatResult(generations=[ChatGeneration(
                message=self._tool_call_msg("query_plans", {"date": date}))])
        # 兜底：不认识的消息类型 → 空回答（防御，正常剧本不会走到）
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=""))])

    def _after_tool(self, msg: ToolMessage, question: str) -> AIMessage:
        content = str(msg.content)
        if content.startswith("User rejected"):
            return AIMessage(content=(
                "分析结论：延期风险确认存在，但建议的高风险调整被人拒绝，未执行。"
                "请人工确定处理方案（改排产/与客户协商延期）。"))
        tool_name = getattr(msg, "name", "") or ""
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            data = {}
        if tool_name == "query_plans":
            plans = [p for p in data.get("plans", []) if isinstance(p, dict)]
            delayed = next((p for p in plans if p.get("status") == "延期"), None)
            if delayed is None:
                return AIMessage(content=(
                    f"分析结论：{data.get('date', '当日')} 共 {data.get('count', 0)} 个计划，"
                    "无延期计划，无需调整。"))
            pid, qty = delayed["plan_id"], delayed["qty"]
            if ("紧急" in question) or ("翻倍" in question):
                new_qty = qty * 2
                return AIMessage(content="", tool_calls=[self._tc(
                    HIGH_RISK_TOOL,
                    {"plan_id": pid, "new_qty": new_qty,
                     "reason": f"急单插单：{pid} 数量翻倍（自动分析建议，待人工审批）"})])
            new_qty = qty + max(1, qty // 20)  # +5% 恢复性提量（≤20% 上限）
            return AIMessage(content="", tool_calls=[self._tc(
                "submit_adjustment",
                {"plan_id": pid, "new_qty": new_qty,
                 "reason": f"延期恢复：{pid} 提量 5%（自动分析建议）",
                 "date": data.get("date", "2026-03-18")})])
        if tool_name in {"submit_adjustment", HIGH_RISK_TOOL}:
            if data.get("submitted") or data.get("idempotent_replay"):
                return AIMessage(content=(
                    f"分析结论：延期计划 {data.get('plan_id')} 的调整已提交"
                    f"（调整单 {data.get('adjustment_id')}，幂等键 {data.get('idempotency_key')}）。"
                    "建议跟踪工单进度确认恢复。"))
            return AIMessage(content=f"分析结论：调整提交未成功（{content[:80]}）。")
        return AIMessage(content=f"分析结论：已获取数据（{content[:60]}）。")

    # -- 小工具 ---------------------------------------------------------------
    def _extract_date(self, question: str) -> str:
        import re

        m = re.search(r"\d{4}-\d{2}-\d{2}", question)
        return m.group(0) if m else "2026-03-18"  # 教学固定演示日

    def _tc(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        self.seq += 1
        return {"id": f"call_{self.seq:03d}", "name": name, "args": args, "type": "tool_call"}

    def _tool_call_msg(self, name: str, args: dict[str, Any]) -> AIMessage:
        return AIMessage(content="", tool_calls=[self._tc(name, args)])


def build_model() -> BaseChatModel:
    """LLM_MODE=real 且有 Key → ChatOpenAI（生产接线）；否则规则模型（离线确定性）。"""
    if os.environ.get("LLM_MODE", "mock").strip().lower() == "real" \
            and os.environ.get("OPENAI_API_KEY"):
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=os.environ.get("P3_MODEL", "gpt-4o-mini"), temperature=0)
    return RuleChatModel()


def build_agent(ctx: ToolContext, checkpointer: InMemorySaver) -> Any:
    """编译一个任务专属 Agent：工具闭包绑定任务上下文，checkpointer 全局共享。"""
    return create_agent(
        model=build_model(),
        tools=build_tools(ctx),
        system_prompt=SYSTEM_PROMPT,
        middleware=[HumanInTheLoopMiddleware(interrupt_on={
            HIGH_RISK_TOOL: {"allowed_decisions": ["approve", "reject"]},
        })],
        checkpointer=checkpointer,
    )


def extract_approval(interrupt_value: Any) -> dict[str, Any]:
    """从 __interrupt__ 载荷提取审批单（给"人"看的全部信息）。"""
    requests = interrupt_value.get("action_requests", []) if isinstance(interrupt_value, dict) else []
    if not requests:
        return {"tool": "", "args": {}, "description": str(interrupt_value)[:200]}
    first = requests[0]
    return {"tool": first.get("name", ""), "args": first.get("args", {}),
            "description": str(first.get("description", ""))[:300]}


def run_analysis(ctx: ToolContext, checkpointer: InMemorySaver, question: str) -> dict[str, Any]:
    """运行一次分析：正常结束返回 final；高风险被拦截返回 waiting_approval 载荷。"""
    agent = build_agent(ctx, checkpointer)
    cfg = {"configurable": {"thread_id": ctx.task_id}}
    result = agent.invoke({"messages": [HumanMessage(content=question)]}, cfg)
    interrupts = result.get("__interrupt__")
    if interrupts:
        return {"status": "waiting_approval",
                "approval_request": extract_approval(interrupts[0].value),
                "final": None}
    return {"status": "succeeded", "approval_request": None,
            "final": str(result["messages"][-1].content)}


def resume_analysis(ctx: ToolContext, checkpointer: InMemorySaver, task_id: str,
                    decision: str) -> dict[str, Any]:
    """审批恢复：decision ∈ approve / reject（ch48 的 Command(resume=...) 语义）。

    approve 时把高风险工具加入审批凭证集合——工具体内的第二道闸门据此放行
    （防绕过 Agent 直调工具）。reject 时中间件会把调用替换为拒绝 ToolMessage，
    工具体根本不会执行。"""
    if decision == "approve":
        ctx.approved_tools.add(HIGH_RISK_TOOL)
    agent = build_agent(ctx, checkpointer)  # 同一 ctx 重建工具闭包 + 同 checkpointer
    cfg = {"configurable": {"thread_id": task_id}}
    result = agent.invoke(Command(resume={"decisions": [{"type": decision}]}), cfg)
    return {"status": "succeeded", "approval_request": None,
            "final": str(result["messages"][-1].content)}
