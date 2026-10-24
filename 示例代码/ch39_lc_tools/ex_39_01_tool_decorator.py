# EX-39-01 | @tool 装饰器：函数变工具，schema 自动生成 | 运行: python3 示例代码/ch39_lc_tools/ex_39_01_tool_decorator.py
"""完整可运行（离线）：@tool 把普通函数变成 BaseTool——docstring 变描述、类型注解变
参数 schema；对照第四部分裸 SDK 里"手写 JSON Schema + 手写执行分发"两份代码。
"""
from __future__ import annotations

from langchain_core.tools import tool, render_text_description


@tool
def get_weather(city: str) -> dict:
    """查询指定城市当日天气。"""
    db = {"北京": {"weather": "晴", "temp": 26}, "上海": {"weather": "小雨", "temp": 22}}
    if city not in db:
        raise ValueError(f"暂不支持城市：{city}")
    return {"city": city, **db[city]}


def main() -> None:
    print("[1] @tool 生成的 BaseTool 元数据（自动提取，零手写）：")
    print(f"    name        = {get_weather.name!r}   ← 函数名")
    print(f"    description = {get_weather.description!r}   ← docstring 第一句")
    print(f"    类型        = {type(get_weather).__name__}（StructuredTool）")
    print(f"    args_schema 生成 JSON Schema properties：")
    props = get_weather.args_schema.model_json_schema()["properties"]
    for k, v in props.items():
        print(f"      {k}: {v}")
    print(f"    required = {get_weather.args_schema.model_json_schema().get('required')}")

    print("\n[2] 工具就是 Runnable：invoke 传 dict，返回值即函数返回值：")
    result = get_weather.invoke({"city": "北京"})
    print(f"    invoke({{'city': '北京'}}) → {result}")
    print(f"    直接函数调用也行（绕过 schema，仅调试用）：{get_weather.func('上海')}")

    print("\n[3] 发给模型看的'工具清单'长什么样（render_text_description）：")
    print("    " + render_text_description([get_weather]))

    print("\n[4] 对照裸 SDK（EX-24-03）：同一工具要写两份代码——")
    print("    ① JSON Schema 声明（手写 name/description/parameters）")
    print("    ② 本地函数实现 + if/elif 分发（模型点 name，你手动路由）")
    print("    LangChain 用 @tool 把两份合成一份：schema 自动生成，name 自动路由。")


if __name__ == "__main__":
    main()
