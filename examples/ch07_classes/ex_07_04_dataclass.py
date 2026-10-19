# EX-07-04 | @dataclass | 运行: python3 examples/ch07_classes/ex_07_04_dataclass.py
from dataclasses import asdict, dataclass, field


@dataclass
class ChatMessage:
    role: str
    content: str
    tokens: int = 0


@dataclass
class Conversation:
    title: str
    tags: list[str] = field(default_factory=list)     # 可变默认值必须用 default_factory
    messages: list[ChatMessage] = field(default_factory=list)
    turn: int = field(init=False, default=0)          # 不进 __init__ 的派生字段

    def __post_init__(self) -> None:
        """__init__ 之后的统一加工（校验/派生）。"""
        if not self.title.strip():
            raise ValueError("标题不能为空")
        self.turn = len(self.messages)

    def append(self, msg: ChatMessage) -> None:
        self.messages.append(msg)
        self.turn = len(self.messages)


@dataclass(frozen=True)
class ModelConfig:
    """frozen=True：不可变（浅），因此可哈希。"""
    model: str
    temperature: float = 0.7


def main() -> None:
    conv = Conversation(title="排障会话", tags=["prod"])
    conv.append(ChatMessage("user", "服务 502 了"))
    conv.append(ChatMessage("assistant", "先看网关日志", tokens=18))
    print(f"自动生成的 __repr__: {conv!r}")

    other = Conversation(title="排障会话", tags=["prod"])
    print(f"自动生成的 __eq__: conv == other -> {conv == other}（conv 多两条消息）")

    c1 = ModelConfig(model="gpt-demo", temperature=0.2)
    c2 = ModelConfig(model="gpt-demo", temperature=0.2)
    print(f"frozen 实例值相等: {c1 == c2}，可哈希: {hash(c1) == hash(c2)}")
    try:
        c1.temperature = 0.9
    except Exception as exc:  # dataclasses.FrozenInstanceError（AttributeError 的子类）
        print(f"修改 frozen 实例 -> {type(exc).__name__}: {exc}")

    print(f"asdict: {asdict(conv)}")


if __name__ == "__main__":
    main()
