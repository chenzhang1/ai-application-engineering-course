# tests/test_p1.py | 项目一 企业文档知识库（p1_doc_kb）集成测试
"""覆盖：入库→检索→问答→引用→权限拒绝→空结果→SSE→覆盖更新/删除→JSON 落盘→评估脚本。
运行：cd /workspace/ai_application_course && python3 -m pytest tests/test_p1.py -v
全部在 LLM_MODE=mock（conftest 默认）下离线确定性运行。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PROJECT = Path(__file__).resolve().parents[1] / "projects" / "p1_doc_kb"
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from app.judge import RuleJudge                     # noqa: E402
from app.kb import ANSWER_SCORE_THRESHOLD, KnowledgeBase  # noqa: E402
from app.main import create_app                     # noqa: E402
from app.security import UserContext                # noqa: E402
from eval.run_eval import run_eval                  # noqa: E402
from ingest.pipeline import ingest_directory        # noqa: E402

EVAL_USER = UserContext.of("tester", "acme", ["hr", "it", "finance", "admin", "security"])
HR_USER = UserContext.of("alice", "acme", ["hr", "all"])
FIN_USER = UserContext.of("bob", "acme", ["finance"])
LEAVE_Q = "年假年底会清零吗"
OFFTOPIC_Q = "程序员节有什么福利"

CITATION_MARK_RE = re.compile(r"\[(\d+)\]")


@pytest.fixture()
def kb(tmp_path: Path) -> KnowledgeBase:
    """每个测试一个干净知识库（临时 JSON 落盘路径），加载全部合成文档。"""
    k = KnowledgeBase(store_path=tmp_path / "store.json")
    ingest_directory(k, PROJECT / "data")
    return k


@pytest.fixture()
def empty_kb() -> KnowledgeBase:
    return KnowledgeBase(store_path=None)


# ---- 入库层 ----

def test_ingest_creates_chunks_with_metadata(kb: KnowledgeBase) -> None:
    assert kb.doc_count == 12                      # 12 篇合成文档全部入库
    assert kb.chunk_count >= 20                    # 切分后每篇 ≥1 块
    sample = next(iter(kb._chunks.values()))
    for field in ("chunk_id", "doc_id", "tenant_id", "department", "title", "text", "vector"):
        assert getattr(sample, field), f"chunk 缺字段 {field}"
    assert sample.chunk_id.startswith(sample.doc_id + "#")
    assert sample.tenant_id == "acme"


def test_ingest_same_doc_id_replaces_old_chunks(kb: KnowledgeBase) -> None:
    old_count = kb.chunk_count
    count, status = kb.ingest_doc("hr_leave_policy", "acme", "hr", "员工请假制度",
                                  "整篇替换后的内容：只有一条规则，年假永不 invalidated。")
    assert status == "replaced" and count == 1
    assert kb.chunk_count == old_count - 1  # 旧 2 块 → 新 1 块
    ids = [c.chunk_id for c in kb._chunks.values() if c.doc_id == "hr_leave_policy"]
    assert ids == ["hr_leave_policy#000"]
    # 旧内容不再可检索
    assert all("12 月 31 日" not in c.text for c in kb._chunks.values()
               if c.doc_id == "hr_leave_policy")


def test_delete_doc_removes_all_chunks(kb: KnowledgeBase) -> None:
    removed = kb.delete_doc("faq_common")
    assert removed >= 1
    assert "faq_common" not in kb._doc_index
    assert all(c.doc_id != "faq_common" for c in kb._chunks.values())
    assert kb.delete_doc("faq_common") == 0  # 再删：0（幂等）


def test_json_persistence_roundtrip(tmp_path: Path) -> None:
    store = tmp_path / "store.json"
    kb1 = KnowledgeBase(store_path=store)
    ingest_directory(kb1, PROJECT / "data")
    assert store.exists() and store.stat().st_size > 0
    kb2 = KnowledgeBase(store_path=store)  # 模拟重启加载
    assert kb2.doc_count == kb1.doc_count
    assert kb2.chunk_count == kb1.chunk_count
    r1 = kb1.search(LEAVE_Q, EVAL_USER, top_k=1)
    r2 = kb2.search(LEAVE_Q, EVAL_USER, top_k=1)
    assert r1 and r2 and r1[0].chunk.chunk_id == r2[0].chunk.chunk_id


# ---- 检索层 ----

def test_search_top1_hits_right_doc(kb: KnowledgeBase) -> None:
    ranked = kb.search(LEAVE_Q, EVAL_USER, top_k=3)
    assert ranked and ranked[0].chunk.doc_id == "hr_leave_policy"
    assert ranked[0].score >= ANSWER_SCORE_THRESHOLD


def test_tenant_isolation(kb: KnowledgeBase) -> None:
    # beta 租户文档对 acme 用户完全不可见（即使检索词精确匹配）
    kb.ingest_doc("beta_note", "beta", "hr", "Beta 门禁", "Beta 公司门禁使用人脸识别。")
    results = kb.search("Beta 公司门禁怎么用", EVAL_USER, top_k=5)
    assert all(c.chunk.tenant_id == "acme" for c in results)
    assert all(c.chunk.doc_id != "beta_note" for c in results)


def test_department_acl_filters_before_ranking(kb: KnowledgeBase) -> None:
    fin_results = kb.search(LEAVE_Q, FIN_USER, top_k=5)
    assert fin_results, "财务用户仍能看到 finance/all 文档"
    assert all(c.chunk.department != "hr" for c in fin_results)  # hr 文档不参与排序
    hr_results = kb.search(LEAVE_Q, HR_USER, top_k=5)
    assert hr_results[0].chunk.department == "hr"
    # 公开文档（department=all）任何租户内用户可见
    faq_for_fin = kb.search("访客 WiFi 密码多少", FIN_USER, top_k=3)
    assert faq_for_fin and faq_for_fin[0].chunk.doc_id == "faq_common"


# ---- 问答层：引用 / 拒答双保险 ----

def test_ask_answered_with_valid_citations(kb: KnowledgeBase) -> None:
    resp = kb.answer(LEAVE_Q, HR_USER, top_k=3)
    assert resp.status == "answered" and resp.refusal_reason is None
    assert "[1]" in resp.answer
    assert len(resp.citations) == 3
    for i, cit in enumerate(resp.citations, 1):
        assert cit.index == i
        assert cit.doc_id and cit.chunk_id.startswith(cit.doc_id + "#")
        assert -1.0 <= cit.score <= 1.0
        assert cit.snippet
    marks = {int(m) for m in CITATION_MARK_RE.findall(resp.answer)}
    assert marks and marks <= {c.index for c in resp.citations}  # 引用编号都真实存在


def test_ask_refused_on_empty_store(empty_kb: KnowledgeBase) -> None:
    resp = empty_kb.answer(LEAVE_Q, HR_USER)
    assert resp.status == "refused"
    assert resp.refusal_reason == "no_relevant_evidence"
    assert resp.answer == "" and resp.citations == []


def test_ask_refused_below_score_threshold(kb: KnowledgeBase) -> None:
    resp = kb.answer(OFFTOPIC_Q, HR_USER)
    assert resp.status == "refused"
    assert resp.refusal_reason == "below_score_threshold"
    assert resp.citations == []


def test_ask_gate2_judge_blocks_when_gate1_lowered(kb: KnowledgeBase) -> None:
    """gate2 独立性：把阈值降到 -1（gate1 永远放行），跑题问题仍被判定器拦下。"""
    loose = KnowledgeBase(store_path=None, score_threshold=-1.0, judge=RuleJudge())
    ingest_directory(loose, PROJECT / "data")
    resp = loose.answer(OFFTOPIC_Q, HR_USER)
    assert resp.status == "refused"
    assert resp.refusal_reason == "evidence_insufficient_judge"


def test_ask_permission_denied_path(kb: KnowledgeBase) -> None:
    """权限拒绝：同一问题，财务用户被拒且回答里不泄露 hr 内容。"""
    resp = kb.answer(LEAVE_Q, FIN_USER)
    assert resp.status == "refused" and resp.citations == []
    assert "清零" not in resp.answer and "年假" not in resp.answer


# ---- 流式 ----

def test_sse_stream_event_sequence(kb: KnowledgeBase) -> None:
    events = list(kb.answer_stream(LEAVE_Q, HR_USER, top_k=3))
    kinds = [e["event"] for e in events]
    assert kinds[0] == "meta" and kinds[-1] == "done"
    assert kinds.count("done") == 1
    meta = events[0]["data"]
    assert meta["status"] == "answered" and len(meta["citations"]) == 3
    deltas = [e["data"]["text"] for e in events if e["event"] == "delta"]
    assert deltas and "".join(deltas) == kb.answer(LEAVE_Q, HR_USER, top_k=3).answer


def test_sse_stream_refusal_has_no_deltas(kb: KnowledgeBase) -> None:
    events = list(kb.answer_stream(OFFTOPIC_Q, FIN_USER, top_k=3))
    kinds = [e["event"] for e in events]
    assert kinds == ["meta", "done"]
    assert events[0]["data"]["status"] == "refused"
    assert events[0]["data"]["refusal_reason"] == "below_score_threshold"
    assert events[1]["data"]["finish_reason"] == "refused"


# ---- HTTP API ----

def test_api_endpoints(tmp_path: Path) -> None:
    app = create_app(store_path=tmp_path / "api_store.json")
    with TestClient(app) as client:
        health = client.get("/health").json()
        assert health["status"] == "ok" and health["docs"] == 0
        ing = client.post("/ingest", json={
            "doc_id": "it_test_doc", "tenant_id": "acme", "department": "it",
            "title": "测试文档",
            "text": "测试设备的保修期为 12 个月。人为损坏不在保修范围内。"}).json()
        assert ing == {"doc_id": "it_test_doc", "chunk_count": 1, "status": "created"}
        assert client.get("/health").json()["docs"] == 1

        asked = client.post("/ask", json={
            "question": "测试设备保修多久", "tenant_id": "acme",
            "user_id": "u1", "departments": ["it"]}).json()
        assert asked["status"] == "answered" and asked["citations"][0]["doc_id"] == "it_test_doc"

        assert client.post("/ask", json={"question": ""}).status_code == 422  # 非法输入
        deleted = client.delete("/docs/it_test_doc").json()
        assert deleted == {"deleted": True, "doc_id": "it_test_doc", "chunks_removed": 1}
        assert client.delete("/docs/it_test_doc").status_code == 404


def test_api_sse_over_http(tmp_path: Path) -> None:
    app = create_app(store_path=tmp_path / "sse_store.json")
    with TestClient(app) as client:
        client.post("/ingest", json={
            "doc_id": "faq_test", "tenant_id": "acme", "department": "all",
            "title": "FAQ", "text": "访客 WiFi 名称是 Acme-Guest，密码向前台索取。"})
        with client.stream("GET", "/ask/stream",
                           params={"question": "访客 WiFi 密码多少",
                                   "tenant_id": "acme", "user_id": "u1",
                                   "departments": "all", "top_k": 2}) as resp:
            assert resp.headers["content-type"].startswith("text/event-stream")
            body = "".join(resp.iter_text())
        assert "event: meta" in body and "event: delta" in body and "event: done" in body
        assert "answered" in body


# ---- 评估 ----

def test_eval_script_full_pass() -> None:
    summary = run_eval()
    assert summary["cases"] == 16
    assert summary["hit_at_2"] == 1.0
    assert summary["keyword_coverage"] == 1.0
    assert summary["citation_validity"] == 1.0
    assert summary["refusal_accuracy"] == 1.0
    assert summary["overall_pass"] == 1.0
