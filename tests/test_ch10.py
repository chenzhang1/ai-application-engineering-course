# ch10 装饰器：正常 / 边界 / 非法输入
import sys
from pathlib import Path

CH10 = Path(__file__).resolve().parent.parent / "examples" / "ch10_decorators"
sys.path.insert(0, str(CH10))

import pytest

import ex_10_02_timer_decorator as m02
import ex_10_03_retry_decorator as m03
import ex_10_04_call_log as m04
import ex_10_05_class_decorator as m05


def test_wraps_preserves_metadata() -> None:
    """functools.wraps 的价值：名字/文档不丢；不写 wraps 的装饰器会顶替身份。"""
    assert m02.fetch_order.__name__ == "fetch_order"
    assert m02.fetch_order.__doc__ is not None and "wraps" in m02.fetch_order.__doc__
    assert m02.fetch_order_naive.__name__ == "wrapper"   # 反例仍在，供对照
    assert m02.fetch_order.__wrapped__.__name__ == "fetch_order"


def test_retry_recovers_after_transient_failures() -> None:
    """正常路径：前 N-1 次失败仍能拿到结果。"""
    m03.flaky_fetch.calls = 0
    result = m03.flaky_fetch("https://api.example.com/orders", fail_times=2)
    assert result == "200 OK from https://api.example.com/orders"
    assert m03.flaky_fetch.calls == 2


def test_retry_raises_after_exhaustion() -> None:
    """边界：次数用尽，最后一次的异常原样上抛。"""
    with pytest.raises(TimeoutError, match="503"):
        m03.always_fails()


def test_retry_rejects_invalid_config_at_decoration_time() -> None:
    """非法输入：参数校验在装饰时立刻失败，而不是运行时。"""
    with pytest.raises(ValueError, match="times"):
        @m03.retry(times=0)
        def _bad() -> None: ...


def test_call_log_idempotency_hook() -> None:
    """调用日志 + 幂等键：同键第二次返回 duplicated，不重复执行副作用。"""
    r1 = m04.submit_refund("SO-TEST", 1.0, idem_key="idem-test-001")
    r2 = m04.submit_refund("SO-TEST", 1.0, idem_key="idem-test-001")
    assert r1 == "refunded:SO-TEST:1.00"
    assert r2 == "duplicated:idem-test-001"


def test_class_decorator_state_and_registry() -> None:
    """类装饰器跨调用计数；注册表装饰器登记并可按名调用。"""
    calls_before = m05.ping.calls
    m05.ping("svc-x")
    assert m05.ping.calls == calls_before + 1
    assert m05.ping("svc-y") == "pong svc-y"

    assert set(m05.TOOL_REGISTRY) == {"query_weather", "query_order"}
    assert m05.TOOL_REGISTRY["query_order"]("SO-9") == "订单 SO-9：已发货"
