# 测试/test_ch26.py | ch26 Prompt 工程
"""覆盖：三段式模板渲染、few-shot 结构（示例含口径）、格式校验回退循环、模板分离红线。"""
from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import BaseModel, Field, ValidationError

from 示例代码.ch26_prompt.ex_26_01_template_parts import SYSTEM_TEMPLATE, render
from 示例代码.ch26_prompt.ex_26_02_few_shot import FEW_SHOT, ZERO_SHOT
from 示例代码.公共.llm_client import MockLLM


def test_template_has_three_sections_and_separates_data() -> None:
    """角色/约束/输入数据三段齐备；工单原文只进『输入数据』段。"""
    rendered = render("客户说屏幕碎了要求退款")
    for section in ("## 角色", "## 约束", "## 输入数据"):
        assert section in rendered
    assert "客户说屏幕碎了要求退款" not in SYSTEM_TEMPLATE.split("## 输入数据")[0]
    assert rendered.rstrip().endswith("客户说屏幕碎了要求退款")


def test_zero_vs_few_shot_structure() -> None:
    """few-shot 比 zero-shot 多示例；两者都带输出格式约束（EX-26-02）。"""
    assert len(FEW_SHOT) > len(ZERO_SHOT)
    assert FEW_SHOT.count("输出：") == 3  # 三个示例
    assert '{"label"' in ZERO_SHOT.replace('{"label"', '{"label"') or '"label"' in ZERO_SHOT
    assert '"label"' in FEW_SHOT


class Extract(BaseModel):
    order_id: str = Field(description="订单号")
    amount: float = Field(default=0.0)


def _parse(text: str, schema: type[BaseModel]) -> Any:
    fields: dict[str, Any] = {}
    for token in text.replace("，", " ").split():
        if "=" in token:
            key, _, value = token.partition("=")
            try:
                fields[key] = float(value) if "." in value else int(value)
            except ValueError:
                fields[key] = value
    return schema.model_validate(fields)


def test_format_guard_retry_loop_recovers() -> None:
    """缺字段 → ValidationError → 错误回传 → 第二次成功（EX-26-03 主线）。"""
    llm = MockLLM(script=[
        {"content": "好的：amount=129.5"},
        {"content": "order_id=ORD-1001 amount=129.5"},
    ])
    messages: list[dict[str, Any]] = [{"role": "user", "content": "订单 1001 花 129.5 退款"}]
    attempts = 0
    for attempt in range(1, 4):
        attempts = attempt
        r = llm.chat(messages)
        try:
            obj = _parse(r.content, Extract)
            break
        except ValidationError as e:
            messages.append({"role": "assistant", "content": r.content})
            messages.append({"role": "user",
                             "content": "你的输出未通过校验："
                                        + "; ".join(f"{err['loc']}: {err['msg']}" for err in e.errors())
                                        + "。请补全后重新输出。"})
    else:
        pytest.fail("重试用尽仍未通过")
    assert attempts == 2
    assert isinstance(obj, Extract) and obj.order_id == "ORD-1001"  # type: ignore[has-type]


def test_few_shot_outputs_are_valid_json_labels() -> None:
    """示例中的输出都是合法 JSON 且 label 在枚举内（golden 口径可被程序校验）。"""
    for line in FEW_SHOT.splitlines():
        if line.startswith("输出："):
            label = json.loads(line.removeprefix("输出："))["label"]
            assert label in {"退款", "换货", "咨询"}
