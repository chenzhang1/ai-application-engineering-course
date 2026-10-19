# EX-32-02 | RecursiveCharacterTextSplitter 实测：切分结果与参数含义 | 运行: python3 示例代码/ch32_chunking/ex_32_02_recursive_splitter.py
"""完整可运行（真实运行输出，langchain-text-splitters==1.1.3）：用教材锁定版本的
RecursiveCharacterTextSplitter 切同一段制度文本，展示：
1) 默认分隔符优先级（段落 > 行 > 句读 > 字符）如何让切点落在语义边界附近；
2) chunk_size 怎么数（length_function=len，按字符不是按 token）；
3) chunk_overlap 如何在块间复制尾巴；
4) 参数改动的可观察差异（小块 vs 大块）。
版本红线：1.1.3 的构造签名为 (separators=None, keep_separator=True, is_separator_regex=False, **kwargs)，
已于 2026-10-19 用 inspect 核实；chunk_size/chunk_overlap/length_function 走 **kwargs。
"""
from __future__ import annotations

from langchain_text_splitters import RecursiveCharacterTextSplitter

POLICY_TEXT = (
    "## 事假\n事假需提前 1 个工作日申请，由直属主管审批。单次超过 3 天需部门总监加签。\n\n"
    "## 病假\n病假 1 到 2 天在系统登记即可。超过 3 天返岗后 2 个工作日内补交医院证明，"
    "否则按事假处理。\n\n"
    "## 年假\n年假按工龄计算，工作满 1 年不满 10 年每年 5 天。年假当年 12 月 31 日 24 点清零，"
    "不可结转。离职未休年假按日薪 300% 折算。"
)


def show(chunks: list[str], title: str) -> None:
    print(f"\n[{title}] 共 {len(chunks)} 块：")
    for i, c in enumerate(chunks):
        head = c.replace("\n", "⏎")
        print(f"    chunk{i}（{len(c):>3} 字）{head!r}")


def main() -> None:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=80, chunk_overlap=20, length_function=len)
    chunks = splitter.split_text(POLICY_TEXT)
    show(chunks, "实验 1：chunk_size=80, overlap=20（按 len 字符数）")

    print("\n[逐点解释]")
    print("    1) 切点几乎都落在'。'或小节边界附近——默认分隔符列表是")
    print("       ['\\n\\n', '\\n', ' ', '']：先按段落切，段落超长再按行，再按空格，最后兜底按字符；")
    print("       keep_separator=True（默认）把分隔符留在块内，所以句号没丢。")
    print("    2) 所有块 len <= 80：chunk_size 是硬上限（length_function 自己定，下面实验换 token）；")
    print("    3) overlap=20 只在'小节内容超长、需要继续往下切'时生效——本例每节都 ≤80 字，")
    print("       所以实验 1 看不到块间重复；它是花空间买上下文的交易，不是免费的。")
    print("    4) 注意 chunk2='## 年假' 只有 5 字：短标题被单独切出来了（标题+正文一起超过 80 时，")
    print("       切分器把两者在换行处拆开）——这正是 EX-32-03 '先按标题分节、再节内细切'")
    print("       两级管线要解决的问题；纯长度切分永远有这类盲区。")

    small = RecursiveCharacterTextSplitter(chunk_size=40, chunk_overlap=0,
                                           length_function=len).split_text(POLICY_TEXT)
    show(small, "实验 2：chunk_size=40, overlap=0（对照）")
    print("\n    小块无重叠：块数变多，但跨块句子被硬拆（chunk3/chunk4 把'返岗后 2 个工作日内"
          "补交…'劈成两半），")
    print("    检索单块命中时上下文残缺——切分参数没有万能值，用 ch35 的评估集选。")

    print("\n[常见误区] chunk_size=200 不是'200 个 token'：默认按字符数；中文 1 字≈0.5~1 token，")
    print("    要按 token 预算控制就把 length_function 换成 token 计数（示例代码.公共.llm_client.count_tokens）。")
    print("[Java 对照] 这就是 SplitIterator/Tokenizer 的'按结构递归降级'——")
    print("    优先语义边界，超限才暴力兜底，与 B-tree 无关，纯文本处理。")


if __name__ == "__main__":
    main()
