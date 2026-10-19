# ch18 测试 | TestClient 测 FastAPI（正常/空输入/非法参数/限流触发）+ respx + monkeypatch
# 运行：cd /workspace/ai_application_course && python3 -m pytest tests/test_ch18.py -v
from typing import Annotated

import httpx
import pytest
import respx
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

# ── 被测服务：为测试自建的迷你服务（与 ch17 收束演练相互独立） ────────────────
_hit_counter: dict[str, int] = {}


def rate_limit(key: str = "global") -> None:
    """简易限流依赖：全局最多 3 次（教学用计数器；ch19 会换成 Redis 固定窗口）。"""
    _hit_counter[key] = _hit_counter.get(key, 0) + 1
    if _hit_counter[key] > 3:
        raise HTTPException(status_code=429, detail="请求过于频繁")


class EchoIn(BaseModel):
    text: str = Field(min_length=1, max_length=20)


class EchoOut(BaseModel):
    echoed: str


app = FastAPI(title="ch18 被测服务")


@app.post("/echo", response_model=EchoOut)
def echo(body: EchoIn, _rl: Annotated[None, Depends(rate_limit)]) -> EchoOut:
    return EchoOut(echoed=body.text)


@app.get("/limited")
def limited(_rl: Annotated[None, Depends(rate_limit)]) -> dict:
    return {"ok": True}


client = TestClient(app)


# ── TestClient 四类覆盖 ───────────────────────────────────────────────────────
def test_normal_request():
    _hit_counter.clear()
    r = client.post("/echo", json={"text": "你好"})
    assert r.status_code == 200
    assert r.json() == {"echoed": "你好"}


def test_empty_input_422():
    _hit_counter.clear()
    r = client.post("/echo", json={})  # 空输入：缺必填字段
    assert r.status_code == 422
    assert r.json()["detail"][0]["type"] == "missing"


def test_invalid_param_422():
    _hit_counter.clear()  # 限流依赖对每个请求计数：先清零，避免被前序用例的调用次数干扰
    r = client.post("/echo", json={"text": ""})  # 非法参数：min_length=1
    assert r.status_code == 422
    assert r.json()["detail"][0]["type"] == "string_too_short"
    r = client.post("/echo", json={"text": "x" * 21})  # 超长
    assert r.status_code == 422
    assert r.json()["detail"][0]["type"] == "string_too_long"


def test_rate_limit_triggered():
    _hit_counter.clear()
    codes = [client.get("/limited").status_code for _ in range(4)]
    assert codes == [200, 200, 200, 429]  # 第 4 次触发限流
    assert client.get("/limited").json()["detail"] == "请求过于频繁"


# ── respx：不联网测试 httpx 客户端逻辑（异步测试） ───────────────────────────
async def get_with_retry_once(url: str) -> httpx.Response:
    """被测客户端逻辑：失败重试一次。"""
    async with httpx.AsyncClient() as c:
        r = await c.get(url)
        if r.status_code >= 500:
            r = await c.get(url)
    return r


@respx.mock
async def test_respx_mock_async_retry():
    route = respx.get("https://api.example.com/x").mock(
        side_effect=[httpx.Response(503), httpx.Response(200, json={"ok": True})])
    r = await get_with_retry_once("https://api.example.com/x")
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    assert route.call_count == 2


# ── monkeypatch：替换配置读取，不依赖真实环境 ────────────────────────────────
def read_limit() -> int:
    import os
    return int(os.environ.get("DEMO_LIMIT", "3"))


def test_monkeypatch_env(monkeypatch: pytest.MonkeyPatch):
    assert read_limit() == 3  # 默认值
    monkeypatch.setenv("DEMO_LIMIT", "7")
    assert read_limit() == 7  # patch 后
    # 测试结束 monkeypatch 自动还原环境变量
