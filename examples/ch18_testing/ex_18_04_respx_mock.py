# EX-18-04 | respx Mock httpx：不联网测试 HTTP 客户端逻辑（可编排失败序列）
# 运行：python3 examples/ch18_testing/ex_18_04_respx_mock.py
import httpx
import respx


def fetch_json(client: httpx.Client, url: str) -> dict:
    resp = client.get(url)
    resp.raise_for_status()
    return resp.json()


def main() -> None:
    with respx.mock(assert_all_called=False) as router:  # 拦截 httpx 的全部传输
        # 1) 固定响应
        route = router.get("https://api.example.com/user/1").respond(
            json={"id": 1, "name": "alice"}, status_code=200)
        with httpx.Client() as client:
            print(f"[固定响应] {fetch_json(client, 'https://api.example.com/user/1')}")

        # 2) 失败序列：第一次 503，第二次 200——重试逻辑测试的标配
        router.get("https://api.example.com/flaky").mock(
            side_effect=[httpx.Response(503), httpx.Response(200, json={"ok": True})])
        with httpx.Client() as client:
            try:
                fetch_json(client, "https://api.example.com/flaky")
            except httpx.HTTPStatusError:
                print("[失败序列] 第 1 次：503 → raise_for_status 抛出（真实网络里这就是重试触发点）")
            print(f"[失败序列] 第 2 次：{fetch_json(client, 'https://api.example.com/flaky')}")

        # 3) 抛异常模拟网络层故障
        router.get("https://api.example.com/timeout").mock(
            side_effect=httpx.ConnectTimeout("connection timed out"))
        with httpx.Client() as client:
            try:
                fetch_json(client, "https://api.example.com/timeout")
            except httpx.ConnectTimeout as exc:
                print(f"[网络故障] 捕获 {type(exc).__name__}（不联网也能测超时处理）")

        # 4) 断言调用次数与参数
        print(f"[断言] /user/1 被调用 {route.call_count} 次，"
              f"最后一次请求头 host={route.calls.last.request.headers['host']}")

    print("[验证] respx 上下文退出后自动停止拦截")


if __name__ == "__main__":
    main()
