# EX-40-02 | RunnablePassthrough.assign / RunnableParallel / RunnableConfig | 运行: python3 examples/ch40_lcel/ex_40_02_parallel_config.py
"""完整可运行（离线）：RAG 风格的"检索注入"管道（context 旁路注入 + 问题透传）、
并行分支（dict → RunnableParallel 的自动包装）、RunnableConfig 的 tags/metadata 贯穿。
"""
from __future__ import annotations

from langchain_core.runnables import (
    RunnableConfig,
    RunnableLambda,
    RunnableParallel,
    RunnablePassthrough,
)


def fake_retrieve(query: str) -> str:
    """桩检索器：真实实现见 EX-41-03（这里只演示管道形状）。"""
    return "《退货政策》7 天内可无理由退货，运费由商家承担。"


def main() -> None:
    print("[1] RunnablePassthrough.assign：往 dict 里'旁路注入'新键（RAG 标准姿势）：")
    inject = RunnablePassthrough.assign(context=RunnableLambda(fake_retrieve))
    out = inject.invoke({"question": "退货政策是什么？"})
    print(f"    输入 {dict(question='退货政策是什么？')}")
    print(f"    输出 {out}")
    print("    → 原键原样透传（question 没丢），新键 context 是检索结果；")
    print("      裸写法需要手工 copy dict，assign 是声明式的。")

    print("\n[2] RunnableParallel：同一输入喂给多个分支，结果按 key 合并：")
    parallel = RunnableParallel(
        answer=RunnableLambda(lambda x: f"回答分支收到：{x}"),
        length=RunnableLambda(lambda x: len(str(x))),
    )
    print(f"    invoke('你好') → {parallel.invoke('你好')}")
    print(f"    batch(['a', 'bc']) → {parallel.batch(['a', 'bc'])}")
    print("    → dict 走 | 时也会被自动包装成 RunnableParallel（本书显式写，意图更清楚）")
    print("    Java 对照 ≈ CompletableFuture.allOf(...) 聚合，但分支共享同一输入。")

    print("\n[3] RunnableConfig：tags/metadata 从 invoke 一路传到每个节点：")
    seen: list[tuple[str, list[str]]] = []

    def probe(x: dict, config: RunnableConfig) -> str:
        seen.append((config.get("run_name") or "unnamed", list(config.get("tags") or [])))
        return f"已处理 {x['question']}"

    pipe = RunnablePassthrough.assign(probed=probe) | RunnableLambda(lambda x: x["probed"])
    result = pipe.invoke({"question": "发票问题"},
                         config={"tags": ["tenant:acme", "env:prod"], "run_name": "faq-pipeline"})
    print(f"    结果：{result}")
    print(f"    每个节点看到的 config.tags = {seen}")
    print("    → trace_id/租户标签这类横切信息不再靠参数层层透传（对照 ch17 中间件思想）")

    print("\n[4] assign 的值也可以是完整链（检索注入 + 生成的雏形，EX-41-03 接上真实检索）：")
    rag_shape = RunnablePassthrough.assign(context=RunnableLambda(fake_retrieve)) \
        | RunnableLambda(lambda x: f"背景资料：{x['context']}\n问题：{x['question']}")
    print(f"    最终喂给模型的文本：\n    {rag_shape.invoke({'question': '退货政策是什么？'})}")


if __name__ == "__main__":
    main()
