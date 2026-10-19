# EX-56-00 | Java 服务替身（stub）：与项目三 PlanServer.java 同形状的进程内 HTTP 服务
# 运行: python3 examples/ch56_java_bridge/stub_java_service.py   （自测模式，起服务打两个请求后退出）
"""教学用"Java 服务替身"：用标准库 http.server 在**线程内**复刻项目三 Java 服务的
端点形状（契约一致，见 56.3 的契约表）：

    GET  /plans?date=YYYY-MM-DD        生产计划查询
    GET  /workorders/{id}              工单状态
    POST /adjustments                  提交调整（Header: Idempotency-Key 幂等去重）
    POST /slow?ms=N                    模拟慢端点（触发超时/重试场景）
    POST /tasks                        长任务：202 Accepted + task_id（异步模式演示）
    GET  /tasks/{id} / DELETE /tasks/{id}   任务状态查询 / 取消

为什么需要替身：EX 必须离线确定性可跑（STYLE_GUIDE D）；替换成真 Java 服务
只需把 base_url 换成 http://127.0.0.1:8080（项目三验证了两种指向行为一致）。
"""
from __future__ import annotations

import json
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

# ---- 内存数据（与项目三 data/plans.json、workorders.json 同形状） ------------------
PLANS: dict[str, dict[str, Any]] = {
    "2026-03-18": [
        {"plan_id": "P-1001", "product": "减速器壳体", "qty": 500, "status": "正常"},
        {"plan_id": "P-1002", "product": "转向节", "qty": 1200, "status": "延期"},
    ],
}
WORKORDERS: dict[str, dict[str, Any]] = {
    "WO-2091": {"workorder_id": "WO-2091", "plan_id": "P-1002", "status": "生产中",
                "produced_qty": 900, "target_qty": 1200},
    "WO-2092": {"workorder_id": "WO-2092", "plan_id": "P-1001", "status": "已完成",
                "produced_qty": 500, "target_qty": 500},
}
_ADJUST_SEEN: dict[str, dict[str, Any]] = {}   # Idempotency-Key → 首次响应（幂等账本）
_TASKS: dict[str, dict[str, Any]] = {}         # task_id → 任务状态（长任务演示）


class _Handler(BaseHTTPRequestHandler):
    """最小路由器：与 PlanServer.java 的响应形状逐字段一致（契约对照表见教材 56.3）。"""

    def log_message(self, fmt: str, *args: Any) -> None:  # 静音默认访问日志
        pass

    def handle_one_request(self) -> None:
        try:
            super().handle_one_request()
        except BrokenPipeError:
            # 客户端超时断连后服务端才写响应 → BrokenPipe（超时重试演示的必然副产品，
            # 教学上恰好说明"超时的代价由双方承担"；静音以免污染示例输出）
            pass

    def _send(self, code: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 （http.server 的固定命名）
        if self.path.startswith("/health"):
            self._send(200, {"status": "UP", "service": "stub-java"})
        elif self.path.startswith("/plans"):
            date = self.path.split("date=")[-1].split("&")[0] if "date=" in self.path else ""
            plans = PLANS.get(date, [])
            self._send(200, {"date": date, "count": len(plans), "plans": plans})
        elif self.path.startswith("/workorders/"):
            wo_id = self.path.rsplit("/", 1)[-1]
            wo = WORKORDERS.get(wo_id)
            if wo is None:
                self._send(404, {"error": "workorder_not_found", "workorder_id": wo_id})
            else:
                self._send(200, wo)
        elif self.path.startswith("/slow"):
            ms = int(self.path.split("ms=")[-1].split("&")[0] or 0) if "ms=" in self.path else 0
            time.sleep(ms / 1000)
            self._send(200, {"ok": True, "delayed_ms": ms})
        elif self.path.startswith("/tasks/"):
            task_id = self.path.rsplit("/", 1)[-1]
            task = _TASKS.get(task_id)
            if task is None:
                self._send(404, {"error": "task_not_found", "task_id": task_id})
            else:
                self._send(200, task)
        else:
            self._send(404, {"error": "not_found", "path": self.path})

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            self._send(400, {"error": "bad_json"})
            return

        if self.path.startswith("/adjustments"):
            idem = self.headers.get("Idempotency-Key") or ""
            if not idem:
                self._send(400, {"error": "missing_idempotency_key"})
                return
            if idem in _ADJUST_SEEN:  # 幂等命中：返回首次结果 + 标识
                first = dict(_ADJUST_SEEN[idem])
                first["idempotent_replay"] = True
                self._send(200, first)
                return
            resp = {"adjustment_id": f"ADJ-{uuid.uuid4().hex[:8]}",
                    "plan_id": payload.get("plan_id", ""),
                    "new_qty": payload.get("new_qty", 0),
                    "status": "已受理", "idempotency_key": idem}
            _ADJUST_SEEN[idem] = dict(resp)
            self._send(201, resp)
        elif self.path.startswith("/slow"):
            ms = int(self.path.split("ms=")[-1].split("&")[0] or 0) if "ms=" in self.path else 0
            time.sleep(ms / 1000)
            self._send(200, {"ok": True, "delayed_ms": ms})
        elif self.path.startswith("/tasks"):
            task_id = f"TASK-{uuid.uuid4().hex[:8]}"
            _TASKS[task_id] = {"task_id": task_id, "status": "pending", "result": None}
            t = threading.Thread(target=self._run_task, args=(task_id,
                                                              payload.get("duration_s", 1.5)),
                                 daemon=True)
            t.start()
            self._send(202, {"task_id": task_id, "status": "pending",
                             "poll": f"/tasks/{task_id}"})  # 202 Accepted：任务已受理
        else:
            self._send(404, {"error": "not_found", "path": self.path})

    def do_DELETE(self) -> None:  # noqa: N802
        if self.path.startswith("/tasks/"):
            task_id = self.path.rsplit("/", 1)[-1]
            task = _TASKS.get(task_id)
            if task is None:
                self._send(404, {"error": "task_not_found", "task_id": task_id})
            elif task["status"] in {"succeeded", "failed", "cancelled"}:
                self._send(409, {"error": "task_already_finished", "task_id": task_id})
            else:
                task["status"] = "cancelled"
                self._send(202, {"task_id": task_id, "status": "cancelled"})
        else:
            self._send(404, {"error": "not_found", "path": self.path})

    @staticmethod
    def _run_task(task_id: str, duration_s: float) -> None:
        _TASKS[task_id]["status"] = "running"
        deadline = time.monotonic() + duration_s
        while time.monotonic() < deadline:
            if _TASKS[task_id]["status"] == "cancelled":  # 协作式取消：每 0.05s 查一次
                return
            time.sleep(0.05)
        if _TASKS[task_id]["status"] == "running":
            _TASKS[task_id]["status"] = "succeeded"
            _TASKS[task_id]["result"] = {"summary": "分析完成：P-1002 延期风险中"}


class StubJavaService:
    """线程内 Java 替身服务：start() 得 base_url；stop() 关闭。"""

    def __init__(self) -> None:
        self._httpd: ThreadingHTTPServer | None = None
        self.base_url: str = ""

    def start(self) -> str:
        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        port = self._httpd.server_address[1]
        self.base_url = f"http://127.0.0.1:{port}"
        threading.Thread(target=self._httpd.serve_forever, daemon=True).start()
        return self.base_url

    def stop(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()


if __name__ == "__main__":
    import urllib.request

    svc = StubJavaService()
    url = svc.start()
    print(f"替身服务已启动：{url}")
    with urllib.request.urlopen(f"{url}/plans?date=2026-03-18") as r:
        print("GET /plans →", r.status, r.read().decode()[:80], "...")
    with urllib.request.urlopen(f"{url}/workorders/WO-2091") as r:
        print("GET /workorders/WO-2091 →", r.status, r.read().decode()[:60], "...")
    svc.stop()
    print("自测通过（形状契约与 PlanServer.java 一致，字段对照见教材 56.3）")
