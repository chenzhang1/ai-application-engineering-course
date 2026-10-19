# demo_shop/core.py | EX-11-02 支撑文件：领域模型
"""核心领域模型（对照 Java 的实体类）。"""
from __future__ import annotations

from dataclasses import dataclass, field

CURRENCY: str = "CNY"  # 包级常量：Java 里相当于 public static final


@dataclass
class Order:
    """一张订单（dataclass 详见 ch07）。"""
    order_id: str
    customer: str
    items: list[str] = field(default_factory=list)
    amount: float = 0.0

    def summary(self) -> str:
        return f"订单 {self.order_id}（{self.customer}）：{len(self.items)} 件商品"
