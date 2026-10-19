# P1 入库管线：data/*.md → 加载 → 清洗 → KnowledgeBase.ingest_doc
"""CLI：python3 -m ingest.pipeline（项目根目录下；P1_STORE_PATH 可改存储位置）。"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.kb import KnowledgeBase            # noqa: E402
from ingest.cleaner import clean_markdown   # noqa: E402
from ingest.loaders import load_directory   # noqa: E402

logger = logging.getLogger("p1.ingest")


def ingest_directory(kb: KnowledgeBase, data_dir: Path) -> dict[str, int]:
    """批量入库，返回 doc_id → chunk 数（供 README 示例与测试断言）。"""
    summary: dict[str, int] = {}
    for doc in load_directory(data_dir):
        count, _ = kb.ingest_doc(doc.doc_id, doc.tenant_id, doc.department,
                                 doc.title, clean_markdown(doc.text))
        summary[doc.doc_id] = count
    return summary


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    store = Path(os.environ.get("P1_STORE_PATH",
                                str(PROJECT_ROOT / "data" / "vector_store.json")))
    kb = KnowledgeBase(store_path=store)
    summary = ingest_directory(kb, PROJECT_ROOT / "data")
    print(f"共入库 {len(summary)} 篇文档，{sum(summary.values())} 个 chunk")
    for doc_id, count in summary.items():
        print(f"  {doc_id:<32} {count} chunks")
    print(f"存储位置：{store}")


if __name__ == "__main__":
    main()
