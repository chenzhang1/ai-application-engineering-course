# EX-59-04 | 最小熔断器：closed → open → half_open | 运行: python3 examples/ch59_stability/ex_59_04_circuit_breaker.py
"""完整可运行（纯标准库，离线）：实现并演示三态熔断器。

  CLOSED（正常放行，滚动窗口统计失败率）→ 失败率达阈值
  OPEN（快速拒绝，直接走降级，不碰故障下游）→ 冷却时间到
  HALF_OPEN（放少量探测请求）→ 探测成功闭合回 CLOSED / 失败重新打开

时间用注入的 time_fn（秒），保证演示与测试完全确定性（不真 sleep）。
Java 对照：Resilience4j CircuitBreaker 的 slidingWindowSize / failureRateThreshold /
waitDurationInOpenState / permittedNumberOfCallsInHalfOpenState——参数一一对应。
"""
from __future__ import annotations

import enum
from collections import deque
from dataclasses import dataclass, field
from typing import Callable


class State(enum.Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreaker:
    """最小三态熔断器（教学实现；生产可评估 Resilience4j 思想的自实现或现成库）。"""

    failure_threshold: float = 0.5        # 失败率阈值（窗口内失败/总数）
    window_size: int = 10                 # 滚动窗口：最近 N 次结果
    cooldown_s: float = 30.0              # OPEN 冷却时长
    half_open_probe_max: int = 2          # 半开态最多放行的探测请求数
    time_fn: Callable[[], float] = lambda: 0.0
    state: State = field(default=State.CLOSED, init=False)
    results: deque[bool] = field(default_factory=deque, init=False)   # True=成功
    opened_at: float = field(default=0.0, init=False)
    half_open_probes: int = field(default=0, init=False)

    def allow(self) -> tuple[bool, str]:
        """是否放行本次调用。OPEN 直接拒绝（调用方走降级），HALF_OPEN 只放探测名额。"""
        if self.state is State.OPEN:
            if self.time_fn() - self.opened_at >= self.cooldown_s:
                self.state = State.HALF_OPEN
                self.half_open_probes = 0
                self.results.clear()
            else:
                return False, f"open（冷却剩 {self.cooldown_s - (self.time_fn() - self.opened_at):.0f}s）"
        if self.state is State.HALF_OPEN:
            if self.half_open_probes >= self.half_open_probe_max:
                return False, "half_open（探测名额已用完，后续请求继续拒绝）"
            self.half_open_probes += 1
            return True, "half_open 探测"
        return True, "closed"

    def record(self, ok: bool) -> None:
        """记录一次调用结果，按状态迁移。"""
        if self.state is State.CLOSED:
            self.results.append(ok)
            while len(self.results) > self.window_size:
                self.results.popleft()
            if len(self.results) == self.window_size:
                rate = 1 - (sum(self.results) / len(self.results))
                if rate >= self.failure_threshold:
                    self.state = State.OPEN
                    self.opened_at = self.time_fn()
        elif self.state is State.HALF_OPEN:
            if ok:
                self.state = State.CLOSED       # 探测成功 → 闭合
                self.results.clear()
            else:
                self.state = State.OPEN         # 探测失败 → 重新打开，重新冷却
                self.opened_at = self.time_fn()


def main() -> None:
    now = [0.0]                                   # 可控时钟
    breaker = CircuitBreaker(time_fn=lambda: now[0])

    print("── 阶段 1：CLOSED —— 上游开始报错，窗口内失败率突破 50% ──")
    seq = [True, True, False, False, False, False, True, False, False, False]
    for i, ok in enumerate(seq, 1):
        breaker.record(ok)
        print(f"    调用{i}: {'成功' if ok else '失败'} → state={breaker.state.value}")
    print(f"    （最近 10 次失败 6 次 ≥ 50% → 打开）state={breaker.state.value}")

    print("\n── 阶段 2：OPEN —— 快速拒绝，调用方走降级，不再撞故障下游 ──")
    print(f"    allow() → {breaker.allow()}")

    print("\n── 阶段 3：冷却结束 → HALF_OPEN —— 只放探测名额 ──")
    now[0] = 31.0                                 # 时间前移 31s > cooldown 30s
    print(f"    第 1 次 allow() → {breaker.allow()}")
    print(f"    第 2 次 allow() → {breaker.allow()}")
    print(f"    第 3 次 allow() → {breaker.allow()}（名额用完，洪峰被挡在外面）")

    print("\n── 阶段 4：探测成功 → CLOSED 恢复 ──")
    breaker.record(True)
    print(f"    探测成功 → state={breaker.state.value}")
    print(f"    allow() → {breaker.allow()}")
    print("\n── 阶段 5（对照）：探测失败 → 重新 OPEN，再冷却一轮 ──")
    now[0] = 200.0
    b2 = CircuitBreaker(failure_threshold=0.5, window_size=4, time_fn=lambda: now[0])
    for ok in (True, False, False, False):        # 小窗口快速复现：失败率 3/4 ≥ 50%
        b2.record(ok)
    print(f"    连续故障 → state={b2.state.value}")
    now[0] = 240.0                                # 冷却结束
    print(f"    冷却结束，allow() → {b2.allow()}")
    b2.record(False)
    print(f"    探测失败 → state={b2.state.value}（重新打开，重新冷却——不给故障下游喘息前的压力）")

    print("\n[LLM 场景要点] 熔断的对象是'上游模型 API'或某个租户/功能维度；")
    print("  OPEN 期间降级链：语义/精确缓存 → 备用小模型 → 排队等待 → 503+Retry-After。")
    print("  参数是起点：窗口 10/阈值 50%/冷却 30s/探测 2 个——需按自身流量压测调整（59.5.1 表）。")


if __name__ == "__main__":
    main()
