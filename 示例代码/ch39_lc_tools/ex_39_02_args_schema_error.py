# EX-39-02 | args_schema 自定义 Pydantic 与 ToolException 三种错误策略 | 运行: python3 示例代码/ch39_lc_tools/ex_39_02_args_schema_error.py
"""完整可运行（离线）：
[1] args_schema 挂自定义 Pydantic 模型：字段描述进 schema、默认值、枚举约束；
[2] ToolException：工具"预期内失败"的表达方式，三种 handle_tool_error 策略实测；
[3] 对照裸 SDK：EX-24-03 里 try/except 转错误 JSON 的手写样板。
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from langchain_core.tools import ToolException, tool


class WeatherArgs(BaseModel):
    """get_weather 的参数模型（描述会写进 JSON Schema 给模型看）。"""

    city: str = Field(description="城市名，如 北京")
    unit: Literal["celsius", "fahrenheit"] = Field(default="celsius", description="温度单位")


@tool(args_schema=WeatherArgs)
def get_weather(city: str, unit: str = "celsius") -> dict:
    """查询指定城市当日天气。"""
    if city == "火星":
        raise ToolException("暂不支持城市：火星（数据库里没有该城市的观测站）")
    return {"city": city, "temp_c": 26, "unit": unit}


def main() -> None:
    print("[1] args_schema 生效：schema 来自 Pydantic 模型（含枚举与默认值）：")
    schema = get_weather.args_schema.model_json_schema()
    print(f"    properties = {schema['properties']}")
    print(f"    required   = {schema.get('required')}（有默认值的 unit 不必填）")
    print(f"    invoke 合法参数 → {get_weather.invoke({'city': '北京'})}")

    print("\n[2] 策略一：handle_tool_error 默认 None → ToolException 直接抛出（调用方处理）：")
    try:
        get_weather.invoke({"city": "火星"})
    except ToolException as e:
        print(f"    捕获 ToolException: {e}")

    print("\n[3] 策略二：handle_tool_error = 定制文案（str）→ 异常被吞，invoke 返回字符串：")
    get_weather.handle_tool_error = "工具内部出错，请稍后重试或联系值班工程师。"
    r = get_weather.invoke({"city": "火星"})
    print(f"    invoke → {r!r}（type = {type(r).__name__}）")

    print("\n[4] 策略三：handle_tool_error = Callable → 函数拿到异常，返回给模型的提示：")
    def to_model_msg(e: Exception) -> str:
        return f"工具执行失败：{e}。建议：换个国内城市名再试一次。"
    get_weather.handle_tool_error = to_model_msg
    print(f"    invoke → {get_weather.invoke({'city': '火星'})!r}")

    print("\n[5] 对照裸 SDK：EX-24-03 的错误样板（真实代码摘录）：")
    print('    try:')
    print('        result = get_weather(**tc.arguments)')
    print('        tool_content = json.dumps(result, ensure_ascii=False)')
    print('    except Exception as e:')
    print('        tool_content = json.dumps({"error": str(e)}, ensure_ascii=False)')
    print("    LangChain 把这段 if/else 收敛成一个 handle_tool_error 属性；")
    print("    关键不变量相同：错误要变成'模型读得懂的话'回传，而不是让整个请求 500。")

    print("\n[6] 非法参数（schema 校验失败）默认抛 ValidationError，可设 handle_validation_error：")
    try:
        get_weather.invoke({"city": "北京", "unit": "开尔文"})  # 枚举外取值
    except Exception as e:
        print(f"    默认：{type(e).__name__}")
    get_weather.handle_validation_error = "参数不合法：unit 只能是 celsius 或 fahrenheit"
    print(f"    设置 handle_validation_error 后 → {get_weather.invoke({'city': '北京', 'unit': '开尔文'})!r}")


if __name__ == "__main__":
    main()
