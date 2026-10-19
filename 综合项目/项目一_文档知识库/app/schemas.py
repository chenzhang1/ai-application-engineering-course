# P1 API 契约（Pydantic v2） | 请求/响应模型，FastAPI 自动生成 OpenAPI 文档的依据
"""所有端点的请求与响应模型。

设计要点（与教材 ch16/ch17 呼应）：
- 请求模型带默认值，方便 curl 快速试验；生产环境身份字段应从 JWT/会话解析，
  绝不从消息内容推断（ch28 红线：提示词不是权限控制）。
- 响应模型固定字段：调用方（Spring Boot 侧）按契约消费，不猜字段。
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    """文档入库请求：一篇文档 → 切分成多个 chunk。重复 doc_id 即覆盖更新。"""

    doc_id: str = Field(min_length=1, description="文档唯一 ID，重复则整篇覆盖")
    tenant_id: str = Field(default="acme", min_length=1, description="租户 ID")
    department: str = Field(default="all", min_length=1, description="可见部门；all 表示租户内公开")
    title: str = Field(min_length=1, description="文档标题（进 chunk 元数据）")
    text: str = Field(min_length=1, description="文档正文（markdown 明文）")


class IngestResponse(BaseModel):
    doc_id: str
    chunk_count: int
    status: Literal["created", "replaced"] = Field(description="created=新增；replaced=覆盖旧版本")


class Citation(BaseModel):
    """引用条目：回答中 [n] 标记与检索证据一一对应。"""

    index: int = Field(description="上下文块编号，从 1 开始")
    doc_id: str
    chunk_id: str
    score: float = Field(description="融合检索得分（向量+词面），仅用于排序与阈值，无跨库可比性")
    snippet: str = Field(description="被引片段前 60 字，便于人眼快速核对")


class AskRequest(BaseModel):
    question: str = Field(min_length=1, description="用户问题")
    tenant_id: str = Field(default="acme", min_length=1)
    user_id: str = Field(default="anonymous", min_length=1)
    departments: list[str] = Field(default_factory=lambda: ["all"],
                                   description="用户可见部门列表；all 表示仅公开文档")
    top_k: int = Field(default=3, ge=1, le=10)


class AskResponse(BaseModel):
    question: str
    status: Literal["answered", "refused"]
    answer: str = Field(default="", description="回答正文，含 [n] 引用标记；拒答时为空")
    refusal_reason: str | None = Field(
        default=None,
        description="no_relevant_evidence / below_score_threshold / evidence_insufficient_judge",
    )
    citations: list[Citation] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str
    docs: int
    chunks: int
    embedder: str
    judge: str
    llm_mode: str
    answer_mode: str
