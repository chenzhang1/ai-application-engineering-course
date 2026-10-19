# EX-16-02 | field_validator（单字段）与 model_validator（跨字段）实战
# 运行：python3 examples/ch16_pydantic/ex_16_02_validators.py
from pydantic import BaseModel, ValidationError, field_validator, model_validator


class RefundRequest(BaseModel):
    """退款申请：演示三种校验层次的分工——字段格式 / 字段规范化 / 跨字段业务规则。"""
    order_id: str
    amount: float
    currency: str = "CNY"
    reason: str

    @field_validator("order_id")
    @classmethod
    def normalize_order_id(cls, v: str) -> str:
        """单字段规范化：去空格、转大写，再检查格式。返回值会成为字段的最终值。"""
        v = v.strip().upper()
        if not v.startswith("ORD-"):
            raise ValueError("order_id 必须以 ORD- 开头")
        return v

    @field_validator("amount")
    @classmethod
    def check_amount(cls, v: float) -> float:
        if v <= 0 or v > 50_000:
            raise ValueError("退款金额必须在 (0, 50000] 内")
        return v

    @model_validator(mode="after")
    def check_business_rules(self) -> "RefundRequest":
        """跨字段规则：校验的是整个模型（self），适合'字段之间'的约束。"""
        if self.currency not in {"CNY", "USD"}:
            raise ValueError(f"暂不支持币种 {self.currency}")
        if self.reason == "质量投诉" and self.amount > 10_000:
            raise ValueError("质量投诉类退款单笔上限 10000，请走人工审核通道")
        return self


def main() -> None:
    ok = RefundRequest(order_id=" ord-00999 ", amount=199.0, reason="漏发货")
    print(f"[通过] order_id 被规范化为：{ok.order_id}（strip+upper 生效）")

    # 跨字段规则拦截：单独看每个字段都合法，合在一起才违规
    try:
        RefundRequest(order_id="ORD-00999", amount=20000.0, reason="质量投诉")
    except ValidationError as exc:
        for err in exc.errors():
            print(f"[拦截] 跨字段规则：loc={err['loc']}  msg={err['msg']}")

    # 字段级规则拦截
    try:
        RefundRequest(order_id="PAY-00999", amount=199.0, reason="其他")
    except ValidationError as exc:
        for err in exc.errors():
            print(f"[拦截] 字段规则：loc={err['loc']}  type={err['type']}  msg={err['msg']}")


if __name__ == "__main__":
    main()
