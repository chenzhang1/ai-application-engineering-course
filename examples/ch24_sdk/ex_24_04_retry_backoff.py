# EX-24-04 | 重试与 429/超时语义：自写指数退避包装（Mock 上真实跑）| 运行: python3 examples/ch24_sdk/ex_24_04_retry_backoff.py
"""完整可运行（Mock）：一个"前 2 次抛异常、第 3 次成功"的不稳定 LLM 桩，
用指数退避+抖动包装重试，打印每次尝试；对照 SDK 内建 max_retries（已核实默认 2）。
"""
from __future__ import annotations

import random
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from examples.common.llm_client import ChatResult, MockLLM  # noqa: E402

MESSAGES: list[dict[str, Any]] = [{"role": "user", "content": "重试语义演示"}]


class FlakyLLM:
    """不稳定 LLM 桩：模拟 429（限流）两次，之后恢复。"""

    def __init__(self, fail_times: int = 2) -> None:
        self.fail_times = fail_times
        self.attempts = 0

    def chat(self, messages: list[dict[str, Any]]) -> ChatResult:
        self.attempts += 1
        if self.attempts <= self.fail_times:
            # 真实 SDK 抛 openai.RateLimitError(429)，这里用自定义异常模拟
            raise TimeoutError(f"[模拟 429] 第 {self.attempts} 次请求被限流（Retry-After: 1s）")
        inner = MockLLM(script=[{"content": "重试成功后的正常回答。"}])
        return inner.chat(messages)


def chat_with_retry(llm: FlakyLLM, messages: list[dict[str, Any]],
                    max_attempts: int = 4, base_delay: float = 0.1) -> ChatResult:
    """指数退避 + 抖动（ch15 的重试模板用在 LLM 上；幂等前提：只读对话可安全重发）。"""
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return llm.chat(messages)
        except TimeoutError as e:
            last_exc = e
            if attempt == max_attempts:
                break
            delay = base_delay * (2 ** (attempt - 1)) + random.uniform(0, 0.05)
            print(f"    attempt {attempt} 失败：{e}")
            print(f"    退避 {delay:.2f}s 后重试…")
            time.sleep(delay)
    raise RuntimeError(f"重试 {max_attempts} 次仍失败") from last_exc


def main() -> None:
    print("[1] 自写重试包装（指数退避，Mock 上真实执行）：")
    result = chat_with_retry(FlakyLLM(fail_times=2), MESSAGES)
    print(f"    最终成功：{result.content}")

    print("\n[2] SDK 内建重试对照（openai 3.35.1，inspect 核实）：")
    from openai import OpenAI

    c = OpenAI(api_key="sk-dummy-not-used")
    print(f"    默认 max_retries = {c.max_retries}（只自动重试连接错误/408/429/部分 5xx）")
    print("    429 语义：服务端要求减速，响应可能带 Retry-After 头——尊重它，别自作聪明加大频率；")
    print("    读超时语义：请求可能已被服务端受理，重发前先想幂等（对话类安全，下单类必须幂等键）。")

    print("\n[3] 什么时候关掉内建重试自己写？")
    print("    需要区分错误类型(429 vs 500 vs 401)、接入熔断/降级、或对延迟敏感时——")
    print("    用 max_retries=0 关内建，再用本示例的包装（第十部分 59 章展开）。")


if __name__ == "__main__":
    main()
