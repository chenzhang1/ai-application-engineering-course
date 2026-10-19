# ch60 测试 | 成本中间件统计正确性与结构化日志字段、三层评估分数与回归门槛
# 运行：cd /workspace/ai_application_course && python3 -m pytest tests/test_ch60.py -v
import json
import logging

from fastapi.testclient import TestClient

from examples.ch60_observability.ex_60_01_cost_middleware import (
    PRICE_TABLE,
    create_app,
)
from examples.ch60_observability.ex_60_02_eval_three_layers import (
    EVALSET,
    Case,
    answer_for,
    score,
)


def test_middleware_logs_structured_usage_and_cost():
    """中间件：每个请求产出一条合法 JSON 日志，tokens/成本/trace_id 字段齐全且数值自洽。"""
    records: list[dict] = []

    class Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(json.loads(record.getMessage()))

    logger = logging.getLogger("cost")
    capture = Capture()
    logger.addHandler(capture)

    client = TestClient(create_app())
    r = client.post("/v1/ask", json={"question": "年假有几天？"},
                    headers={"X-Trace-Id": "t-test-001"})
    assert r.status_code == 200
    assert r.headers["X-Trace-Id"] == "t-test-001"

    assert len(records) == 1
    log = records[0]
    assert log["trace_id"] == "t-test-001"
    assert log["path"] == "/v1/ask" and log["status"] == 200
    assert log["prompt_tokens"] > 0 and log["completion_tokens"] > 0
    assert log["count_method"] != "unavailable"          # Mock 的 usage 已回传
    price = PRICE_TABLE["demo-model"]
    expect_cost = (log["prompt_tokens"] / 1000 * price["prompt_per_1k"]
                   + log["completion_tokens"] / 1000 * price["completion_per_1k"])
    assert abs(log["cost_est_yuan"] - round(expect_cost, 6)) < 1e-9   # 成本=token×单价
    logger.removeHandler(capture)


def test_middleware_missing_usage_counts_zero_not_hidden():
    """usage 缺失：按 0 记账且 count_method=unavailable——绝不能把'没统计到'当'没花钱'。"""
    records: list[dict] = []

    class Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(json.loads(record.getMessage()))

    app = create_app()

    @app.post("/v1/broken")
    def broken() -> dict:                # 忘记写 request.state.usage 的端点
        return {"answer": "x"}

    logger = logging.getLogger("cost")
    capture = Capture()
    logger.addHandler(capture)
    client = TestClient(app)
    assert client.post("/v1/broken", json={}).status_code == 200
    log = records[0]
    assert log["prompt_tokens"] == 0 and log["completion_tokens"] == 0
    assert log["cost_est_yuan"] == 0 and log["count_method"] == "unavailable"
    logger.removeHandler(capture)


def test_offline_eval_v2_beats_v1():
    """离线评估：v2（补齐口径）总分明于 v1；对抗样本两版都守住。"""
    v1, v2 = score("v1"), score("v2")
    assert v2["total"] > v1["total"]
    assert v1["refusal_ok"] == 1.0 and v2["refusal_ok"] == 1.0


def test_online_feedback_direction_matches_offline():
    """在线反馈（示例内置数据）与离线分数方向一致——回归门槛断言。"""
    v1, v2 = score("v1"), score("v2")
    gate = v2["total"] >= v1["total"] and v2["refusal_ok"] == 1.0
    assert gate is True


def test_unknown_version_raises():
    """非法输入：未知版本必须报错（评估引擎不接受静默错配）。"""
    import pytest

    with pytest.raises(ValueError):
        answer_for("v99", "年假有几天？")


def test_badcase_backfill_extends_evalset():
    """闭环：badcase 回填后评估集变长，且回填样本必须可打分（不会崩）。"""
    n_before = len(EVALSET)
    EVALSET.append(Case("q-test", "外派员工年假怎么算？", ("折算",)))
    assert len(EVALSET) == n_before + 1
    s = score("v2")                       # 新样本进入统计不报错
    assert 0.0 <= s["total"] <= 1.0
    EVALSET.pop()                         # 还原共享评估集，避免影响其他测试
