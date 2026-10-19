# P1 评估脚本：检索命中率 / 关键词覆盖 / 引用有效性 / 拒答正确率
"""用法（项目根目录下）：
    python3 eval/run_eval.py

评估口径（与教材 ch35 的"可计算定义"一致）：
- 检索命中率@2（hit@2）：expect_doc_id 出现在引用前 2 条的 doc_id 里；
- 关键词覆盖率：expect_keywords 全部出现在回答文本中（Mock 抽取式回答下可计算）；
- 引用有效性：回答里的 [n] 标记都指向本次返回的引用条目；
- 拒答正确率：expect_refused=true 的用例必须 refused 且 citations 为空。

局限（诚实声明）：以上全是词面级/结构级指标，只能做回归守门；
"答案是否真的对"需要人工抽检（ch35 自动评估局限）。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.kb import KnowledgeBase              # noqa: E402
from app.security import UserContext          # noqa: E402
from ingest.pipeline import ingest_directory  # noqa: E402

CITATION_MARK_RE = re.compile(r"\[(\d+)\]")
EVAL_USER = UserContext.of("eval-bot", "acme",
                           ["hr", "it", "finance", "admin", "security"])


def load_evalset(path: Path) -> list[dict[str, object]]:
    cases = [json.loads(line) for line in
             path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not cases:
        raise ValueError(f"评估集为空：{path}")
    return cases


def run_eval(data_dir: Path | None = None,
             eval_path: Path | None = None) -> dict[str, object]:
    """跑完整评估并返回汇总 dict（打印见 main；pytest 直接断言本函数返回值）。"""
    data_dir = data_dir or PROJECT_ROOT / "data"
    eval_path = eval_path or PROJECT_ROOT / "eval" / "evalset.jsonl"
    kb = KnowledgeBase(store_path=None)          # 评估用全新内存库，不碰落盘数据
    ingest_directory(kb, data_dir)
    cases = load_evalset(eval_path)

    rows: list[dict[str, object]] = []
    for case in cases:
        resp = kb.answer(str(case["query"]), EVAL_USER, top_k=3)
        row: dict[str, object] = {"qid": case["qid"], "query": case["query"],
                                  "status": resp.status}
        if case.get("expect_refused"):
            row["expect"] = "refused"
            row["pass"] = resp.status == "refused" and not resp.citations
            row["note"] = resp.refusal_reason or ""
        else:
            row["expect"] = "answered"
            if resp.status != "answered":
                row["pass"] = False
                row["note"] = f"误拒（{resp.refusal_reason}）"
            else:
                top2_docs = [c.doc_id for c in resp.citations[:2]]
                hit2 = str(case.get("expect_doc_id")) in top2_docs
                covered = all(k in resp.answer for k in case.get("expect_keywords", []))
                marks = {int(m) for m in CITATION_MARK_RE.findall(resp.answer)}
                cit_ok = bool(marks) and marks <= {c.index for c in resp.citations}
                row["hit2"] = hit2
                row["keyword_cover"] = covered
                row["citation_valid"] = cit_ok
                row["top1_score"] = resp.citations[0].score
                row["pass"] = hit2 and covered and cit_ok
                row["note"] = "" if row["pass"] else (
                    "hit@2 未中" if not hit2 else
                    "关键词缺失" if not covered else "引用标记无效")
        rows.append(row)

    should_refuse = [r for r in rows if r["expect"] == "refused"]
    should_answer = [r for r in rows if r["expect"] == "answered"]
    answered_rows = [r for r in should_answer if r["status"] == "answered"]
    summary: dict[str, object] = {
        "cases": len(rows),
        "hit_at_2": (sum(1 for r in answered_rows if r.get("hit2"))
                     / max(1, len(answered_rows))),
        "keyword_coverage": (sum(1 for r in answered_rows if r.get("keyword_cover"))
                             / max(1, len(answered_rows))),
        "citation_validity": (sum(1 for r in answered_rows if r.get("citation_valid"))
                              / max(1, len(answered_rows))),
        "refusal_accuracy": (sum(1 for r in should_refuse if r["pass"])
                             / max(1, len(should_refuse))),
        "overall_pass": sum(1 for r in rows if r["pass"]) / len(rows),
        "rows": rows,
    }
    return summary


def print_report(summary: dict[str, object]) -> None:
    print(f"{'qid':<5} {'query':<16} {'状态':<9} {'hit@2':<6} {'关键词':<6} {'引用':<5} {'top1分':<8} 备注")
    print("-" * 86)
    for r in summary["rows"]:  # type: ignore[index]
        def mark(flag: object) -> str:
            return "-" if flag is None else ("✓" if flag else "✗")
        print(f"{r['qid']:<5} {str(r['query']):<16} {str(r['status']):<9} "
              f"{mark(r.get('hit2')):<6} {mark(r.get('keyword_cover')):<6} "
              f"{mark(r.get('citation_valid', None)):<5} "
              f"{str(r.get('top1_score', '-')):<8} {r.get('note', '')}")
    print("-" * 86)
    print(f"检索命中率@2：{summary['hit_at_2']:.2%}（{summary['cases']} 条用例）")
    print(f"关键词覆盖率：{summary['keyword_coverage']:.2%}")
    print(f"引用有效率　：{summary['citation_validity']:.2%}")
    print(f"拒答正确率　：{summary['refusal_accuracy']:.2%}")
    print(f"整体通过　　：{summary['overall_pass']:.2%}")


def main() -> None:
    print_report(run_eval())


if __name__ == "__main__":
    main()
