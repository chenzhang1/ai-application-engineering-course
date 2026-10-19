# EX-10-04 | 调用日志装饰器：为后文的幂等/审计埋点
# 运行：python3 examples/ch10_decorators/ex_10_04_call_log.py
"""完整可运行：用 logging（工程规范，非 print）记录每次调用的入参与结果。
ch48「人工介入的副作用幂等性」与 ch54「工具治理：审计日志」直接复用这个模式。
"""
from __future__ import annotations

import functools
import logging
import time
import uuid
from collections.abc import Callable
from typing import Any

# 模块级 logger：命名用 __name__，配置只做一次（真实项目在入口统一配置）
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
logger = logging.getLogger(__name__)


def call_log(func: Callable[..., Any]) -> Callable[..., Any]:
    """记录：调用时间、函数名、参数、返回值/异常、耗时。"""
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        call_id = uuid.uuid4().hex[:8]  # trace_id 思想：一次调用一个唯一标识
        logger.info("[%s] -> %s args=%s kwargs=%s", call_id, func.__name__, args, kwargs)
        start = time.perf_counter()
        try:
            result = func(*args, **kwargs)
        except Exception:
            logger.exception("[%s] !! %s 失败，耗时 %.2f ms",
                             call_id, func.__name__, (time.perf_counter() - start) * 1000)
            raise  # 记录后原样抛出，绝不吞异常
        logger.info("[%s] <- %s 返回=%r 耗时 %.2f ms",
                    call_id, func.__name__, result, (time.perf_counter() - start) * 1000)
        return result
    return wrapper


_idempotency_keys: set[str] = set()


@call_log
def submit_refund(order_id: str, amount: float, idem_key: str | None = None) -> str:
    """模拟"退款"这类有副作用的操作：用幂等键防止重复执行。"""
    key = idem_key or f"{order_id}:{amount}"
    if key in _idempotency_keys:
        logger.info("幂等命中：%s 已处理过，直接返回，不重复退款", key)
        return f"duplicated:{key}"
    _idempotency_keys.add(key)
    return f"refunded:{order_id}:{amount:.2f}"


@call_log
def risky_divide(a: int, b: int) -> float:
    return a / b


def main() -> None:
    submit_refund("SO-1001", 199.0, idem_key="idem-001")
    submit_refund("SO-1001", 199.0, idem_key="idem-001")  # 同一幂等键：第二次不执行副作用
    try:
        risky_divide(10, 0)
    except ZeroDivisionError:
        logger.info("上层已按预期捕获 ZeroDivisionError")
    risky_divide(10, 4)


if __name__ == "__main__":
    main()
