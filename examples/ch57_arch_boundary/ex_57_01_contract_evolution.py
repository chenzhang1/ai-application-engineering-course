# EX-57-01 | 序列化契约演进：只加不改的兼容性规则 | 运行: python3 examples/ch57_arch_boundary/ex_57_01_contract_evolution.py
"""完整可运行（纯标准库 + pydantic，离线）：演示 Python AI 服务与 Spring Boot 客户端
之间的 JSON 序列化契约如何"安全演进"。

三条规则（本章正文展开）：
  R1 新增字段必须带默认值        → 旧客户端解析新响应：兼容（多出的字段被忽略）
  R2 删除/改名字段              → 旧客户端解析新响应：直接炸（必填字段缺失）
  R3 改字段类型/语义            → 比删除更隐蔽：能解析但含义错了，事故在下游
"""
from __future__ import annotations

from pydantic import BaseModel, ValidationError


# ── AI 服务侧的响应契约 ────────────────────────────────────────────────
# V1：上线时的版本（Spring 客户端按它写的 DTO）。注意 refs 是必填——
# 这是"引用溯源"产品的硬承诺，所以进了契约的必填区（可选字段见 V1 的边界说明）。
class AIReplyV1(BaseModel):
    answer: str
    refs: list[str]               # 必填：无引用的回答不符合产品承诺


# V2：第一次演进——"新增"一个字段，带默认值（规则 R1）
class AIReplyV2(AIReplyV1):
    confidence: float = 0.0       # 新增：模型置信度。旧客户端不认识它，但没关系


# V3（反面教材）：第二次"演进"——把 refs 从字符串列表改成了对象列表（规则 R3）
class AIReplyV3Broken(BaseModel):
    answer: str
    refs: list[dict[str, str]] = []   # [ {"doc_id": "...", "quote": "..."} ]


def main() -> None:
    # ── 场景 1：V2 服务返回新响应，V1 时代的 Spring 客户端（用 V1 模型模拟）解析 ──
    v2_payload = {"answer": "年假不清零，可结转。", "refs": ["HR-007"],
                  "confidence": 0.87}
    old_client_view = AIReplyV1.model_validate(v2_payload)
    print("[场景1] V2 响应 → V1 客户端（新增字段带默认值）")
    print(f"        解析成功：answer={old_client_view.answer!r}，"
          f"refs={old_client_view.refs}（confidence 被安全忽略）→ 兼容 ✓")

    # ── 场景 2：服务端"顺手"删掉必填的 refs 字段（规则 R2 的代价）──
    removed_refs_payload = {"answer": "年假不清零，可结转。"}
    print("[场景2] 删除必填字段 refs → V1 客户端")
    try:
        AIReplyV1.model_validate(removed_refs_payload)
    except ValidationError as exc:
        print(f"        解析失败：{exc.errors()[0]['type']} "
              f"loc={exc.errors()[0]['loc']} → 破坏契约 ✗（Spring 侧反序列化同样会抛异常）")
    print("        边界：若字段本来就是可选带默认值，删除不会让解析报错，但读到默认值的")
    print("        客户端行为仍可能改变——删字段永远要走评审，'解析不炸'不等于'语义无害'。")

    # ── 场景 3：refs 类型悄悄从 list[str] 变成 list[dict]（规则 R3 的隐蔽性）──
    v3_payload = {"answer": "年假不清零，可结转。",
                  "refs": [{"doc_id": "HR-007", "quote": "年假可结转"}]}
    print("[场景3] refs 改类型 list[str]→list[dict] → V1 客户端")
    try:
        AIReplyV1.model_validate(v3_payload)
    except ValidationError as exc:
        print(f"        解析失败：{exc.errors()[0]['type']}（期望 str 得到 dict）→ 破坏契约 ✗")
    else:  # 兜底断言：本例必然抛错，走到这里说明实验设计有 bug
        raise AssertionError("场景 3 预期 ValidationError，实际解析成功——示例本身出了问题")

    print("\n[契约演进军规]")
    print("  R1 新增字段必须带默认值（旧端忽略未知字段）")
    print("  R2 永不删除/改名已有字段；要下线就先停止写入、观察一个版本周期再删")
    print("  R3 类型与语义冻结；确需变更 → 换新字段 + 新版本路径（/v2/ask）双跑过渡")
    print("  R4 契约测试进 CI：把本示例的三个场景写成 pytest（tests/test_ch57.py 即做了）")


if __name__ == "__main__":
    main()
