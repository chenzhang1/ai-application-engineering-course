# EX-09-04 | 模拟 LLM 流式输出：用生成器逐 token 返回
# 运行：python3 examples/ch09_iterators/ex_09_04_llm_stream.py
"""完整可运行：MODE=mock 离线演示（不联网，无 Key 要求）。
原理与真实 LLM API 的流式返回一致：服务端每生成一小段（chunk/token）就推给客户端，
客户端用 for 循环增量消费——这正是 ch23「流式 chunk 拼接」与 ch17「SSE」的底层形态。
"""
from __future__ import annotations

import os
import time
from collections.abc import Iterator

# 预先"生成好"的回答（模拟：真实场景中这些 token 是模型逐个算出来的）
MOCK_TOKENS: list[str] = [
    "迭代器", "是", "Python", "中", "实现", "惰性", "求值", "的", "基石", "。",
    "LLM", "流式", "输出", "正是", "它的", "最佳", "实战", "场景", "。", "EOF",
]


def stream_tokens(mode: str | None = None, delay: float = 0.0) -> Iterator[str]:
    """模拟流式 API：每被要一次，才吐出一个 token（生成器天然支持暂停/恢复）。"""
    mode = mode or os.environ.get("LLM_MODE", "mock")
    if mode != "mock":
        raise RuntimeError("本示例只实现了 mock 模式；真实 API 流式调用见第四部分 ch23/ch24")
    for token in MOCK_TOKENS:
        if delay > 0:
            time.sleep(delay)  # 模拟网络/模型出字延迟
        yield token


def main() -> None:
    print("[1] 逐 token 消费（用户看到打字机效果）:")
    collected: list[str] = []
    start = time.perf_counter()
    for token in stream_tokens():
        collected.append(token)
        print(token, end="", flush=True)  # flush 立即刷出，模拟边生成边显示
    elapsed_ms = (time.perf_counter() - start) * 1000
    print(f"\n    共 {len(collected)} 个 token，消费耗时 {elapsed_ms:.2f} ms")

    print("[2] 首字延迟对比（惰性的价值）:")
    # 全量模式：等全部内容生成完才返回第一个字
    def full_response() -> str:
        time.sleep(0.1)  # 模拟整段生成耗时
        return "".join(MOCK_TOKENS)

    t0 = time.perf_counter()
    _ = full_response()
    full_ms = (time.perf_counter() - t0) * 1000
    t0 = time.perf_counter()
    first = next(stream_tokens())
    stream_first_ms = (time.perf_counter() - t0) * 1000
    print(f"    全量模式拿到第一个字: {full_ms:.2f} ms")
    print(f"    流式模式拿到第一个字: {stream_first_ms:.4f} ms（token={first!r}）")

    print("[3] 中途停止消费（生成器被抛弃，后面的 token 根本不会生成）:")
    for token in stream_tokens():
        print(token, end=" ")
        if token == "求值":
            print("… 用户点了“停止生成”，循环 break")
            break


if __name__ == "__main__":
    main()
