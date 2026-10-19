# ch15 测试 | 重试成功/耗尽、退避上限、超时三件套、幂等键去重（全部打本地测试服务器）
# 运行：cd /workspace/ai_application_course && python3 -m pytest 测试/test_ch15.py -v
import threading

import httpx
import pytest

from 示例代码.ch15_http_client.ex_15_02_retry_backoff import request_with_retry
from 示例代码.ch15_http_client.server_stub import make_server


@pytest.fixture()
def stub() -> httpx.Client:
    server = make_server()
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    client = httpx.Client(base_url=base,
                          timeout=httpx.Timeout(connect=1.0, read=2.0, write=1.0, pool=1.0))
    client.post("/reset")
    yield client
    client.close()
    server.shutdown()


def test_retry_eventually_succeeds(stub: httpx.Client):
    resp = request_with_retry(stub, "GET", "/flaky", params={"fail": 2, "key": "t1"},
                              base_delay=0.01)
    assert resp.status_code == 200
    assert resp.json()["attempt"] == 3  # 前两次 503，第三次成功


def test_retry_returns_last_response_when_exhausted(stub: httpx.Client):
    resp = request_with_retry(stub, "GET", "/flaky", params={"fail": 99, "key": "t2"},
                              max_attempts=3, base_delay=0.01)
    assert resp.status_code == 503  # 重试耗尽：返回最后一次的真实响应，由调用方决定怎么办
    assert resp.json()["attempt"] == 3


def test_retry_transport_error_raises_after_exhaustion():
    """连接被拒绝（服务不存在）属于传输层错误：重试耗尽后原样抛出。"""
    # 端口 1 上的连接会被立即拒绝（无需启动任何服务）
    with httpx.Client(base_url="http://127.0.0.1:1",
                      timeout=httpx.Timeout(connect=0.5, read=1.0, write=1.0, pool=1.0)) as c:
        with pytest.raises(httpx.ConnectError):
            request_with_retry(c, "GET", "/ok", max_attempts=2, base_delay=0.01)


def test_backoff_delay_respects_exponential_ceiling(stub: httpx.Client, monkeypatch):
    """抖动的意义：真实等待在 [0, 2^n*base] 内随机，且上限逐次翻倍。"""
    seen: list[float] = []
    monkeypatch.setattr("time.sleep", seen.append)  # 不真睡，只记录

    request_with_retry(stub, "GET", "/flaky", params={"fail": 3, "key": "t3"},
                       max_attempts=5, base_delay=0.1, max_delay=0.4)

    ceilings = [0.1, 0.2, 0.4]  # 第 n 次重试上限 = min(max_delay, base*2^(n-1))
    assert len(seen) == 3  # 第 1~3 次失败各退避一次，第 4 次成功不再退避
    for delay, ceiling in zip(seen, ceilings):
        assert 0 <= delay <= ceiling + 1e-9
    assert ceilings[0] < ceilings[1] < ceilings[2]  # 指数增长（0.4 已到 max_delay 封顶）


def test_read_timeout_uses_client_setting(stub: httpx.Client):
    stub.timeout = httpx.Timeout(connect=1.0, read=0.2, write=1.0, pool=1.0)
    with pytest.raises(httpx.ReadTimeout):
        stub.get("/slow", params={"ms": 1500})


def test_idempotency_key_prevents_double_charge(stub: httpx.Client):
    key = {"Idempotency-Key": "order-2024-test-001"}
    r1 = stub.post("/pay", json={"amount": 99}, headers=key)
    r2 = stub.post("/pay", json={"amount": 99}, headers=key)
    assert r1.json()["order_id"] == r2.json()["order_id"]  # 同一业务操作 → 同一订单
    assert r2.headers["X-Idempotent-Replay"] == "true"     # 第二次是回放，未再次扣款

    r3 = stub.post("/pay", json={"amount": 99})  # 无幂等键：被当成新订单
    assert r3.json()["order_id"] != r1.json()["order_id"]
