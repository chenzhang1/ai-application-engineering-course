# EX-16-01 | Pydantic v2 BaseModel 基础：字段类型与约束、校验失败的样子
# 运行：python3 examples/ch16_pydantic/ex_16_01_basics.py
from pydantic import BaseModel, Field, ValidationError


class Order(BaseModel):
    """订单模型：类型注解即校验规则（Java 对照：Bean Validation 注解 + Jackson 二合一）。"""
    order_id: str = Field(pattern=r"^ORD-\d{5}$", examples=["ORD-12345"])
    amount: float = Field(gt=0, le=100_000)          # 0 < amount ≤ 10万
    quantity: int = Field(ge=1, default=1)            # ≥1，缺省 1
    tags: list[str] = Field(default_factory=list)     # 可变默认值必须用 default_factory
    memo: str | None = None                           # 可选字段（None 是合法值）


def main() -> None:
    # 正常路径：从 dict 构造（等价于把外部输入"装进"强类型对象）
    order = Order(order_id="ORD-12345", amount=99.5, tags=["vip", "urgent"])
    print(f"[正常] {order.model_dump()}")          # 模型 → dict
    print(f"[正常] quantity 取了默认值 1：{order.quantity}，memo 为 None：{order.memo is None}")

    # 校验失败：构造时立刻抛 ValidationError（不是等到访问字段才炸——运行时校验前移）
    try:
        Order(order_id="ORD-12", amount=-5)  # 两个约束都不满足
    except ValidationError as exc:
        print(f"[失败] 共捕获 {exc.error_count()} 个错误：")
        for err in exc.errors():
            print(f"    loc={err['loc']}  type={err['type']}  msg={err['msg']}")

    # 类型也会自动尝试转换：int 字段收到 "3" 字符串会被转成 3（宽松模式，Java 的 Jackson 反之默认严格）
    order2 = Order(order_id="ORD-00001", amount=10, quantity="3")
    print(f"[宽松转换] quantity 收到字符串 '3'，实际类型 {type(order2.quantity).__name__}，值 {order2.quantity}")


if __name__ == "__main__":
    main()
