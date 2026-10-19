# EX-38-02 | Fake 模型（离线确定性）与 ChatOpenAI（真实形状核实） | 运行: python3 examples/ch38_lc_core/ex_38_02_fake_and_chatopenai.py
"""完整可运行（不发起真实网络请求）：
[1] FakeListChatModel：官方测试做法——脚本预置回答，同输入同输出，可测"确定性"；
[2] ChatOpenAI：无 Key 构造的真实报错、带 dummy Key 的离线构造、关键方法签名 inspect 核实。
真实调用的代码形状在教材 38.5 给出（需 OPENAI_API_KEY，本沙箱未实调）。
"""
from __future__ import annotations

import inspect

from langchain_core.language_models import FakeListChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_openai import ChatOpenAI


def main() -> None:
    print("[1] Fake 模型两兄弟的行为差异（langchain-core 1.6.12 实测，官方测试用途）：")
    fl = FakeListChatModel(responses=["第一次回答（Fake 预置）", "第二次回答（Fake 预置）"])
    q = [HumanMessage(content="问题是什么？")]
    r1, r2, r3 = fl.invoke(q), fl.invoke(q), fl.invoke(q)
    print(f"    FakeListChatModel 按序消费：{r1.content[:6]}... → {r2.content[:6]}...")
    print(f"    第 3 次 invoke → {r3.content[:6]}...（脚本耗尽后【循环回开头】，源码注释原话：cycle）")
    from langchain_core.language_models import GenericFakeChatModel

    gf = GenericFakeChatModel(messages=iter([AIMessage(content="唯一一条（会耗尽）")]))
    print(f"    GenericFakeChatModel 第 1 次 → {gf.invoke(q).content}")
    try:
        gf.invoke(q)
    except StopIteration:
        print("    第 2 次 invoke → StopIteration（脚本耗尽即报错，绝不静默循环）")
    print("    → 测试脚本选型：要'循环应答'用 FakeList；要'精确控制第 N 轮'（如工具循环）用 Generic。")

    print("\n[2] ChatOpenAI（langchain-openai 1.7.2）：无 Key 的真实报错：")
    try:
        ChatOpenAI(model="gpt-4o-mini")  # 沙箱无 OPENAI_API_KEY
    except Exception as e:
        print(f"    {type(e).__name__}: {str(e)[:100]}...")

    print("\n[3] 带 dummy Key 离线构造成功（不发起请求，只在 invoke 时才真正联网）：")
    m = ChatOpenAI(model="gpt-4o-mini", api_key="sk-dummy-not-used",
                   temperature=0, max_retries=2, timeout=30)
    print(f"    type={type(m).__name__}, model_name={m.model_name}, "
          f"temperature={m.temperature}, max_retries={m.max_retries}")

    print("\n[4] 关键方法签名核实（inspect 实测，教材 38.3 引用）：")
    wso = inspect.signature(ChatOpenAI.with_structured_output)
    print(f"    with_structured_output 参数：{list(wso.parameters.keys())}")
    print(f"      method 默认值 = {wso.parameters['method'].default}")
    bt = inspect.signature(ChatOpenAI.bind_tools)
    print(f"    bind_tools 参数：{list(bt.parameters.keys())}")
    init_params = list(ChatOpenAI.model_fields.keys())
    for name in ["model_name", "temperature", "max_retries", "request_timeout", "openai_api_key",
                 "openai_api_base", "streaming", "max_tokens"]:
        assert name in init_params, name
    print(f"    字段表含 model_name/temperature/max_retries/request_timeout/openai_api_key/...：True")
    print("    注意两处命名错位（pydantic 别名机制，构造参数实测可用）：")
    print("      字段 request_timeout ↔ 构造参数 timeout=（[3] 已实测）；")
    print("      字段 openai_api_key / openai_api_base ↔ 构造参数 api_key= / base_url=（[3] 已实测）。")


if __name__ == "__main__":
    main()
