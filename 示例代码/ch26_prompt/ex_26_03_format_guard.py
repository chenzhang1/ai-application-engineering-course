# EX-26-03 | 输出格式约束与校验回退：失败→把错误回传→重试成功 | 运行: python3 示例代码/ch26_prompt/ex_26_03_format_guard.py
"""完整可运行（Mock，脚本驱动）：完整的"校验失败→重试"回退循环。

模型第一次输出缺字段（模拟真实模型偶发不守格式），Pydantic 校验失败；
程序把错误说明拼回对话再请求一次，第二次输出通过校验——生产系统的标准姿势。
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from 示例代码.公共.llm_client import MockLLM  # noqa: E402


class ExtractResult(BaseModel):
    order_id: str = Field(description="订单号")
    amount: float = Field(default=0.0, description="涉及金额")
    category: str = Field(default="咨询", description="退款|换货|咨询")


def parse_with_schema(text: str, schema: type[BaseModel]) -> BaseModel:
    """从模型文本解析 key=value 并用 Pydantic 校验（教学最小实现）。"""
    fields: dict[str, Any] = {}
    for token in text.replace("，", " ").replace(";", " ").split():
        if "=" in token:
            key, _, value = token.partition("=")
            try:  # 数字尽量转原生类型，交由 Pydantic 兜底
                fields[key] = float(value) if "." in value else int(value)
            except ValueError:
                fields[key] = value
    return schema.model_validate(fields)  # 失败抛 ValidationError


def main() -> None:
    llm = MockLLM(script=[
        # 第 1 次输出：缺 order_id（真实模型偶发不守格式的代偿演示）
        {"content": "好的：category=退款 amount=129.5"},
        # 第 2 次输出：补齐后通过
        {"content": "order_id=ORD-1001 category=退款 amount=129.5"},
    ])

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": "从客户留言抽取字段，只输出 key=value 形式，不要解释。"},
        {"role": "user", "content": "客户留言：我的订单 1001 花了 129 块 5，申请退款"},
    ]

    for attempt in range(1, 4):
        r = llm.chat(messages)
        print(f"[第 {attempt} 次请求] 模型输出：{r.content}")
        try:
            obj = parse_with_schema(r.content, ExtractResult)
        except ValidationError as e:
            print(f"    ✗ 校验失败：{e.error_count()} 个错误 → {e.errors()}")
            # 回退核心：把错误翻译成模型能懂的话，追加为新的 user 消息
            errors_text = "; ".join(
                f"字段 {'.'.join(str(x) for x in err['loc'])}: {err['msg']}" for err in e.errors()
            )
            messages.append({"role": "assistant", "content": r.content})
            messages.append({"role": "user",
                             "content": f"你的输出未通过校验（{errors_text}）。"
                                        "请补全缺失字段后重新输出，仍然只输出 key=value。"})
            continue
        print(f"    ✓ 校验通过：{obj.model_dump()}")
        print(f"\n[回退循环] 共发起 {attempt} 次模型请求；重试上限内修复，服务未向用户报错。")
        break
    else:
        print("    重试用尽——生产里应降级为人工队列，而不是把异常抛给用户。")

    print("\n[要点] 校验回退是'输出格式约束'的保底，不是邀请模型自由发挥的理由：")
    print("    能用 ch24 的 response_format/结构化输出就不要裸奔提示词约束；")
    print("    回退次数要有上限（本例 3 次），并记录失败样本用于改进 prompt（ch28）。")


if __name__ == "__main__":
    main()
