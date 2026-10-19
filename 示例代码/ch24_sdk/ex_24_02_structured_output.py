# EX-24-02 | 结构化输出：response_format + Pydantic（Mock 路径真实运行）| 运行: python3 示例代码/ch24_sdk/ex_24_02_structured_output.py
"""完整可运行（Mock）：chat_structured 把"模型输出"直接变成 Pydantic 对象。

Mock 路径：从最后一条 user 消息解析 key=value → Pydantic 校验（真实运行）。
Real 路径：client.chat.completions.parse(response_format=Schema)——3.35.1 已核实存在；
部分兼容服务不支持 response_format，需回退到提示词约束+自行解析（教材 24.4 清单）。
"""
from __future__ import annotations

import sys
from pathlib import Path

from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from 示例代码.公共.llm_client import StructuredOutputError, get_llm  # noqa: E402


class RefundCheck(BaseModel):
    """退款预检结果（字段语义写在 description 里，会变成 JSON Schema 提示）。"""
    order_id: str = Field(description="订单号，格式 ORD-数字")
    eligible: bool = Field(description="是否符合自动退款条件")
    reason: str = Field(default="无", description="不符合时的原因")


MESSAGES_OK = [{"role": "user",
                "content": "抽取退款预检字段：order_id=ORD-1001 eligible=true reason=无"}]
MESSAGES_BAD = [{"role": "user",
                 "content": "抽取退款预检字段：eligible=true（忘了订单号）"}]


def main() -> None:
    llm = get_llm()

    print("[1] 成功路径：解析 + 校验一步到位，拿到的是强类型对象：")
    obj = llm.chat_structured(MESSAGES_OK, RefundCheck)
    print(f"    type(obj) = {type(obj).__name__}")
    print(f"    obj.model_dump() = {obj.model_dump()}")
    print(f"    obj.model_dump_json() = {obj.model_dump_json()}")
    print(f"    直接点字段：obj.order_id = {obj.order_id!r}, obj.eligible = {obj.eligible}")

    print("\n[2] 失败路径：缺必填字段 → StructuredOutputError（真实抛出，非脚本模拟）：")
    try:
        llm.chat_structured(MESSAGES_BAD, RefundCheck)
    except StructuredOutputError as e:
        print(f"    {e}")
        print(f"    errors = {e.errors}")
        print(f"    hint   = {e.hint}")

    print("\n[3] Java 对照：ChatResult 是 Map<String,Object>，chat_structured 之后的")
    print("    Pydantic 对象 ≈ 经 Jackson 反序列化 + Bean Validation 的强类型 DTO。")


if __name__ == "__main__":
    main()
