# EX-17-05 | BackgroundTasks：响应先返回，耗时收尾工作在后台做
# 运行：python3 示例代码/ch17_fastapi_service/ex_17_05_background_tasks.py
import json
import time
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

app = FastAPI(title="后台任务演示")
AUDIT = Path(__file__).parent / "_ex_17_05_audit.log"


def write_audit(order_id: str, action: str) -> None:
    """真实收尾动作：写审计日志（也可能发通知、更新统计）。故意慢 0.3s。"""
    time.sleep(0.3)
    with AUDIT.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"order_id": order_id, "action": action, "ts": time.time()}) + "\n")


class Order(BaseModel):
    order_id: str
    sku: str = Field(min_length=2)


@app.post("/orders", status_code=201)
def create_order(order: Order, background: BackgroundTasks) -> dict:
    background.add_task(write_audit, order.order_id, "create")  # 注册任务，不等待
    return {"accepted": True, "order_id": order.order_id}


def main() -> None:
    AUDIT.unlink(missing_ok=True)  # 每次运行清空演示文件
    with TestClient(app) as client:
        started = time.perf_counter()
        r = client.post("/orders", json={"order_id": "ORD-77777", "sku": "B200"})
        latency = time.perf_counter() - started
        print(f"[响应] status={r.status_code}  body={r.json()}  测得耗时 {latency * 1000:.0f}ms")
        # 注意：TestClient 会等整个 ASGI 生命周期（含后台任务）结束才返回，所以这里测得
        # 的耗时包含 0.3s 审计写入；真实 uvicorn 中响应先发出，后台任务由事件循环后续执行。
        # 用 curl 打真实服务可观察到"响应立刻返回、审计随后落盘"的时序（见 run log）。

        lines = AUDIT.read_text(encoding="utf-8").strip().splitlines()
        print(f"[审计] 后台任务确实执行了：{lines[0]}")
    AUDIT.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
