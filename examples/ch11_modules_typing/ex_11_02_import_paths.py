# EX-11-02 | import 搜索路径与包结构：__init__.py、相对导入
# 运行：python3 examples/ch11_modules_typing/ex_11_02_import_paths.py
"""完整可运行：观察 sys.path、导入 demo_shop 包、验证相对导入与包门面。"""
from __future__ import annotations

import sys

# 脚本所在目录会被自动放进 sys.path[0]，所以同目录的 demo_shop 包能被找到
print("[1] sys.path 前 3 项（解释器找模块的搜索顺序）:")
for i, p in enumerate(sys.path[:3]):
    print(f"    sys.path[{i}] = {p}")

print("\n[2] 导入包并使用包门面导出的名字:")
import demo_shop                                  # 包：目录 + __init__.py
from demo_shop import Order, calc_total           # 从包门面直接拿（不必知道具体模块）
from demo_shop.textfmt import format_receipt      # 子包：demo_shop/textfmt/

print("    demo_shop.__file__ =", demo_shop.__file__)
print("    demo_shop.__all__  =", demo_shop.__all__)

order = Order(order_id="SO-3001", customer="李工", items=["键盘", "显示器"], amount=4999.0)
print("    calc_total:", calc_total(order, tax_rate=0.13))
print("    format_receipt（textfmt 里用了 from ..core 相对导入）:")
print("    " + format_receipt(order).replace("\n", "\n    "))

print("\n[3] 包的层次就是一个目录树:")
print("    demo_shop/            ← 包（有 __init__.py）")
print("    ├── core.py           ← 模块")
print("    ├── pricing.py        ← 模块")
print("    └── textfmt/          ← 子包")
print("        ├── __init__.py")
print("        └── textutil.py   ← 模块（from ..core import ...）")

print("\n[4] 导入不存在的模块会怎样（EAFP 风格，ch08 呼应）:")
try:
    import demo_shop.nonexistent  # type: ignore[import-not-found]  # 故意演示
except ModuleNotFoundError as exc:
    print(f"    ModuleNotFoundError: {exc}")
