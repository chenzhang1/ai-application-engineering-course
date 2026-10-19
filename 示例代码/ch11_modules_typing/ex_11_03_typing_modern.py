# EX-11-03 | typing 类型注解体系：TypedDict / Protocol / Literal / TypeVar / Annotated
# 运行：python3 示例代码/ch11_modules_typing/ex_11_03_typing_modern.py
"""完整可运行：现代注解写法（3.10+）速览——给静态检查器看，也给人类看。"""
from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Literal, Protocol, TypedDict, TypeVar, runtime_checkable

# ---- 1. 内置泛型写法：list[str]、dict[str, int]（3.9+；旧写法 typing.List 已过时）----
ids: list[str] = ["SO-1", "SO-2"]
price_by_id: dict[str, float] = {"SO-1": 99.0}

# ---- 2. Optional 的现代写法：str | None（旧写法 Optional[str] / Union[str, None]）----
def find_order(order_id: str) -> dict[str, str] | None:  # ↔ Java 的 Optional<Map<...>>
    db = {"SO-1": {"status": "PAID"}}
    return db.get(order_id)


# ---- 3. TypedDict：给"字典"定义结构（Java record 的远亲——相似在形状，差异在校验时机）----
class OrderDict(TypedDict):
    order_id: str
    amount: float
    status: Literal["CREATED", "PAID", "SHIPPED"]  # Literal：值只能取列出的字面量


def describe(order: OrderDict) -> str:
    return f"{order['order_id']}（{order['status']}）: {order['amount']:.2f} 元"


# ---- 4. Protocol：结构化子类型——"长得像"就行，不需要继承（Java 没有的能力）----
@runtime_checkable
class Greeter(Protocol):
    def greet(self) -> str: ...


class Robot:  # 没有继承任何东西
    def greet(self) -> str:
        return "机器人向你问好"


class Stone:  # 没有 greet 方法
    pass


# ---- 5. TypeVar：泛型函数（↔ Java 的 <T>）----
T = TypeVar("T")


def first_or_default(items: list[T], default: T) -> T:
    return items[0] if items else default


# ---- 6. Callable：把"函数类型"当作一等公民标注 ----
def make_adder(step: int) -> Callable[[int], int]:
    return lambda x: x + step


# ---- 7. Annotated：给类型附加元数据（Pydantic/FastAPI 用它承载校验规则）----
OrderAmount = Annotated[float, "必须 > 0，由 Pydantic 在运行时校验（ch16）"]


def log_amount(amount: OrderAmount) -> None:
    print(f"金额 {amount}（注解里的元数据运行时不校验，见 ex_11_04）")


def main() -> None:
    order: OrderDict = {"order_id": "SO-1", "amount": 99.5, "status": "PAID"}
    print("[TypedDict+Literal]", describe(order))

    print("[Optional 现代写法]", find_order("SO-1"), "| 查不到 →", find_order("SO-404"))

    print("[Protocol] Robot 是 Greeter 吗:", isinstance(Robot(), Greeter))
    print("[Protocol] Stone 是 Greeter 吗:", isinstance(Stone(), Greeter))
    # 注意：runtime_checkable 的 isinstance 只检查"有没有该方法"，不检查签名/返回值

    print("[TypeVar]", first_or_default([1, 2, 3], default=0),
          "| 空列表:", first_or_default(list[str](), default="空"))
    print("[Callable]", make_adder(100)(23))

    print("[Annotated]", end=" ")
    log_amount(88.8)


if __name__ == "__main__":
    main()
