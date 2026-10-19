# EX-56-03 | 超时与重试语义：对慢 Java 端点演示"重试哪些、怎么重、何时停"
# 运行: python3 examples/ch56_java_bridge/ex_56_03_timeout_retry_semantics.py
"""完整可运行（httpx + 线程内 Java 替身 /slow 端点，确定性）：

ch15 讲过超时三件套与指数退避的"怎么写"；本章补上"为什么这么写"的语义层：

    ① 超时不是失败处理，是止损——read 超时后连接里的时间已经花掉了，
      重试是在**追加成本**，所以重试次数必须有限（本例 3 次封顶）；
    ② 只自动重试"幂等安全"的调用：GET 直接重；POST /adjustments 必须带
      Idempotency-Key——同一个 key 重试，Java 侧幂等账本保证不会提交两次；
    ③ 退避 + 抖动：base*2^n + 随机抖动，防止上游恢复瞬间被重试风暴二次打死；
    ④ 可重试错误白名单：超时/连接错误/5xx 重试；404/422（业务错误）绝不重试——
      重试一个"参数错了"的请求只会得到同样的 422，纯属烧钱。

实验数据：/slow?ms=1200 vs read 超时 0.3s → 3 次尝试全超时，总耗时 ≈ 3×0.3s+退避，
证明"超时上限 + 重试上限 = 最坏情况响应时间的确定上界"。
"""
from __future__ import annotations

import random
import sys
import time
from pathlib import Path
from typing import Any

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from stub_java_service import StubJavaService  # noqa: E402

RETRYABLE = (httpx.TimeoutException, httpx.TransportError)  # 可重试：超时/连接层


def call_with_retry(client: httpx.Client, method: str, path: str, *,
                    headers: dict[str, str] | None = None,
                    json_body: Any = None, max_attempts: int = 3,
                    base_backoff_s: float = 0.1) -> dict[str, Any]:
    """带重试语义的调用：白名单错误 × 有限次数 × 退避抖动。
    返回响应 JSON；重试耗尽抛最后一次的异常（不吞——调用方要能感知失败）。"""
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        t0 = time.monotonic()
        try:
            r = client.request(method, path, headers=headers, json=json_body)
            if r.status_code >= 500:  # 5xx：服务端事故，可重试
                last_exc = httpx.TransportError(f"上游 5xx：{r.status_code}")
                print(f"    尝试{attempt}：{r.status_code}（5xx，可重试）")
            else:
                return r.json()  # 2xx/4xx 直接返回：4xx 是业务错误，重试无意义
        except RETRYABLE as e:
            last_exc = e
            print(f"    尝试{attempt}：{type(e).__name__}（{time.monotonic()-t0:.2f}s 内失败，可重试）")
        if attempt < max_attempts:  # 指数退避 + 抖动
            delay = base_backoff_s * (2 ** (attempt - 1)) + random.uniform(0, 0.05)
            print(f"    退避 {delay:.2f}s 后重试")
            time.sleep(delay)
    assert last_exc is not None
    raise last_exc


def main() -> None:
    svc = StubJavaService()
    base = svc.start()
    print(f"== 超时与重试语义（目标服务 {base}）==\n")

    print("[1] 快端点：/slow?ms=50，read 超时 1s → 一次成功，零重试")
    client = httpx.Client(base_url=base, timeout=httpx.Timeout(connect=1.0, read=1.0, write=1.0, pool=1.0))
    r = call_with_retry(client, "GET", "/slow?ms=50")
    print(f"    → {r}\n")

    print("[2] 慢端点：/slow?ms=1200，read 超时 0.3s → 3 次全超时后放弃（止损上界）")
    slow_client = httpx.Client(base_url=base, timeout=httpx.Timeout(connect=1.0, read=0.3, write=1.0, pool=1.0))
    t0 = time.monotonic()
    try:
        call_with_retry(slow_client, "GET", "/slow?ms=1200")
    except httpx.TimeoutException as e:
        print(f"    重试耗尽：{type(e).__name__}，总耗时 {time.monotonic()-t0:.2f}s")
        print("    → 最坏情况 = Σ(每次超时) + Σ(退避)，可预算、可告警，不是'无限等'\n")

    print("[3] 幂等重试：POST /adjustments 同一 Idempotency-Key 重发两次")
    headers = {"Idempotency-Key": "idem-demo-001"}
    body = {"plan_id": "P-1002", "new_qty": 1250, "reason": "客户加急（幂等演示）"}
    first = call_with_retry(client, "POST", "/adjustments", headers=headers, json_body=body)
    print(f"    首次：{first['status']}，adjustment_id={first['adjustment_id']}")
    replay = call_with_retry(client, "POST", "/adjustments", headers=headers, json_body=body)
    print(f"    重放：HTTP 200 + 同 adjustment_id={replay['adjustment_id']}，"
          f"idempotent_replay={replay.get('idempotent_replay')}")
    print("    → 重试安全的前提：写操作带幂等键，服务端按 key 去重（Java 侧 Map 账本）\n")

    print("[4] 业务错误不重试：404 直接返回给调用方（数据，不是事故）")
    r = client.get("/workorders/WO-9999")
    print(f"    GET /workorders/WO-9999 → {r.status_code}（call_with_retry 对 4xx 零重试）")

    print("\n语义四条：有限次数 / 幂等才重试 / 退避加抖动 / 白名单错误。")
    svc.stop()


if __name__ == "__main__":
    main()
