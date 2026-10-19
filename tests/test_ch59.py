# ch59 测试 | 重试重复计费、背压快速拒绝、语义缓存误命中、熔断器状态迁移
# 运行：cd /workspace/ai_application_course && python3 -m pytest tests/test_ch59.py -v
import asyncio

import pytest

from examples.ch59_stability.ex_59_01_retry_double_billing import (
    FakeLLMBackend,
    ReadTimeout,
    attempt,
)
from examples.ch59_stability.ex_59_02_backpressure import BackpressureGate, QueueFull
from examples.ch59_stability.ex_59_04_circuit_breaker import CircuitBreaker, State


def test_naive_retry_bills_every_attempt():
    """读超时 + 无幂等键：3 次尝试 = 3 次计费（重复计费真实存在）。"""
    b = FakeLLMBackend(fail_with_timeout_times=2)
    answers = [attempt(b, "q", None) for _ in range(3)]
    assert b.billed_calls == 3
    assert answers == [None, None, answers[2]] and answers[2] is not None


def test_idempotent_key_retry_bills_once():
    """读超时 + 幂等键：重发命中账本，只计费 1 次且结果一致。"""
    b = FakeLLMBackend(fail_with_timeout_times=2)
    answers = [attempt(b, "q", key="req-1") for _ in range(3)]
    assert b.billed_calls == 1
    assert answers[1] == answers[2] and answers[1] is not None


def test_no_retry_after_failure_still_billed_once():
    """只试 1 次也计费 1 次：钱花了没拿到结果——这就是'不自动重试'策略的成本边界。"""
    b = FakeLLMBackend(fail_with_timeout_times=1)
    with pytest.raises(ReadTimeout):
        b.chat("q")
    assert b.billed_calls == 1


def test_backpressure_gate_rejects_when_full():
    """背压：并发 3 + 队列 2，10 个并发请求 → 恰好 5 完成 / 5 快速拒绝。"""

    async def run() -> tuple[int, int, int]:
        gate = BackpressureGate(concurrency=3, queue_depth=2)
        results = await asyncio.gather(*(gate.run(i, 5) for i in range(10)),
                                       return_exceptions=True)
        done = sum(1 for r in results if isinstance(r, str))
        rejected = sum(1 for r in results if isinstance(r, QueueFull))
        return done, rejected, gate.stats["rejected"]

    done, rejected, rej_stat = asyncio.run(run())
    assert done == 5 and rejected == 5 and rej_stat == 5


def test_semantic_cache_mishit_at_loose_threshold():
    """语义缓存误命中：阈值 0.8 时'年假有几天'命中'病假有几天'的错误答案。"""
    import examples.ch59_stability.ex_59_03_semantic_cache_mishit as m

    m.cache.clear()
    m.cache["病假有几天"] = m.KB["病假有几天"]
    answer, source = m.semantic_lookup("年假有几天", 0.8)
    assert answer == m.KB["病假有几天"]            # 返回的是病假答案！
    assert source.startswith("cache")
    assert "病假" in answer


def test_semantic_cache_safe_at_strict_threshold():
    """阈值收紧到 0.9 后同一查询不命中 → 回源后答案正确（阈值是准确率/命中率旋钮）。"""
    import examples.ch59_stability.ex_59_03_semantic_cache_mishit as m

    m.cache.clear()
    m.cache["病假有几天"] = m.KB["病假有几天"]
    answer, source = m.semantic_lookup("年假有几天", 0.9)
    assert source == "miss" and answer == "miss"


def test_circuit_breaker_transitions():
    """熔断器：CLOSED→OPEN（失败率达阈值）→ 冷却后 HALF_OPEN → 探测成功 CLOSED。"""
    now = [0.0]
    b = CircuitBreaker(failure_threshold=0.5, window_size=4, cooldown_s=30.0,
                       time_fn=lambda: now[0])
    for ok in (True, False, False, False):        # 3/4 失败 ≥ 50%
        b.record(ok)
    assert b.state is State.OPEN
    ok, _ = b.allow()
    assert ok is False                            # OPEN 快速拒绝
    now[0] = 31.0                                 # 冷却结束
    ok, why = b.allow()
    assert ok and b.state is State.HALF_OPEN
    b.record(True)                                # 探测成功 → 闭合
    assert b.state is State.CLOSED


def test_circuit_breaker_reopens_on_failed_probe():
    """半开探测失败 → 重新 OPEN；且半开探测名额用完后继续拒绝。"""
    now = [0.0]
    b = CircuitBreaker(failure_threshold=0.5, window_size=4, cooldown_s=30.0,
                       half_open_probe_max=1, time_fn=lambda: now[0])
    for ok in (True, False, False, False):
        b.record(ok)
    now[0] = 31.0
    assert b.allow()[0] is True                   # 用掉唯一探测名额
    ok, _ = b.allow()
    assert ok is False                            # 名额用完 → 拒绝
    b.record(True)                                # 探测成功 → closed
    assert b.state is State.CLOSED
    for ok in (False, False, True, False):
        b.record(ok)
    assert b.state is State.OPEN                  # 再次达阈值 → 打开
    now[0] = 70.0
    assert b.allow()[0] is True                   # 半开放行探测
    b.record(False)                               # 探测失败 → 重新打开
    assert b.state is State.OPEN
