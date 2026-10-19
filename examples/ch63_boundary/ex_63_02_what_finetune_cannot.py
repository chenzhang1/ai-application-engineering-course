# EX-63-02 | 微调做不了什么：知识时效与权限（教学模拟对照） | 运行: python3 examples/ch63_boundary/ex_63_02_what_finetune_cannot.py
"""完整可运行（共享 MockLLM + 纯标准库，离线）：两个"微调解决不了"的对照实验。

【诚实标注】MockLLM 脚本扮演"用 2025 年政策语料微调过的模型"——它的回答由脚本
预设，用于演示问题方向（时效/权限为何不该指望微调），不是真实训练产物。
真实模型的行为规律（知识截止、权重静态）见正文 63.3 的逐条说理。

实验 A（知识时效）：新政策发布后，微调模型仍答旧口径；RAG 检索新文档即答新口径。
实验 B（权限）：权限是运行时上下文——同一个模型实例服务所有用户，权重里不存在
  "当前调用者是谁"；权限过滤只能发生在代码层（检索过滤/工具校验，ch58）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from examples.common.llm_client import MockLLM  # noqa: E402

QUESTION_NEW_POLICY = "2026 年新版年假政策是什么？"

# ── 实验 A：知识时效 ─────────────────────────────────────────────────────
# "微调模型"：训练语料截止在 2025 年——它只认识旧政策（新知识不在权重里）
sft_model = MockLLM(script=[
    {"content": "年假政策：入职满一年 5 天。（2025 年版《考勤管理办法》）"},
])
# "RAG 流程"：同一份底层模型，但检索到了 2026 年新文件
KB_2026 = {"content": "2026 年新版《考勤管理办法》：入职满一年年假 8 天，可结转次年。",
           "doc_id": "HR-2026-011", "version": "v2026"}


def rag_answer(question: str) -> str:
    ctx = KB_2026["content"]                       # 检索阶段：命中 2026 新文件
    llm = MockLLM(script=[
        {"content": f"依据 {KB_2026['doc_id']}（{KB_2026['version']}）：入职满一年年假 8 天，可结转次年。"},
    ])
    return llm.chat([
        {"role": "system", "content": "你是制度问答助手，只依据检索到的文件回答并注明文件编号。"},
        {"role": "user", "content": f"检索结果：{ctx}\n\n问题：{question}"},
    ]).content


# ── 实验 B：权限 ─────────────────────────────────────────────────────────
def check_salary_permission(caller: str, target: str) -> bool:
    """代码层的权限判定：只认会话身份（谁登录了），不认消息里自称什么。"""
    return caller == target                        # 只能看自己的薪资单


def main() -> None:
    print("【教学模拟声明】以下'微调模型'的回答由 MockLLM 脚本预设，演示问题方向而非真实训练行为。\n")

    print("── 实验 A：知识时效——新政策发布后 ──")
    print(f"    问题：{QUESTION_NEW_POLICY}")
    sft_out = sft_model.chat([{"role": "user", "content": QUESTION_NEW_POLICY}]).content
    print(f"    微调模型：{sft_out}")
    print(f"    RAG 模型：{rag_answer(QUESTION_NEW_POLICY)}")
    print("    说理：微调把知识'冻'进权重——更新知识 = 重新标注 + 重新训练 + 重新评估，")
    print("          周期以周/月计；政策每月变，微调永远追不上。RAG 换检索库即换知识，分钟级生效，")
    print("          还能引用与按权限过滤。→ 知识时效问题的答案是 RAG/工具查询，不是微调。")

    print("\n── 实验 B：权限——同一个模型实例，谁都有权'问'，没权'看' ──")
    alice_q = "帮我看一下张三的薪资单"
    print(f"    alice 问模型：{alice_q!r}")
    print("    模型视角：这只是一段文本——权重是静态的、全局的，模型不知道'这次调用来自 alice'；")
    print("              就算把权限规则微调进模型，也无法验证、无法审计、无法按租户隔离（ch58.3）。")
    caller = "alice"
    allowed = check_salary_permission(caller, "zhangsan")
    print(f"    代码层判定：caller={caller} 访问 zhangsan 的薪资单 → allowed={allowed}")
    print("    正确架构：检索前按会话身份过滤数据（看不到的文档根本不进上下文，ch34 红线）+")
    print("              工具执行前校验权限（EX-58-03）——模型只在'被允许的数据'上生成。")

    print("\n── 结论对照表（正文 63.3 逐条展开）──")
    print("  ┌────────┬──────────────────────────┬───────────────────────┐")
    print("  │ 问题   │ 微调能不能解决           │ 正确工具              │")
    print("  ├────────┼──────────────────────────┼───────────────────────┤")
    print("  │ 知识时效│ 不能（重训周期追不上更新）│ RAG / 工具查询        │")
    print("  │ 幻觉   │ 缓解有限且不可验证       │ 引用+拒答+评估（ch35）│")
    print("  │ 权限   │ 不能（权重无运行时上下文）│ 检索过滤+工具权限+审计│")
    print("  └────────┴──────────────────────────┴───────────────────────┘")


if __name__ == "__main__":
    main()
