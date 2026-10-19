# EX-59-01 | LLM 重试的两笔账：重复计费与幂等 | 运行: python3 examples/ch59_stability/ex_59_01_retry_double_billing.py
"""完整可运行（纯标准库，离线）：为什么 LLM 的"读超时"不能无脑自动重试。

关键时序（读超时的本质）：客户端没等到响应 ≠ 服务端没干活。
服务端往往已经完整生成并计费，只是响应没能按时送回。此时原样重发：
  策略 A（朴素重试）：再生成一次、再计费一次 → 账单 ×3，多个结果里只用到一份；
  策略 B（幂等键重试）：服务端按 Idempotency-Key 记账 → 重发命中账本，
        返回既有结果、不再生成不再计费。
边界：策略 B 要求服务端支持幂等键（OpenAI 官方接口无此参数——需网关层实现，
以厂商文档为准）；不支持时，读超时的正确处置是"不自动重试，转降级/人工"，见 59.4 的处置决策表（参数表在 59.5.1）。
"""
from __future__ import annotations

from dataclasses import dataclass, field


class ReadTimeout(Exception):
    """客户端等待响应超时（连接早已建立——这正是问题所在）。"""


@dataclass
class FakeLLMBackend:
    """模拟 LLM 服务端：每次"真实生成"都计费；幂等账本记录已生成的结果。

    idempotency_ledger：key → 生成结果。超时场景下结果也会入账
    （生成已完成，只是响应没送到）——重发时命中账本直接取回。
    """

    fail_with_timeout_times: int = 0
    prompt_tokens: int = 500
    completion_tokens: int = 300
    idempotency_ledger: dict[str, str] = field(default_factory=dict)
    billed_calls: int = 0          # 真实执行生成并计费的次数（账单看这里）
    total_calls: int = 0           # 收到的请求总数（监控看这里）

    def chat(self, prompt: str, idempotency_key: str | None = None) -> str:
        self.total_calls += 1
        # 幂等命中：不生成、不计费，直接返回既有结果（重试从"再花一次钱"变"再取一次货"）
        if idempotency_key is not None and idempotency_key in self.idempotency_ledger:
            return self.idempotency_ledger[idempotency_key]
        if self.billed_calls < self.fail_with_timeout_times:
            # 服务端完整生成并计费（钱已花），但响应没能按时送回 → 客户端视角"读超时"
            self.billed_calls += 1
            if idempotency_key is not None:
                self.idempotency_ledger[idempotency_key] = f"答案[{self.billed_calls}]：{prompt}"
            raise ReadTimeout(f"客户端读超时（服务端其实已完成第 {self.billed_calls} 次生成并计费）")
        self.billed_calls += 1
        answer = f"答案[{self.billed_calls}]：{prompt}"
        if idempotency_key is not None:
            self.idempotency_ledger[idempotency_key] = answer
        return answer


def attempt(backend: FakeLLMBackend, prompt: str, key: str | None) -> str | None:
    try:
        return backend.chat(prompt, idempotency_key=key)
    except ReadTimeout:
        return None


def main() -> None:
    prompt = "解释一下什么是缓存击穿"

    print("── 策略 A：朴素重试（读超时 → 原样重发，共试 3 次）──")
    a = FakeLLMBackend(fail_with_timeout_times=2)
    answers_a = [attempt(a, prompt, None) for _ in range(3)]
    print(f"    收到的请求：{a.total_calls} 次；服务端真实生成并计费：{a.billed_calls} 次")
    print(f"    客户端拿到的答案：{answers_a}")
    print(f"    账单视角：{a.billed_calls} × ({a.prompt_tokens}+{a.completion_tokens}) tokens，"
          f"其中只有 {sum(1 for x in answers_a if x)} 份结果被用到——其余是白烧的钱。")

    print("\n── 策略 B：幂等键重试（同一 Idempotency-Key 重发 3 次）──")
    b = FakeLLMBackend(fail_with_timeout_times=2)
    answers_b = [attempt(b, prompt, key="spring-req-88") for _ in range(3)]
    print(f"    收到的请求：{b.total_calls} 次（含重发）；服务端真实生成并计费：{b.billed_calls} 次")
    print(f"    客户端拿到的答案：{answers_b}（重发命中账本，三次同一个结果）")
    print(f"    账单视角：只计费 1 次——同样的故障，代价差 3 倍。")

    print("\n── 处置决策表（读超时怎么办）──")
    print("  有幂等键且服务端支持   → 放心重试（策略 B）")
    print("  无幂等能力，请求只读   → 默认不自动重试：转降级（缓存/小模型/拒答）或人工重试")
    print("  无幂等能力，有副作用   → 绝不自动重试：先查副作用是否已发生（工具调用/写操作）")
    print("  429/连接失败（请求没到）→ 可以自动重试（还没花钱），退避+抖动，见 59.5.1 参数表")


if __name__ == "__main__":
    main()
