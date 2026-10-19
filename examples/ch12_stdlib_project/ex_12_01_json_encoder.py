# EX-12-01 | json 实战：ensure_ascii / indent / 自定 JSONEncoder 处理 datetime
# 运行：python3 examples/ch12_stdlib_project/ex_12_01_json_encoder.py
"""完整可运行：中文不转义、缩进美化、datetime 序列化的标准解法。"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from json import JSONEncoder
from pathlib import Path


class SafeEncoder(JSONEncoder):
    """自定义编码器：遇到 json 不认识的类型（如 datetime）时被 default() 回调。

    对照 Java：Jackson 的 ObjectMapper.registerModule(new JavaTimeModule()) 干的是同一件事。
    """

    def default(self, o: object) -> str:
        if isinstance(o, datetime):
            return o.isoformat()  # 统一转成 ISO 8601 字符串（带时区）
        # 兜底必须抛 TypeError，这是协议要求（json 会据此升级为报错）
        return super().default(o)


def main() -> None:
    record = {
        "order_id": "SO-4001",
        "customer": "张三",
        "amount": 199.0,
        "created_at": datetime(2026, 10, 19, 9, 30, 0, tzinfo=timezone.utc),
    }

    # 1) 先看真实报错：datetime 不是 JSON 认识的类型（这是最常撞见的一手）
    print("[1] 直接 json.dumps(record) 会怎样：")
    try:
        json.dumps(record)
    except TypeError as exc:
        print(f"    TypeError: {exc}")
    print("    → 报错信息已经告诉你原因；解法见下面 [2][3]")

    # 2) ensure_ascii：默认 True 会把中文转义成 \uXXXX，接口调试时肉眼难读
    print("[2] ensure_ascii 对比（default=str 临时兜底 datetime）：")
    print("    ensure_ascii=True（默认）:")
    print("   ", json.dumps(record, ensure_ascii=True, default=str)[:100], "...")
    print("    ensure_ascii=False:")
    print("   ", json.dumps(record, ensure_ascii=False, default=str)[:100], "...")

    # 3) indent：人读的配置/报告用缩进；机器间通信用默认紧凑模式（省流量）
    print("[3] indent=2 + 自定编码器 SafeEncoder:")
    pretty = json.dumps(record, ensure_ascii=False, indent=2, cls=SafeEncoder)
    print(pretty)

    # 4) 写文件 + 读回来：roundtrip 的不对称性——datetime 出去是字符串，回来还是字符串
    path = Path(__file__).parent / "_demo_order.json"
    path.write_text(pretty, encoding="utf-8")  # pathlib 写文件（下一例细讲）
    loaded = json.loads(path.read_text(encoding="utf-8"))
    print("[4] 读回后 created_at 的类型:", type(loaded["created_at"]).__name__,
          "值 =", loaded["created_at"])
    print("    → 反序列化不会'还原'datetime；需要强类型/强校验时用 Pydantic（ch16）")
    path.unlink()  # 演示完清理


if __name__ == "__main__":
    main()
