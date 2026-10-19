# EX-07-06 | Protocol 结构化子类型 | 运行: python3 示例代码/ch07_classes/ex_07_06_protocol.py
from typing import Protocol, runtime_checkable


@runtime_checkable
class Summarizable(Protocol):
    """只要"长得像"（有 summarize 方法）就算实现，无需继承或声明。"""

    def summarize(self) -> str: ...


class LogSnippet:                           # 没有继承任何东西
    def __init__(self, text: str) -> None:
        self.text = text

    def summarize(self) -> str:
        return self.text[:10] + "..."


class Article:
    def __init__(self, title: str, body: str) -> None:
        self.title, self.body = title, body

    def summarize(self) -> str:
        return self.title


def render(item: Summarizable) -> str:      # 类型上要求满足 Summarizable 协议
    return f"[摘要] {item.summarize()}"


def main() -> None:
    print(render(LogSnippet("这是一段很长的服务日志内容，包含堆栈信息")))
    print(render(Article("Python 对象模型", "正文略")))

    # runtime_checkable 让 isinstance 按"有没有该方法"判断（结构化检查）
    print(f"isinstance(LogSnippet 实例, Summarizable): {isinstance(LogSnippet('x'), Summarizable)}")

    class NoMethod:                          # 没有 summarize：不满足协议
        pass

    print(f"isinstance(NoMethod 实例, Summarizable): {isinstance(NoMethod(), Summarizable)}")
    try:
        render(NoMethod())
    except AttributeError as exc:
        print(f"塞进不满足协议的对象 -> AttributeError: {exc}")


if __name__ == "__main__":
    main()
