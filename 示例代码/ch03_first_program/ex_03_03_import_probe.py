# EX-03-03 | 运行命令: python3 示例代码/ch03_first_program/ex_03_03_import_probe.py
"""依赖冲突探针：逐个导入关键包，打印版本或失败原因。

用法：在"怀疑装坏了"的解释器上运行它，一次看清哪些包能导入、
版本是多少。排查思路：pip check 管元数据一致性，本探针管真实导入。
探针本身必须兜住一切异常——它就是在烂环境里跑的工具。
"""
from __future__ import annotations

import importlib
import importlib.metadata

PROBE = ["pydantic", "pydantic_settings"]


def probe(names: list[str]) -> list[str]:
    lines: list[str] = []
    for name in names:
        try:
            module = importlib.import_module(name)
            version = importlib.metadata.version(name)
            lines.append(f"[OK]   {name} {version}（模块 {module.__name__}）")
        except Exception as exc:  # noqa: BLE001 排查工具必须兜底
            lines.append(f"[FAIL] {name}: {type(exc).__name__}: {exc}")
    return lines


def main() -> None:
    for line in probe(PROBE):
        print(line)


if __name__ == "__main__":
    main()
