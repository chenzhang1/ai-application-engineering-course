# P1 路径引导：把教材仓库根目录加进 sys.path（示例代码.公共 依赖）
"""本项目按全书约定复用 示例代码/公共 的 embedder/LLM 基座。
无论从 uvicorn、pipeline CLI 还是 pytest 进入，只要经过本引导，
`from 示例代码.公共.embeddings import ...` 都能解析。
"""
from __future__ import annotations

import sys
from pathlib import Path

_MARKER = Path("示例代码") / "公共" / "llm_client.py"


def ensure_examples_on_path() -> None:
    """向上查找教材仓库根（含 示例代码/公共/llm_client.py 的目录）并插入 sys.path。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / _MARKER).exists():
            if str(parent) not in sys.path:
                sys.path.insert(0, str(parent))
            return
    raise RuntimeError(
        "未找到教材仓库根目录（应包含 示例代码/公共/llm_client.py）。"
        "本项目依赖全书共享的 embeddings/llm_client 基座，请确认项目位于教材仓库 综合项目/ 下。")
