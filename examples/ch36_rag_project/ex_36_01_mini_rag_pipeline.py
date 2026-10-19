# EX-36-01 | 端到端 mini RAG：入库→检索→拒答→引用问答 | 运行: python3 examples/ch36_rag_project/ex_36_01_mini_rag_pipeline.py
"""完整可运行（MockEmbedder，真实运行输出）：第六部分的收官演示——
把 ch31~ch34 的零件组装成 ~120 行的完整管线：加载 → 清洗 → 切分（1.1.3 切分器）
→ 向量化入库 → 权限过滤 → 余弦检索 → 阈值拒答 → 抽取式回答 + 引用。
它是项目一（projects/p1_doc_kb）的缩影：正式实现加了 JSON 落盘、FastAPI、
SSE 流式、评估集与 17 个 pytest 测试——学完本例直接去跑项目一。
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np  # noqa: E402
from langchain_text_splitters import RecursiveCharacterTextSplitter  # noqa: E402

from examples.common.embeddings import get_embedder  # noqa: E402

SCORE_THRESHOLD = 0.17  # 教学演示值（P1 为 0.16，均按各自语料校准）


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    department: str
    text: str
    vector: list[float]


RAW_DOCS = {  # 真实系统来自文件/网页/PDF（ch31），这里内联省篇幅
    "doc_leave": ("hr", "## 事假\n事假需提前 1 个工作日申请，由主管审批。\n\n"
                        "## 年假\n年假当年 12 月 31 日 24 点清零，不可结转到次年。"),
    "doc_reimburse": ("finance", "报销需在每月 25 日前提交，审核通过后 3 个工作日内到账。"
                                 "发票抬头必须为示例公司 Acme。"),
    "doc_vpn": ("it", "VPN 启用双因素认证，验证码收不到先检查手机时间同步。"
                      "连接后无法访问内网先确认 10.x 网段。"),
}


def build_store() -> list[Chunk]:
    emb = get_embedder()
    splitter = RecursiveCharacterTextSplitter(chunk_size=60, chunk_overlap=10,
                                              length_function=len)
    chunks: list[Chunk] = []
    for doc_id, (dept, text) in RAW_DOCS.items():
        for i, piece in enumerate(splitter.split_text(text)):
            chunks.append(Chunk(chunk_id=f"{doc_id}#{i:03d}", doc_id=doc_id,
                                department=dept, text=piece,
                                vector=emb.embed_one(piece)))
    return chunks


def search(question: str, chunks: list[Chunk], departments: set[str],
           top_k: int = 3) -> list[tuple[Chunk, float]]:
    """权限过滤（检索前）→ 余弦 → top-k。"""
    emb = get_embedder()
    q = np.asarray(emb.embed_one(question))
    q = q / np.linalg.norm(q)
    scored = [(c, float(np.asarray(c.vector) @ q)) for c in chunks
              if c.department in departments or c.department == "all"]
    scored.sort(key=lambda kv: -kv[1])
    return scored[:top_k]


def answer(question: str, chunks: list[Chunk],
           departments: set[str]) -> tuple[str, list[tuple[Chunk, float]]]:
    ranked = search(question, chunks, departments)
    if not ranked or ranked[0][1] < SCORE_THRESHOLD:
        return f"[拒答] 证据不足（top1={ranked[0][1]:.3f} < {SCORE_THRESHOLD}）" if ranked \
            else "[拒答] 可见范围内没有候选", []
    q_tokens = set(re.findall(r"[\u4e00-\u9fff]{2}", question))
    best, best_score = ranked[0]
    sentences = [s for s in best.text.replace("。", "。|").split("|") if s.strip()]
    hits = [s for s in sentences if q_tokens & set(re.findall(r"[\u4e00-\u9fff]{2}", s))]
    body = "".join(hits[:2]) if hits else sentences[0]
    cite = "  引用: " + "; ".join(f"[{i}] {c.chunk_id} score={s:.3f}"
                                  for i, (c, s) in enumerate(ranked, 1))
    return f"（Mock·抽取式回答）{body} [1]{cite}", ranked


def main() -> None:
    chunks = build_store()
    print(f"[入库] {len(RAW_DOCS)} 篇 → {len(chunks)} 块："
          f"{[c.chunk_id for c in chunks]}")

    print("\n[问答 1] hr 员工问年假（可见 hr+finance）")
    text, ranked = answer("年假年底会清零吗", chunks, {"hr", "finance"})
    print(f"    {text}")

    print("\n[问答 2] 财务员工问年假（只可见 finance → 无权文档不可见）")
    text, ranked = answer("年假年底会清零吗", chunks, {"finance"})
    print(f"    {text}")

    print("\n[问答 3] 问库里没有的知识（拒答路径）")
    text, ranked = answer("公司年会抽奖什么时候公布", chunks, {"hr", "finance", "it"})
    print(f"    {text}")

    print("\n[下一步 → 项目一]")
    print("    projects/p1_doc_kb 把本例工程化：向量 JSON 落盘、FastAPI + SSE、")
    print("    多租户 + 部门 ACL、LLM 证据判定双保险、16 条评估集与 17 个 pytest 用例。")
    print("    启动：cd projects/p1_doc_kb && python3 -m ingest.pipeline")
    print("          LLM_MODE=mock python3 -m uvicorn app.main:app --port 8765")


if __name__ == "__main__":
    main()
