# ch09 迭代器与生成器：正常 / 边界 / 非法输入
import itertools
import sys
from pathlib import Path

CH09 = Path(__file__).resolve().parent.parent / "示例代码" / "ch09_iterators"
sys.path.insert(0, str(CH09))

import pytest

import ex_09_01_iter_protocol as m01
import ex_09_02_generator_yield as m02
import ex_09_03_genexpr_lazy as m03  # noqa: F401  # 确认可导入
import ex_09_04_llm_stream as m04
import ex_09_05_yield_from as m05


def test_countdown_for_loop_and_repeatable() -> None:
    """正常路径：for 循环协议正确，且可迭代对象可重复遍历。"""
    assert list(m01.Countdown(3)) == [3, 2, 1]
    assert list(m01.Countdown(3)) == [3, 2, 1]  # 每次 __iter__ 返回新迭代器
    assert list(m01.Countdown(0)) == []         # 边界：起点即耗尽


def test_iterator_is_one_shot() -> None:
    """边界：迭代器耗尽后为空（生成器同理）。"""
    it = iter(m01.Countdown(2))
    assert next(it) == 2
    assert next(it) == 1
    with pytest.raises(StopIteration):
        next(it)


def test_generator_pause_resume_trace() -> None:
    """生成器在 yield 处暂停：第一次 next 前函数体不执行。"""
    steps: list[str] = []
    gen = m02.trace_generator(steps, 2)
    assert steps == []                      # 调用生成器函数 ≠ 执行函数体
    assert next(gen) == 1
    assert len(steps) == 3                  # 开始/准备/yield 三步，尚未恢复
    with pytest.raises(StopIteration):
        next(gen); next(gen); next(gen)     # noqa: B018  # 消费到耗尽
    assert steps[-1].startswith("5. 函数体执行完毕")


def test_genexpr_is_lazy_and_one_shot() -> None:
    """生成器表达式：惰性 + 二次消费得 0 的经典陷阱。"""
    squares = (x * x for x in range(5))
    assert sum(squares) == 30
    assert sum(squares) == 0                # 已耗尽，不报错——更隐蔽
    assert m03.__doc__ is not None          # 占位断言：模块可导入


def test_llm_stream_mock_shapes() -> None:
    """AI 场景挂钩：流式 token 逐个产出、中途可停。"""
    tokens = list(m04.stream_tokens())
    assert len(tokens) == 20
    assert tokens == m04.MOCK_TOKENS
    # 中途 break：消费端只拿到前缀
    collected: list[str] = []
    for token in m04.stream_tokens():
        collected.append(token)
        if token == "求值":
            break
    assert collected[-1] == "求值" and len(collected) < 20


def test_llm_stream_rejects_real_mode() -> None:
    """非法输入：real 模式本示例未实现，必须显式报错而不是静默降级。"""
    with pytest.raises(RuntimeError, match="mock"):
        next(m04.stream_tokens(mode="real"))


def test_yield_from_delegation_and_infinite_islice() -> None:
    """yield from 透传多轮子流；无限生成器配 islice 安全截断。"""
    assert "".join(m05.agent_stream(2)) == "[r1]模型输出片段|[r2]模型输出片段|DONE"
    assert list(itertools.islice(m05.counter(1), 3)) == [0, 1, 2]
    assert list(itertools.islice(m05.counter(2), 5)) == [0, 2, 4, 6, 8]
