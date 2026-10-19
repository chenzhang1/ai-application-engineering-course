# EX-32-01 | 固定长度切分：坑在哪、overlap 救什么 | 运行: python3 examples/ch32_chunking/ex_32_01_fixed_window.py
"""完整可运行（确定性程序，真实运行输出）：手写最朴素的切分——每 50 字一刀，
观察它怎样把一句话拦腰斩断；再开 overlap=15，观察"块间重叠"如何把被切断的
上下文补回来。结论：固定窗口是理解切分问题的基线，不是工程答案（ch32.5）。
"""
from __future__ import annotations

POLICY_TEXT = (
    "公司的请假制度分为事假、病假和年假三类。事假需要提前一个工作日申请，由直属主管审批。"
    "病假超过三天需要提供医院证明，否则按事假处理。年假按工龄计算，每年十二月三十一日"
    "二十四点清零，不可结转到次年。离职时未休年假按日薪百分之三百折算。"
)


def fixed_split(text: str, size: int, overlap: int = 0) -> list[str]:
    """固定窗口切分：步长 = size - overlap（overlap < size）。"""
    if not 0 <= overlap < size:
        raise ValueError("要求 0 <= overlap < size")
    step = size - overlap
    return [text[i:i + size] for i in range(0, len(text), step)
            if i < len(text)]  # 末尾不足一刀时只出一块


def show(chunks: list[str], title: str) -> None:
    print(f"\n[{title}] 共 {len(chunks)} 块：")
    for i, c in enumerate(chunks):
        print(f"    chunk{i}（{len(c)} 字）:{c!r}")


def main() -> None:
    print(f"原文 {len(POLICY_TEXT)} 字。注意三个'语义断点'：。/，/；——切分最好落在这些位置。")

    show(fixed_split(POLICY_TEXT, size=50), "实验 1：固定 50 字、无重叠")
    print("    ✗ chunk0 结尾'病假超过三'——'天'被切走；检索'病假要什么材料'时，")
    print("      这块既没有'证明'也没有完整谓语，匹配质量直接受损（ch32.5 的切片伤语义）。")

    show(fixed_split(POLICY_TEXT, size=50, overlap=15), "实验 2：固定 50 字、重叠 15 字")
    print("    ✓ chunk1 的开头把 chunk0 尾部补了回来（'病假超过三天需要提供…'重新完整出现），")
    print("      检索命中任何一块都能看到相对完整的规则。代价：相邻块内容重复，")
    print("      库体积与索引成本按重叠比例上涨——overlap 是花空间买上下文的交易。")

    print("\n[固定窗口的固有缺陷] 它不知道句子在哪里：无论 size 多大，都可能切在主语和谓语中间。")
    print("[Java 对照] 相当于按字节长度硬拆 JSON 字符串——大概率拆出非法片段；")
    print("    工程答案都是'按结构边界拆'，下一示例的递归切分就是干这个的。")


if __name__ == "__main__":
    main()
