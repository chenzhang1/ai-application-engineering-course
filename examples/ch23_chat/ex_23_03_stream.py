# EX-23-03 | 流式 chunk 拼接 + UTF-8 增量解码 | 运行: python3 examples/ch23_chat/ex_23_03_stream.py
"""完整可运行（Mock，不联网）：用 llm_client.chat_stream 演示流式输出的三个要点：
1) chunk 是增量文本，拼接 == 非流式整体；2) 打字机效果与"首字延迟"；
3) 经典坑：多字节字符跨 chunk 时，逐 chunk 独立 decode 会出乱码（U+FFFD）。
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from examples.common.llm_client import MockLLM  # noqa: E402


def main() -> None:
    llm = MockLLM()
    messages = [{"role": "user", "content": "为什么直播要打字机效果？"}]

    print("[1] 逐 chunk 消费（打字机效果）：")
    start = time.perf_counter()
    parts: list[str] = []
    for chunk in llm.chat_stream(messages):
        parts.append(chunk)
        print(chunk, end="", flush=True)
        time.sleep(0.01)  # 模拟网络间隔
    elapsed = (time.perf_counter() - start) * 1000
    print(f"\n    共 {len(parts)} 个 chunk，总耗时 {elapsed:.1f} ms")

    print("\n[2] 拼接 == 整体：")
    joined = "".join(parts)
    whole = llm.chat(messages).content
    print(f"    join(chunks) == chat().content → {joined == whole}")

    print("\n[3] 多字节边界坑（Mock 按 tiktoken 真实 token 切 chunk）：")
    raw_text = "流式输出的拼接结果必须与整体一致"  # 已验证：该句存在跨 token 的多字节字符
    token_ids = None
    try:
        from examples.common.llm_client import _get_encoding

        enc = _get_encoding()
        token_ids = enc.encode(raw_text)
    except Exception:
        enc = None
    if token_ids and enc is not None:
        # 故意按 token 边界把字节流切碎后逐块独立解码（错误示范）
        naive = "".join(enc.decode([t]) for t in token_ids)
        print(f"    原文：{raw_text!r}")
        print(f"    错误示范（逐 token decode）：{naive!r}  ← 出现 U+FFFD 乱码")
        print("    正确做法：字节层缓冲，用 codecs 增量解码器凑齐再吐字（llm_client 已内置）。")
    else:
        print("    （词表不可用，跳过真实 token 切分演示——回退路径下 chunk 是等宽切片，无此问题）")

    print("\n[4] 中途停止生成（断开即省 token）：")
    for i, chunk in enumerate(llm.chat_stream(messages)):
        print(chunk, end="")
        if i == 4:
            print("\n    … 用户点了『停止』，后面的 chunk 不再请求（真实 API 也按已生成长度计费）")
            break


if __name__ == "__main__":
    main()
