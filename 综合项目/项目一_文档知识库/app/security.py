# P1 多租户权限（检索前过滤的依据） | ch28 红线的代码落点
"""权限模型：租户隔离 + 部门级可见性。

核心原则（与教材 ch28/ch34 一致）：
- 身份来自"会话/请求上下文"（这里简化为请求字段；生产从 JWT/Session 解析），
  绝不来自问题文本或模型输出；
- 过滤发生在"打分之前"——无权文档根本不进入候选集，不参与排序、
  不进入上下文、不出现在引用里。事后过滤（先排序再删）会泄露
  "有这文档但你看不到"的信息，也浪费召回名额。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UserContext:
    """请求发起者：租户 + 可见部门集合。"""

    user_id: str
    tenant_id: str
    departments: frozenset[str]

    @staticmethod
    def of(user_id: str, tenant_id: str, departments: list[str] | tuple[str, ...]) -> "UserContext":
        return UserContext(user_id=user_id, tenant_id=tenant_id,
                           departments=frozenset(departments))


def can_read(doc_tenant_id: str, doc_department: str, user: UserContext) -> bool:
    """单个 chunk 的可见性判定。

    规则：
    1. 租户不同 → 一律不可见（即使部门匹配）；
    2. 文档 department == "all" → 租户内公开（FAQ 类）；
    3. 用户的 departments 含 "all" → 租户内全可见（管理员语义）；
    4. 否则要求文档部门在用户可见部门列表里。
    """
    if doc_tenant_id != user.tenant_id:
        return False
    return doc_department == "all" or "all" in user.departments or doc_department in user.departments
