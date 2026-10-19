# 测试/test_common_llm.py | 全书 LLM 基座（示例代码/公共）测试
"""覆盖：mock 普通回复/脚本工具调用循环/规则触发/结构化输出成功与失败/脚本耗尽/
real 缺 key 报错/usage 回退/流式拼接/embedding 相似度性质/respx 拦截下的 real 转换路径。
"""
from __future__ import annotations

import math
import os
from typing import Any

import pytest
from pydantic import BaseModel, Field

from 示例代码.公共.embeddings import MockEmbedder, cosine_similarity, get_embedder
from 示例代码.公共.llm_client import (
    ChatResult,
    MockLLM,
    RealLLM,
    StructuredOutputError,
    count_tokens,
    get_llm,
)

# ---------------------------------------------------------------------------
# mock 普通回复（确定性与风格规则）
# ---------------------------------------------------------------------------


def test_mock_plain_reply_deterministic_and_styles() -> None:
    """同输入同输出；system 关键词改变风格；无 system 用默认模板。"""
    msgs_default = [{"role": "user", "content": "什么是 token？"}]
    r1 = MockLLM().chat(msgs_default)
    r2 = MockLLM().chat(msgs_default)
    assert r1.content == r2.content  # 确定性
    assert r1.finish_reason == "stop"
    assert not r1.has_tool_calls
    assert "Mock 默认回复" in r1.content and "token" in r1.content

    pirate = [{"role": "system", "content": "你是海盗风格客服"},
              {"role": "user", "content": "查下订单"}]
    rp = MockLLM().chat(pirate)
    assert "海盗" in rp.content

    cs = [{"role": "system", "content": "你是有礼貌的客服"},
          {"role": "user", "content": "查下订单"}]
    rc = MockLLM().chat(cs)
    assert "客服" in rc.content and rc.content != rp.content


def test_get_llm_factory_modes() -> None:
    """LLM_MODE 默认 mock；非法值报错；real 缺 key 报中文指引 RuntimeError。"""
    old = os.environ.get("LLM_MODE")
    try:
        os.environ.pop("LLM_MODE", None)
        assert isinstance(get_llm(), MockLLM)
        os.environ["LLM_MODE"] = "bogus"
        with pytest.raises(ValueError, match="LLM_MODE"):
            get_llm()
        os.environ["LLM_MODE"] = "real"
        os.environ.pop("OPENAI_API_KEY", None)
        with pytest.raises(RuntimeError, match="OPENAI_API_KEY") as ei:
            get_llm()
        assert "LLM_MODE=mock" in str(ei.value)  # 指引里给了兜底方案
    finally:
        if old is None:
            os.environ.pop("LLM_MODE", None)
        else:
            os.environ["LLM_MODE"] = old


# ---------------------------------------------------------------------------
# 脚本驱动的工具调用循环（agent loop 教学核心）
# ---------------------------------------------------------------------------


class TestScriptedToolLoop:
    def test_two_step_loop(self) -> None:
        """第 1 次=工具调用请求 → 程序执行 → tool 消息回传 → 第 2 次=最终回答。"""
        llm = MockLLM(script=[
            {"tool_calls": [{"name": "get_weather", "arguments": {"city": "北京"}}]},
            {"content": "北京今天晴，26℃。"},
        ])
        tools = [{"type": "function", "function": {"name": "get_weather"}}]
        messages: list[dict[str, Any]] = [{"role": "user", "content": "北京天气怎么样？"}]

        r1 = llm.chat(messages, tools=tools)
        assert r1.finish_reason == "tool_calls"
        assert r1.tool_calls[0].name == "get_weather"
        assert r1.tool_calls[0].arguments == {"city": "北京"}
        assert r1.tool_calls[0].id.startswith("call_")

        # 程序执行工具（示例桩），把结果按 OpenAI 形态回传
        messages.append({"role": "assistant", "content": r1.content,
                         "tool_calls": [{"id": r1.tool_calls[0].id, "type": "function",
                                         "function": {"name": "get_weather",
                                                      "arguments": '{"city": "北京"}'}}]})
        messages.append({"role": "tool", "tool_call_id": r1.tool_calls[0].id,
                         "content": '{"city": "北京", "weather": "晴", "temp": 26}'})
        r2 = llm.chat(messages)
        assert r2.content == "北京今天晴，26℃。"
        assert r2.finish_reason == "stop" and not r2.has_tool_calls
        assert len(llm.calls) == 2 and len(llm.calls[1]) == 3  # 第 2 次收到 3 条消息

    def test_script_accepts_chatresult_and_dict(self) -> None:
        llm = MockLLM(script=[ChatResult(content="你好"), {"content": "再见"}])
        assert llm.chat([]).content == "你好"
        assert llm.chat([]).content == "再见"

    def test_script_exhausted_raises_teachable_error(self) -> None:
        llm = MockLLM(script=[{"content": "唯一一条"}])
        assert llm.chat([]).content == "唯一一条"
        with pytest.raises(RuntimeError, match="script 已耗尽"):
            llm.chat([])


def test_mock_rule_triggered_tool_call() -> None:
    """消息含 USE_TOOL:名字 key=value → 解析出工具调用请求；value 尽量转原生类型。"""
    llm = MockLLM()
    msgs = [{"role": "user", "content": "USE_TOOL:query_order order_id=ORD-1001 count=2"}]
    r = llm.chat(msgs)
    assert r.finish_reason == "tool_calls"
    assert r.tool_calls[0].name == "query_order"
    assert r.tool_calls[0].arguments == {"order_id": "ORD-1001", "count": 2}


# ---------------------------------------------------------------------------
# 结构化输出（成功 / 失败 / 默认值 / 重试）
# ---------------------------------------------------------------------------


class OrderInfo(BaseModel):
    order_id: str = Field(description="订单号")
    amount: float = Field(default=0.0, description="金额")
    urgent: bool = Field(default=False, description="是否加急")


class StrictInfo(BaseModel):
    name: str  # 必填且无默认值
    note: str = "（无备注）"


def test_structured_success_with_defaults() -> None:
    """key=value 解析 + Pydantic 宽松转换（"3"→int 语义）+ 缺省走字段默认值。"""
    llm = MockLLM()
    msgs = [{"role": "user", "content": "order_id=ORD-77 amount=129.5 urgent=true 请抽取"}]
    obj = llm.chat_structured(msgs, OrderInfo)
    assert isinstance(obj, OrderInfo)
    assert obj.order_id == "ORD-77"
    assert obj.amount == 129.5
    assert obj.urgent is True

    # 只给必填字段，其余走 schema 默认值
    obj2 = llm.chat_structured([{"role": "user", "content": "order_id=ORD-88"}], OrderInfo)
    assert obj2.order_id == "ORD-88" and obj2.amount == 0.0 and obj2.urgent is False


def test_structured_failure_then_retry() -> None:
    """必填缺失 → StructuredOutputError（含 errors 与教学 hint）→ 补充信息后成功。"""
    llm = MockLLM()
    bad: list[dict[str, Any]] = [{"role": "user", "content": "帮我看下（没给订单号）"}]
    with pytest.raises(StructuredOutputError) as ei:
        llm.chat_structured(bad, StrictInfo)
    assert ei.value.errors and "name" in str(ei.value.errors[0]["loc"])
    assert "重试" in ei.value.hint

    # 校验失败→把错误回传模型再试（教学演示：Mock 用补充 key=value 的消息模拟重试成功）
    good: list[dict[str, Any]] = [{"role": "user", "content": "name=吉他 note=生日礼物"}]
    obj = llm.chat_structured(good, StrictInfo)
    assert obj.name == "吉他" and obj.note == "生日礼物"


# ---------------------------------------------------------------------------
# usage / token 计数 / 流式
# ---------------------------------------------------------------------------


def test_usage_tiktoken_then_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """优先 tiktoken 精确计数；词表不可用时回退 len//4，且 count_method 如实标注。"""
    n, method = count_tokens("hello world")
    assert method == "tiktoken:cl100k_base" and n >= 1 and isinstance(n, int)

    # 强制词表加载失败，验证回退路径（Mock/无网环境下的真实行为）
    import 示例代码.公共.llm_client as lc

    def boom(name: str = "cl100k_base") -> Any:
        raise OSError("BPE 词表下载失败（模拟离线环境）")

    monkeypatch.setattr(lc, "_get_encoding", boom)
    n2, method2 = lc.count_tokens("hello world, hi again")  # 20 字符 → 近似 5
    assert method2 == "approx:chars//4" and n2 == 5

    msgs = [{"role": "user", "content": "hello world, hi again"}]
    usage = MockLLM().chat(msgs).usage
    assert usage["completion_tokens"] >= 1
    assert usage["total_tokens"] == usage["prompt_tokens"] + usage["completion_tokens"]
    assert usage["count_method"] in {"approx:chars//4", "tiktoken:cl100k_base"}


def test_mock_stream_chunks_join_back() -> None:
    """chat_stream 逐段 yield；拼接结果 == 非流式 content（脚本模式同样成立）。"""
    llm = MockLLM(script=[{"content": "流式输出的拼接结果必须与整体一致"}])
    messages = [{"role": "user", "content": "讲讲流式"}]
    whole = llm.chat(messages).content
    chunks = list(MockLLM(script=[{"content": whole}]).chat_stream(messages))
    assert len(chunks) >= 2
    assert "".join(chunks) == whole


# ---------------------------------------------------------------------------
# real 模式：respx 拦截 HTTP 层，验证 SDK→ChatResult 转换路径（沙箱无 Key 的诚实验证方式）
# ---------------------------------------------------------------------------


_FAKE_COMPLETION = {
    "id": "chatcmpl-test-1",
    "object": "chat.completion",
    "created": 1,
    "model": "gpt-4o-mini",
    "choices": [{
        "index": 0,
        "message": {
            "role": "assistant",
            "content": "北京今天晴。",
            "tool_calls": [{
                "id": "call_test_1",
                "type": "function",
                "function": {"name": "get_weather", "arguments": '{"city": "北京"}'},
            }],
        },
        "finish_reason": "tool_calls",
    }],
    "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
}


def test_real_llm_conversion_via_mock_transport() -> None:
    """httpx.MockTransport 注入 SDK：验证 RealLLM 的鉴权、payload 与 ChatResult 转换。

    说明：沙箱无 OPENAI_API_KEY，无法真连服务；本测试用 openai SDK 官方支持的
    http_client 注入（签名已核实）在 httpx 层伪造一次真实形态的响应，验证的是
    "我们的转换代码对 SDK 响应形状的处理"，而非真实服务行为——教材如实标注该边界。
    """
    import json as _json

    import httpx

    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers.get("authorization")
        captured["body"] = _json.loads(request.content.decode("utf-8"))
        return httpx.Response(200, json=_FAKE_COMPLETION)

    llm = RealLLM(api_key="sk-test-dummy", max_retries=0,
                  http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    r = llm.chat(
        [{"role": "user", "content": "北京天气？"}],
        tools=[{"type": "function", "function": {"name": "get_weather"}}],
    )

    assert captured["auth"] == "Bearer sk-test-dummy"
    assert captured["body"]["model"] == "gpt-4o-mini"
    assert captured["body"]["tools"][0]["function"]["name"] == "get_weather"
    assert r.content == "北京今天晴。"
    assert r.finish_reason == "tool_calls"
    assert r.tool_calls[0].name == "get_weather"
    assert r.tool_calls[0].arguments == {"city": "北京"}  # JSON 字符串已被解析为 dict
    assert r.usage == {"prompt_tokens": 10, "completion_tokens": 5,
                       "total_tokens": 15, "count_method": "server_reported"}


def test_real_stream_via_mock_transport() -> None:
    """MockTransport 伪造 SSE 流，验证 chat_stream 的增量解析路径。"""
    import httpx

    sse_body = (
        'data: {"id":"c1","object":"chat.completion.chunk","created":1,"model":"gpt-4o-mini",'
        '"choices":[{"index":0,"delta":{"role":"assistant","content":"你"},"finish_reason":null}]}\n\n'
        'data: {"id":"c1","object":"chat.completion.chunk","created":1,"model":"gpt-4o-mini",'
        '"choices":[{"index":0,"delta":{"content":"好"},"finish_reason":null}]}\n\n'
        'data: {"id":"c1","object":"chat.completion.chunk","created":1,"model":"gpt-4o-mini",'
        '"choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}\n\n'
        "data: [DONE]\n\n"
    )
    llm = RealLLM(
        api_key="sk-test-dummy", max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(
            lambda request: httpx.Response(200, content=sse_body.encode("utf-8"),
                                           headers={"content-type": "text/event-stream"}))),
    )
    chunks = list(llm.chat_stream([{"role": "user", "content": "hi"}]))
    assert chunks == ["你", "好"]


# ---------------------------------------------------------------------------
# embeddings：相似度性质
# ---------------------------------------------------------------------------


class TestEmbeddings:
    def test_self_similarity_is_one(self) -> None:
        emb = MockEmbedder()
        v = emb.embed_one("订单 ORD-1001 已支付")
        assert math.isclose(cosine_similarity(v, v), 1.0, abs_tol=1e-9)
        # 归一化：模长为 1
        assert math.isclose(sum(x * x for x in v), 1.0, abs_tol=1e-9)

    def test_semantic_ordering_phone_food(self) -> None:
        """sim(手机,电话) > sim(手机,披萨) —— 概念词典带来粗粒度语义。"""
        emb = MockEmbedder()
        v_phone = emb.embed_one("手机")
        v_tel = emb.embed_one("电话")
        v_pizza = emb.embed_one("披萨")
        s_near = cosine_similarity(v_phone, v_tel)
        s_far = cosine_similarity(v_phone, v_pizza)
        assert s_near > 0.99      # 同概念方向重合（Mock 的粗粒度语义）
        assert s_far < 0.01       # 不同概念近似正交
        assert s_near > s_far

    def test_orthogonal_and_zero_vector(self) -> None:
        # 手工构造正交向量：余弦 = 0；反向 = -1；零向量约定 = 0.0
        assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0
        assert math.isclose(cosine_similarity([1.0, 0.0], [-1.0, 0.0]), -1.0)
        assert cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0

    def test_embedder_factory_bad_mode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LLM_MODE", "bogus")
        with pytest.raises(ValueError, match="LLM_MODE"):
            get_embedder()

    def test_mock_embedder_deterministic(self) -> None:
        a = MockEmbedder().embed_one("手机充值")
        b = MockEmbedder().embed_one("手机充值")
        assert a == b
