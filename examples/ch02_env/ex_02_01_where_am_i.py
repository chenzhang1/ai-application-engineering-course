# EX-02-01 | 运行命令: python3 examples/ch02_env/ex_02_01_where_am_i.py
"""确认"当前运行的是哪个解释器、哪个环境"。

排错第一步永远是先搞清楚：我调的是哪个 python、装在哪个目录、
在不在虚拟环境里。这个脚本就是把这件事打印出来。
"""
from __future__ import annotations

import sys
import sysconfig
from pathlib import Path


def describe() -> dict[str, str]:
    """收集当前解释器的关键信息。"""
    site_packages = Path(sysconfig.get_paths()["purelib"])
    return {
        "python版本": sys.version.split()[0],
        "解释器路径": sys.executable,
        "sys.prefix": sys.prefix,
        "base_prefix": sys.base_prefix,
        "是否在venv": "是" if sys.prefix != sys.base_prefix else "否（全局解释器）",
        "site-packages": str(site_packages),
    }


def main() -> None:
    for key, value in describe().items():
        print(f"{key:>14}: {value}")


if __name__ == "__main__":
    main()
