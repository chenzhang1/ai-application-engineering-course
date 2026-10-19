# ch17 收束演练测试 | 用 TestClient 覆盖：正常查询 / 404 / 非法参数 / 鉴权 / 限流 429 / SSE
# 运行：cd /workspace/ai_application_course && python3 -m pytest tests/test_ch17.py -v
import json
from pathlib import Path

from fastapi.testclient import TestClient

from examples.ch17_fastapi_service.app import Settings, create_app

HEADERS = {"X-API-Key": "demo-key-123"}


def make_client(**overrides) -> TestClient:
    settings = Settings(rate_limit_per_minute=1000, audit_log_path=str(Path("_test_audit.log")))
    for k, v in overrides.items():
        setattr(settings, k, v)
    return TestClient(create_app(settings))


def test_healthz_ok():
    with make_client() as client:
        r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["backend"] == "fakeredis"  # 未配置 ORDER_SVC_REDIS_URL 时的离线后端


def test_get_order_normal():
    with make_client() as client:
        r = client.get("/orders/ORD-10001", headers=HEADERS)
    assert r.status_code == 200
    assert r.json() == {"order_id": "ORD-10001", "user": "alice",
                        "amount": 129.0, "status": "paid"}
    assert len(r.headers["X-Trace-Id"]) == 16  # 中间件注入了 trace_id


def test_get_order_404_returns_trace_id():
    with make_client() as client:
        r = client.get("/orders/ORD-99999", headers=HEADERS)
    assert r.status_code == 404
    body = r.json()
    assert body["detail"] == "订单 ORD-99999 不存在"
    assert body["trace_id"] == r.headers["X-Trace-Id"]  # 异常响应也带 trace_id，日志可对上


def test_invalid_path_param_returns_422():
    with make_client() as client:
        r = client.get("/orders/not-an-order", headers=HEADERS)
    assert r.status_code == 422
    assert "pattern" in r.json()["detail"][0]["msg"]


def test_missing_or_wrong_api_key_401():
    with make_client() as client:
        assert client.get("/orders/ORD-10001").status_code == 422  # 缺头：Header 必填校验
        r = client.get("/orders/ORD-10001", headers={"X-API-Key": "wrong"})
    assert r.status_code == 401
    assert r.json()["detail"] == "无效的 API Key"


def test_rate_limit_429_with_retry_after():
    with make_client(rate_limit_per_minute=2) as client:  # 低阈值便于触发
        codes = [client.get("/orders/ORD-10001", headers=HEADERS).status_code for _ in range(3)]
    assert codes[:2] == [200, 200]
    assert codes[2] == 429
    r = client.get("/orders/ORD-10001", headers=HEADERS)
    assert r.status_code == 429
    assert int(r.headers["Retry-After"]) >= 1  # 告诉客户端多久后可重试（固定窗口语义）
    assert r.json()["detail"] == "请求过于频繁，请稍后重试"


def test_sse_full_stream_events():
    with make_client() as client:
        with client.stream("GET", "/orders/ORD-10002/stream", headers=HEADERS) as r:
            assert r.headers["content-type"].startswith("text/event-stream")
            events = [line[5:].strip() for line in r.iter_lines() if line.startswith("data:")]
    assert len(events) == 6  # 5 个进度 + 1 个 done
    progress = [json.loads(e) for e in events[:5]]
    assert [p["percent"] for p in progress] == [20, 40, 60, 80, 100]
    assert events[-1] == "{}"


def test_sse_early_disconnect_is_safe():
    """客户端读 2 行就断开：不应抛异常，服务端靠 is_disconnected/finally 兜底。"""
    with make_client() as client:
        with client.stream("GET", "/orders/ORD-10002/stream", headers=HEADERS) as r:
            for i, _line in enumerate(r.iter_lines()):
                if i >= 1:
                    break
    assert True  # 走到这里没有异常即通过（服务端清理逻辑由日志验证，见 run log）


def test_create_order_background_audit(tmp_path):
    audit = tmp_path / "audit.jsonl"
    with make_client(audit_log_path=str(audit)) as client:
        r = client.post("/orders", headers=HEADERS,
                        json={"order_id": "ORD-20001", "user": "dave", "amount": 10.0,
                              "status": "paid"})
        assert r.status_code == 201
        r2 = client.get("/orders/ORD-20001", headers=HEADERS)
    assert r2.status_code == 200  # 新订单立即可查（内存 DB）
    line = json.loads(audit.read_text(encoding="utf-8").strip())
    assert line["order_id"] == "ORD-20001"
    assert len(line["trace_id"]) == 16  # 后台任务里也能读到同一 trace_id
