# projects/p2_log_triage/scripts/build_data.py | 生成/重置合成数据 | 运行: python3 scripts/build_data.py
"""确定性生成 data/ 下的 3 类日志 + 服务状态快照 + 运维清单 SQLite。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]          # projects/p2_log_triage
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent.parent))          # 仓库根（examples.common 可用）

from triage.synth_data import build_all              # noqa: E402


def main() -> None:
    data_dir = ROOT / "data"
    build_all(data_dir)
    files = sorted(p.name for p in data_dir.iterdir())
    print("合成数据已生成/重置 →", data_dir)
    for f in files:
        print("  -", f)


if __name__ == "__main__":
    main()
