# EX-07-05 | 继承 vs 组合 | 运行: python3 examples/ch07_classes/ex_07_05_inheritance_composition.py
from collections.abc import Callable


# --- 继承：只在 is-a 关系上使用 ---
class Retriever:
    def search(self, query: str) -> list[str]:
        return [f"命中({query}-1)", f"命中({query}-2)"]


class KeywordRetriever(Retriever):
    def search(self, query: str) -> list[str]:      # 覆写：先按父类逻辑再过滤
        base = super().search(query)
        return [h for h in base if query in h] or base


# --- 组合：has-a / 可替换部件用组合（多数业务场景的正确选择） ---
class AnswerPipeline:
    def __init__(
        self,
        retriever: Retriever,
        rerank: Callable[[list[str]], list[str]] | None = None,
    ) -> None:
        self.retriever = retriever                  # 持有部件，而不是继承部件
        self.rerank = rerank

    def answer_contexts(self, query: str) -> list[str]:
        hits = self.retriever.search(query)
        if self.rerank is not None:
            hits = self.rerank(hits)
        return hits[:2]


def main() -> None:
    kr = KeywordRetriever()
    print(f"继承+覆写: {kr.search('订单超时')}")

    pipeline = AnswerPipeline(kr, rerank=lambda hits: list(reversed(hits)))
    print(f"组合可插拔: {pipeline.answer_contexts('订单超时')}")

    # 换一个实现，管道代码一行不改（多态来自"鸭子类型+一致的方法名"）
    class EmptyRetriever(Retriever):
        def search(self, query: str) -> list[str]:
            return []

    empty_pipeline = AnswerPipeline(EmptyRetriever())
    print(f"替换部件: {empty_pipeline.answer_contexts('任意')}（检索为空则上下文为空）")


if __name__ == "__main__":
    main()
