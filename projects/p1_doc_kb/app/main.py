# P1 FastAPI 服务：文档入库 / 检索问答 / SSE 流式 / 权限过滤 / 文档删除
"""启动（项目根目录下）：
    LLM_MODE=mock python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8765

端点一览：
    GET    /health                 健康检查（含 chunk/doc 计数与模式信息）
    POST   /ingest                 文档入库（同 doc_id 覆盖更新）
    DELETE /docs/{doc_id}          整篇删除
    POST   /ask                    问答（JSON：回答 + 引用 + 拒答原因）
    GET    /ask/stream             SSE 流式问答（meta → delta* → done）

身份说明（教学简化 + 生产红线）：请求里的 tenant_id/departments 在真实系统
必须从 JWT/Session 解析（ch28：提示词不是权限控制，身份也不来自消息内容）。
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.bootstrap import ensure_examples_on_path
from app.judge import get_judge
from app.kb import KnowledgeBase
from app.schemas import (AskRequest, AskResponse, HealthResponse,
                         IngestRequest, IngestResponse)
from app.security import UserContext

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("p1.main")

ensure_examples_on_path()

DEFAULT_STORE = Path(__file__).resolve().parents[1] / "data" / "vector_store.json"


def create_app(store_path: Path | None = None) -> FastAPI:
    """应用工厂（ch17 模式）：测试注入临时 store_path，不污染真实数据目录。"""
    path = store_path if store_path is not None else Path(
        os.environ.get("P1_STORE_PATH", str(DEFAULT_STORE)))
    kb = KnowledgeBase(store_path=path)
    app = FastAPI(title="P1 企业文档知识库", version="1.0.0")
    app.state.kb = kb

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(
            status="ok", docs=kb.doc_count, chunks=kb.chunk_count,
            embedder=kb._embedder.kind, judge=get_judge().kind,
            llm_mode=os.environ.get("LLM_MODE", "mock"),
            answer_mode=kb._resolve_answer_mode())

    @app.post("/ingest", response_model=IngestResponse)
    def ingest(req: IngestRequest) -> IngestResponse:
        try:
            count, status = kb.ingest_doc(req.doc_id, req.tenant_id,
                                          req.department, req.title, req.text)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        logger.info("ingest %s → %d chunks (%s)", req.doc_id, count, status)
        return IngestResponse(doc_id=req.doc_id, chunk_count=count, status=status)

    @app.delete("/docs/{doc_id}")
    def delete_doc(doc_id: str) -> dict[str, object]:
        removed = kb.delete_doc(doc_id)
        if removed == 0:
            raise HTTPException(status_code=404, detail=f"文档 {doc_id} 不存在")
        return {"deleted": True, "doc_id": doc_id, "chunks_removed": removed}

    @app.post("/ask", response_model=AskResponse)
    def ask(req: AskRequest) -> AskResponse:
        user = UserContext.of(req.user_id, req.tenant_id, req.departments)
        return kb.answer(req.question, user, req.top_k)

    @app.get("/ask/stream")
    def ask_stream(
        question: str = Query(min_length=1),
        tenant_id: str = Query(default="acme"),
        user_id: str = Query(default="anonymous"),
        departments: str = Query(default="all",
                                 description="逗号分隔，如 hr,finance"),
        top_k: int = Query(default=3, ge=1, le=10),
    ) -> StreamingResponse:
        user = UserContext.of(user_id, tenant_id, departments.split(","))

        def event_source():
            for ev in kb.answer_stream(question, user, top_k):
                yield f"event: {ev['event']}\ndata: {json.dumps(ev['data'], ensure_ascii=False)}\n\n"

        return StreamingResponse(event_source(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache",
                                          "X-Accel-Buffering": "no"})

    return app


app = create_app()
