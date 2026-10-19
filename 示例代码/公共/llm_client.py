# EX-00-00 | 示例代码/公共/llm_client.py | 全书共享 LLM 客户端（Mock/Real 双模式）
"""全书统一的 LLM 客户端基座 —— 所有章节 import 本模块，不得各写一套。

接口摘要（后续章节作者必读）
=================================
消息格式：OpenAI 风格 dict 列表
    system  : {"role": "system", "content": "..."}
    user    : {"role": "user", "content": "..."}
    assistant: {"role": "assistant", "content": "..."}
    assistant 发起工具调用时（真实 API 形态）：{"role": "assistant", "content": "",
        "tool_calls": [{"id": "call_001", "type": "function",
                        "function": {"name": "get_weather", "arguments": "{\"city\": \"北京\"}"}}]}
    工具结果: {"role": "tool", "tool_call_id": "call_001", "content": "{\"temp\": 26}"}

返回值：ChatResult(content, tool_calls: list[ToolCall], usage: dict, finish_reason)
    ToolCall(id, name, arguments: dict)   # arguments 已解析为 dict，非 JSON 字符串
    usage = {"prompt_tokens", "completion_tokens", "total_tokens", "count_method"}

用法：
    from 示例代码.公共.llm_client import get_llm, chat_structured
    llm = get_llm()                      # LLM_MODE=mock(默认)/real
    r = llm.chat([{"role": "user", "content": "..."}])
    for chunk in llm.chat_stream(messages): ...   # 增量文本生成器
    obj = llm.chat_structured(messages, MySchema) # Pydantic BaseModel

MockLLM 三种核心演示：
    1) 普通回复：按 system 关键词返回固定风格文本（确定性，同输入同输出）；
    2) 工具调用：script=[ChatResult|dict] 按调用次序返回（agent loop 演示用），
       或规则触发——最后一条 user 消息含 "USE_TOOL:名字 key=value ..."；
    3) 结构化输出：chat_structured 从最后一条 user 消息解析 key=value 填充字段，
       缺省用 schema 字段默认值；解析/校验失败抛 StructuredOutputError（可教学重试）。

Real 模式（openai==3.35.1，签名已于 2026-10-19 用 inspect 核实，见教材 ch24）：
    - OpenAI.__init__ 可用参数包含：api_key / base_url / timeout / max_retries /
      organization / project / default_headers / http_client 等；max_retries 默认 2；
    - client.chat.completions.create 参数包含：messages, model, temperature, top_p,
      max_tokens, max_completion_tokens, stream, stream_options, tools, tool_choice,
      response_format, parallel_tool_calls, stop, seed, n, user ...；
    - client.chat.completions.parse 存在于 3.35.1（参数含 response_format，无 stream）；
    - client.embeddings.create 参数：input, model, dimensions, encoding_format, user。

红线：mock 模式绝不发起任何网络请求；token 计数优先 tiktoken（0.14.0 首次使用会
联网下载 BPE 词表并缓存到 TIKTOKEN_CACHE_DIR 或系统临时目录），失败回退 len//4 近似，
所用方式记录在 usage["count_method"] 与各函数返回值中，绝不静默混淆。
"""
from __future__ import annotations

import ast
import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Iterator

from pydantic import BaseModel, ValidationError

__all__ = [
    "ToolCall",
    "ChatResult",
    "StructuredOutputError",
    "MockLLM",
    "RealLLM",
    "get_llm",
    "count_tokens",
    "chat_structured",
]

# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------


@dataclass
class ToolCall:
    """一次工具调用请求：模型说"请帮我调这个函数"。

    对应真实 API 的 choices[0].message.tool_calls[i]（openai 3.35.1 的
    ChatCompletionMessage 已核实含 tool_calls 字段）。
    """

    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChatResult:
    """轻量统一的对话结果（对应真实 API 的 choices[0] + usage 的扁平化）。

    Java 对照：相当于把 HTTP 客户端的 Response 对象摘出四个常用字段做成 DTO——
    固定字段、固定语义，后续章节全部基于它编写，接口稳定。
    """

    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: dict[str, Any] = field(default_factory=dict)
    finish_reason: str = "stop"  # stop / tool_calls / length / ...

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)


class StructuredOutputError(Exception):
    """模型输出不符合 Pydantic schema 时抛出（教学用：捕获后把错误回传模型重试）。

    属性：
        errors: Pydantic ValidationError.errors() 列表（每个错误含 loc/msg/type）；
        raw_text: 未能通过校验的原始文本；
        hint: 面向教学的修复提示。
    """

    def __init__(self, message: str, errors: list[dict[str, Any]] | None = None,
                 raw_text: str = "") -> None:
        super().__init__(message)
        self.errors = errors or []
        self.raw_text = raw_text
        self.hint = ("常见做法：校验失败→重试——捕获本异常，把 errors 拼进一条 user 消息"
                     "再请求一次（ch26 演示完整回退循环）。")


# ---------------------------------------------------------------------------
# token 计数（tiktoken 优先 / 近似回退，方式透明记录）
# ---------------------------------------------------------------------------

_ENCODING_CACHE: dict[str, Any] = {}


def _get_encoding(name: str = "cl100k_base") -> Any:
    """惰性加载 tiktoken 编码器（首次使用需联网下载 BPE 词表，之后读磁盘缓存）。"""
    if name not in _ENCODING_CACHE:
        import tiktoken  # 延迟导入：不用计数功能就不触发下载

        _ENCODING_CACHE[name] = tiktoken.get_encoding(name)
    return _ENCODING_CACHE[name]


def count_tokens(text: str) -> tuple[int, str]:
    """返回 (token 数, 计数方式)。

    计数方式取值：
        "tiktoken:cl100k_base" —— 精确（需联网下载词表一次，之后离线）；
        "approx:chars//4"      —— 近似回退（无网络/词表下载失败时），
                                  对英文约 4 字符≈1 token；对中文明显低估，
                                  只用于 Mock 演示，生产不可用。
    """
    try:
        return len(_get_encoding().encode(text)), "tiktoken:cl100k_base"
    except Exception:
        return max(1, len(text) // 4), "approx:chars//4"


def _build_usage(messages: list[dict[str, Any]], completion_text: str) -> dict[str, Any]:
    """Mock 的 usage：逐条消息累计 prompt，加 completion；计数方式透明写出。"""
    prompt = 0
    methods: set[str] = set()
    for m in messages:
        n, method = count_tokens(str(m.get("content") or ""))
        prompt += n
        methods.add(method)
    comp, comp_method = count_tokens(completion_text)
    methods.add(comp_method)
    method = "tiktoken:cl100k_base" if methods == {"tiktoken:cl100k_base"} else "+".join(sorted(methods))
    return {
        "prompt_tokens": prompt,
        "completion_tokens": comp,
        "total_tokens": prompt + comp,
        "count_method": method,
    }


# ---------------------------------------------------------------------------
# MockLLM：确定性规则模型（离线，可复现）
# ---------------------------------------------------------------------------

_USE_TOOL_RE = re.compile(r"USE_TOOL:\s*([A-Za-z_]\w*)((?:\s+[A-Za-z_]\w*=\S+)*)")
_KV_RE = re.compile(r"([A-Za-z_]\w*)=(\S+)")


def _parse_value(raw: str) -> Any:
    """key=value 的 value 尽量转成原生类型：数字/布尔/带引号字符串→字面量；其余保留字符串。"""
    try:
        return ast.literal_eval(raw)
    except (ValueError, SyntaxError):
        return raw


def _extract_key_values(text: str) -> dict[str, Any]:
    """从文本中解析所有 key=value 片段（空格分隔）。供规则触发与结构化填充共用。"""
    return {k: _parse_value(v) for k, v in _KV_RE.findall(text)}


def _coerce_script_item(item: ChatResult | dict[str, Any]) -> ChatResult:
    """script 条目兼容 ChatResult 与简写 dict（content / tool_calls / finish_reason）。"""
    if isinstance(item, ChatResult):
        return item
    if isinstance(item, dict):
        raw_calls = item.get("tool_calls") or []
        tool_calls = [
            ToolCall(
                id=tc.get("id") or f"call_{i + 1:03d}",
                name=tc["name"],
                arguments=tc.get("arguments") or {},
            )
            for i, tc in enumerate(raw_calls)
        ]
        return ChatResult(
            content=item.get("content", ""),
            tool_calls=tool_calls,
            usage=item.get("usage") or {},
            finish_reason=item.get("finish_reason", "tool_calls" if tool_calls else "stop"),
        )
    raise TypeError(f"script 条目必须是 ChatResult 或 dict，得到 {type(item).__name__}")


class MockLLM:
    """确定性规则模型：完全离线、同输入同输出，用于演示控制流与接口契约。

    决策顺序（每次 chat()）：
        1. 若构造时给了 script，按调用次数依次返回（耗尽时抛 RuntimeError，绝不硬编）；
        2. 若最后一条 user 消息含 "USE_TOOL:名字 key=value ..."，解析出工具调用请求；
        3. 否则按 system 关键词风格返回普通回复（无 system 时用默认模板）。
    """

    def __init__(self, script: list[ChatResult | dict[str, Any]] | None = None) -> None:
        self._script: list[ChatResult] = [_coerce_script_item(x) for x in (script or [])]
        self._cursor = 0
        self._call_seq = 0
        self.calls: list[list[dict[str, Any]]] = []  # 每次 chat 收到的 messages 快照，供测试断言

    # -- 核心决策 -----------------------------------------------------------

    def _respond(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None) -> ChatResult:
        self.calls.append([dict(m) for m in messages])
        self._call_seq += 1

        # 1) 脚本模式
        if self._script:
            if self._cursor >= len(self._script):
                raise RuntimeError(
                    f"MockLLM 的 script 已耗尽（共 {len(self._script)} 条，已消费 {self._cursor} 条）。"
                    "请在构造时追加条目，或去掉 script 使用规则模式。"
                )
            item = self._script[self._cursor]
            self._cursor += 1
            if not item.usage:
                item.usage = _build_usage(messages, item.content)
            return item

        last_user = next(
            (str(m["content"]) for m in reversed(messages) if m.get("role") == "user"), ""
        )

        # 2) 工具结果回传轮（最后一条是 tool 消息）：整合结果作答，不再触发新调用
        if messages and messages[-1].get("role") == "tool":
            tool_text = str(messages[-1].get("content") or "")
            reply = f"（Mock·整合工具结果）根据查询返回：{tool_text[:60]}。以上为确定性整合回答。"
            return ChatResult(content=reply, usage=_build_usage(messages, reply),
                              finish_reason="stop")

        # 3) 规则触发工具调用：USE_TOOL:名字 key=value（仅当最后一条是 user 消息）
        m = _USE_TOOL_RE.search(last_user) if (messages and messages[-1].get("role") == "user") else None
        if m:
            name, argtext = m.group(1), m.group(2)
            args = _extract_key_values(argtext)
            tc = ToolCall(id=f"call_{self._call_seq:03d}", name=name, arguments=args)
            return ChatResult(
                content="",
                tool_calls=[tc],
                usage=_build_usage(messages, ""),
                finish_reason="tool_calls",
            )

        # 4) 按 system 关键词选择风格（确定性）
        system_text = " ".join(
            str(m.get("content") or "") for m in messages if m.get("role") == "system"
        )
        reply = self._styled_reply(system_text, last_user)
        return ChatResult(content=reply, usage=_build_usage(messages, reply), finish_reason="stop")

    def _styled_reply(self, system_text: str, last_user: str) -> str:
        short = (last_user or "（无用户输入）")[:40]
        if "海盗" in system_text:
            return f"（Mock·海盗风）啊哈！关于「{short}」，扬帆，启航！"
        if "客服" in system_text:
            return f"（Mock·客服）您好，已收到您的问题「{short}」，工号 007 为您服务。"
        return f"（Mock 默认回复）已收到问题「{short}」。沙箱未接入真实模型，本回答由确定性规则生成。"

    # -- 公开接口（与 RealLLM 同签名）----------------------------------------

    def chat(self, messages: list[dict[str, Any]], *, tools: list[dict[str, Any]] | None = None,
             **_kwargs: Any) -> ChatResult:
        """返回一次"模型回答"。tools 仅记录接口形态，Mock 不做工具选择决策。

        注意：**_kwargs 接受 temperature/top_p/max_tokens 等参数但全部忽略——
        Mock 没有随机性，这正是演示"temperature 无效 ⇒ 输出确定"的实验基础（ch21/ch23）。
        """
        return self._respond(messages, tools)

    def chat_stream(self, messages: list[dict[str, Any]], *, tools: list[dict[str, Any]] | None = None,
                    **_kwargs: Any) -> Iterator[str]:
        """增量文本生成器：把 _respond 的内容切成小片段逐段 yield。

        切分方式优先用 tiktoken 真实 token（每个 token 一段，教学"chunk≈token"），
        词表不可用时按 4 字符切片回退。脚本模式下同样生效（流式输出脚本内容）。

        实现要点（也是真实流式处理的经典坑）：一个 UTF-8 中文字符可能被 BPE 词表
        拆成跨 token 的多字节序列，**逐 token 独立 decode 会产生乱码（U+FFFD）**，
        必须用增量解码器缓冲不完整字节，凑齐再吐字——ch23 正文展开。
        """
        result = self._respond(messages, tools)
        text = result.content
        try:
            import codecs

            enc = _get_encoding()
            decoder = codecs.getincrementaldecoder("utf-8")()
            for tid in enc.encode(text):
                piece = decoder.decode(enc.decode_bytes([tid]))
                if piece:
                    yield piece
            tail = decoder.decode(b"", final=True)
            if tail:
                yield tail
        except Exception:
            for i in range(0, len(text), 4):
                yield text[i:i + 4]

    def chat_structured(self, messages: list[dict[str, Any]],
                        schema: type[BaseModel]) -> BaseModel:
        """结构化输出：从最后一条 user 消息解析 key=value 填充 schema 字段。

        - 解析到的键做 Pydantic 校验（复用 v2 宽松转换："3"→int）；
        - 未提到的字段用 schema 字段默认值；无默认值且未提到 → StructuredOutputError；
        - 类型校验失败（如 age=abc）→ 同样包装成 StructuredOutputError。
        """
        last_user = next(
            (str(m["content"]) for m in reversed(messages) if m.get("role") == "user"), ""
        )
        parsed = _extract_key_values(last_user)
        kwargs: dict[str, Any] = {}
        for name, f in schema.model_fields.items():
            if name in parsed:
                kwargs[name] = parsed[name]
            elif not f.is_required():
                kwargs[name] = f.get_default(call_default_factory=True)
            # 必填且未解析到 → 留空交给校验报错（教学：看 errors 学修 prompt）
        try:
            return schema.model_validate(kwargs)
        except ValidationError as e:
            raise StructuredOutputError(
                f"Mock 输出无法通过 schema {schema.__name__} 校验：{e.error_count()} 个错误",
                errors=e.errors(),
                raw_text=last_user,
            ) from e


# ---------------------------------------------------------------------------
# RealLLM：openai 3.35.1 真实调用（缺 Key 报中文指引）
# ---------------------------------------------------------------------------


class RealLLM:
    """openai SDK 真实客户端。构造参数与签名已用 inspect 于 2026-10-19 核实（3.35.1）。

    - 鉴权：OPENAI_API_KEY；兼容 OpenAI 接口的服务再设 OPENAI_BASE_URL（一般为 /v1 结尾，
      具体以厂商文档为准——兼容≠功能一致，见 ch24 支持边界清单）；
    - SDK 内建重试：max_retries 默认 2（已核实），只自动重试连接错误/408/429/5xx；
    - 流式：create(stream=True) 返回增量事件迭代器，本类把 delta.content 摘成纯文本流。
    """

    def __init__(self, model: str = "gpt-4o-mini", base_url: str | None = None,
                 api_key: str | None = None, timeout: float = 60.0,
                 max_retries: int = 2, http_client: Any = None) -> None:
        """http_client：可选 httpx.Client（openai SDK 官方签名含此参数，已核实）。

        测试注入用：传入 httpx.MockTransport 的客户端即可在 httpx 层拦截 SDK 请求，
        无需真实网络——这是沙箱无 Key 时验证 RealLLM 转换路径的诚实手段（见 test_common_llm）。
        """
        api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "real 模式需要 OPENAI_API_KEY，但环境变量未设置。三种解决方式：\n"
                "  1) export OPENAI_API_KEY=sk-... 后重试；\n"
                "  2) 使用兼容 OpenAI 接口的服务：再设置 OPENAI_BASE_URL=https://<厂商域名>/v1"
                "（路径以厂商文档为准）；\n"
                "  3) 没有Key就保持 LLM_MODE=mock（默认，离线可跑全部教学示例）。"
            )
        from openai import OpenAI  # 延迟导入：mock 用户无需安装 openai 也能跑

        self.model = model
        client_kwargs: dict[str, Any] = {
            "api_key": api_key,
            "base_url": base_url or os.environ.get("OPENAI_BASE_URL") or None,
            "timeout": timeout,
            "max_retries": max_retries,
        }
        if http_client is not None:
            client_kwargs["http_client"] = http_client
        self._client = OpenAI(**client_kwargs)

    def chat(self, messages: list[dict[str, Any]], *, tools: list[dict[str, Any]] | None = None,
             **kwargs: Any) -> ChatResult:
        """非流式对话。构建工具/max_tokens/temperature 等参数直接透传 SDK（签名已核实存在）。"""
        payload: dict[str, Any] = {"model": self.model, "messages": messages, **kwargs}
        if tools:
            payload["tools"] = tools
        resp = self._client.chat.completions.create(**payload)
        choice = resp.choices[0]
        msg = choice.message
        tool_calls = [
            ToolCall(id=tc.id, name=tc.function.name,
                     arguments=json.loads(tc.function.arguments or "{}"))
            for tc in (msg.tool_calls or [])
        ]
        usage: dict[str, Any] = {}
        if resp.usage is not None:
            usage = {
                "prompt_tokens": getattr(resp.usage, "prompt_tokens", 0),
                "completion_tokens": getattr(resp.usage, "completion_tokens", 0),
                "total_tokens": getattr(resp.usage, "total_tokens", 0),
                "count_method": "server_reported",
            }
        return ChatResult(
            content=msg.content or "",
            tool_calls=tool_calls,
            usage=usage,
            finish_reason=choice.finish_reason or "",
        )

    def chat_stream(self, messages: list[dict[str, Any]], *, tools: list[dict[str, Any]] | None = None,
                    **kwargs: Any) -> Iterator[str]:
        """流式对话：yield 增量文本（delta.content），拼起来等于完整回答。"""
        payload: dict[str, Any] = {"model": self.model, "messages": messages,
                                   "stream": True, **kwargs}
        if tools:
            payload["tools"] = tools
        stream = self._client.chat.completions.create(**payload)
        for chunk in stream:  # type: ignore[union-attr]
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content

    def chat_structured(self, messages: list[dict[str, Any]],
                        schema: type[BaseModel]) -> BaseModel:
        """结构化输出：3.35.1 的 client.chat.completions.parse（已核实存在，无 stream 参数）。

        服务端按 schema 的 JSON Schema 约束生成并反序列化为 Pydantic 实例；
        注意部分兼容服务不支持 response_format，需自行回退到提示词约束（ch24 清单）。
        """
        completion = self._client.chat.completions.parse(
            model=self.model, messages=messages, response_format=schema
        )
        parsed = completion.choices[0].message.parsed
        if parsed is None:
            refusal = completion.choices[0].message.refusal
            raise StructuredOutputError(
                f"模型未返回可解析的结构化结果（refusal={refusal!r}）",
                raw_text=completion.choices[0].message.content or "",
            )
        return parsed


# ---------------------------------------------------------------------------
# 工厂函数
# ---------------------------------------------------------------------------


def get_llm(script: list[ChatResult | dict[str, Any]] | None = None) -> MockLLM | RealLLM:
    """按 LLM_MODE 返回客户端实例：mock（默认）/ real。

    - real 缺 OPENAI_API_KEY 会抛带中文指引的 RuntimeError（测试与示例都依赖该行为）；
    - get_llm() 每次返回新实例，无全局状态（脚本模式需要每次新实例，避免污染）。
    """
    mode = os.environ.get("LLM_MODE", "mock").strip().lower()
    if mode == "mock":
        return MockLLM(script=script)
    if mode == "real":
        return RealLLM()
    raise ValueError(f"LLM_MODE 只能是 mock 或 real，当前为 {mode!r}")


def chat_structured(messages: list[dict[str, Any]], schema: type[BaseModel],
                    script: list[ChatResult | dict[str, Any]] | None = None) -> BaseModel:
    """模块级便捷函数：get_llm().chat_structured 的快捷方式（教学示例少写一行）。"""
    return get_llm(script=script).chat_structured(messages, schema)
