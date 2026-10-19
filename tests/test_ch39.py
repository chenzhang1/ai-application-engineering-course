# tests/test_ch39.py | ch39 工具：@tool、args_schema、错误处理
"""覆盖：schema 自动生成（正常）、三种 handle_tool_error 策略（边界）、
枚举参数校验失败（非法输入）、渲染文本含工具名与描述。"""
from __future__ import annotations

from typing import Literal

import pytest
from pydantic import BaseModel, Field

from langchain_core.tools import ToolException, render_text_description, tool

from examples.ch39_lc_tools.ex_39_01_tool_decorator import get_weather as base_tool


@tool
def divide(a: int, b: int) -> float:
    """两数相除；b 为 0 时抛 ToolException。"""
    if b == 0:
        raise ToolException("除数不能为 0")
    return a / b


class WeatherArgs(BaseModel):
    city: str = Field(description="城市名")
    unit: Literal["celsius", "fahrenheit"] = Field(default="celsius", description="单位")


@tool(args_schema=WeatherArgs)
def weather(city: str, unit: str = "celsius") -> dict:
    """查询天气。"""
    return {"city": city, "unit": unit}


def test_tool_schema_auto_generated() -> None:
    """@tool 自动提取：name/docstring/参数 schema/required。"""
    assert base_tool.name == "get_weather"
    assert base_tool.description == "查询指定城市当日天气。"
    schema = base_tool.args_schema.model_json_schema()
    assert schema["properties"]["city"]["type"] == "string"
    assert schema["required"] == ["city"]
    assert base_tool.invoke({"city": "北京"})["weather"] == "晴"


def test_handle_tool_error_three_strategies() -> None:
    """策略一默认抛 ToolException；策略二 str 吞异常返文案；策略三 Callable 定制。"""
    with pytest.raises(ToolException):
        divide.invoke({"a": 1, "b": 0})
    divide.handle_tool_error = "定制文案"
    assert divide.invoke({"a": 1, "b": 0}) == "定制文案"
    divide.handle_tool_error = lambda e: f"包装：{e}"
    assert divide.invoke({"a": 1, "b": 0}) == "包装：除数不能为 0"
    assert divide.invoke({"a": 6, "b": 3}) == 2.0  # 正常路径不受影响


def test_args_schema_custom_pydantic_validation() -> None:
    """args_schema：枚举+默认值生效；枚举外取值默认抛 ValidationError（非法输入）。"""
    schema = weather.args_schema.model_json_schema()
    assert schema["properties"]["unit"]["enum"] == ["celsius", "fahrenheit"]
    assert schema.get("required") == ["city"]
    assert weather.invoke({"city": "北京"})["unit"] == "celsius"
    with pytest.raises(Exception):
        weather.invoke({"city": "北京", "unit": "kelvin"})


def test_render_text_description_contains_tools() -> None:
    """模型看到的'工具菜单'包含名字与描述（给 39.5 的描述质量讨论做锚）。"""
    text = render_text_description([base_tool, divide])
    assert "get_weather" in text and "查询指定城市当日天气" in text
    assert "divide" in text
