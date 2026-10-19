# EX-11-05 | 循环导入：报错现场与两种解法
# 运行：python3 示例代码/ch11_modules_typing/ex_11_05_circular_import.py
"""完整可运行：用子进程触发 circular_bad 的真实报错，再验证 circular_good 的修复。"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> None:
    print("[1] 坏写法现场：python -m circular_bad.a（子进程真实运行，捕获真实报错）")
    proc = subprocess.run(
        [sys.executable, "-m", "circular_bad.a"],
        cwd=HERE, capture_output=True, text=True, check=False,
    )
    print(f"    退出码: {proc.returncode}")
    print("    " + proc.stderr.strip().replace("\n", "\n    "))

    print("\n[2] 好写法验证：调整顺序/导入模块对象后，环解开")
    from circular_good.a import greet_a  # noqa: E402  # 放在函数内，演示用

    print("    " + greet_a())

    print("\n[3] 三种解法备忘：")
    print("    a) 重排模块内语句顺序（把被依赖的定义放在 import 之前）")
    print("    b) from xx import yy → import xx（用模块对象，调用时才解析属性）")
    print("    c) 把 import 挪进函数体内（延迟导入，最后手段）")


if __name__ == "__main__":
    main()
