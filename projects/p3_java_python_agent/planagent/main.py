# projects/p3_java_python_agent/planagent/main.py
"""FastAPI 入口：对外暴露异步分析任务 API（教材 56.4 长任务模式的服务方视角）。

端点：
    POST   /analysis                     提交分析任务 → 202 {task_id, poll}
    GET    /analysis/{task_id}           查询状态与结果 → 200 | 404
    POST   /analysis/{task_id}/approval  人工审批（approve/reject）→ 200 | 404 | 409
    DELETE /analysis/{task_id}           取消（协作式）→ 202 | 404 | 409
    GET    /health                       存活检查

启动：
    uvicorn planagent.main:app --port 8000   （在 projects/p3_java_python_agent/ 目录下）
环境变量：
    PLAN_JAVA_BASE_URL  Java 服务地址（默认 http://127.0.0.1:8080）
    P3_AUDIT_PATH       审计 JSONL 路径（默认 audit/audit.jsonl）
    P3_READ_TIMEOUT_S   上游读超时秒（默认 5；压 /slow 演示时可调小）
"""
from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from planagent.task_store import TaskConflict, TaskNotFound, TaskStore


class AnalysisRequest(BaseModel):
    """POST /analysis 的请求体：分析问题（规则模型按关键词分流低风险/高风险剧本）。"""

    question: str = Field(min_length=4, max_length=500,
                          examples=["分析 2026-03-18 的延期计划并提交恢复调整"])
    operator: str = Field(default="demo-user", min_length=1, max_length=50)


class ApprovalRequest(BaseModel):
    """POST /analysis/{id}/approval 的请求体（ch48：resume 值要带操作者身份）。"""

    decision: str = Field(pattern=r"^(approve|reject)$")
    operator: str = Field(default="demo-reviewer", min_length=1, max_length=50)


def create_app(*, java_base_url: str | None = None, audit_path: str | None = None,
               read_s: float | None = None, store: TaskStore | None = None) -> FastAPI:
    """应用工厂：测试注入 base_url/审计路径；生产用环境变量。"""
    base = java_base_url or os.environ.get("PLAN_JAVA_BASE_URL", "http://127.0.0.1:8080")
    audit = audit_path or os.environ.get("P3_AUDIT_PATH", "audit/audit.jsonl")
    read_timeout = read_s if read_s is not None else float(os.environ.get("P3_READ_TIMEOUT_S", "5"))
    task_store = store or TaskStore(java_base_url=base, audit_path=audit,
                                    read_s=read_timeout)

    app = FastAPI(title="P3 生产计划分析 Agent", version="1.0.0")
    app.state.store = task_store

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "UP", "service": "p3-plan-agent"}

    @app.post("/analysis", status_code=202)
    def submit_analysis(req: AnalysisRequest) -> dict[str, Any]:
        """202 Accepted：任务已受理（异步执行），凭 task_id 轮询——绝不阻塞等结果。"""
        rec = task_store.submit(req.question)
        return {"task_id": rec.task_id, "status": rec.status,
                "poll": f"/analysis/{rec.task_id}"}

    @app.get("/analysis/{task_id}")
    def get_analysis(task_id: str) -> dict[str, Any]:
        try:
            return task_store.get(task_id).public()
        except TaskNotFound:
            raise HTTPException(status_code=404, detail=f"任务不存在：{task_id}") from None

    @app.post("/analysis/{task_id}/approval")
    def approve(task_id: str, req: ApprovalRequest) -> dict[str, Any]:
        """人工审批：approve → 高风险工具真正执行；reject → 记录拒绝并给出结论。
        同步恢复（教学实现）；生产建议审批回调服务异步 resume（ch48.8）。"""
        try:
            rec = task_store.decide(task_id, req.decision, req.operator)
        except TaskNotFound:
            raise HTTPException(status_code=404, detail=f"任务不存在：{task_id}") from None
        except TaskConflict as e:
            raise HTTPException(status_code=409, detail=str(e)) from None
        return rec.public()

    @app.delete("/analysis/{task_id}", status_code=202)
    def cancel(task_id: str) -> dict[str, Any]:
        try:
            rec = task_store.cancel(task_id)
        except TaskNotFound:
            raise HTTPException(status_code=404, detail=f"任务不存在：{task_id}") from None
        except TaskConflict as e:
            raise HTTPException(status_code=409, detail=str(e)) from None
        return {"task_id": rec.task_id, "status": rec.status}

    return app


app = create_app()  # uvicorn planagent.main:app 使用此实例


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
