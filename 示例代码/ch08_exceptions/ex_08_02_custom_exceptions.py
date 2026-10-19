# EX-08-02 | 自定义异常与业务异常基类 | 运行: python3 示例代码/ch08_exceptions/ex_08_02_custom_exceptions.py
class AppError(Exception):
    """本项目所有业务异常的基类：统一 code，方便上层一次捕获。"""

    code: str = "APP_ERROR"

    def __init__(self, message: str, *, detail: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.detail: dict[str, object] = detail or {}


class ValidationError(AppError):
    code = "VALIDATION_ERROR"


class NotFoundError(AppError):
    code = "NOT_FOUND"


class LlmQuotaExceededError(AppError):
    code = "LLM_QUOTA_EXCEEDED"


def find_order(order_id: str) -> str:
    orders = {"A1001": "已发货"}
    if not order_id.startswith("A"):
        raise ValidationError(f"订单号格式非法: {order_id!r}", detail={"field": "order_id"})
    if order_id not in orders:
        raise NotFoundError(f"订单不存在: {order_id}", detail={"order_id": order_id})
    return orders[order_id]


def main() -> None:
    for order_id in ["A1001", "A4040", "B2002"]:
        try:
            result = find_order(order_id)
        except AppError as exc:          # 只捕获业务基类：第三方错误不会被误吞
            print(f"[{exc.code}] {exc} detail={exc.detail}")
        else:
            print(f"查询成功: {order_id} -> {result}")


if __name__ == "__main__":
    main()
