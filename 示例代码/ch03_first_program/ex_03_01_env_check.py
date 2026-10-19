# EX-03-01 | 运行命令: python3 示例代码/ch03_first_program/ex_03_01_env_check.py
"""第一个程序：环境体检（飞机起飞前检查单）。

做三件事：
1. 检查 Python 版本是否达到本书下限（3.10）；
2. 检查本书首批必需依赖是否装齐、各是什么版本；
3. 全部通过打印"体检通过"并以退出码 0 结束；任一失败打印缺失项
   并以退出码 1 结束（CI 与 shell 可据此拦截）。
纯标准库实现，任何 venv 里都能跑——包括"什么都没装"的干净 venv。
"""
from __future__ import annotations

import importlib.metadata
import sys

REQUIRED_MIN = (3, 10)
REQUIRED_PACKAGES = ["pydantic", "pydantic-settings", "httpx"]


def is_compatible(current: tuple[int, int], minimum: tuple[int, int]) -> bool:
    """纯函数：当前版本是否达到最低要求（元组逐位比较）。"""
    return current >= minimum


def collect_env_info(packages: list[str]) -> dict[str, str]:
    """收集解释器版本与各依赖包的安装版本；未安装记为"缺失"。"""
    info = {
        "python": ".".join(str(n) for n in sys.version_info[:3]),
        "executable": sys.executable,
    }
    for name in packages:
        try:
            info[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            info[name] = "缺失"
    return info


def main() -> int:
    info = collect_env_info(REQUIRED_PACKAGES)
    current = (sys.version_info.major, sys.version_info.minor)
    ok = True

    if not is_compatible(current, REQUIRED_MIN):
        print(f"[不通过] Python {current} 低于本书下限 {REQUIRED_MIN}")
        ok = False
    else:
        print(f"[通过] Python {info['python']} >= {REQUIRED_MIN[0]}.{REQUIRED_MIN[1]}")

    for name in REQUIRED_PACKAGES:
        version = info[name]
        if version == "缺失":
            print(f"[不通过] {name}: 缺失（请先 pip install -r requirements.txt）")
            ok = False
        else:
            print(f"[通过] {name}: {version}")

    if ok:
        print("体检通过：可以开始跑本书示例了。")
        return 0
    print("体检未通过：请先补齐上面的缺失项。")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
