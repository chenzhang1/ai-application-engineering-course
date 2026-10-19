# EX-36-02 | 项目一环境自检与结构地图 | 运行: python3 examples/ch36_rag_project/ex_36_02_project_one_map.py
"""完整可运行（真实运行输出）：进入项目一之前的"体检脚本"——核对项目文件是否齐全、
合成数据与评估集是否就位、端口是否空闲，并打印组件地图与启动命令。
全部检查通过后，读者可以直接按 README 启动服务。
"""
from __future__ import annotations

import socket
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
P1_ROOT = REPO_ROOT / "projects" / "p1_doc_kb"

REQUIRED = [
    "README.md",
    "app/main.py",
    "app/kb.py",
    "app/security.py",
    "app/judge.py",
    "app/schemas.py",
    "ingest/pipeline.py",
    "ingest/loaders.py",
    "ingest/cleaner.py",
    "eval/evalset.jsonl",
    "eval/run_eval.py",
]
REQUIRED_TEST = "tests/test_p1.py"
PORT = 8765


def port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def main() -> None:
    print("[1] 教材仓库与项目根")
    print(f"    仓库根：{REPO_ROOT}")
    print(f"    项目根：{P1_ROOT}  {'✓' if P1_ROOT.is_dir() else '✗ 不存在'}")

    print("\n[2] 必需文件")
    missing = [rel for rel in REQUIRED if not (P1_ROOT / rel).is_file()]
    for rel in REQUIRED:
        print(f"    {'✓' if (P1_ROOT / rel).is_file() else '✗'} {rel}")
    test_path = REPO_ROOT / REQUIRED_TEST
    print(f"    {'✓' if test_path.is_file() else '✗'} {REQUIRED_TEST}（统一测试目录）")

    print("\n[3] 合成数据与评估集")
    docs = sorted((P1_ROOT / "data").glob("*.md"))
    print(f"    data/*.md：{len(docs)} 篇 → {', '.join(d.stem for d in docs[:4])} …")
    evalset = (P1_ROOT / "eval" / "evalset.jsonl")
    n_cases = len([l for l in evalset.read_text(encoding="utf-8").splitlines() if l.strip()])
    print(f"    evalset.jsonl：{n_cases} 条用例")

    print("\n[4] 端口检查")
    busy = port_in_use(PORT)
    print(f"    127.0.0.1:{PORT} {'被占用（启动前先停掉旧进程，或换端口）' if busy else '空闲 ✓'}")

    print("\n[5] 组件地图（与教材章节的对应）")
    print("    ingest/loaders+cleaner ← ch31 文档处理    ingest/pipeline ← ch32 切分与元数据")
    print("    app/kb.py(search)      ← ch33 检索        app/kb.py(answer) ← ch34 生成/引用/拒答")
    print("    app/security.py        ← ch34 权限过滤    eval/run_eval.py ← ch35 评估")
    print("    app/main.py            ← ch17 FastAPI/SSE 全部复用")

    print("\n[6] 启动命令（项目根目录下）")
    print("    python3 -m ingest.pipeline")
    print("    LLM_MODE=mock python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8765")
    print("    python3 eval/run_eval.py")
    print("    cd " + str(REPO_ROOT) + " && python3 -m pytest tests/test_p1.py -v")

    problems = (len(missing) + (0 if test_path.is_file() else 1)
                + (1 if busy else 0))
    print(f"\n[结论] {'环境就绪，可以进入项目一' if problems == 0 else f'有 {problems} 项待处理'}")


if __name__ == "__main__":
    main()
