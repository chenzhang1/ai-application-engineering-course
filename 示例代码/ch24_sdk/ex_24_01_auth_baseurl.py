# EX-24-01 | openai SDK 鉴权/BaseURL 与关键签名核实 | 运行: python3 示例代码/ch24_sdk/ex_24_01_auth_baseurl.py
"""完整可运行：1) 演示缺 OPENAI_API_KEY 时 SDK/RealLLM 的真实报错；
2) 用 inspect 打印 openai==3.35.1 的关键签名（FACTS 红线：不确定的 API 必须核实后写）。
沙箱无 Key，本示例不发起任何真实网络请求。
"""
from __future__ import annotations

import inspect
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def main() -> None:
    print("[1] 缺 Key 的真实报错（捕获打印，非虚构）：")
    os.environ.pop("OPENAI_API_KEY", None)
    from 示例代码.公共.llm_client import RealLLM

    try:
        RealLLM()
    except RuntimeError as e:
        print("    RuntimeError:", str(e).replace("\n", "\n      "))

    print("\n[2] openai 3.35.1 关键签名核实（inspect 实测）：")
    import openai
    from openai import OpenAI
    from openai.resources.chat.completions import Completions
    from openai.resources.embeddings import Embeddings

    print(f"    openai.__version__ = {openai.__version__}")
    init_params = list(inspect.signature(OpenAI.__init__).parameters)
    print(f"    OpenAI.__init__ 含 api_key/base_url/timeout/max_retries/http_client："
          f"{all(p in init_params for p in ['api_key', 'base_url', 'timeout', 'max_retries', 'http_client'])}")

    client = OpenAI(api_key="sk-dummy-not-used", base_url="http://127.0.0.1:9/v1", max_retries=0)
    default_client = OpenAI(api_key="sk-dummy-not-used")
    print(f"    client.max_retries 默认值 = {default_client.max_retries}")
    print(f"    client.base_url 可注入   = {client.base_url!r}（兼容接口服务改这里）")
    print(f"    有 with_options() 方法   = {hasattr(client, 'with_options')}（可临时覆盖 max_retries 等默认值）")

    create_params = list(inspect.signature(Completions.create).parameters)
    for name in ["messages", "model", "temperature", "top_p", "max_tokens",
                 "max_completion_tokens", "stream", "stream_options", "tools",
                 "tool_choice", "response_format", "parallel_tool_calls", "seed", "stop", "n"]:
        assert name in create_params, name
    print(f"    chat.completions.create 含 15 个常用参数（messages/model/temperature/...）＝ True")

    print(f"    chat.completions.parse 存在 = {hasattr(Completions, 'parse')}"
          f"（参数含 response_format；含 stream = {'stream' in inspect.signature(Completions.parse).parameters}）")
    emb_params = list(inspect.signature(Embeddings.create).parameters)
    print(f"    embeddings.create 前置参数 = {[p for p in emb_params if p != 'self'][:5]}")

    print("\n[3] BaseURL 兼容边界提醒（教材 24.2 展开）：")
    print("    OpenAI 兼容 ≠ 功能一致：response_format/工具调用/多模态/流式用法都可能被")
    print("    兼容服务裁剪。上线前按本示例输出清单逐项向厂商文档核实。")


if __name__ == "__main__":
    main()
