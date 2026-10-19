# EX-17-01 | FastAPI 参数声明：路径/查询/Body + 请求响应模型（Pydantic 接管校验）
# 运行：python3 examples/ch17_fastapi_service/ex_17_01_params_models.py
from fastapi import FastAPI, Path, Query
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

app = FastAPI(title="参数声明演示")


class OrderCreate(BaseModel):
    """请求体模型：FastAPI 自动用它校验 JSON，失败自动返回 422。"""
    sku: str = Field(min_length=2, max_length=32)
    quantity: int = Field(ge=1, le=999)


class OrderOut(BaseModel):
    """响应模型：response_model 做"输出过滤"，内部字段（如成本价）不会被泄露。"""
    order_id: str
    sku: str
    quantity: int
    unit_price: float


_DB: dict[str, dict] = {}


@app.post("/orders", response_model=OrderOut, status_code=201)
def create_order(body: OrderCreate) -> OrderOut:
    order_id = f"ORD-{len(_DB) + 10001:05d}"
    _DB[order_id] = {"order_id": order_id, "sku": body.sku, "quantity": body.quantity,
                     "unit_price": 9.9, "cost_price": 6.6}  # cost_price 不该出现在响应里
    return OrderOut(**_DB[order_id])


@app.get("/orders")
def list_orders(offset: int = Query(0, ge=0), limit: int = Query(10, ge=1, le=100)) -> dict:
    """查询参数：offset/limit 带范围约束。"""
    ids = list(_DB)[offset:offset + limit]
    return {"total": len(_DB), "items": [_DB[i] for i in ids]}


@app.get("/orders/{order_id}")
def get_order(order_id: str = Path(pattern=r"^ORD-\d{5}$")) -> dict:
    """路径参数：pattern 在进入函数前校验，格式不对直接 422，函数体永远拿到合法输入。"""
    return _DB[order_id]  # KeyError 在这里只可能因为"不存在"，与"格式非法"已被 422 分离


def main() -> None:
    with TestClient(app) as client:  # with 语句触发 lifespan（本例无 lifespan，只是习惯）
        r = client.post("/orders", json={"sku": "A100", "quantity": 2})
        print(f"[正常创建] status={r.status_code}  body={r.json()}")
        assert "cost_price" not in r.json(), "response_model 过滤了内部字段"

        r = client.get("/orders", params={"offset": 0, "limit": 10})
        print(f"[查询列表] status={r.status_code}  total={r.json()['total']}")

        r = client.post("/orders", json={"sku": "A", "quantity": 0})  # 两个约束都违反
        print(f"[非法Body] status={r.status_code}（422=不可处理的实体）  loc={[e['loc'] for e in r.json()['detail']]}")

        r = client.get("/orders/not-an-order")  # 不满足路径参数 pattern
        print(f"[非法路径参数] status={r.status_code}  detail={r.json()['detail'][0]['msg']}")


if __name__ == "__main__":
    main()
