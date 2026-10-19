# EX-15-03 | 幂等性：POST 重复提交问题与 Idempotency-Key 思想（服务端账本去重）
# 运行：python3 examples/ch15_http_client/ex_15_03_idempotency_key.py
import httpx
from server_stub import make_server


def main() -> None:
    server = make_server()
    import threading
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"

    with httpx.Client(base_url=base, timeout=5.0) as client:
        client.post("/reset")

        # 场景一：无幂等键——网络抖动导致客户端重发同一笔支付 → 两次扣款
        r1 = client.post("/pay", json={"amount": 99})
        r2 = client.post("/pay", json={"amount": 99})  # 同样的业务请求重发了一次
        print(f"[无幂等键] 第一次：{r1.json()['order_id']}  第二次：{r2.json()['order_id']}")
        print("[无幂等键] 两笔订单号不同 → 被服务端当成两笔扣款（资金事故的根源）")

        # 场景二：带 Idempotency-Key——客户端为"同一笔业务操作"生成唯一键，重发也不重复扣款
        headers = {"Idempotency-Key": "user-42-order-2024-0601"}
        r3 = client.post("/pay", json={"amount": 99}, headers=headers)
        r4 = client.post("/pay", json={"amount": 99}, headers=headers)  # 网络重试/用户双击都重发它
        print(f"[带幂等键] 第一次：{r3.json()['order_id']}  第二次：{r4.json()['order_id']}")
        print(f"[带幂等键] 订单号相同，第二次响应头 X-Idempotent-Replay={r4.headers.get('X-Idempotent-Replay')}")

    server.shutdown()


if __name__ == "__main__":
    main()
