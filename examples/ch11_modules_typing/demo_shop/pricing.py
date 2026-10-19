# demo_shop/pricing.py | EX-11-02 支撑文件：定价逻辑
"""定价计算：演示"包内模块互相导入"的两种写法。"""
from __future__ import annotations

from .core import Order, CURRENCY  # 相对导入（包内推荐写法）
# 等价绝对导入：from demo_shop.core import Order, CURRENCY


def calc_total(order: Order, tax_rate: float = 0.0) -> float:
    """计算含税总额（示例逻辑，非真实计价规则）。"""
    total = order.amount * (1 + tax_rate)
    return round(total, 2)
