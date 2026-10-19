# EX-61-02 | 存活与就绪分离：/healthz 与 /readyz | 运行: python3 examples/ch61_release/ex_61_02_readiness_probe.py
"""完整可运行（fastapi，离线）：K8s 探针语义的最小演示。

  /healthz（liveness，存活）：进程活着就 200——失败会被**重启**；
  /readyz（readiness，就绪）：关键依赖可用才 200——失败只被**摘除流量**，不重启。

区别为什么要命：Redis 抖一下，如果把它写进 liveness，K8s 会把整个服务杀掉重拉，
把"依赖抖动"放大成"全局重启风暴"。依赖健康只该影响 readyz。
Java 对照：Spring Boot Actuator 的 /actuator/health/liveness 与 /readiness（K8s Probes 支持）。
"""
from __future__ import annotations

from fastapi import FastAPI, Response
from fastapi.testclient import TestClient


def create_app(dependencies: dict[str, callable] | None = None) -> FastAPI:
    """dependencies: 名称 → 健康检查函数（返回 True=可用；抛异常=不可用）。
    生产里这些函数是 Redis ping / DB SELECT 1 / LLM 配置自检（ch17 的 healthz 是它的雏形）。"""
    app = FastAPI()
    deps = dependencies or {}

    @app.get("/healthz")
    def healthz() -> dict:
        # 存活：只回答"进程还活着吗"。不检查任何外部依赖！
        return {"status": "alive"}

    @app.get("/readyz")
    def readyz(response: Response) -> dict:
        # 就绪：逐个检查依赖，任何一个不可用 → 503，并告诉运维是谁挂了
        failed = []
        for name, check in deps.items():
            try:
                if not check():
                    failed.append(f"{name}: 检查返回 False")
            except Exception as exc:            # 依赖抛异常 = 不可用，绝不让 500 冒出去
                failed.append(f"{name}: {type(exc).__name__}: {exc}")
        if failed:
            response.status_code = 503             # 就绪失败：摘除流量（不是重启）
            return {"status": "not_ready", "failed": failed}
        return {"status": "ready"}

    return app


def main() -> None:
    redis_ok = lambda: True                     # type: ignore[assignment]
    redis_down = lambda: (_ for _ in ()).throw(ConnectionError("connection refused"))  # type: ignore[assignment]

    print("── 场景 1：依赖全部健康 → 就绪 ──")
    client = TestClient(create_app({"redis": redis_ok, "llm_config": lambda: True}))
    print(f"    GET /healthz → {client.get('/healthz').status_code} {client.get('/healthz').json()}")
    r = client.get("/readyz")
    print(f"    GET /readyz  → {r.status_code} {r.json()}")

    print("\n── 场景 2：Redis 挂了 → 就绪失败（503），但存活仍是 200 ──")
    client2 = TestClient(create_app({"redis": redis_down, "llm_config": lambda: True}))
    print(f"    GET /healthz → {client2.get('/healthz').status_code}（进程本身没问题，不该重启）")
    r = client2.get("/readyz")
    print(f"    GET /readyz  → {r.status_code} {r.json()}（K8s 把 pod 从 Service 摘除，流量不再打进来）")
    print("    反面教材：如果把 redis 检查写进 /healthz，K8s 会重启 pod——")
    print("    Redis 抖 30s，你的服务被重启 N 次，恢复后还得重新预热缓存，抖动被放大。")

    print("\n── K8s 探针最小集（正文 61.5 展开，○进阶选修）──")
    print("    readinessProbe: httpGet /readyz port=8917 initialDelaySeconds=5 periodSeconds=10")
    print("    livenessProbe:  httpGet /healthz port=8917 initialDelaySeconds=15 periodSeconds=20")
    print("    （探针失败会重启容器——所以 liveness 的检查逻辑必须'只管进程自己'。）")


if __name__ == "__main__":
    main()
