# EX-30-02 | 什么时候不用 RAG：四种方案的 token 算账与决策表 | 运行: python3 examples/ch30_rag_why/ex_30_02_decision_matrix.py
"""完整可运行（真实 token 计数）：把"方案选型"从感觉变成算术——
同一份知识（5 篇制度文档），比较三种喂法的 token 成本：
A 长上下文全量塞入、B RAG 只塞 top-3、C 微调（0 上下文但另有训练成本），
再给出"什么时候该用工具查询而不是 RAG"的边界。决策依据用真实算出的数字。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np  # noqa: E402

from examples.common.embeddings import cosine_similarity, get_embedder  # noqa: E402
from examples.common.llm_client import count_tokens  # noqa: E402

POLICY_DOCS = {
    "hr_leave": "公司年假于每年 12 月 31 日 24 点清零，不可结转。病假超过 3 天需医院证明。事假提前 1 个工作日申请。",
    "finance_reimburse": "报销需在费用发生后 30 天内提交，每月 25 日为截止日。5000 元以上需财务总监加签。",
    "finance_travel": "高铁一律二等座，飞机经济舱。一线城市住宿上限每晚 600 元，其他城市 400 元。餐补每天 100 元。",
    "it_vpn": "VPN 权限由主管审批后 2 个工作日开通。登录启用双因素认证，验证码收不到先检查手机时间同步。",
    "admin_meeting": "会议室最多提前 7 天预约，开始后 15 分钟未签到自动释放。当月 3 次爽约暂停预约权限 1 周。",
}
QUERY = "年假年底会清零吗？"
TOP_K = 3


def main() -> None:
    n, method = count_tokens(" ".join(POLICY_DOCS.values()))
    assert method == "tiktoken:cl100k_base", f"token 计数方式异常：{method}"

    # ---- 三种喂法的上下文 token 账（每次请求都要付的钱）----
    plan_a_text = "以下是公司全部制度文档：\n" + "\n".join(POLICY_DOCS.values())
    plan_a = count_tokens(plan_a_text)[0] + count_tokens(QUERY)[0]

    emb = get_embedder()
    q_vec = np.asarray(emb.embed_one(QUERY))
    ranked = sorted(POLICY_DOCS.items(),
                    key=lambda kv: cosine_similarity(q_vec, np.asarray(emb.embed_one(kv[1]))),
                    reverse=True)
    topk = ranked[:TOP_K]
    plan_b_text = "以下是相关制度片段：\n" + "\n".join(f"[{i}] {t}" for i, (_, t) in enumerate(topk, 1))
    plan_b = count_tokens(plan_b_text)[0] + count_tokens(QUERY)[0]

    print(f"[知识库规模] {len(POLICY_DOCS)} 篇文档，正文共 {n} tokens")
    print(f"\n[方案 A：长上下文全量塞入]   每次请求 ≈ {plan_a:>4} tokens（全部知识 + 问题）")
    print(f"[方案 B：RAG 只塞 top-{TOP_K}]       每次请求 ≈ {plan_b:>4} tokens"
          f"（命中 {[d for d, _ in topk]}）")
    print(f"[方案 C：微调（SFT）]        每次请求 ≈ {count_tokens(QUERY)[0]:>4} tokens"
          f"（知识进了参数；但训练数据/算力/评估是一次性大额投入，且更新知识=重新训练）")
    print(f"\n本次对比：RAG 比全量塞入每次省 {plan_a - plan_b} tokens；"
          f"当知识库是 5000 篇文档时，方案 A 直接爆上下文窗口——"
          f"这就是'知识量大'压垮长上下文的算术。")

    # ---- 决策表：四个维度各归各的方案 ----
    rows = [
        ("知识量小（<几千 token）且极少变化", "长上下文", "塞一次省掉整套检索设施；简单问题别上重武器"),
        ("知识量大 / 更新频繁 / 有权限隔离", "RAG", "更新=改文档；权限在检索层过滤（ch34）"),
        ("要改变风格、格式、任务模式（不是注入知识）", "微调", "SFT 教'怎么做'，RAG 送'要知道什么'——两者常混用"),
        ("答案是实时/精确数据（汇率、库存、订单状态）", "工具查询", "RAG 送的是'文本'，算不出实时值；让模型调 API（ch24）"),
        ("问题本质是'算'（报表、统计）", "工具查询", "检索 10 篇文档也凑不出正确的 SUM——别用 RAG 硬算"),
    ]
    print("\n[决策表] 需求特征 → 首选方案 → 一句话理由")
    print("-" * 88)
    for need, choice, why in rows:
        print(f"  {need:<30} → {choice:<6} ｜ {why}")
    print("-" * 88)
    print("[反直觉提醒] RAG 不是默认答案：先问'知识会不会变、多大、要不要权限、要不要实时'，")
    print("    四问里有三个说'不'，长上下文或工具查询通常更便宜、更简单、更可测。")
    print(f"[诚实声明] 本例 token 数字为真实 tiktoken 计数（{method}）；"
          f"方案 C 的训练成本未在本书实测，只给量级判断依据。")


if __name__ == "__main__":
    main()
