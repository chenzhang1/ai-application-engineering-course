# EX-16-04 | model_dump_json / model_validate_json 往返 + JSON Schema 生成（结构化输出铺垫）
# 运行：python3 示例代码/ch16_pydantic/ex_16_04_json_schema.py
import json

from pydantic import BaseModel, Field


class ExtractionResult(BaseModel):
    """第 21~24 章的'结构化输出'会用同一思路：把 JSON Schema 交给模型，把模型输出喂回 Pydantic。"""
    intent: str = Field(description="用户意图，取值 query_order | complain | other")
    order_id: str | None = Field(default=None, description="订单号，形如 ORD-12345，无法提取时为 null")
    confidence: float = Field(ge=0, le=1, description="模型自评置信度")


def main() -> None:
    # 1) 模型 → JSON 字符串（序列化）
    obj = ExtractionResult(intent="query_order", order_id="ORD-12345", confidence=0.92)
    js = obj.model_dump_json()  # 比 json.dumps(obj.model_dump()) 更快且语义一致
    print(f"[序列化] model_dump_json() → {js}")

    # 2) JSON 字符串 → 模型（反序列化 + 校验一步到位）
    raw = '{"intent": "query_order", "order_id": "ORD-67890", "confidence": 0.7}'
    parsed = ExtractionResult.model_validate_json(raw)  # 校验失败会抛 ValidationError
    print(f"[反序列化] order_id={parsed.order_id}，类型 {type(parsed).__name__}")

    # 3) 模型输出不可信：缺字段 / 越界值都会被拦下
    for bad in ('{"intent": "query_order"}',
                '{"intent": "query_order", "order_id": "ORD-1", "confidence": 1.5}'):
        try:
            ExtractionResult.model_validate_json(bad)
            print("[意外] 没有拦截（不应发生）")
        except Exception as exc:  # ValidationError
            first = exc.errors()[0]
            print(f"[拦截] {bad[:40]}… → loc={first['loc']} type={first['type']}")

    # 4) 生成 JSON Schema——这就是"让模型按 schema 输出"时交给它的那份契约
    schema = ExtractionResult.model_json_schema()
    print("[JSON Schema]")
    print(json.dumps(schema, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
