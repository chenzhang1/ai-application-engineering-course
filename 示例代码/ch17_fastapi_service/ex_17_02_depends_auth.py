# EX-17-02 | Depends 依赖注入：API Key 鉴权链（依赖可以再依赖，最终共享请求级状态）
# 运行：python3 示例代码/ch17_fastapi_service/ex_17_02_depends_auth.py
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

app = FastAPI(title="Depends 鉴权演示")

_FAKE_USERS = {"key-alice": {"name": "alice", "role": "admin"},
               "key-bob": {"name": "bob", "role": "viewer"}}


def get_user(api_key: str = Header(alias="X-API-Key")) -> dict:
    """一级依赖：从请求头取 Key 查用户。查不到抛 401——异常会中断请求，不会进入业务函数。"""
    user = _FAKE_USERS.get(api_key)
    if user is None:
        raise HTTPException(status_code=401, detail="无效的 API Key")
    return user


def require_admin(user: dict = Depends(get_user)) -> dict:
    """二级依赖：依赖另一个依赖（Java 对照：Spring 的 Filter→Interceptor→@PreAuthorize 链，
    但 Depends 是"函数参数级"的组合，粒度到每个端点，显式声明、无反射魔法）。"""
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="需要 admin 角色")
    return user


class Me(BaseModel):
    name: str
    role: str


@app.get("/me", response_model=Me)
def whoami(user: dict = Depends(get_user)) -> Me:
    return Me(name=user["name"], role=user["role"])


@app.delete("/orders/{order_id}")
def delete_order(order_id: str, admin: dict = Depends(require_admin)) -> dict:
    return {"deleted": order_id, "by": admin["name"]}


def main() -> None:
    with TestClient(app) as client:
        r = client.get("/me", headers={"X-API-Key": "key-alice"})
        print(f"[合法Key]  status={r.status_code}  body={r.json()}")

        r = client.get("/me")  # 缺头：Header 必填校验失败
        print(f"[缺Key]    status={r.status_code}  detail={r.json()['detail']}")

        r = client.get("/me", headers={"X-API-Key": "key-bob"})
        print(f"[Key存在但未注册/无效] bob 在册：{r.status_code}")
        r = client.get("/me", headers={"X-API-Key": "wrong-key"})
        print(f"[非法Key]  status={r.status_code}  detail={r.json()['detail']}")

        r = client.delete("/orders/ORD-00001", headers={"X-API-Key": "key-bob"})
        print(f"[权限不足] status={r.status_code}  detail={r.json()['detail']}（403 由二级依赖抛出）")
        r = client.delete("/orders/ORD-00001", headers={"X-API-Key": "key-alice"})
        print(f"[管理员]   status={r.status_code}  body={r.json()}")


if __name__ == "__main__":
    main()
