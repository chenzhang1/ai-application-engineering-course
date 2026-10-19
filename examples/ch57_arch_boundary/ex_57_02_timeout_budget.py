# EX-57-02 | 超时预算分解与传播：每一层只能花"分到的钱" | 运行: python3 examples/ch57_arch_boundary/ex_57_02_timeout_budget.py
"""完整可运行（纯标准库，离线）：演示同步 HTTP 集成模式里超时（deadline）如何逐级分配。

核心规则：下游超时 < 上游剩余预算。反例（每层都配 30s）的后果：
Java 侧 30s 先到 → 断开返回 504，而 Python 侧的 LLM 调用继续跑完——
token 照样计费，结果却没人接收（白烧钱）。
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Budget:
    """超时预算：总预算固定，分配给子步骤，且子步骤之和必须小于总预算。"""

    name: str
    total_s: float
    children: list[Budget] = field(default_factory=list)

    def allocate(self, *parts: tuple[str, float]) -> list[Budget]:
        """把总预算分给若干子步骤；校验：所有子步骤之和 < 总预算（留出网络与排队余量）。"""
        allocated = sum(sec for _, sec in parts)
        if allocated >= self.total_s:
            raise ValueError(
                f"{self.name}：子步骤预算之和 {allocated}s 必须 < 总预算 {self.total_s}s"
                f"（要给序列化/排队/重试留余量，精确用满是事故配置）")
        self.children = [Budget(name, sec) for name, sec in parts]
        return self.children


def describe(b: Budget, indent: int = 0) -> None:
    pad = "  " * indent
    print(f"{pad}{b.name}: {b.total_s}s")
    for child in b.children:
        describe(child, indent + 1)


def main() -> None:
    print("── 正确配置：预算逐级递减 ──")
    # 链路：用户 → 网关 → Spring Boot 业务服务 → Python AI 服务 → LLM API
    gateway = Budget("网关总预算", 30.0)
    # 网关分配：留给业务服务 26s（4s 余量给网关自身与响应传输）
    business = gateway.allocate(("Spring 业务服务", 26.0))[0]
    # 业务服务分配：其中 22s 给 AI 服务（4s 余量给自己的业务处理与落库）
    ai_call = business.allocate(("Python AI 服务调用", 22.0))[0]
    # AI 服务分配：其中 18s 给 LLM API（4s 余量给检索/重排/Prompt 组装）
    ai_call.allocate(("LLM API（首字节 8s / 整体 18s）", 18.0))
    describe(gateway)

    print("\n── 错误配置：每层都抄 30s ──")
    print("  网关 30s / 业务 30s / AI 服务 30s / LLM 30s")
    print("  后果：LLM 第 29s 才吐完 → 业务层 30s 已超时返回 504 →")
    print("        Python 进程里这次调用若未被取消，token 已计费、结果无人接收。")
    print("  修复：① 预算逐级递减（本示例的正确配置）；② Python 侧监听客户端断连，")
    print("        断连即取消上游 LLM 请求（FastAPI 里 request.is_disconnected()，ch17 的 SSE 同款手法）。")

    print("\n── 校验器演示：子步骤之和 >= 总预算时直接报错（把事故拦在配置期）──")
    try:
        Budget("业务服务", 10.0).allocate(("AI 调用", 10.0))
    except ValueError as exc:
        print(f"  ValueError: {exc}")

    print("\n[流式场景补充] SSE 透传模式的三段预算：连接 2s / 首 token（TTFB）10s /")
    print("  token 间隔（流空闲）30s——整体不设大超时，靠'空闲超时'判死流，ch59 参数表展开。")


if __name__ == "__main__":
    main()
