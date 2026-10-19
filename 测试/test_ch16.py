# ch16 测试 | 模型校验、验证器、Settings 优先级、JSON Schema
# 运行：cd /workspace/ai_application_course && python3 -m pytest 测试/test_ch16.py -v
from pathlib import Path

import pytest
from pydantic import ValidationError

from 示例代码.ch16_pydantic.ex_16_01_basics import Order
from 示例代码.ch16_pydantic.ex_16_02_validators import RefundRequest
from 示例代码.ch16_pydantic.ex_16_03_settings import Settings
from 示例代码.ch16_pydantic.ex_16_04_json_schema import ExtractionResult


def test_valid_order_parses_with_defaults():
    order = Order(order_id="ORD-12345", amount=99.5, tags=["vip"])
    assert order.quantity == 1       # 默认值生效
    assert order.memo is None        # 可选字段缺省 None
    assert order.model_dump()["tags"] == ["vip"]


def test_invalid_order_raises_with_field_locations():
    with pytest.raises(ValidationError) as exc_info:
        Order(order_id="ORD-12", amount=-5)
    locs = {err["loc"][0] for err in exc_info.value.errors()}
    assert locs == {"order_id", "amount"}  # 两个字段的错误都被收集


def test_field_validator_normalizes_and_rejects():
    ok = RefundRequest(order_id=" ord-00999 ", amount=199, reason="漏发货")
    assert ok.order_id == "ORD-00999"  # strip+upper 规范化

    with pytest.raises(ValidationError):
        RefundRequest(order_id="PAY-00999", amount=199, reason="其他")  # 字段规则拒绝


def test_model_validator_cross_field_rule():
    with pytest.raises(ValidationError) as exc_info:
        RefundRequest(order_id="ORD-00999", amount=20_000, reason="质量投诉")
    assert "人工审核" in str(exc_info.value)  # 跨字段业务规则生效


def test_settings_env_overrides_env_file(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("ORDER_APP_ENV=staging\nORDER_RATE_LIMIT_PER_MINUTE=30\n",
                        encoding="utf-8")

    s = Settings(_env_file=env_file)
    assert s.app_env == "staging"        # .env 覆盖默认值
    assert s.rate_limit_per_minute == 30

    monkeypatch.setenv("ORDER_APP_ENV", "production")  # 真实环境变量优先级最高
    s2 = Settings(_env_file=env_file)
    assert s2.app_env == "production"
    assert s2.rate_limit_per_minute == 30  # 未覆盖的字段仍取 .env


def test_json_schema_and_roundtrip():
    obj = ExtractionResult.model_validate_json(
        '{"intent": "query_order", "order_id": "ORD-67890", "confidence": 0.7}')
    assert obj.order_id == "ORD-67890"
    assert obj.model_dump_json() == (
        '{"intent":"query_order","order_id":"ORD-67890","confidence":0.7}')

    schema = ExtractionResult.model_json_schema()
    assert schema["required"] == ["intent", "confidence"]
    assert schema["properties"]["confidence"]["maximum"] == 1

    with pytest.raises(ValidationError):
        ExtractionResult.model_validate_json('{"intent": "query_order"}')  # 缺 confidence
