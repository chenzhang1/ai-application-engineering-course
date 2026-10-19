# demo_shop/textfmt/textutil.py | EX-11-02 支撑文件：跨层相对导入（.. 回到上一级包）
"""演示两级相对导入：from ..core 表示"上一级包 demo_shop 里的 core 模块"。"""
from __future__ import annotations

from ..core import CURRENCY, Order  # .. = 上一级包（demo_shop），. = 本包（textfmt）


def format_receipt(order: Order) -> str:
    """把订单格式化成收据文本。"""
    lines = [f"===== 收据 =====", order.summary()]
    for item in order.items:
        lines.append(f"  - {item}")
    lines.append(f"金额：{CURRENCY} {order.amount:.2f}")
    return "\n".join(lines)
