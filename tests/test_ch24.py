# tests/test_ch24.py | ch24 openai SDK 全流程
"""覆盖：缺 Key 报错指引、结构化输出成功/失败、脚本化工具调用闭环、
SDK 签名核实（3.35.1：parse 存在且无 stream、max_retries 默认 2）。"""
from __future__ import annotations

import inspect
import json

import pytest
from pydantic import BaseModel, Field

from examples.common.llm_client import (
    MockLLM,
    RealLLM,
    StructuredOutputError,
    get_llm,
)


class Order(BaseModel):
    order_id: str = Field(description="订单号")
    amount: float = Field(default=0.0)


def test_missing_key_error_is_actionable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError) as ei:
        RealLLM()
    msg = str(ei.value)
    assert "OPENAI_API_KEY" in msg and "OPENAI_BASE_URL" in msg and "mock" in msg


def test_structured_output_success_and_failure() -> None:
    llm = MockLLM()
    ok = llm.chat_structured([{"role": "user", "content": "order_id=ORD-9 amount=66.5"}], Order)
    assert ok.order_id == "ORD-9" and isinstance(ok.amount, float)
    with pytest.raises(StructuredOutputError) as ei:
        llm.chat_structured([{"role": "user", "content": "（没给订单号）"}], Order)
    assert ei.value.errors[0]["type"] == "missing"


def test_tool_call_loop_scripted() -> None:
    """完整闭环：脚本第 1 次=工具请求，程序执行，第 2 次=基于结果回答（EX-24-03）。"""
    llm = MockLLM(script=[
        {"tool_calls": [{"name": "get_weather", "arguments": {"city": "北京"}}]},
        {"content": "北京今天晴，26℃。"},
    ])
    msgs: list[dict] = [{"role": "user", "content": "北京天气怎么样？"}]
    r1 = llm.chat(msgs, tools=[{"type": "function", "function": {"name": "get_weather"}}])
    assert r1.finish_reason == "tool_calls" and r1.tool_calls[0].arguments == {"city": "北京"}
    tool_result = json.dumps({"city": "北京", "temp": 26}, ensure_ascii=False)
    msgs.append({"role": "assistant", "content": r1.content,
                 "tool_calls": [{"id": r1.tool_calls[0].id, "type": "function",
                                 "function": {"name": "get_weather",
                                              "arguments": json.dumps(r1.tool_calls[0].arguments)}}]})
    msgs.append({"role": "tool", "tool_call_id": r1.tool_calls[0].id, "content": tool_result})
    r2 = llm.chat(msgs)
    assert r2.finish_reason == "stop" and r2.content == "北京今天晴，26℃。"


def test_sdk_signature_facts_v3351() -> None:
    """FACTS 红线核实：3.35.1 的 parse 存在且无 stream；max_retries 默认 2。"""
    from openai import OpenAI
    from openai.resources.chat.completions import Completions

    assert hasattr(Completions, "parse")
    assert "response_format" in inspect.signature(Completions.parse).parameters
    assert "stream" not in inspect.signature(Completions.parse).parameters
    assert "tools" in inspect.signature(Completions.create).parameters
    client = OpenAI(api_key="sk-dummy")
    assert client.max_retries == 2


def test_get_llm_script_only_affects_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_MODE", "mock")
    llm = get_llm(script=[{"content": "脚本回复"}])
    assert llm.chat([]).content == "脚本回复"  # type: ignore[union-attr]
