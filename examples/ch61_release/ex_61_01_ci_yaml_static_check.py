# EX-61-01 | CI 流水线 YAML 的静态检查器 | 运行: python3 examples/ch61_release/ex_61_01_ci_yaml_static_check.py
"""完整可运行（纯标准库，离线）：用正则核对 CI YAML 的 12 项关键特征。

为什么这样做：本沙箱没有 GitHub 运行环境（FACTS），与 ch20 检查 Dockerfile 同一思路——
"用可执行的静态检查替代不可执行的真实运行"，把教材承诺落成可验证的文本特征。
边界说清楚：静态特征全对 ≠ 流水线能跑通；真实验证需要在 GitHub 仓库上触发
（STYLE_GUIDE 与正文 61.4 都做了标注，读者采用前必须实跑一次）。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

YAML_PATH = Path(__file__).resolve().parent / "github_workflows_ci.yml"

CHECKS: list[tuple[str, str]] = [
    ("工作流命名与触发器（push + PR）", r"(?m)^name:\s+\S"),
    ("触发器声明（on: push/pull_request）", r"(?mi)^on:"),
    ("测试任务运行在 CI 机器（runs-on）", r"(?m)^\s*runs-on:\s*ubuntu-latest"),
    ("Python 版本与镜像对齐（3.12）", r"(?m)python-version:.*3\.12"),
    ("依赖安装走 requirements（锁定版本）", r"(?m)pip install -r requirements\.txt"),
    ("pip 缓存（setup-python cache: pip）", r"(?m)cache:\s*pip"),
    ("静态检查步骤（ruff/compileall）", r"(?m)ruff check"),
    ("测试命令指向 tests/ 且安静模式", r"(?m)pytest tests/ -q"),
    ("CI 强制 Mock 模式（LLM_MODE=mock，不联网不花钱）", r"(?m)LLM_MODE:\s*mock"),
    ("部署任务依赖测试与构建（needs: build）", r"(?m)needs:\s*build"),
    ("部署使用受保护环境（environment: production）", r"(?m)environment:\s*production"),
    ("密钥只走 secrets 注入（不硬编码）", r"(?m)\$\{\{ secrets\." ),
]


def main() -> int:
    text = YAML_PATH.read_text(encoding="utf-8")
    print(f"静态检查目标：{YAML_PATH}")
    print()
    failed = 0
    for name, pattern in CHECKS:
        ok = re.search(pattern, text) is not None
        failed += (not ok)
        print(f"  [{'✓' if ok else '✗'}] {name}")
    print(f"\n结果：{len(CHECKS) - failed}/{len(CHECKS)} 项通过")
    print("说明：仅验证 YAML 文本特征，不等价于流水线可运行（沙箱无 GitHub，")
    print("未实际触发过 workflow）。读者采用前需在真实仓库触发并观察一次。")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
