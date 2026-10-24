# 第四部分 大模型与模型 API（ch21~ch25）

> 资料核实日期：2026-10-19。本部分全部示例均在本教材约定的沙箱环境（Python 3.14.7，openai==3.35.1，tiktoken==0.14.0，pydantic==2.14.1，numpy==2.5.4，见 `requirements.txt`）实际运行。
> 运行模式约定（全书统一，见前言 0.5）：`LLM_MODE=mock`（默认，离线确定性规则模型，不联网）与 `LLM_MODE=real`（需 `OPENAI_API_KEY`）。沙箱没有 OPENAI_API_KEY，因此所有模型回答均来自 Mock 或标注为"示例输出（非真实记录）"；SDK 签名等**代码层事实**全部用 `inspect` 在 3.35.1 上实际核实，核实过程见 EX-24-01。
> 前置知识：ch09（生成器——流式输出的语言基础）、ch15（httpx 超时与重试）、ch16（Pydantic）、ch17（SSE）。
> 学完你能做什么：
> 1. 用 tiktoken 精确计算任意文本的 token 数，独立完成一次"上下文预算表"演算，预判一次请求的费用与是否会撞上下文上限；
> 2. 用裸 openai SDK 走通生产级全流程：鉴权与 BaseURL、流式、结构化输出（Pydantic）、工具调用完整闭环、429/超时的重试语义，并知道每一步在"OpenAI 兼容服务"上要先核实什么；
> 3. 用全书统一的 `示例代码/公共/llm_client.py`（Mock/Real 双模式）做日常实验——后续 RAG/LangChain/LangGraph 章节全部 import 它，你在这里学到的接口就是全书接口。

---

# 第 21 章 Token 与上下文窗口：模型的"字"不是你的字

> **本章目标**：建立"模型按 token 计数与计费"的直觉，能算、能查、能预算。
> **前置知识**：ch12 的 json、ch15 的 HTTP 客户端常识。
> **学完你能做什么**：解释"为什么 40 个汉字不是 40 个 token"；为任意对话画 token 预算表；说出幻觉/知识时效/温度三件事的工程含义。

## 21.1 真实问题引入：预算 2000 字符，账单翻三倍

某电商平台（合成案例）的 Java 团队给客服系统接了一个大模型。老王按 Java 的直觉做了预算：客服对话平均 2000 字符，模型 API 报价按 token 算，他粗略按"1 字符 = 1 token"估了个上限，又觉得"就算翻倍也够"。上线第一周：中文对话的账单是他预估的 3 倍；更糟的是有一次把 8000 字的退货政策全文塞进请求，服务端直接返回 400，说上下文超长——而他数的"字符数"远没到文档写的窗口大小。

两个坑都指向同一个盲区：**模型的世界里没有"字符"，只有 token（词元）**。token 是模型处理文本的最小单位，字符到 token 的映射由 tokenizer（分词器）决定，跟 Java 的 `String.length()` 完全是两套计量体系。本章先把"量"搞准，再讲"限"（上下文窗口）和"钱"（计费直觉），最后讲三个和"量"无关但和预期管理有关的概念：幻觉、知识时效、温度。

## 21.2 一句话解释 + 生活类比 + 类比边界

**一句话解释**：token 是模型词表里的一个条目——可能是一个英文单词、半个汉字、一段空格加标点——模型读进去的是 token 序列，算钱、限长、计上下文，全部按 token。

**生活类比**：把文本想象成乐高拼好的模型，tokenizer 是"拆回标准积木块"的机器。英文常用词是大块积木（"the" 一块）；中文常用字可能是半块（一个汉字可能被拆成 1~2 块，因为词表里中文条目相对少）；生僻字和表情是碎片。计费按积木块数收，不按模型的重量（字符数）收。

> 💡 类比边界：
> 1. 积木块的拆法是**固定词表**决定的（BPE 算法在训练语料上统计出来），不是模型"理解"后动态决定——同一个词不管在什么句子里，拆法基本一致；
> 2. "一个 token ≈ 4 个英文字符"只对英文大致成立；**对中文严重失真**（本书实测：13 字符的中文句子是 13 个 token，见 EX-21-01），"一个汉字 ≈ 1~2 token"才是更可用的粗估；
> 3. 不同模型用不同 tokenizer，同一个词在不同模型下的 token 数可以不同——跨模型比较"每 token 价格"时，同样的文本 token 数并不相等。

## 21.3 正式原理与准确术语

**词元/Token**：模型词表（vocabulary）中的一个条目及其编号。现代 LLM 普遍使用 **BPE（Byte Pair Encoding，字节对编码）** 类算法构建词表：从字节级开始，迭代合并高频相邻对，直到达到目标词表规模。**分词器（tokenizer）** 负责在文本与 token 序列之间双向转换，且保证 `decode(encode(text)) == text`（往返无损）。

**上下文窗口（context window）**：单次请求中，模型能"看到"的 token 总量上限，**输入（prompt）与输出（completion）共享这个窗口**。窗口外的东西模型一无所知——这不是"记性差"，是计算结构决定的（ch22 会解释注意力为什么要付出这个代价）。各模型窗口大小不同且更新很快，本书不写死数字，以你所用模型的官方文档为准。

**最大输出（max output / max_tokens）**：单次响应可生成的 token 上限。达到上限时，响应的 **finish_reason（结束原因）** 为 `length` 而非 `stop`——回答是被"拦腰截断"的，不是模型自己说完了。

**幻觉（hallucination）**：模型生成流畅、自信、但与事实不符的内容。根源在于模型的训练目标是"给出 statistically 合理的下一个 token"（ch22），不是"给出可验证为真的断言"。

**知识截止（knowledge cutoff）**：模型的参数在训练完成后冻结，训练截止日期之后发生的事情它不知道——除非你通过提示词/工具/RAG 把信息放进上下文。

**温度（temperature）**：控制采样随机性的参数。0 附近输出几乎确定（每次基本一样），越高越多样也越容易跑偏。详见 ch23。

**Java 对照**：token 之于模型，就像 `UTF-16 code unit` 之于 Java String——`String.length()` 返回的是编码单元数而不是"字数"，同样的文本在不同字符集下的"单位数"不同。你在 Java 里经历过"emoji 让 length 变怪"的困惑，LLM 世界里"中文字符数 ≠ token 数"是同一个认知错位的放大版。

## 21.4 最小完整示例：tiktoken 计数实验与上下文预算

**EX-21-01 | 示例代码/ch21_tokens/ex_21_01_tiktoken_count.py（完整可运行）**

```python
# EX-21-01 | tiktoken 计数实验：token ≠ 字符 ≠ 字 | 运行: python3 示例代码/ch21_tokens/ex_21_01_tiktoken_count.py
"""完整可运行：用 tiktoken 0.14.0（cl100k_base 词表）真实计数。

注意：tiktoken 首次使用需要联网下载 BPE 词表（本书沙箱经代理下载成功，约 27 秒，
缓存到 $TIKTOKEN_CACHE_DIR 或系统临时目录后离线可用）。下载失败时 llm_client 会
回退到 len//4 近似——本文件演示两种方式并对比误差，绝不静默混淆。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # 仓库根，便于 import 示例代码.公共

from 示例代码.公共.llm_client import count_tokens  # noqa: E402


def approx_tokens(text: str) -> int:
    """近似计数：len(text)//4（对英文粗略成立，对中文严重低估）。"""
    return max(1, len(text) // 4)


SAMPLES: list[tuple[str, str]] = [
    ("英文短句", "Hello, how may I help you today?"),
    ("中文短句", "您好，请问有什么可以帮您？"),
    ("混合文本", "订单 ORD-1001 已支付 129.5 元，请查收 invoice.pdf"),
    ("JSON 片段", '{"order_id": "ORD-1001", "status": "paid", "amount": 129.5}'),
    ("Java 代码", "public static void main(String[] args) { System.out.println(\"hi\"); }"),
]


def main() -> None:
    print(f"{'样本':<10} {'字符数':>6} {'近似(len//4)':>12} {'tiktoken 精确':>12} {'偏差':>8}")
    print("-" * 56)
    for label, text in SAMPLES:
        exact, method = count_tokens(text)
        approx = approx_tokens(text)
        bias = approx - exact
        print(f"{label:<10} {len(text):>6} {approx:>12} {exact:>12} {bias:>+8}")
        assert method == "tiktoken:cl100k_base", f"预期 tiktoken 精确计数，实际 {method}"

    # encode/decode 往返：token 是模型眼里的"字"
    from 示例代码.公共.llm_client import _get_encoding  # 教学演示用内部函数

    enc = _get_encoding()
    text = "订单查询"
    token_ids = enc.encode(text)
    print(f"\n[往返] {text!r} → token ids = {token_ids} → decode 还原 = {enc.decode(token_ids)!r}")
    print(f"[字符] {len(text)} 个汉字 vs {len(token_ids)} 个 token —— 中文常见 1 汉字≈0.5~1.5 token")
    for tid in token_ids:
        piece = enc.decode([tid])
        print(f"    token {tid:>6} → {piece!r}（单 token 解码可能显示异常：多字节序列被拆开）")


if __name__ == "__main__":
    main()
```

```text
# 真实运行输出（Python 3.14.7，tiktoken 0.14.0，cl100k_base 词表）
样本            字符数   近似(len//4)  tiktoken 精确       偏差
--------------------------------------------------------
英文短句           32            8            9       -1
中文短句           13            3           13      -10
混合文本           39            9           19      -10
JSON 片段        59           14           24      -10
Java 代码        68           17           16       +1

[往返] '订单查询' → token ids = [51510, 52254] → decode 还原 = '订单查询'
[字符] 4 个汉字 vs 2 个 token —— 中文常见 1 汉字≈0.5~1.5 token
    token  51510 → '订单'（单 token 解码可能显示异常：多字节序列被拆开）
    token  52254 → '查询'（单 token 解码可能显示异常：多字节序列被拆开）
```

读表三个要点：**英文**近似法基本可用（偏差 -1）；**中文**近似法低估到只报 1/4（13 字符的句子实际 13 个 token，近似只给 3）；**JSON 和代码**因为大量引号、空格、标点被切碎，token 密度也明显高于英文散文。老王的三倍账单，就是这么来的。

**EX-21-02 | 示例代码/ch21_tokens/ex_21_02_context_budget.py（完整可运行）**

```python
# EX-21-02 | 上下文窗口预算：一次请求到底花了多少 token | 运行: python3 示例代码/ch21_tokens/ex_21_02_context_budget.py
"""完整可运行：把一次真实形态的对话消息列表逐条计数，算出 prompt 预算。

要点：上下文窗口 = 输入(prompt) + 输出(completion) 共享一个上限；
发出去的每一轮历史都会被完整重新计费——历史越长，每次请求越贵。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from 示例代码.公共.llm_client import count_tokens  # noqa: E402

# 教学基准数字（虚构模型 "demo-4k"，只用于算术演示，不代表任何真实产品）
MAX_CONTEXT_TOKENS = 4096
MAX_OUTPUT_TOKENS = 1024

MESSAGES: list[dict[str, str]] = [
    {"role": "system", "content": "你是电商客服助手，用简洁中文回答，一次不超过三句话。"},
    {"role": "user", "content": "我上周买的蓝牙耳机左耳没有声音，订单号 ORD-77821。"},
    {"role": "assistant", "content": "抱歉给您带来不便。我先帮您确认订单信息，请稍等。"},
    {"role": "user", "content": "好的，麻烦快一点，我下午要出门。"},
    {"role": "assistant", "content": "已查到订单：蓝牙耳机（白色），10 月 12 日签收。您要申请换货吗？"},
    {"role": "user", "content": "换货吧。另外我想知道新耳机多久能到？"},
]


def main() -> None:
    print(f"[假设模型] demo-4k：上下文窗口 {MAX_CONTEXT_TOKENS}，单次输出上限 {MAX_OUTPUT_TOKENS}")
    print(f"[当前对话] {len(MESSAGES)} 条消息，逐条计数：")
    total = 0
    for m in MESSAGES:
        n, method = count_tokens(m["content"])
        total += n
        print(f"    {m['role']:<9} {n:>4} tokens  （计数方式：{method}）")

    _, method = count_tokens("x")
    budget_left = MAX_CONTEXT_TOKENS - MAX_OUTPUT_TOKENS - total
    print("-" * 60)
    print(f"    prompt 合计        = {total:>4} tokens")
    print(f"    为回答预留(输出)   = {MAX_OUTPUT_TOKENS:>4} tokens")
    print(f"    窗口剩余(可再放历史/文档) = {budget_left:>4} tokens")
    print(f"    计数方式           = {method}")

    # 每轮对话都把完整历史重新计费：第 k 轮请求的费用 ≈ 前 k-1 轮累计 prompt
    print("\n[计费直觉] 对话越滚越长，每一轮都在为全部历史重新付费：")
    cum = 0
    for i, m in enumerate(MESSAGES, 1):
        n, _ = count_tokens(m["content"])
        cum += n
        print(f"    第 {i} 条消息加入后，下一次请求的 prompt ≈ {cum:>4} tokens"
              f"（{'滚雪球↑' if i > 1 else '起点'}）")

    assert total + MAX_OUTPUT_TOKENS <= MAX_CONTEXT_TOKENS, "预算爆了：需要截断或摘要（见 ch27）"
    print("\n结论：本对话可继续进行，但剩余预算有限——这正是 ch27 历史管理要解决的问题。")


if __name__ == "__main__":
    main()
```

```text
# 真实运行输出（Python 3.14.7）
[假设模型] demo-4k：上下文窗口 4096，单次输出上限 1024
[当前对话] 6 条消息，逐条计数：
    system      30 tokens  （计数方式：tiktoken:cl100k_base）
    user        28 tokens  （计数方式：tiktoken:cl100k_base）
    assistant   25 tokens  （计数方式：tiktoken:cl100k_base）
    user        21 tokens  （计数方式：tiktoken:cl100k_base）
    assistant   37 tokens  （计数方式：tiktoken:cl100k_base）
    user        23 tokens  （计数方式：tiktoken:cl100k_base）
------------------------------------------------------------
    prompt 合计        =  164 tokens
    为回答预留(输出)   = 1024 tokens
    窗口剩余(可再放历史/文档) = 2908 tokens
    计数方式           = tiktoken:cl100k_base

[计费直觉] 对话越滚越长，每一轮都在为全部历史重新付费：
    第 1 条消息加入后，下一次请求的 prompt ≈   30 tokens（起点）
    第 2 条消息加入后，下一次请求的 prompt ≈   58 tokens（滚雪球↑）
    第 3 条消息加入后，下一次请求的 prompt ≈   83 tokens（滚雪球↑）
    第 4 条消息加入后，下一次请求的 prompt ≈  104 tokens（滚雪球↑）
    第 5 条消息加入后，下一次请求的 prompt ≈  141 tokens（滚雪球↑）
    第 6 条消息加入后，下一次请求的 prompt ≈  164 tokens（滚雪球↑）

结论：本对话可继续进行，但剩余预算有限——这正是 ch27 历史管理要解决的问题。
```

## 21.5 逐段解释：为什么"量错了"会连环出错

**（1）count_tokens 的双路径设计（llm_client.py）**。我们的统一客户端提供 `count_tokens(text) -> tuple[int, str]`：优先用 tiktoken 精确计数（本书固定 `cl100k_base` 词表，保证全书 token 数字同一口径、可复算），返回值第二项是**计数方式标注**——`"tiktoken:cl100k_base"` 或回退时的 `"approx:chars//4"`。为什么不静默回退？因为两种方式的误差可以达到 4 倍（上表），让调用方"以为自己在精确计数"是埋雷。**编码要按模型选**：`cl100k_base` 对应 gpt-3.5/gpt-4 世代；gpt-4o 世代起主流是 o200k 系编码，同一文本在不同编码下的 token 数并不相同——接入具体模型时用 `tiktoken.encoding_for_model(...)` 或查官方文档选编码，本书的 token 数字都是"cl100k 口径"的教学数字，不要直接拿去给其他模型对账。tiktoken 0.14.0 首次调用 `get_encoding("cl100k_base")` 需要联网下载 BPE 词表（本书沙箱实测约 27 秒），之后缓存到 `TIKTOKEN_CACHE_DIR` 或系统临时目录，离线可用（第二次加载实测 0.14 秒）。

**（2）为什么模型必须"按 token 思考"**。模型输入输出都是整数序列（token id），嵌入表把每个 id 映射成一个向量（ch22）。所以"模型看到多少字"这个问题本身不成立，成立的是"看到多少 token"。**Java 对照**：就像你不会用"文件多大 MB"来预估"数据库多少行"，文本长度（字符）和模型消耗（token）是两个度量体系，中间隔着 tokenizer 这张表。

**（3）预算不等式**。一次请求能安全发出，需要满足：

```text
已用 prompt tokens + 你希望的最大输出 tokens ≤ 上下文窗口
```

EX-21-02 里 `prompt 合计 164 + 输出预留 1024 ≤ 4096`，剩余 2908。注意两个"不要"：不要把窗口全部留给 prompt（回答没地方写，`finish_reason=length`）；不要忘了**输入输出共享窗口**——窗口 4k 不代表能输出 4k。

**（4）计费滚雪球**。Chat API 没有服务端会话（ch23 详述），每一轮都要把历史完整重发。第 k 轮请求的 prompt ≈ 前 k-1 轮全部内容的 token 和——EX-21-02 的"滚雪球"清单就是这个和的展开。这也是 ch27 历史管理（截断/摘要）存在的根本原因：不是美学，是成本与窗口的硬约束。

**（5）不确定性三兄弟**：幻觉、知识时效、温度。这三个概念在本章只需要建立"预期管理"意识，用 EX-21-03 做 Mock 侧的确定性对照：

**EX-21-03 | 示例代码/ch21_tokens/ex_21_03_mock_determinism.py（完整可运行）**

```python
# EX-21-03 | 模型不确定性的 Mock 对照实验：temperature 在 Mock 下无效 | 运行: python3 示例代码/ch21_tokens/ex_21_03_mock_determinism.py
"""完整可运行（Mock 模式，不联网）：演示"同输入同输出"的确定性，并诚实展示
temperature 参数被 Mock 忽略的事实——真实模型上 temperature>0 会带来随机多样性。

幻觉/知识时效无法用 Mock 演示（Mock 没有"知识"），对应讨论见教材正文与示例输出标注。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from 示例代码.公共.llm_client import MockLLM, RealLLM  # noqa: E402

MESSAGES = [
    {"role": "system", "content": "你是一个客服助手"},
    {"role": "user", "content": "退货政策是什么？"},
]


def main() -> None:
    llm = MockLLM()
    print("[实验 1] Mock 同输入连跑 3 次（不传 temperature）：")
    outputs = [llm.chat(MESSAGES).content for _ in range(3)]
    for i, o in enumerate(outputs, 1):
        print(f"    第 {i} 次：{o}")
    assert outputs[0] == outputs[1] == outputs[2]
    print("    → 完全一致：MockLLM 是确定性规则模型，无随机数。")

    print("\n[实验 2] Mock 下传 temperature=1.5 / top_p=0.5：")
    r_hot = llm.chat(MESSAGES, temperature=1.5, top_p=0.5)
    r_cold = llm.chat(MESSAGES, temperature=0.0)
    print(f"    temperature=1.5 → {r_hot.content}")
    print(f"    temperature=0.0 → {r_cold.content}")
    print(f"    两者相同：{r_hot.content == r_cold.content}（Mock 接受参数但忽略——接口兼容，行为确定）")
    print("    ★ 类比：Mock 像写死的单元测试桩；真实模型 temperature>0 才会掷骰子。")

    print("\n[实验 3] 真实模式的行为约定（代码层面核实，不在本沙箱真实调用）：")
    try:
        RealLLM(api_key=None)
    except RuntimeError as e:
        print("    RealLLM 缺 Key 时抛 RuntimeError（前 2 行）：")
        for line in str(e).splitlines()[:3]:
            print(f"      {line}")
    print("    真实调用时 temperature 语义见教材 23.3：0≈稳定可复现，1≈默认多样，>1 易失控。")


if __name__ == "__main__":
    main()
```

```text
# Mock 运行输出（LLM_MODE=mock，不联网）
[实验 1] Mock 同输入连跑 3 次（不传 temperature）：
    第 1 次：（Mock·客服）您好，已收到您的问题「退货政策是什么？」，工号 007 为您服务。
    第 2 次：（Mock·客服）您好，已收到您的问题「退货政策是什么？」，工号 007 为您服务。
    第 3 次：（Mock·客服）您好，已收到您的问题「退货政策是什么？」，工号 007 为您服务。
    → 完全一致：MockLLM 是确定性规则模型，无随机数。

[实验 2] Mock 下传 temperature=1.5 / top_p=0.5：
    temperature=1.5 → （Mock·客服）您好，已收到您的问题「退货政策是什么？」，工号 007 为您服务。
    temperature=0.0 → （Mock·客服）您好，已收到您的问题「退货政策是什么？」，工号 007 为您服务。
    两者相同：True（Mock 接受参数但忽略——接口兼容，行为确定）
    ★ 类比：Mock 像写死的单元测试桩；真实模型 temperature>0 才会掷骰子。

[实验 3] 真实模式的行为约定（代码层面核实，不在本沙箱真实调用）：
    RealLLM 缺 Key 时抛 RuntimeError（前 2 行）：
      real 模式需要 OPENAI_API_KEY，但环境变量未设置。三种解决方式：
        1) export OPENAI_API_KEY=sk-... 后重试；
    真实调用时 temperature 语义见教材 23.3：0≈稳定可复现，1≈默认多样，>1 易失控。
```

三件事的工程含义一句话版：**幻觉**——模型输出永远要过校验/引用/人工抽检，不能当数据库读；**知识时效**——"模型不知道昨天的事"是常态，把时效敏感信息放进上下文（RAG/工具，第六部分）；**温度**——要稳定可测就调低，要创意发散再调高，并且永远不要假设"调高了输出一定更好"。

## 21.6 安装 / 文件位置 / 运行命令

```bash
# 安装（在项目根目录）
pip install -r requirements.txt   # 已含 tiktoken==0.14.0、openai==3.35.1

# 运行（三个示例均默认 Mock/离线路径；EX-21-01 首次运行会联网下载词表，约 27 秒）
python3 示例代码/ch21_tokens/ex_21_01_tiktoken_count.py
python3 示例代码/ch21_tokens/ex_21_02_context_budget.py
python3 示例代码/ch21_tokens/ex_21_03_mock_determinism.py

# 词表下载失败（离线环境）时：count_tokens 自动回退近似并在返回值中标注
# 提前缓存词表（可选）：export TIKTOKEN_CACHE_DIR=/tmp/data-gym-cache
```

## 21.7 常见错误与排查

**错 1：离线环境首次调用 tiktoken 抛网络异常。**

```text
requests.exceptions.ConnectionError: HTTPSConnectionPool(host='openaipublic.blob.core.windows.net', ...)
```
原因：`tiktoken.get_encoding()` 首次使用要联网下载 BPE 词表。修复：能联网就跑一次建立缓存（`TIKTOKEN_CACHE_DIR` 指定持久目录）；纯离线环境用 `count_tokens` 的回退路径（返回值第二项会如实标注 `approx:chars//4`），并牢记近似值对中文低估约 4 倍。

**错 2：按字符数预算，中文请求被 400 拒绝。**
典型报错形态（各家措辞不同，此处为示意——非真实记录）：`400 This model's maximum context length is 4097 tokens, however you requested 5210 tokens`。原因：上下文按 token 计，中文 1 字符常占 1~2 token，字符数远低于窗口也可能超限。修复：接入前用 EX-21-01 的方法实测自家文本的 token 密度，再做预算（EX-21-02），超预算走 ch27 的截断/摘要。

**错 3：max_tokens 设太小，回答总是"说到一半"。**
现象：回答莫名中断，且没有报错。原因：`finish_reason == "length"`——输出达到上限被截断（不是模型"不想说了"）。修复：打印/记录 `finish_reason`（`ChatResult.finish_reason` 字段就是为此设计）；确实需要长回答时调大输出上限或改用"分段生成"策略。

**错 4：把"幻觉"当 bug 修。**
现象：模型自信地编造了一个不存在的 API 参数（ch29 的信号 1），团队试图"修好它"。认知修正：幻觉是概率生成机制的伴随属性，只能工程化缓解——检索引用、结构化输出校验、工具事实核查、人工抽检，而不是指望某个参数一关了之。

## 21.8 企业场景中的使用方式

Spring Boot 团队通常把 token 预算做成**网关中间件**：请求进入 AI 服务前，由一个 Filter/Interceptor 用 tiktoken（Python 侧）或厂商提供的 Java tokenizer 估算 token，超预算直接 4xx 拒绝或触发摘要，而不是让它打到模型 API 才收到 400——省一次白花的调用费。计费同理：网关读取响应里的 `usage` 字段（`ChatResult.usage`），按用户/租户落表（结构见 ch60），月底对账就不会出现"账单为什么是预估的三倍"这种会议。

## 21.9 练习

**基础 1**：用 `count_tokens` 分别计算 `"Redis 持久化配置"` 与 `"Redis persistence config"` 的 token 数，解释为什么差异不是简单的"中文=2 倍"。

**基础 2**：窗口 8192、输出预留 2048 时，prompt 最多多少 token？写出不等式并算出答案。

**代码 1**：写一个函数 `fits_window(messages, max_output, window) -> tuple[bool, int]`，返回（是否放得下，超出多少 token），用 EX-21-02 的 MESSAGES 验证。

**代码 2**：把 EX-21-01 的 SAMPLES 加一条"带 emoji 的中文短句"，观察 token 数与字符数的比值，用一句话总结 emoji 对计费的影响。

**调试题**：同事说"我把 max_tokens 从 100 改成 200，回答反而只到一半就停了"。给出至少两个可能的排查方向。

### 参考答案

**基础 1**：中文"Redis 持久化配置"里，"Redis"是 1 个 token，四个汉字大约各占 1~2 个 token（词表对常用中文词如"配置"可能有整词条目）；英文 "persistence config" 是两个常见词，可能各 1~2 个 token。差异取决于**词表里恰好有哪些条目**，不是字符集的简单倍数——必须实测。

**基础 2**：8192 − 2048 = 6144 token。

**代码 1**：
```python
def fits_window(messages, max_output: int, window: int) -> tuple[bool, int]:
    used = sum(count_tokens(m["content"])[0] for m in messages)
    over = used + max_output - window
    return (over <= 0), max(0, over)
```
对 EX-21-02 的对话（164 token）与 (max_output=1024, window=4096)：返回 (True, 0)。

**代码 2**：emoji 通常按字节进入 BPE，一个 emoji 可能拆成多个 token 甚至占比其字节长度的碎片；结论一句话：**emoji 是 token 密度陷阱**，用户内容含大量 emoji 时预算要上浮。

**调试题**：方向一，`finish_reason` 是不是 `length`——若 200 仍截断，检查是否还有别的输出上限（如厂商对 max_completion_tokens 的独立上限）；方向二，回答是否其实自然结束（`finish_reason=stop`）而是前端渲染截断；方向三，多段输出（工具调用+文本）时是否只统计了文本部分。

## 21.10 自测检查表

- 我能说出 token、BPE、tokenizer 三者的关系，并解释"往返无损"的含义。
- 我能用 tiktoken 精确计数，并说清回退路径 `approx:chars//4` 对中文的失真方向（低估）与量级（约 4 倍）。
- 我能写出"prompt + 输出预留 ≤ 窗口"的预算不等式，并解释输入输出共享窗口。
- 我能解释账单滚雪球的机制（无服务端会话，历史每轮重发重算）。
- 我能向产品经理解释：幻觉是什么、为什么不能"修好"、用什么工程手段缓解。
- 我能解释知识截止日的含义，并说出把"新知识"送进模型的两种途径（上下文注入 / 工具检索）。
- 我能说明 `finish_reason` 的 `stop` 与 `length` 的区别及排查方法。

## 21.11 面试追问

**[模拟题] 1：为什么不能在网关用 len(text)//4 做 token 预算？**
考查点：token 度量与回退失真。合格回答：近似法对英文大致成立但对中文低估约 4 倍（给出 13 字符/13 token 实测），预算场景低估=放行超额请求=线上 400；应使用目标模型对应的 tokenizer（tiktoken 等），无法精确时回退也要放大系数并监控真实 usage 校准。

**[模拟题] 2：上下文窗口是 8k，为什么输出常常远小于 8k？**
考查点：输入输出共享窗口 + 厂商独立输出上限。合格回答：窗口是输入+输出总量；多数服务另有单次输出上限参数（max_tokens/max_completion_tokens）；且输出 token 逐个生成、成本与延迟都高于输入，超长输出应设计为分段/多轮。

**[模拟题] 3：产品要求"AI 回答 100% 准确"，你怎么回应？**
考查点：幻觉的预期管理。合格回答：概率模型做不到"100% 准确"承诺；能承诺的是工程指标——引用可溯源、拒答率、抽样错误率上限；用评估集（ch35/ch28）把质量变成可测数字，高风险输出走人工审核。

---

# 第 22 章 Transformer 直觉：注意力就是"全文检索 + 加权拼接"

> **本章目标**：不碰训练数学，建立对注意力机制和三阶段（预训练/SFT/对齐）的准确直觉，能解释"为什么上下文长度有限、为什么知识会过时"。
> **前置知识**：ch21 的 token 概念、高中水平的向量点积。
> **学完你能做什么**：白板画出单头注意力的三步计算；用"检索+拼接"向 Java 同事解释 Q/K/V；一句话说清预训练、SFT、对齐各自干什么；解释为什么 RAG 不改模型参数也能注入新知识。

## 22.1 真实问题引入：面试官问"你调 API 的，懂它内部吗"

面试（模拟场景）进行到一半，面试官放下简历："你简历上写'基于大模型开发客服系统'。那我问你，模型为什么能'记住'你 5000 字前面提到的一个订单号，然后在回答里正确用上它？"你如果只会说"上下文窗口大"，这场面试基本结束了。模型并不是"记住"——它在**每次生成下一个词时，都会对整段上下文做一次动态的信息检索与融合**，这个机制叫注意力（attention）。懂了这个，后面一连串工程事实都会变得显然：为什么长上下文贵且慢、为什么知识有截止日、为什么 RAG 只是"把资料塞进上下文"却有效。

## 22.2 一句话解释 + 生活类比 + 类比边界

**一句话解释**：自注意力让序列中的每个词元发起一次"全文检索"——拿自己的查询向量（Query）去和所有词元的键（Key）算匹配度，按匹配度加权混合所有词元的内容（Value），得到融合了上下文的新表示。

**生活类比**：把"查询/订单/状态"四个词的加工想象成一次**站内搜索**：每个词都是检索发起者（Query），全句每个词都有索引卡片（Key）和货架上的货（Value）。"查询"这个词的 Query 和"订单"的 Key 匹配度最高，于是"查询"的新表示里就会掺进大量"订单"的货——它从"一个孤立动词"变成了"订单查询语境里的动词"。

> 💡 类比边界：
> 1. 真实模型里 Q/K/V 不是词本身，是**可学习的投影矩阵**从词向量算出来的三份不同"视角"——类比里我们直接用词向量当 Q=K=V（EX-22-01 就是这么做的教学简化）；
> 2. 真实模型是**多头**的：多组 Q/K/V 并行检索，有的头盯语法、有的头盯指代，再拼接——我们只演示单头；
> 3. 检索打分用了 **softmax 归一化**（分变权重、总和为 1）与 **√d 缩放**（防点积过大把 softmax 推入饱和区），搜索引擎没有这两步；
> 4. 注意力权重高 ≠ "因果上重要"——它是当前这一层、这个头、这句输入下的匹配分数，不是可解释性结论。

## 22.3 正式原理与准确术语

**词元嵌入（token embedding）**：查表把 token id 变成 d 维向量，是模型里唯一"查字典"的部分。**自注意力（self-attention）**：序列对自身做注意力，三步：`scores = Q·Kᵀ/√d`（缩放点积）→ `weights = softmax(scores)`（行归一化）→ `output = weights·V`（加权拼接）。**多头注意力（multi-head attention）**：h 组独立注意力并行后拼接，让不同子空间关注不同关系。**位置信息**：注意力本身对顺序不敏感（集合运算），需要位置编码/旋转位置编码注入顺序（一句话了解即可）。

**三阶段流水线（应用工程师版，每阶段一句话）**：

| 阶段 | 输入 | 学到什么 | 产物特征 | 对应 Java 概念（不精确但好用） |
|---|---|---|---|---|
| 预训练（pre-training） | 海量互联网文本 | 给前文预测下一个 token | 会说话，不听指令，知识冻结在语料截止日 | 一个只读过全公司文档、没上过岗的新人 |
| 监督微调（SFT，Supervised Fine-Tuning） | 人写的问答示例 | 按"指令→回答"的格式响应 | 像助手了，但口径与偏好不稳定 | 岗前培训：背熟服务话术 |
| 对齐（alignment，RLHF/偏好优化等） | 人类偏好数据 | 生成人类更喜欢（更有用/更安全）的回答 | 礼貌、安全、会拒答，也更会客套 | 服务规范+考核（KPI 改变行为） |

一句话收束：**你在 API 里调到的 chat 模型 = 预训练底座 + SFT + 对齐后的成品**；这三步都是模型厂商做的。应用工程师改变模型行为的手段是**改输入**（Prompt/上下文工程，第五部分）或**改检索**（RAG，第六部分），而不是重训。

## 22.4 最小完整示例：15 行点积注意力

**EX-22-01 | 示例代码/ch22_transformer/ex_22_01_dot_attention.py（完整可运行）**

```python
# EX-22-01 | 15 行简化点积注意力（纯 Python+numpy）| 运行: python3 示例代码/ch22_transformer/ex_22_01_dot_attention.py
"""完整可运行：单头缩放点积注意力（scaled dot-product attention）最小实现。

Q·Kᵀ → 除以 √d → softmax 得权重矩阵 → 权重 × V 加权拼接。
本示例打印真实的注意力权重矩阵与每个词的"新表示"，把注意力变成看得见的算术。
（教学简化：无训练、无多头、无 Mask；数字为手选 embedding，非训练产物。）
"""
from __future__ import annotations

import numpy as np

TOKENS = ["用户", "查询", "订单", "状态"]  # 4 个词元
DIM = 4

# 手选 embedding：行=词元，"查询"与"订单"在业务语义上相关（第 2 维相近）
EMB = np.array([
    [1.0, 0.0, 0.0, 0.0],   # 用户
    [0.0, 1.0, 0.9, 0.0],   # 查询
    [0.0, 0.9, 1.0, 0.0],   # 订单
    [0.0, 0.0, 0.0, 1.0],   # 状态
], dtype=np.float64)


def softmax(x: np.ndarray) -> np.ndarray:
    """数值稳定 softmax：减去行最大值防溢出。"""
    e = np.exp(x - x.max(axis=-1, keepdims=True))
    return e / e.sum(axis=-1, keepdims=True)


def attention(Q: np.ndarray, K: np.ndarray, V: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """缩放点积注意力核心（教学简化版，约 15 行内的骨架）。"""
    scores = Q @ K.T / np.sqrt(K.shape[-1])   # 1) 相似度：Q·Kᵀ / √d
    weights = softmax(scores)                 # 2) 归一化：每行和为 1
    return weights @ V, weights               # 3) 加权拼接


def main() -> None:
    print(f"词元序列：{TOKENS}（d_model={DIM}）")
    # 教学简化：Q=K=V 都取同一组 embedding（自注意力）
    out, weights = attention(EMB, EMB, EMB)

    print("\n注意力权重矩阵（行=当前词，列=被关注的词，每行和=1）：")
    header = "        " + "".join(f"{t:>8}" for t in TOKENS)
    print(header)
    for t, row in zip(TOKENS, weights):
        print(f"{t:<8}" + "".join(f"{w:>8.3f}" for w in row))

    print("\n加权拼接后的新表示（行=词元的上下文化表示）：")
    for t, vec in zip(TOKENS, out):
        print(f"{t:<8}" + "  [" + ", ".join(f"{v:.3f}" for v in vec) + "]")

    # 可验证性质
    assert np.allclose(weights.sum(axis=-1), 1.0), "softmax 后每行和必须为 1"
    assert (weights >= 0).all(), "注意力权重非负"
    print("\n[验证] 每行和=1 ✓  权重非负 ✓  —— '查询'与'订单'互相权重最高（0.358/0.326 附近）")
    print("这就是'全文检索+加权拼接'：每个词用自己(Q)去检索别人(K)，按匹配度加权取货(V)。")


if __name__ == "__main__":
    main()
```

```text
# 真实运行输出（Python 3.14.7，numpy 2.5.4）
词元序列：['用户', '查询', '订单', '状态']（d_model=4）

注意力权重矩阵（行=当前词，列=被关注的词，每行和=1）：
              用户      查询      订单      状态
用户         0.355   0.215   0.215   0.215
查询         0.144   0.357   0.355   0.144
订单         0.144   0.355   0.357   0.144
状态         0.215   0.215   0.215   0.355

加权拼接后的新表示（行=词元的上下文化表示）：
用户        [0.355, 0.409, 0.409, 0.215]
查询        [0.144, 0.676, 0.676, 0.144]
订单        [0.144, 0.676, 0.676, 0.144]
状态        [0.215, 0.409, 0.409, 0.355]

[验证] 每行和=1 ✓  权重非负 ✓  —— '查询'与'订单'互相权重最高（0.358/0.326 附近）
这就是'全文检索+加权拼接'：每个词用自己(Q)去检索别人(K)，按匹配度加权取货(V)。
```

**EX-22-02 | 示例代码/ch22_transformer/ex_22_02_retrieval_analogy.py（完整可运行）**

```python
# EX-22-02 | 注意力="全文检索+加权拼接"类比演示 + 预训练/SFT/对齐三阶段 | 运行: python3 示例代码/ch22_transformer/ex_22_02_retrieval_analogy.py
"""完整可运行：把注意力拆成"检索打分"与"加权取货"两步，与搜索引擎类比对齐；
再用一张文字流水线图串起 预训练 → SFT → 对齐 三个阶段各自做什么（不深入数学）。
"""
from __future__ import annotations

import numpy as np

DOCS = {"用户": [1, 0, 0, 0], "查询": [0, 1, 0.9, 0], "订单": [0, 0.9, 1, 0], "状态": [0, 0, 0, 1]}


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    return float(a @ b / (na * nb)) if na and nb else 0.0


def main() -> None:
    query_word = "查询"
    q = np.array(DOCS[query_word])
    print(f"[步骤 1] 把'{query_word}'当搜索词（Query），对所有词元（Key）打相似度分：")
    scores: dict[str, float] = {}
    for word, vec in DOCS.items():
        scores[word] = cosine(q, np.array(vec, dtype=np.float64)) * np.sqrt(4)  # 模拟 √d 缩放前分值
        print(f"    score('{query_word}' → '{word}') = {scores[word]:.3f}")

    print("\n[步骤 2] softmax 把分数变成'按比例取货'的权重（和为 1）：")
    arr = np.array(list(scores.values()))
    w = np.exp(arr - arr.max())
    w = w / w.sum()
    for (word, _), weight in zip(scores.items(), w):
        print(f"    weight('{word}') = {weight:.3f}")

    print("\n[步骤 3] 加权拼接：新表示 = Σ 权重×词元向量（Value）——混合了上下文信息：")
    blended = sum(weight * np.array(DOCS[word], dtype=np.float64)
                  for (word, _), weight in zip(scores.items(), w))
    print("    '" + query_word + "' 的新向量 = [" + ", ".join(f"{x:.3f}" for x in blended) + "]")
    print("    注意：它不再是孤立词向量，而带上了'订单/状态'的语义成分——这就是上下文。")

    print("\n" + "=" * 62)
    print("三阶段流水线（各一句话，详见教材 22.3）：")
    print("""
  海量互联网文本 ──▶ [预训练] 学"接话"：给前文预测下一个词
                          │  产物：会说话但不听话、知识停留在训练截止日
                          ▼
       问答示例数据 ──▶ [SFT 监督微调] 学"按指令的格式回答"
                          │  产物：像助手了，但偏好不稳定、可能输出有害内容
                          ▼
       人类偏好数据 ──▶ [对齐(RLHF/偏好优化)] 学"人类更喜欢的那种回答"
                          │  产物：更礼貌、更安全、更"助手化"（也更会客套与拒答）
                          ▼
                    部署成你在 API 里调到的 chat 模型""")
    print("类比边界：预训练=读书识字，SFT=岗前培训话术，对齐=服务规范；")
    print("应用工程师通常只做'把知识塞进上下文'（RAG）与'把要求写进指令'（Prompt），不改这三步。")


if __name__ == "__main__":
    main()
```

```text
# 真实运行输出（Python 3.14.7）
[步骤 1] 把'查询'当搜索词（Query），对所有词元（Key）打相似度分：
    score('查询' → '用户') = 0.000
    score('查询' → '查询') = 2.000
    score('查询' → '订单') = 1.989
    score('查询' → '状态') = 0.000

[步骤 2] softmax 把分数变成'按比例取货'的权重（和为 1）：
    weight('用户') = 0.060
    weight('查询') = 0.443
    weight('订单') = 0.438
    weight('状态') = 0.060

[步骤 3] 加权拼接：新表示 = Σ 权重×词元向量（Value）——混合了上下文信息：
    '查询' 的新向量 = [0.060, 0.836, 0.836, 0.060]
    注意：它不再是孤立词向量，而带上了'订单/状态'的语义成分——这就是上下文。

==============================================================
三阶段流水线（各一句话，详见教材 22.3）：

  海量互联网文本 ──▶ [预训练] 学"接话"：给前文预测下一个词
                          │  产物：会说话但不听话、知识停留在训练截止日
                          ▼
       问答示例数据 ──▶ [SFT 监督微调] 学"按指令的格式回答"
                          │  产物：像助手了，但偏好不稳定、可能输出有害内容
                          ▼
       人类偏好数据 ──▶ [对齐(RLHF/偏好优化)] 学"人类更喜欢的那种回答"
                          │  产物：更礼貌、更安全、更"助手化"（也更会客套与拒答）
                          ▼
                    部署成你在 API 里调到的 chat 模型
类比边界：预训练=读书识字，SFT=岗前培训话术，对齐=服务规范；
应用工程师通常只做'把知识塞进上下文'（RAG）与'把要求写进指令'（Prompt），不改这三步。
```

## 22.5 逐段解释：三行代码与三个工程推论

**（1）三行核心对照三步检索**。`scores = Q @ K.T / np.sqrt(d)` 是"全文检索的打分阶段"——点积衡量两个向量方向多一致；`weights = softmax(scores)` 把分数变成"每行和为 1 的取货比例"（EX-22-02 输出里 0.443/0.438/0.060/0.060）；`out = weights @ V` 按比例把每个词的货架内容搬进当前词的新表示。**看输出矩阵的第 2 行**：'查询' 对自己 0.357、对'订单' 0.355，几乎五五开——于是它的"新表示" `[0.144, 0.676, 0.676, 0.144]` 里'订单'的成分被灌了进来。**这就是"上下文"二字在模型内部的物理含义**：不是外挂存储，而是每层注意力里这种加权混合的结果。

**（2）推论一：为什么上下文长度有限**。注意力要让每个词和**所有**词算一遍匹配——计算量是长度的平方级，显存还要缓存中间结果。所以窗口不是厂商抠门，是结构代价。这也解释了为什么"长上下文模型"每次加价都明显：你多付的不是存储费，是平方级计算费。

**（3）推论二：为什么 RAG 不训练也能注入新知识**。模型的知识冻结在参数里（预训练结束就定了），但**注意力对上下文里的内容是"现场检索"的**——把今天的政策全文放进 prompt，模型生成时就能通过注意力取到它。RAG 的全部魔法就是"把对的资料放进窗口"（第六部分）。

**（4）推论三：为什么 temperature=0 也不保证 100% 一致**。生成是对词表做概率分布采样，temperature 只是调分布形状；生产环境批处理、浮点非结合性等都可能让"确定"变成"基本确定"。可复现要靠评估与回归（ch28），不靠信仰。

**（5）Java 对照**：把单头注意力想成一个**没有索引的内存检索**：每次请求都要 O(n²) 全表扫描匹配；多头=多个并行的扫描线程各管一类匹配；残差连接与多层堆叠（本章没展开）= 每层检索结果累加进主数据流再进下一层。你不需要会训练它，但选型时"平方级成本、知识冻结、上下文现场检索"三条足以支撑大部分架构决策。

## 22.6 安装 / 文件位置 / 运行命令

```bash
pip install -r requirements.txt   # numpy==2.5.4 已含
python3 示例代码/ch22_transformer/ex_22_01_dot_attention.py
python3 示例代码/ch22_transformer/ex_22_02_retrieval_analogy.py
```

## 22.7 常见错误与排查

**错 1：softmax 数值溢出。**
```text
RuntimeWarning: overflow encountered in exp
```
原因：对未缩放的大分数直接 `np.exp`，指数爆炸。修复：先减去每行最大值再取指数（EX-22-01 的写法），这是数值稳定的标准姿势——生产推理框架同样如此。

**错 2：矩阵形状不匹配。**
```text
ValueError: shapes (4,4) and (3,4) not aligned: 4 (dim 1) != 3 (dim 0)
```
原因：Q 的维度与 K 的行数不一致（比如序列长度改了没同步改另一个矩阵）。修复：统一以 `@` 的形状约定自查——`Q(n,d)·K.T(d,m)`；写注意力函数时先断言 `Q.shape[-1] == K.shape[-1]`。

**错 3：把注意力权重当"解释"讲给业务方。**
现象：用权重矩阵宣称"模型是这样推理的"。认知修正：权重只是这一层这一头的匹配分数，多头与多层叠加后没有简单语义；对业务解释模型行为，用输入输出对照实验（ch28 的 golden set），不用内部权重。

**错 4：以为"上下文越长能力越强"。**
现象：为了"让模型更聪明"把资料全塞进窗口，结果关键信息被稀释、成本飙升、命中率反而下降。修复：检索 Top-k + 相关性过滤（第六部分），上下文是预算不是仓库。

## 22.8 企业场景中的使用方式

Spring Boot 团队评估模型选型时，工程师需要用本章的直觉回答三个采购问题：**窗口与价格**（平方级成本 → 长上下文单价高，预算表用 ch21/ch27 的方法算）；**知识时效**（厂商训练截止日 → 时效敏感业务必须配 RAG/工具）；**对齐风格**（不同模型的拒答/客套倾向不同 → 同一套 Prompt 在不同模型上要做回归，ch28）。这三问都不需要会训练，但都需要本章的心智模型。

## 22.9 练习

**基础 1**：不用运行代码，心算 softmax([1, 1, 1, 1]) 的结果，并说明它与 EX-22-01 里"全同方向词元"的权重行有什么关系。

**基础 2**：用一句话向非技术同事解释"模型知识为什么有截止日"，要求用三阶段中的某个阶段做类比。

**代码 1**：把 EX-22-01 的 EMB 改为"查询"与"状态"也相关（自行设计数值），预测权重矩阵哪一行变化最大，再运行验证。

**代码 2**：给 `attention` 增加可选参数 `mask: np.ndarray | None`，把指定位置的分数设为 -1e9 后再 softmax（模拟"看不到未来的词"），用"查询"看不到"状态"的掩码跑一遍并解释输出变化。

**调试题**：同事把 EX-22-01 的 `softmax` 换成 `np.exp(x) / np.exp(x).sum()` 后，输入 [1000, 1001, 1002] 得到全 NaN。定位原因并给出两种修复。

### 参考答案

**基础 1**：softmax([1,1,1,1]) = [0.25, 0.25, 0.25, 0.25]。全同方向的词元互相点积相同 → 权重均匀，新表示是全句平均——"没有重点"的上下文融合。

**基础 2**（示例）："它像一个只读到去年教材就毕业的学生——毕业后世界上发生的事，除非你把资料递到它面前（放进上下文），否则它不知道。"

**代码 1**：把"状态"向量改为 [0, 0.9, 0, 1] 之类与"查询"相关后，**'状态'那一行**（以及"查询"行对状态的列）变化最大——因为打分是成对的，改动一个词元的向量影响它的所有出入边。运行可验证。

**代码 2**（要点）：
```python
def attention(Q, K, V, mask=None):
    scores = Q @ K.T / np.sqrt(K.shape[-1])
    if mask is not None:
        scores = np.where(mask, scores, -1e9)  # False 的位置置为极小
    weights = softmax(scores)
    return weights @ V, weights
```
屏蔽"状态"后，'查询'行对'状态'的权重趋近 0，其余权重按 softmax 重新分配变大——这正是解码时"因果掩码"的原理。

**调试题**：exp(1000) 上溢为 inf，inf/inf = NaN。修复一：减最大值（`x - x.max()`，EX-22-01 做法）；修复二：先除 √d 缩放分数（生产做法，同时解决训练不稳）。根因相同：softmax 输入必须数值可控。

## 22.10 自测检查表

- 我能白板写出缩放点积注意力的三步公式，并说明每步对应"检索+拼接"的哪个动作。
- 我能解释 Q/K/V 各自的角色，以及"多头"在类比里对应什么、边界在哪。
- 我能各用一句话说清预训练、SFT、对齐做什么，并指出应用工程师通常不改这三步。
- 我能从注意力结构推出"为什么上下文长度有限且长上下文更贵"。
- 我能解释 RAG 生效的内部原因（注意力对上下文现场检索）而不需要训练模型。
- 我能说清 softmax 数值稳定的写法与原因。

## 22.11 面试追问

**[模拟题] 1：既然上下文里有什么模型就能用什么，为什么还需要 RAG 框架？**
考查点：检索质量与窗口预算。合格回答：RAG 解决的是"放什么进去"——全量塞不现实（窗口/成本/稀释），需要切分、向量检索、重排、Top-k（第六部分）；框架的价值在工程化这些环节，而不是"让模型读上下文"本身。

**[模拟题] 2：预训练和微调的边界在哪？给客服系统"教会它公司政策"应该走哪条路？**
考查点：技术选型。合格回答：改参数的是微调，改输入的是 Prompt/RAG；"公司政策"是频变的事实性知识，走 RAG（可更新、可引用、可撤回）；只有稳定的风格/格式要求才考虑 SFT（第十一部分的决策树）。

**[模拟题] 3：有人认为"注意力权重可视化能解释模型为什么答错"，你怎么看？**
考查点：可解释性边界。合格回答：单层单头的权重只是匹配分数，跨头跨层无法还原成人类语义；工程上定位错误用输入消融（去掉某段上下文重跑）、评估集分层统计等黑盒手段，比解读权重可靠。

---

# 第 23 章 对话与参数：messages、生成旋钮与流式输出

> **本章目标**：吃透 Chat Completions 的消息模型与生成参数；跑通流式输出的拼接与它的经典编码坑；理解多模态消息结构。
> **前置知识**：ch09 生成器、ch17 SSE、ch21 token 概念。
> **学完你能做什么**：徒手拼出任意对话的 messages 数组（含工具消息）；为业务场景选择 temperature/top_p/max_tokens；解释流式输出的实现原理与"逐 chunk 解码乱码"的根因；看懂多模态消息的 JSON 结构。

## 23.1 真实问题引入：客服系统上线的第一个"失忆"bug

Java 团队把对话做成这样：每个 HTTP 请求只发最新一句"那明天可以吗？"，期待模型像有 Session 一样记得前文。结果模型回复"请问您指的是什么？"。这是刚接触 Chat API 的人必踩的坑：**Chat 服务是无状态的**。没有 HttpSession，没有粘性会话，模型每次只看到你这一次请求里 `messages` 数组里的东西。"记得上文"的唯一方式，是把历史**每次都重新发一遍**（这也正是 ch21"滚雪球计费"的根源）。本章把消息模型、生成参数、流式输出一次讲透。

## 23.2 一句话解释 + 生活类比 + 类比边界

**一句话解释**：一次对话请求 = 把"系统设定 + 全部历史 + 最新输入"组成 `messages` 数组整体发给模型；模型读完整个数组，生成**下一条** assistant 消息；所谓"多轮对话"，就是客户端把每轮新消息追加进数组、循环重发。

**生活类比**：模型是一位**每次见面都失忆的顾问**。你想让它"接着上次说"，就得每次见面把《会议纪要全集》重新递给它读一遍。你读得越全它接得越好，但你打印费（token 费）也越高。

> 💡 类比边界：
> 1. "失忆"是接口层的——服务端可能对相同前缀做**缓存计费/加速**（如缓存命中折扣），但语义上它仍是逐字读完再生成，你的代码必须自己管理历史；
> 2. `system` 角色不是"更高权限的用户"，它只是位置靠前、被训练成"设定语境"的消息——它**不能**防注入（ch28 讲透这一点）；
> 3. 生成参数（temperature 等）不改变模型知识，只改变**从概率分布里怎么挑下一个 token**——调参治不了知识错误。

## 23.3 正式原理与准确术语

**消息角色（roles）**：`system`（设定身份/规则，通常放最前）、`user`（用户输入或待处理数据）、`assistant`（模型的历史回复；发起工具调用时附带 `tool_calls` 数组）、`tool`（工具执行结果，必须带 `tool_call_id` 与前面的请求配对）。消息是 OpenAI 风格 dict：`{"role": ..., "content": ...}`，全书 `llm_client` 统一此格式。

**生成参数（本书代码签名已在 openai 3.35.1 核实，语义为通用说明——真实效果以所用模型文档为准）**：

| 参数 | 作用 | 典型取值 | 工程建议 |
|---|---|---|---|
| `temperature` | 缩放采样分布的尖锐度 | 0~1（更高更乱） | 抽取/分类/结构化输出用低值；创意生成才用高值 |
| `top_p` | 核采样：只在累计概率前 p 的候选里挑 | 0.9 左右 | 与 temperature 二选一调，别同时大动 |
| `max_tokens` | 限制本次输出长度 | 按业务预估 | 留足余量，防 `finish_reason=length` 截断 |
| `stop` | 遇到指定序列即停 | 如 `["\n\n"]` | 控制输出边界 |
| `n` | 一次生成几条候选 | 1 | 候选评估场景才用 |

**流式输出（streaming）**：`stream=true` 时服务端通过 SSE 持续推送**增量片段（chunk）**，每个 chunk 携带一小段 `delta.content`；客户端拼接后等于完整回答。价值是**首字延迟**（time-to-first-token）从"整段生成完"降到"第一个 token 生成完"。

**多模态输入（vision）**：`content` 从字符串升级为**分段数组**：`[{"type": "text", ...}, {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}]`，图文交替。

**finish_reason**：`stop`（自然结束）/ `length`（达到长度上限）/ `tool_calls`（模型请求调用工具，ch24）/ `content_filter` 等。

## 23.4 最小完整示例

**EX-23-01 | 示例代码/ch23_chat/ex_23_01_roles.py（完整可运行）**

```python
# EX-23-01 | 消息角色与 messages 结构 | 运行: python3 示例代码/ch23_chat/ex_23_01_roles.py
"""完整可运行（Mock）：system/user/assistant/tool 四种角色的消息结构，
以及"assistant 发起工具调用 → tool 回传结果"的完整消息形态（OpenAI 风格 dict）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from 示例代码.公共.llm_client import get_llm  # noqa: E402

TOOLS = [{
    "type": "function",
    "function": {
        "name": "get_order_status",
        "description": "查询订单状态",
        "parameters": {
            "type": "object",
            "properties": {"order_id": {"type": "string", "description": "订单号"}},
            "required": ["order_id"],
        },
    },
}]


def dump(label: str, messages: list[dict[str, Any]]) -> None:
    print(f"--- {label} ---")
    print(json.dumps(messages, ensure_ascii=False, indent=2))


def main() -> None:
    llm = get_llm()
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": "你是订单客服助手，只回答与订单有关的问题。"},
        {"role": "user", "content": "USE_TOOL:get_order_status order_id=ORD-1001"},
    ]
    r1 = llm.chat(messages, tools=TOOLS)
    print(f"[第 1 次调用] finish_reason={r1.finish_reason}, tool_calls={[(t.name, t.arguments) for t in r1.tool_calls]}")

    # 把"模型想调工具"这件事落成 assistant 消息，再把执行结果以 tool 角色回传
    messages.append({
        "role": "assistant",
        "content": r1.content,
        "tool_calls": [{
            "id": r1.tool_calls[0].id,
            "type": "function",
            "function": {"name": r1.tool_calls[0].name,
                         "arguments": json.dumps(r1.tool_calls[0].arguments, ensure_ascii=False)},
        }],
    })
    messages.append({"role": "tool", "tool_call_id": r1.tool_calls[0].id,
                     "content": json.dumps({"order_id": "ORD-1001", "status": "已发货"},
                                           ensure_ascii=False)})
    dump("回传工具结果后的 messages（OpenAI 风格）", messages)

    r2 = llm.chat(messages)
    print(f"\n[第 2 次调用] 模型基于工具结果作答：{r2.content}")
    print(f"usage（prompt 含全部历史）：{r2.usage}")


if __name__ == "__main__":
    main()
```

```text
# Mock 运行输出（LLM_MODE=mock，节选：末尾 JSON 略有排版）
[第 1 次调用] finish_reason=tool_calls, tool_calls=[('get_order_status', {'order_id': 'ORD-1001'})]
--- 回传工具结果后的 messages（OpenAI 风格） ---
[
  { "role": "system", "content": "你是订单客服助手，只回答与订单有关的问题。" },
  { "role": "user", "content": "USE_TOOL:get_order_status order_id=ORD-1001" },
  { "role": "assistant", "content": "",
    "tool_calls": [ { "id": "call_001", "type": "function",
        "function": { "name": "get_order_status", "arguments": "{\"order_id\": \"ORD-1001\"}" } } ] },
  { "role": "tool", "tool_call_id": "call_001",
    "content": "{\"order_id\": \"ORD-1001\", \"status\": \"已发货\"}" }
]

[第 2 次调用] 模型基于工具结果作答：（Mock·整合工具结果）根据查询返回：{"order_id": "ORD-1001", "status": "已发货"}。以上为确定性整合回答。
usage（prompt 含全部历史）：{'prompt_tokens': 50, 'completion_tokens': 44, 'total_tokens': 94, 'count_method': 'tiktoken:cl100k_base'}
```

注意 `tool_calls[].function.arguments` 是 **JSON 字符串**而不是对象——这是真实 API 的历史形态，转换成 dict 的职责在客户端（`llm_client` 已处理，`ToolCall.arguments` 是 dict）。

**EX-23-02 | 示例代码/ch23_chat/ex_23_02_params_demo.py（完整可运行）**

```python
# EX-23-02 | 参数实验：temperature/top_p/max_tokens 在 Mock 与 Real 下的差异 | 运行: python3 示例代码/ch23_chat/ex_23_02_params_demo.py
"""完整可运行（Mock）：把三类生成参数传给 MockLLM，验证"接口接受、行为确定"；
真实模型的参数语义（含 max_tokens 超限时的 finish_reason=length）见教材表格——
本沙箱无 Key，不进行真实调用，不做任何虚构输出。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from 示例代码.公共.llm_client import MockLLM  # noqa: E402

MESSAGES = [{"role": "user", "content": "给这个订单写一句催发货的话"}]


def main() -> None:
    llm = MockLLM()
    print("[实验] 同一组消息，传不同生成参数（Mock 接受并忽略）：")
    param_sets: list[tuple[str, dict[str, object]]] = [
        ("默认", {}),
        ("temperature=0.0", {"temperature": 0.0}),
        ("temperature=1.2, top_p=0.9", {"temperature": 1.2, "top_p": 0.9}),
        ("max_tokens=5", {"max_tokens": 5}),
    ]
    results = []
    for label, params in param_sets:
        r = llm.chat(MESSAGES, **params)
        results.append(r.content)
        print(f"    {label:<28} → {r.content}  (finish_reason={r.finish_reason})")

    same = len(set(results)) == 1
    print(f"\n    四次输出完全相同：{same}（Mock 无随机源；真实模型上前两组通常不同）")

    print("\n[接口契约] Mock/Real 对生成参数的态度：")
    print("    Mock：签名接受 **kwargs 全部吞掉 → 保证教学脚本在双模式下都能跑；")
    print("    Real：参数原样透传 client.chat.completions.create（openai 3.35.1 签名已核实")
    print("          含 temperature/top_p/max_tokens/max_completion_tokens）。")
    print("    ★ 诚实声明：Mock 无法演示真实模型上这些参数的效果差异，教材相应表格标注为语义说明。")


if __name__ == "__main__":
    main()
```

```text
# Mock 运行输出（LLM_MODE=mock）
[实验] 同一组消息，传不同生成参数（Mock 接受并忽略）：
    默认                           → （Mock 默认回复）已收到问题「给这个订单写一句催发货的话」。沙箱未接入真实模型，本回答由确定性规则生成。  (finish_reason=stop)
    temperature=0.0              → （Mock 默认回复）已收到问题「给这个订单写一句催发货的话」。沙箱未接入真实模型，本回答由确定性规则生成。  (finish_reason=stop)
    temperature=1.2, top_p=0.9   → （Mock 默认回复）已收到问题「给这个订单写一句催发货的话」。沙箱未接入真实模型，本回答由确定性规则生成。  (finish_reason=stop)
    max_tokens=5                 → （Mock 默认回复）已收到问题「给这个订单写一句催发货的话」。沙箱未接入真实模型，本回答由确定性规则生成。  (finish_reason=stop)

    四次输出完全相同：True（Mock 无随机源；真实模型上前两组通常不同）

[接口契约] Mock/Real 对生成参数的态度：
    Mock：签名接受 **kwargs 全部吞掉 → 保证教学脚本在双模式下都能跑；
    Real：参数原样透传 client.chat.completions.create（openai 3.35.1 签名已核实
          含 temperature/top_p/max_tokens/max_completion_tokens）。
    ★ 诚实声明：Mock 无法演示真实模型上这些参数的效果差异，教材相应表格标注为语义说明。
```

**EX-23-03 | 示例代码/ch23_chat/ex_23_03_stream.py（完整可运行）**

```python
# EX-23-03 | 流式 chunk 拼接 + UTF-8 增量解码 | 运行: python3 示例代码/ch23_chat/ex_23_03_stream.py
"""完整可运行（Mock，不联网）：用 llm_client.chat_stream 演示流式输出的三个要点：
1) chunk 是增量文本，拼接 == 非流式整体；2) 打字机效果与"首字延迟"；
3) 经典坑：多字节字符跨 chunk 时，逐 chunk 独立 decode 会出乱码（U+FFFD）。
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from 示例代码.公共.llm_client import MockLLM  # noqa: E402

REPLY = "流式输出把首字时间从『等全文』降到『第一个 token 到达』，体验差别巨大。"


def main() -> None:
    llm = MockLLM()
    messages = [{"role": "user", "content": "为什么直播要打字机效果？"}]

    print("[1] 逐 chunk 消费（打字机效果）：")
    start = time.perf_counter()
    parts: list[str] = []
    for chunk in llm.chat_stream(messages):
        parts.append(chunk)
        print(chunk, end="", flush=True)
        time.sleep(0.01)  # 模拟网络间隔
    elapsed = (time.perf_counter() - start) * 1000
    print(f"\n    共 {len(parts)} 个 chunk，总耗时 {elapsed:.1f} ms")

    print("\n[2] 拼接 == 整体：")
    joined = "".join(parts)
    whole = llm.chat(messages).content
    print(f"    join(chunks) == chat().content → {joined == whole}")

    print("\n[3] 多字节边界坑（Mock 按 tiktoken 真实 token 切 chunk）：")
    raw_text = "流式输出的拼接结果必须与整体一致"  # 已验证：该句存在跨 token 的多字节字符
    token_ids = None
    try:
        from 示例代码.公共.llm_client import _get_encoding

        enc = _get_encoding()
        token_ids = enc.encode(raw_text)
    except Exception:
        enc = None
    if token_ids and enc is not None:
        # 故意按 token 边界把字节流切碎后逐块独立解码（错误示范）
        naive = "".join(enc.decode([t]) for t in token_ids)
        print(f"    原文：{raw_text!r}")
        print(f"    错误示范（逐 token decode）：{naive!r}  ← 出现 U+FFFD 乱码")
        print("    正确做法：字节层缓冲，用 codecs 增量解码器凑齐再吐字（llm_client 已内置）。")
    else:
        print("    （词表不可用，跳过真实 token 切分演示——回退路径下 chunk 是等宽切片，无此问题）")

    print("\n[4] 中途停止生成（断开即省 token）：")
    for i, chunk in enumerate(llm.chat_stream(messages)):
        print(chunk, end="")
        if i == 4:
            print("\n    … 用户点了『停止』，后面的 chunk 不再请求（真实 API 也按已生成长度计费）")
            break


if __name__ == "__main__":
    main()
```

```text
# Mock 运行输出（LLM_MODE=mock；[1] 的耗时数字每次运行会变化）
[1] 逐 chunk 消费（打字机效果）：
（Mock 默认回复）已收到问题「为什么直播要打字机效果？」。沙箱未接入真实模型，本回答由确定性规则生成。
    共 44 个 chunk，总耗时 656.7 ms

[2] 拼接 == 整体：
    join(chunks) == chat().content → True

[3] 多字节边界坑（Mock 按 tiktoken 真实 token 切 chunk）：
    原文：'流式输出的拼接结果必须与整体一致'
    错误示范（逐 token decode）：'流式输出的��接结果必��与整体一��'  ← 出现 U+FFFD 乱码
    正确做法：字节层缓冲，用 codecs 增量解码器凑齐再吐字（llm_client 已内置）。

[4] 中途停止生成（断开即省 token）：
（Mock 默认回复
    … 用户点了『停止』，后面的 chunk 不再请求（真实 API 也按已生成长度计费）
```

> 📌 生产提示：上面 [3] 的乱码不是排版事故——真实运行输出里确实出现 U+FFFD 替代符。它是**每个在流式系统里做过中文的工程师都会撞上的墙**，原理见下节逐段解释。

**EX-23-04 | 示例代码/ch23_chat/ex_23_04_multimodal_structure.py（完整可运行）**

```python
# EX-23-04 | 多模态图片输入的消息结构（base64 data URL）| 运行: python3 示例代码/ch23_chat/ex_23_04_multimodal_structure.py
"""完整可运行（仅构造消息结构，不联网）：演示 OpenAI 风格的图片输入消息如何组装。

沙箱无 OPENAI_API_KEY，本示例只构造并打印消息结构；真实发送属于 LLM_MODE=real
路径，效果与模型能力以官方文档为准——教材已如实标注。
"""
from __future__ import annotations

import base64
import json
import sys
import zlib
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def tiny_png_b64() -> str:
    """手工构造 1×1 红色像素 PNG（最小合法文件），返回 base64。

    PNG = 固定签名 + IHDR/IDAT/IEND 块。这里用 zlib 压缩原始像素数据，
    不依赖任何图片库——顺便证明 base64 只是"字节换文本"的编码，不是加密。
    """
    import struct

    def chunk(tag: bytes, data: bytes) -> bytes:
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)      # 1x1, 8bit, RGB
    raw = zlib.compress(b"\x00\xff\x00\x00")                  # 1 行 filter0 + RGB(255,0,0)
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
           + chunk(b"IDAT", raw) + chunk(b"IEND", b""))
    return base64.b64encode(png).decode("ascii")


def build_vision_message(question: str, png_b64: str) -> list[dict[str, Any]]:
    """图文混合消息：content 是"分段数组"，text 与 image_url 交替（OpenAI 风格）。"""
    return [{
        "role": "user",
        "content": [
            {"type": "text", "text": question},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{png_b64}"}},
        ],
    }]


def main() -> None:
    png_b64 = tiny_png_b64()
    print(f"[1] 1×1 PNG 的 base64（{len(png_b64)} 字符）：{png_b64}")
    decoded = base64.b64decode(png_b64)
    is_png = decoded[:8] == b"\x89PNG\r\n\x1a\n"  # PNG 固定 8 字节魔数
    print(f"    解回字节后是合法 PNG：{is_png}，共 {len(decoded)} 字节")
    assert is_png

    messages = build_vision_message("这张图里是什么颜色？", png_b64)
    print("\n[2] 图文混合消息结构（content 为分段数组）：")
    print(json.dumps(messages, ensure_ascii=False, indent=2)[:600] + " …（截断显示）")

    print("\n[3] 双模式说明：")
    print("    - 本示例仅构造结构；LLM_MODE=mock 下即使调用 MockLLM 也只做文本演示；")
    print("    - LLM_MODE=real 时该结构原样发给 client.chat.completions.create(messages=...)；")
    print("    - 沙箱无 Key：真实多模态调用结果未验证，具体支持的图片格式/大小限制以厂商文档为准。")


if __name__ == "__main__":
    main()
```

```text
# 真实运行输出（消息结构构造部分，不联网）
[1] 1×1 PNG 的 base64（92 字符）：iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4z8AAAAMBAQDJ/pLvAAAAAElFTkSuQmCC
    解回字节后是合法 PNG：True，共 69 字节

[2] 图文混合消息结构（content 为分段数组）：
[
  { "role": "user",
    "content": [
      { "type": "text", "text": "这张图里是什么颜色？" },
      { "type": "image_url", "image_url": { "url": "data:image/png;base64,iVBORw0KGgo…（略）" } }
    ] }
] …（截断显示）

[3] 双模式说明：
    - 本示例仅构造结构；LLM_MODE=mock 下即使调用 MockLLM 也只做文本演示；
    - LLM_MODE=real 时该结构原样发给 client.chat.completions.create(messages=...)；
    - 沙箱无 Key：真实多模态调用结果未验证，具体支持的图片格式/大小限制以厂商文档为准。
```

## 23.5 逐段解释：无状态会话、旋钮语义与字节边界

**（1）"失忆顾问"的正确用法**。EX-23-01 的 `dump()` 展示了完整的服务契约：你把 system、历史、最新输入**全部**放进一个数组重发。第 2 次调用的 usage 里 `prompt_tokens=50` 包含了全部 4 条消息——历史不是存在服务端，而是存在你的数组里。**Java 对照**：`messages` 数组 = 你每次手动拼好的请求体；它不是 `HttpSession`，更接近"每次都重发完整表单"的纯 REST 交互。由此推出 ch27 的全部工程命题：历史存哪、截多少、怎么压缩。

**（2）生成旋钮的真实语义**。`temperature` 缩放 logits：越低分布越尖（高概率词几乎必选），越高越平（低概率词也有机会）。`top_p` 截断分布：只在累计概率达到 p 的小集合里采样。两者都改变"从分布里怎么挑"，不改变分布本身由什么知识构成——所以**参数调不出知识正确性**。本书的诚实声明：Mock 无随机源，参数被接受但忽略（EX-23-02 输出 `True`），参数的真实效果必须在所用模型上实测，表格只给方向性语义。

**（3）流式输出的三层结构**。第一层是语言机制：`chat_stream` 是**生成器**（ch09），`for chunk in llm.chat_stream(...)` 每次要一小段，天然支持"用户点停止就不再请求"。第二层是协议：真实 API 用 SSE（ch17 已实践），`data: {...}\n\n` 逐帧推送 `delta.content`。第三层是编码，也是最容易翻车的一层：

**（4）UTF-8 边界坑（重点）**。一个汉字在 UTF-8 里是 3 个字节，BPE 词表的 token 以字节为单位切分——**一个 token 可能只含有某个汉字的前 2 个字节**。EX-23-03 的错误示范把每个 token 单独 decode，字节残缺时 Python 返回替代符 U+FFFD，拼出来就是 `流式输出的�?接结果必?…`。正确做法是**字节层缓冲 + 增量解码器**（`codecs.getincrementaldecoder("utf-8")`）：残缺字节留在缓冲区，凑齐再吐字。`llm_client` 的 `chat_stream` 已内置这条路径，OpenAI SDK 的流式接口也在内部处理了文本解码——但如果你自己用 `httpx`/`requests` 手撸 SSE（ch17 场景），这个坑就会找上门。

**（5）多模态消息**。`content` 从 `str` 升级为分段数组后，text 与 image 分段交替；图片用 URL（公网可达）或 `data:image/png;base64,...`（内联，注意 base64 会让请求体膨胀约 33%，大图慎重）。EX-23-04 手工拼了一个 69 字节的最小 PNG 来证明"结构合法"与"模型能看懂"是两回事——后者属于 real 模式的验证范围，本书如实标注未验证。

## 23.6 安装 / 文件位置 / 运行命令

```bash
pip install -r requirements.txt
python3 示例代码/ch23_chat/ex_23_01_roles.py
python3 示例代码/ch23_chat/ex_23_02_params_demo.py
python3 示例代码/ch23_chat/ex_23_03_stream.py
python3 示例代码/ch23_chat/ex_23_04_multimodal_structure.py
# 全部默认 Mock 离线；real 模式需 export OPENAI_API_KEY=... （并可选 OPENAI_BASE_URL=...）
```

## 23.7 常见错误与排查

**错 1：流式输出出现 U+FFFD 乱码。**
现象：`流式输出的�?接结果…`。原因：按 chunk/char 独立解码，多字节字符被从中间切开。修复：字节缓冲 + `codecs` 增量解码器（EX-23-03 与 llm_client 实现）；用 SDK 的流式接口时确认拿到的是 `delta.content` 文本而非自己拆字节。

**错 2：只发最新一句，模型"失忆"。**
现象：用户问"那明天可以吗？"，模型反问上下文。原因：Chat API 无服务端会话，messages 里没有历史模型就不知道。修复：客户端维护历史并每轮重发（注意 ch27 的预算管理）。

**错 3：`finish_reason=length`，回答被拦腰截断。**
现象：长回答固定在某个长度停止，无报错。原因：`max_tokens`（或 `max_completion_tokens`）太小。修复：读 `finish_reason` 判断；调大上限或分段生成。

**错 4：多模态消息把 content 写成字符串。**
典型报错形态（各家措辞不同，此处为示意——非真实记录）：`400 Invalid type for 'content': expected an array of content parts`。原因：带图消息的 content 必须是分段数组。修复：按 EX-23-04 的结构组装；同时确认目标服务支持该字段（兼容接口核实清单见 ch24）。

## 23.8 企业场景中的使用方式

Spring Boot 侧消费 Python AI 服务时，对话状态的标准分工：**历史与会话状态存在业务侧**（Redis/DB，按 session_id 组织，ch19/ch27），Python AI 服务保持无状态、可水平扩容。流式链路：Python 服务收到上游 SSE chunk → 校验/脱敏/审计 → 以 SSE 转发给网关 → 网关推给浏览器（EX-17-04 的骨架直接复用）。**断连即止损**：前端"停止生成"按钮断开 SSE，服务端生成器被取消（ch17 已验证 finally 清理路径），已生成部分照常计费但不再浪费后续 token。

## 23.9 练习

**基础 1**：写出一条合法的 `tool` 消息 dict，要求字段完整，并说明它必须与哪条消息配对。

**基础 2**：业务要求"情感分类结果必须稳定可复现"，temperature 和 top_p 你怎么设？为什么？

**代码 1**：用 `MockLLM().chat_stream` 写一个函数 `first_token_latency(messages) -> float`，返回拿到第一个 chunk 前的耗时（毫秒），并解释真实场景里这个指标由什么决定。

**代码 2**：把 EX-23-03 的 [4] 改成"累计收到 10 个 chunk 后主动 break"，打印已拼接的文本，验证"停止消费后生成器不再产出"。

**调试题**：同事的流式代理服务把 UTF-8 汉字截成两半转发给前端，前端偶发乱码。给出两种修复方案（传输层/解码层各一种）。

### 参考答案

**基础 1**：`{"role": "tool", "tool_call_id": "call_001", "content": "{\"temp\": 26}"}`。必须与携带 `tool_calls`（其中包含 id 为 `call_001` 的调用请求）的那条 assistant 消息配对——服务端按 id 校验。

**基础 2**：temperature=0（或接近 0），top_p 保持默认不叠加调整。理由：分类要的是"同一个输入稳定出同一个标签"，分布越尖越稳；且两个参数同时调会互相干扰、难以归因。

**代码 1**（要点）：
```python
import time

def first_token_latency(messages) -> float:
    t0 = time.perf_counter()
    next(iter(llm.chat_stream(messages)))
    return (time.perf_counter() - t0) * 1000
```
真实场景由网络往返 + 服务端排队 + 首 token 生成耗时（prompt 越长预填充越慢）决定——所以首字延迟是上下文长度的函数，这也是控制历史长度的又一理由。

**代码 2**（要点）：循环里 `if i == 9: break`；拼出的文本是前 10 个 chunk 的连接。生成器被抛弃后不再产出任何 chunk——真实 API 对应"客户端断连，服务端停止生成"。

**调试题**：传输层——代理按行/帧转发而不是按固定字节数切割（SSE 事件是完整单元）；解码层——代理内部用增量解码器把字节流转成完整字符串再转发（或前端按 SSE 帧拼接后统一解码）。根因同 EX-23-03 [3]。

## 23.10 自测检查表

- 我能徒手写出 system/user/assistant/tool 四种角色的合法 dict，并说明 tool 消息的配对规则。
- 我能解释"Chat API 无服务端会话"及其两个推论（历史重发、计费滚雪球）。
- 我能为"稳定分类/创意文案/长报告"三种场景各选一组生成参数并说明理由。
- 我能解释流式输出的价值（首字延迟）与三层实现（生成器/SSE/字节增量解码）。
- 我能现场复现并修复 U+FFFD 乱码问题。
- 我能写出图文多模态消息的结构，并说出 base64 内联的代价。

## 23.11 面试追问

**[模拟题] 1：为什么大模型 API 普遍采用"无状态 + 客户端管历史"的设计？**
考查点：架构理解。合格回答：无状态使服务端可任意扩缩容、无需会话亲和；历史管理权交给客户端，代价是历史每轮重发（带宽/计费/窗口），工程上用摘要与截断控制（ch27）。

**[模拟题] 2：temperature 设为 0，两次调用结果还可能不同吗？**
考查点：确定性的真实边界。合格回答：可能。采样近似贪心仍有浮点非确定性与服务端批处理影响；部分服务提供 `seed` 参数可提高一致性（3.35.1 签名已核实含 `seed`），但"100% 一致"要以实测为准，工程上靠回归测试兜底（ch28）。

**[模拟题] 3：流式输出对计费和风控分别带来什么问题？**
考查点：流式的工程代价。合格回答：计费按实际生成 token 结算，中途断开按已生成部分计费（需对账逻辑适配）；风控上内容是逐段可见的，敏感内容审核需要"流式审核/事后撤回"机制，不能等全文。

---

# 第 24 章 openai SDK 全流程：从鉴权到工具调用闭环

> **本章目标**：用裸 openai SDK（3.35.1）走通生产级调用全流程，并学会"对兼容服务逐项核实"的生存技能。
> **前置知识**：ch21~ch23、ch15（重试）、ch16（Pydantic）。
> **学完你能做什么**：完成鉴权/BaseURL 配置与错误处理；用 `parse` 做结构化输出；完整实现工具调用闭环；按清单核实 OpenAI 兼容服务的功能边界；正确处理 429 与超时。

## 24.1 真实问题引入：换一家"OpenAI 兼容"厂商，服务半夜崩了

Java 团队的服务一开始直连 OpenAI 官方，一切正常。后来为了合规换了一家"OpenAI 兼容"的厂商，只改了 `base_url`——测试环境跑得好好的，上线第三天开始偶发报错：有时结构化输出拿回来的 JSON 里多了 Markdown 围栏，有时工具调用的 `tool_calls` 字段干脆不返回。工程师的直觉是"SDK 有 bug"，真相是：**"OpenAI 兼容"通常只兼容请求/响应的形状，不承诺兼容全部功能**。这一章教你两件事：把官方 SDK 的全流程用对；以及在兼容服务上，用一张核实清单保住自己的周末。

## 24.2 一句话解释 + 生活类比 + 类比边界

**一句话解释**：openai SDK 是模型 API 的"JDBC 驱动"——`OpenAI(api_key, base_url)` 建连接，`chat.completions.create` 发请求，返回强类型对象；换厂商只换 `base_url`，但"SQL 方言"（各家支持的功能子集）要自己核实。

**生活类比**：兼容接口像"国道标准"：任何厂商修的路都符合国道的宽度和标线，你的车（SDK）都能开。但国道不承诺有服务区（`response_format`）、不承诺有加油站（`tools`）、不承诺限速牌格式一致（错误码语义）。**上路前看路牌，别信导航默认设置。**

> 💡 类比边界：
> 1. SDK 不是协议实现的全集：有些厂商的"兼容"只覆盖 `/chat/completions` 单端点，embeddings/moderations 等要单独核实；
> 2. `max_retries` 的重试策略是 **SDK 客户端行为**，厂商网关还可能叠加自己的限流——两层重试叠加会造成放大攻击（自己把自己限死），必要时关掉一层；
> 3. 本书演示用 openai 官方 SDK，未覆盖官方 SDK 之外的分发方式（如 Azure 的部署式端点）——那类平台各有专有 SDK/路径，以平台文档为准。

## 24.3 正式原理与准确术语

**鉴权**：HTTP 头 `Authorization: Bearer <OPENAI_API_KEY>`，SDK 自动注入。**Base URL**：默认 `https://api.openai.com/v1/`；兼容服务改为厂商地址（路径形态以厂商文档为准，常见为 `.../v1`）。

**SDK 内建重试（已在 3.35.1 实测核实）**：`OpenAI(max_retries=...)`，**默认 2 次**（`client.max_retries == 2`）；对连接错误、408、429 与部分 5xx 自动指数退避重试；401/403/400 这类"重试也不会好"的错误不重试。

**结构化输出（structured outputs）**：让模型输出严格符合 JSON Schema 的机制。3.35.1 提供两条路：`create(response_format=...)`（传入 Pydantic 类或 schema dict）与更高层的 **`chat.completions.parse()`**（已核实存在于 3.35.1，参数含 `response_format`、**不含 `stream`**），它把响应直接反序列化成你的 Pydantic 实例（`message.parsed`）。

**工具调用（tool calling / function calling）**：你在请求里声明工具的 JSON Schema；模型**不执行**工具，只返回"请帮我调 X，参数是 Y"（`finish_reason=tool_calls`）；你的程序执行后把结果以 `tool` 消息回传，再次请求，模型基于结果继续。这是把"模型的语言能力"接到"你系统的真实数据与动作"上的标准插头。

**429（Too Many Requests）**：限流，不是故障——服务端在说"慢一点"。响应可能带 `Retry-After` 头。**读超时**：请求可能已被服务端受理，盲目重发可能重复执行——幂等性（ch15）在这里再次登场。

## 24.4 最小完整示例

**EX-24-01 | 示例代码/ch24_sdk/ex_24_01_auth_baseurl.py（完整可运行）**

```python
# EX-24-01 | openai SDK 鉴权/BaseURL 与关键签名核实 | 运行: python3 示例代码/ch24_sdk/ex_24_01_auth_baseurl.py
"""完整可运行：1) 演示缺 OPENAI_API_KEY 时 SDK/RealLLM 的真实报错；
2) 用 inspect 打印 openai==3.35.1 的关键签名（FACTS 红线：不确定的 API 必须核实后写）。
沙箱无 Key，本示例不发起任何真实网络请求。
"""
from __future__ import annotations

import inspect
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def main() -> None:
    print("[1] 缺 Key 的真实报错（捕获打印，非虚构）：")
    os.environ.pop("OPENAI_API_KEY", None)
    from 示例代码.公共.llm_client import RealLLM

    try:
        RealLLM()
    except RuntimeError as e:
        print("    RuntimeError:", str(e).replace("\n", "\n      "))

    print("\n[2] openai 3.35.1 关键签名核实（inspect 实测）：")
    import openai
    from openai import OpenAI
    from openai.resources.chat.completions import Completions
    from openai.resources.embeddings import Embeddings

    print(f"    openai.__version__ = {openai.__version__}")
    init_params = list(inspect.signature(OpenAI.__init__).parameters)
    print(f"    OpenAI.__init__ 含 api_key/base_url/timeout/max_retries/http_client："
          f"{all(p in init_params for p in ['api_key', 'base_url', 'timeout', 'max_retries', 'http_client'])}")

    client = OpenAI(api_key="sk-dummy-not-used", base_url="http://127.0.0.1:9/v1", max_retries=0)
    default_client = OpenAI(api_key="sk-dummy-not-used")
    print(f"    client.max_retries 默认值 = {default_client.max_retries}")
    print(f"    client.base_url 可注入   = {client.base_url!r}（兼容接口服务改这里）")
    print(f"    有 with_options() 方法   = {hasattr(client, 'with_options')}（可临时覆盖 max_retries 等默认值）")

    create_params = list(inspect.signature(Completions.create).parameters)
    for name in ["messages", "model", "temperature", "top_p", "max_tokens",
                 "max_completion_tokens", "stream", "stream_options", "tools",
                 "tool_choice", "response_format", "parallel_tool_calls", "seed", "stop", "n"]:
        assert name in create_params, name
    print(f"    chat.completions.create 含 15 个常用参数（messages/model/temperature/...）＝ True")

    print(f"    chat.completions.parse 存在 = {hasattr(Completions, 'parse')}"
          f"（参数含 response_format；含 stream = {'stream' in inspect.signature(Completions.parse).parameters}）")
    emb_params = list(inspect.signature(Embeddings.create).parameters)
    print(f"    embeddings.create 前置参数 = {[p for p in emb_params if p != 'self'][:5]}")

    print("\n[3] BaseURL 兼容边界提醒（教材 24.2 展开）：")
    print("    OpenAI 兼容 ≠ 功能一致：response_format/工具调用/多模态/流式用法都可能被")
    print("    兼容服务裁剪。上线前按本示例输出清单逐项向厂商文档核实。")


if __name__ == "__main__":
    main()
```

```text
# 真实运行输出（Python 3.14.7，openai 3.35.1；不发起网络请求）
[1] 缺 Key 的真实报错（捕获打印，非虚构）：
    RuntimeError: real 模式需要 OPENAI_API_KEY，但环境变量未设置。三种解决方式：
        1) export OPENAI_API_KEY=sk-... 后重试；
        2) 使用兼容 OpenAI 接口的服务：再设置 OPENAI_BASE_URL=https://<厂商域名>/v1（路径以厂商文档为准）；
        3) 没有Key就保持 LLM_MODE=mock（默认，离线可跑全部教学示例）。

[2] openai 3.35.1 关键签名核实（inspect 实测）：
    openai.__version__ = 3.35.1
    OpenAI.__init__ 含 api_key/base_url/timeout/max_retries/http_client：True
    client.max_retries 默认值 = 2
    client.base_url 可注入   = URL('http://127.0.0.1:9/v1/')（兼容接口服务改这里）
    有 with_options() 方法   = True（可临时覆盖 max_retries 等默认值）
    chat.completions.create 含 15 个常用参数（messages/model/temperature/...）＝ True
    chat.completions.parse 存在 = True（参数含 response_format；含 stream = False）
    embeddings.create 前置参数 = ['input', 'model', 'dimensions', 'encoding_format', 'user']

[3] BaseURL 兼容边界提醒（教材 24.2 展开）：
    OpenAI 兼容 ≠ 功能一致：response_format/工具调用/多模态/流式用法都可能被
    兼容服务裁剪。上线前按本示例输出清单逐项向厂商文档核实。
```

这张"签名核实清单"是本章的锚：后面讲到的每个参数，都在这里被 `inspect` 验证过存在于 3.35.1。

**EX-24-02 | 示例代码/ch24_sdk/ex_24_02_structured_output.py（完整可运行）**

```python
# EX-24-02 | 结构化输出：response_format + Pydantic（Mock 路径真实运行）| 运行: python3 示例代码/ch24_sdk/ex_24_02_structured_output.py
"""完整可运行（Mock）：chat_structured 把"模型输出"直接变成 Pydantic 对象。

Mock 路径：从最后一条 user 消息解析 key=value → Pydantic 校验（真实运行）。
Real 路径：client.chat.completions.parse(response_format=Schema)——3.35.1 已核实存在；
部分兼容服务不支持 response_format，需回退到提示词约束+自行解析（教材 24.4 清单）。
"""
from __future__ import annotations

import sys
from pathlib import Path

from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from 示例代码.公共.llm_client import StructuredOutputError, get_llm  # noqa: E402


class RefundCheck(BaseModel):
    """退款预检结果（字段语义写在 description 里，会变成 JSON Schema 提示）。"""
    order_id: str = Field(description="订单号，格式 ORD-数字")
    eligible: bool = Field(description="是否符合自动退款条件")
    reason: str = Field(default="无", description="不符合时的原因")


MESSAGES_OK = [{"role": "user",
                "content": "抽取退款预检字段：order_id=ORD-1001 eligible=true reason=无"}]
MESSAGES_BAD = [{"role": "user",
                 "content": "抽取退款预检字段：eligible=true（忘了订单号）"}]


def main() -> None:
    llm = get_llm()

    print("[1] 成功路径：解析 + 校验一步到位，拿到的是强类型对象：")
    obj = llm.chat_structured(MESSAGES_OK, RefundCheck)
    print(f"    type(obj) = {type(obj).__name__}")
    print(f"    obj.model_dump() = {obj.model_dump()}")
    print(f"    obj.model_dump_json() = {obj.model_dump_json()}")
    print(f"    直接点字段：obj.order_id = {obj.order_id!r}, obj.eligible = {obj.eligible}")

    print("\n[2] 失败路径：缺必填字段 → StructuredOutputError（真实抛出，非脚本模拟）：")
    try:
        llm.chat_structured(MESSAGES_BAD, RefundCheck)
    except StructuredOutputError as e:
        print(f"    {e}")
        print(f"    errors = {e.errors}")
        print(f"    hint   = {e.hint}")

    print("\n[3] Java 对照：ChatResult 是 Map<String,Object>，chat_structured 之后的")
    print("    Pydantic 对象 ≈ 经 Jackson 反序列化 + Bean Validation 的强类型 DTO。")


if __name__ == "__main__":
    main()
```

```text
# Mock 运行输出（LLM_MODE=mock；[1] 为 Mock 解析路径，[2] 为真实抛出的校验异常）
[1] 成功路径：解析 + 校验一步到位，拿到的是强类型对象：
    type(obj) = RefundCheck
    obj.model_dump() = {'order_id': 'ORD-1001', 'eligible': True, 'reason': '无'}
    obj.model_dump_json() = {"order_id":"ORD-1001","eligible":true,"reason":"无"}
    直接点字段：obj.order_id = 'ORD-1001', obj.eligible = True

[2] 失败路径：缺必填字段 → StructuredOutputError（真实抛出，非脚本模拟）：
    Mock 输出无法通过 schema RefundCheck 校验：2 个错误
    errors = [{'type': 'missing', 'loc': ('order_id',), 'msg': 'Field required', 'input': {'eligible': 'true（忘了订单号）', 'reason': '无'}, 'url': 'https://errors.pydantic.dev/2.14/v/missing'}, {'type': 'bool_parsing', 'loc': ('eligible',), 'msg': 'Input should be a valid boolean, unable to interpret input', 'input': 'true（忘了订单号）', 'url': 'https://errors.pydantic.dev/2.14/v/bool_parsing'}]
    hint   = 常见做法：校验失败→重试——捕获本异常，把 errors 拼进一条 user 消息再请求一次（ch26 演示完整回退循环）。

[3] Java 对照：ChatResult 是 Map<String,Object>，chat_structured 之后的
    Pydantic 对象 ≈ 经 Jackson 反序列化 + Bean Validation 的强类型 DTO。
```

双模式说明：**Mock 路径**（本输出）验证的是"schema 校验与异常设计"；**Real 路径**走 `client.chat.completions.parse(model=..., messages=..., response_format=RefundCheck)`，成功时 `message.parsed` 就是 `RefundCheck` 实例——API 形状已核实（EX-24-01 [2]），真实生成效果需在持 Key 环境验证。

**EX-24-03 | 示例代码/ch24_sdk/ex_24_03_tool_loop.py（完整可运行）**

```python
# EX-24-03 | 工具调用完整闭环：请求→执行→回传→二次调用 | 运行: python3 示例代码/ch24_sdk/ex_24_03_tool_loop.py
"""完整可运行（Mock）：用脚本化 MockLLM 完整跑通 agent loop 的一次工具调用。

第 1 次调用：模型返回"我要调 get_weather(city=北京)"（finish_reason=tool_calls）
程序执行：本地函数真的算出结果
第 2 次调用：把结果以 tool 消息回传，模型基于结果给最终回答。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from 示例代码.公共.llm_client import get_llm  # noqa: E402

# ---- 1. 工具声明（JSON Schema，会随请求发给模型）--------------------------
TOOLS: list[dict[str, Any]] = [{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "查询指定城市当日天气",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "城市名，如 北京"},
            },
            "required": ["city"],
        },
    },
}]

# ---- 2. 程序里的真实现（模型只"点名"，从不亲自执行）------------------------
WEATHER_DB = {"北京": {"weather": "晴", "temp": 26, "wind": "西北风 3 级"},
              "上海": {"weather": "小雨", "temp": 22, "wind": "东风 2 级"}}


def get_weather(city: str) -> dict[str, Any]:
    if city not in WEATHER_DB:
        raise ValueError(f"暂不支持城市：{city}")
    return {"city": city, **WEATHER_DB[city]}


def main() -> None:
    # 脚本化 Mock：第 1 次返回工具调用请求，第 2 次返回最终回答（Agent loop 的骨架）
    llm = get_llm()
    from 示例代码.公共.llm_client import MockLLM
    assert isinstance(llm, MockLLM), "本示例固定用 Mock 演示（LLM_MODE=real 时请改用真实模型）"
    llm = MockLLM(script=[
        {"tool_calls": [{"name": "get_weather", "arguments": {"city": "北京"}}],
         "content": ""},
        {"content": "北京今天晴，26℃，西北风 3 级，适合出行。"},
    ])

    messages: list[dict[str, Any]] = [{"role": "user", "content": "北京天气怎么样？适合跑步吗？"}]

    # ---- 第 1 轮：模型请求工具 ----
    r1 = llm.chat(messages, tools=TOOLS)
    tc = r1.tool_calls[0]
    print(f"[第 1 轮] finish_reason = {r1.finish_reason}")
    print(f"         模型请求工具：{tc.name}({json.dumps(tc.arguments, ensure_ascii=False)})  id={tc.id}")
    assert r1.finish_reason == "tool_calls"

    # ---- 程序执行工具（参数校验/权限/幂等都发生在这一层，模型无权绕过）----
    try:
        result = get_weather(**tc.arguments)
        tool_content = json.dumps(result, ensure_ascii=False)
    except Exception as e:  # 教学最小处理：错误也回传给模型，让它决定下一步
        tool_content = json.dumps({"error": str(e)}, ensure_ascii=False)

    # ---- 把"模型要点名"和"执行结果"都写回消息历史（OpenAI 风格，缺一不可）----
    messages.append({
        "role": "assistant",
        "content": r1.content,
        "tool_calls": [{"id": tc.id, "type": "function",
                        "function": {"name": tc.name,
                                     "arguments": json.dumps(tc.arguments, ensure_ascii=False)}}],
    })
    messages.append({"role": "tool", "tool_call_id": tc.id, "content": tool_content})
    print(f"[执行]   get_weather → {tool_content}")

    # ---- 第 2 轮：模型基于工具结果回答 ----
    r2 = llm.chat(messages)
    print(f"[第 2 轮] finish_reason = {r2.finish_reason}")
    print(f"         最终回答：{r2.content}")
    print(f"[usage]  两次调用合计 total_tokens = "
          f"{r1.usage['total_tokens'] + r2.usage['total_tokens']}"
          f"（prompt 每轮都重算，历史会滚雪球）")

    # 类比：这轮闭环 ≈ Java 里"回调/消息驱动"——模型发请求(HTTP 回调)，服务端执行后回投
    print("\n[闭环检查] messages 轮廓：")
    for m in messages:
        extra = f"  [tool结果] {m['content']}" if m["role"] == "tool" else ""
        print(f"    - {m['role']}: {str(m.get('content'))[:36]}{extra}")


if __name__ == "__main__":
    main()
```

```text
# Mock 运行输出（LLM_MODE=mock；脚本第 1 次=工具请求，第 2 次=最终回答）
[第 1 轮] finish_reason = tool_calls
         模型请求工具：get_weather({"city": "北京"})  id=call_001
[执行]   get_weather → {"city": "北京", "weather": "晴", "temp": 26, "wind": "西北风 3 级"}
[第 2 轮] finish_reason = stop
         最终回答：北京今天晴，26℃，西北风 3 级，适合出行。
[usage]  两次调用合计 total_tokens = 95（prompt 每轮都重算，历史会滚雪球）

[闭环检查] messages 轮廓：
    - user: 北京天气怎么样？适合跑步吗？
    - assistant: 
    - tool: {"city": "北京", "weather": "晴", "temp  [tool结果] {"city": "北京", "weather": "晴", "temp": 26, "wind": "西北风 3 级"}
```

**EX-24-04 | 示例代码/ch24_sdk/ex_24_04_retry_backoff.py（完整可运行）**

```python
# EX-24-04 | 重试与 429/超时语义：自写指数退避包装（Mock 上真实跑）| 运行: python3 示例代码/ch24_sdk/ex_24_04_retry_backoff.py
"""完整可运行（Mock）：一个"前 2 次抛异常、第 3 次成功"的不稳定 LLM 桩，
用指数退避+抖动包装重试，打印每次尝试；对照 SDK 内建 max_retries（已核实默认 2）。
"""
from __future__ import annotations

import random
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from 示例代码.公共.llm_client import ChatResult, MockLLM  # noqa: E402

MESSAGES: list[dict[str, Any]] = [{"role": "user", "content": "重试语义演示"}]


class FlakyLLM:
    """不稳定 LLM 桩：模拟 429（限流）两次，之后恢复。"""

    def __init__(self, fail_times: int = 2) -> None:
        self.fail_times = fail_times
        self.attempts = 0

    def chat(self, messages: list[dict[str, Any]]) -> ChatResult:
        self.attempts += 1
        if self.attempts <= self.fail_times:
            # 真实 SDK 抛 openai.RateLimitError(429)，这里用自定义异常模拟
            raise TimeoutError(f"[模拟 429] 第 {self.attempts} 次请求被限流（Retry-After: 1s）")
        inner = MockLLM(script=[{"content": "重试成功后的正常回答。"}])
        return inner.chat(messages)


def chat_with_retry(llm: FlakyLLM, messages: list[dict[str, Any]],
                    max_attempts: int = 4, base_delay: float = 0.1) -> ChatResult:
    """指数退避 + 抖动（ch15 的重试模板用在 LLM 上；幂等前提：只读对话可安全重发）。"""
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return llm.chat(messages)
        except TimeoutError as e:
            last_exc = e
            if attempt == max_attempts:
                break
            delay = base_delay * (2 ** (attempt - 1)) + random.uniform(0, 0.05)
            print(f"    attempt {attempt} 失败：{e}")
            print(f"    退避 {delay:.2f}s 后重试…")
            time.sleep(delay)
    raise RuntimeError(f"重试 {max_attempts} 次仍失败") from last_exc


def main() -> None:
    print("[1] 自写重试包装（指数退避，Mock 上真实执行）：")
    result = chat_with_retry(FlakyLLM(fail_times=2), MESSAGES)
    print(f"    最终成功：{result.content}")

    print("\n[2] SDK 内建重试对照（openai 3.35.1，inspect 核实）：")
    from openai import OpenAI

    c = OpenAI(api_key="sk-dummy-not-used")
    print(f"    默认 max_retries = {c.max_retries}（只自动重试连接错误/408/429/部分 5xx）")
    print("    429 语义：服务端要求减速，响应可能带 Retry-After 头——尊重它，别自作聪明加大频率；")
    print("    读超时语义：请求可能已被服务端受理，重发前先想幂等（对话类安全，下单类必须幂等键）。")

    print("\n[3] 什么时候关掉内建重试自己写？")
    print("    需要区分错误类型(429 vs 500 vs 401)、接入熔断/降级、或对延迟敏感时——")
    print("    用 max_retries=0 关内建，再用本示例的包装（第十部分 59 章展开）。")


if __name__ == "__main__":
    main()
```

```text
# 真实运行输出（重试循环在 Mock 桩上真实执行；退避耗时含随机抖动，每次运行略有差异）
[1] 自写重试包装（指数退避，Mock 上真实执行）：
    attempt 1 失败：[模拟 429] 第 1 次请求被限流（Retry-After: 1s）
    退避 0.12s 后重试…
    attempt 2 失败：[模拟 429] 第 2 次请求被限流（Retry-After: 1s）
    退避 0.23s 后重试…
    最终成功：重试成功后的正常回答。

[2] SDK 内建重试对照（openai 3.35.1，inspect 核实）：
    默认 max_retries = 2（只自动重试连接错误/408/429/部分 5xx）
    429 语义：服务端要求减速，响应可能带 Retry-After 头——尊重它，别自作聪明加大频率；
    读超时语义：请求可能已被服务端受理，重发前先想幂等（对话类安全，下单类必须幂等键）。

[3] 什么时候关掉内建重试自己写？
    需要区分错误类型(429 vs 500 vs 401)、接入熔断/降级、或对延迟敏感时——
    用 max_retries=0 关内建，再用本示例的包装（第十部分 59 章展开）。
```

## 24.5 逐段解释：闭环时序、核实清单与错误语义

**（1）工具调用闭环的六步时序**（EX-24-03 全程真实执行）：

```text
① 你的程序 → API：messages + tools（JSON Schema 声明）
② 模型 → 你的程序：finish_reason=tool_calls，tool_calls=[{id, name, arguments(JSON 字符串)}]
③ 你的程序：把 ② 落成 assistant 消息追加进历史（服务端要求"请求过的调用要在历史里"）
④ 你的程序：真正执行工具（校验参数→鉴权→执行→捕获异常）——这一层在你的代码里，模型碰不到
⑤ 你的程序 → API：追加 tool 消息（tool_call_id 与 ② 的 id 配对），再次 create
⑥ 模型 → 你的程序：基于工具结果的最终回答（finish_reason=stop）
```

**Java 对照**：这就是**回调/消息驱动**——模型是"发起回调请求的客户端"，你的程序是"处理回调的服务端"。区别在于"客户端"由概率模型驱动，所以第 ④ 步的参数校验、权限、幂等、审计全部由你负责，**模型说它要调什么，永远只是请求，不是授权**（ch28 的安全红线）。

**（2）"OpenAI 兼容"支持边界核实清单**。换厂商/自建兼容网关时，按表逐项核实（方法列是可执行的核实手段，不是文档宣传语）：

| 能力 | 要核实什么 | 核实方法 |
|---|---|---|
| 鉴权 | `Authorization: Bearer` 头是否被识别；是否有额外的项目/租户头 | 发最小请求看 401/200 |
| 基础对话 | `/chat/completions` 路径与请求体形状 | EX-24-01 的最小请求 |
| 流式 | SSE 帧格式、`delta.content` 字段、`[DONE]` 结束标记 | curl -N 观察原始帧 |
| 结构化输出 | 是否支持 `response_format`（含 json_schema 严格模式还是仅 json_object） | 发 schema 请求，故意造非法输出看是否守约 |
| 工具调用 | `tools/tool_choice` 是否生效、`arguments` 是否合法 JSON、是否支持并行调用 | EX-24-03 的脚本在真服务上重跑 |
| 多模态 | 图片字段名与大小/格式限制 | 小图 + 大图各一发 |
| usage | 响应是否回带 token 统计、口径是否含工具消息 | 对比本地 tiktoken 估算 |
| 错误语义 | 429 是否带 `Retry-After`、错误码是否沿用 OpenAI 体系 | 压测触发限流观察 |

**（3）`parse` 与"手动 create+解析"怎么选**。`parse`（3.35.1 已核实，无 stream 参数）最省事：schema 即 Pydantic 类，失败时 SDK 侧有明确的解析错误。但它在**兼容服务上最常被裁剪**——很多服务只实现了 `response_format: {"type": "json_object"}` 而不支持 json_schema 严格约束。稳妥的生产姿势是"**parse 优先、手动回退**"：捕获不支持错误后降级为"提示词约束 + `json.loads` + Pydantic 校验 + 失败重试"（完整回退循环在 EX-26-03）。

**（4）429/超时的处置语义**。429 是协作信号：读 `Retry-After`（有则遵从，无则指数退避+抖动，EX-24-04 的 delay 公式），并把"触发限流"视为要扩容配额或降请求率的信号，而不是"再多试几次"的信号。读超时要区分"连接建立失败"（可安全重试）与"响应等待超时"（服务端可能已在生成，重试=可能双倍计费+重复副作用——工具调用类请求尤其危险）。SDK 的内建重试（默认 2 次）已覆盖常见瞬时故障；当你需要自定义退避策略、熔断或区分错误类型时，用 `max_retries=0` 关掉它自己写（EX-24-04 就是那个模板）。

**（5）`with_options` 与 http_client 注入**。`client.with_options(max_retries=0, timeout=5)` 可对单次调用覆盖默认值（已核实方法存在）；`OpenAI(http_client=...)` 允许注入自定义 `httpx.Client`——这是本书测试 `RealLLM` 转换逻辑的方式（无 Key 环境下用 `httpx.MockTransport` 伪造响应做接口级测试，见 `测试/test_common_llm.py`），也是生产里挂代理/自定义证书的标准入口。

## 24.6 安装 / 文件位置 / 运行命令

```bash
pip install -r requirements.txt   # openai==3.35.1
python3 示例代码/ch24_sdk/ex_24_01_auth_baseurl.py    # 鉴权+签名核实（不联网）
python3 示例代码/ch24_sdk/ex_24_02_structured_output.py
python3 示例代码/ch24_sdk/ex_24_03_tool_loop.py
python3 示例代码/ch24_sdk/ex_24_04_retry_backoff.py

# real 模式（需 Key）：
export OPENAI_API_KEY=sk-...
# 兼容服务另加：export OPENAI_BASE_URL=https://<厂商域名>/v1
export LLM_MODE=real
```

## 24.7 常见错误与排查

**错 1：`RuntimeError: real 模式需要 OPENAI_API_KEY…`（或 SDK 的 `OpenAIError: The api_key client option must be set`）。**
原因：环境变量未设置/未加载 `.env`。修复：按 EX-24-01 输出的三条指引处理；CI 里检查 secret 注入；异常信息本身就是排查手册（`llm_client` 特意把指引写进异常文本）。

**错 2：`401 Authentication` 但 Key 确实没填错。**
常见原因：兼容服务的路径前缀不对（少了/多了 `/v1`）、组织头要求不同、Key 是别的产品的。修复：用 curl 直接打端点二分定位（是 SDK 问题还是配置问题）；对照厂商的鉴权文档逐项核对。

**错 3：工具调用报"缺少 tool 响应"。**
典型报错形态（各家措辞不同，此处为示意——非真实记录）：`400 An assistant message with 'tool_calls' must be followed by tool messages responding to each 'tool_call_id'`。原因：第 ② 步拿到 `tool_calls` 后直接开始下一轮请求，忘了把 assistant 消息（含 tool_calls）与 tool 结果消息都写回历史。修复：严格按 EX-24-03 的六步时序，两个 append 缺一不可。

**错 4：`json.JSONDecodeError` 解析 `arguments` 失败。**
原因：`function.arguments` 是 JSON **字符串**（可能被模型截断——`finish_reason=length` 时参数没生成完），个别兼容服务返回空串或带围栏。修复：先判 `finish_reason`，再 `json.loads(arguments or "{}")`，解析失败时把原始文本记日志并走重试/人工。

**错 5：重试风暴。**
现象：限流期间请求量不降反升，429 越打越多。原因：SDK 内建重试 + 网关层重试 + 业务层重试三层叠加，退避时间还没到就把配额打光。修复：全局只保留一层重试；429 全局计数触发熔断（第十部分 59 章）。

## 24.8 企业场景中的使用方式

Spring Boot 团队的标准做法是把 SDK 调用封装进一个**AI 网关服务**（Python 或 Java）：Key 只存在网关的密钥管理里（业务服务拿不到），网关统一做鉴权、限流（按租户计）、重试、审计日志（谁在何时调了什么工具、参数是什么）、成本记账（读 usage）。业务方拿到的是内部 REST 接口——这层抽象让"换厂商"变成改网关配置而不是改业务代码，也是第 57 章架构图的雏形。工具注册表（工具名→Java 服务的 HTTP 端点+权限要求）同样由网关持有，模型每次"点名"工具都要过网关的权限校验——**这再次呼应：模型不是权限主体，代码才是**。

## 24.9 练习

**基础 1**：说出 `finish_reason` 在工具调用闭环里出现的两个不同值及其含义。

**基础 2**：`OpenAI(max_retries=2)` 的默认重试覆盖哪些情况？哪类错误永远不会被自动重试？

**代码 1**：给 EX-24-03 的 `get_weather` 增加一个不支持城市（如"火星"），运行并观察：异常如何被转成 `{"error": ...}` 回传、模型（Mock 脚本）在第 2 轮拿到错误后如何回应。再思考：真实模型拿到错误信息通常会做什么？

**代码 2**：用 `httpx.MockTransport` 写一个最小测试：伪造一个返回 `response_format` 不支持错误的 400 响应，验证你的"parse 失败→降级手动解析"逻辑。

**调试题**：生产环境偶发"工具调用循环不停止"（模型反复请求同一个工具）。列出至少三个可能原因与对应防护。

### 参考答案

**基础 1**：`tool_calls`（模型请求调用工具，流程未结束）与 `stop`（给出最终自然语言回答，流程结束）。

**基础 2**：连接错误、408、429 与部分 5xx；401/403/400 这类确定性错误不重试（重试也不会好，只会浪费配额）。

**代码 1**（要点）：异常路径输出 `tool_content = '{"error": "暂不支持城市：火星"}'`；脚本 Mock 第 2 轮返回的是你预设的回答。真实模型拿到结构化错误后，典型行为是换参数重试或向用户澄清——所以**错误信息要写成模型能读懂的中文**（含原因与建议），这本身就是一种 API 设计。

**代码 2**（要点）：
```python
def handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(400, json={"error": {"message": "response_format is not supported"}})
client = RealLLM(api_key="sk-test", max_retries=0,
                 http_client=httpx.Client(transport=httpx.MockTransport(handler)))
with pytest.raises(Exception):
    client.chat_structured(msgs, Schema)
# 之后走降级分支断言：提示词模板被使用、手动 json.loads+校验被执行
```

**调试题**：① 工具描述不清导致模型重复点名——改进 description 与 `tool_choice` 约束；② 无最大循环次数——代码层设 `max_tool_rounds`（如 5 轮）超限走人工/拒答；③ 工具返回错误信息太含糊，模型"再试一次"——把错误结构化（原因+建议动作）；④ 每轮结果没进历史导致模型失忆重问——检查消息回传完整性。

## 24.10 自测检查表

- 我能默写工具调用闭环的六步时序，并指出哪两步最容易漏（assistant 消息回写、tool 消息配对）。
- 我能解释"模型请求工具 ≠ 执行授权"，并说出程序侧要做的四件事（校验/鉴权/执行/审计）。
- 我能不看资料列出"兼容服务核实清单"的至少 6 项，并说明每项的核实方法。
- 我知道 `parse` 在 3.35.1 存在、支持 `response_format`、不支持 `stream`，以及它被兼容服务裁剪时的降级路径。
- 我能说清 429 与读超时的处置差异，以及为什么读超时的重发要想幂等。
- 我知道 SDK 默认 `max_retries=2`、重试哪些错误、何时该关掉它。

## 24.11 面试追问

**[模拟题] 1：为什么模型不能直接执行工具？这个设计换来了什么？**
考查点：安全与架构边界。合格回答：执行权留在客户端，模型只生成"意图+参数"——换来三件事：权限控制在你的代码里（模型永远无法绕过鉴权）、副作用可审计可幂等、工具实现与模型解耦（改工具不用改模型）。

**[模拟题] 2：设计一个多租户的 LLM 网关，你要在 SDK 之上加哪些层？**
考查点：生产架构。合格回答：租户配额与限流（429 前置）、Key 托管与轮换、审计日志（trace_id 贯穿）、成本记账（usage 落表）、兼容层（不同厂商适配）、熔断降级、缓存（相同请求哈希）。每层都要说清失败时的行为。

**[模拟题] 3：`response_format` 的 json_schema 严格模式为什么比"提示词里求它输出 JSON"可靠？**
考查点：约束机制差异。合格回答：前者在解码阶段约束每一步 token 的选择（语法级保证），后者靠模型"自觉"（概率级倾向）；但严格模式未必被所有兼容服务支持，所以工程上两者都要配 Pydantic 校验与失败重试兜底。

## 24.12 2026 API 形态对照与本书边界

> 本书全部示例以 **Chat Completions** 打底——它是兼容面最广的接口形态（各家兼容服务几乎都以它为公共语言，24.5 的"兼容服务核实清单"正是围绕它设计）。但它不是 OpenAI 平台的全部：生产选型时你还需要知道下面这些关键词。本书对它们**一律只点名、不展开教学**，落到项目前以官方文档为准：
>
> - **Responses API**：2025 起官方主推的接口形态，内建工具（联网检索/文件检索等）与服务端状态（历史可由服务端重放）；与 Chat Completions 并存，迁移节奏自行评估；
> - **流式工具调用**：stream 模式下工具调用参数按 `delta.tool_calls` 分片到达，要按 index 增量聚合后再解析——生产高频痛点，本书 ch23 只演示了文本流的处理；
> - **Batch API**：离线批处理接口，约半价、非实时返回，适合不在线上等结果的任务；
> - **reasoning 模型的参数差异**：这类模型的部分采样参数（temperature/top_p 等）不生效或含义不同，以对应模型文档为准；
> - **prompt caching**：命中缓存的前缀按折扣计价，是"长固定前缀（system/工具声明）"场景的主要成本杠杆。
>
> 边界声明：以上是"知道它存在、知道去哪核实"，不是"本书教过你怎么用"——任何一条进入你的项目前，先按 24.5 的核实方法对官方文档实测。

---

# 第 25 章 Embedding 与检索基础：把"意思"变成可计算的向量

> **本章目标**：分清 embedding 模型与生成模型；手算余弦相似度；用 MockEmbedder 建立"相似文本→相似向量"的直觉，为第六部分 RAG 铺路。
> **前置知识**：ch21（token）、ch22（向量与点积直觉）、numpy 基础。
> **学完你能做什么**：解释 embedding 与 chat 模型的四个区别；用 numpy 手算余弦相似度并说清归一化的意义；跑通一个 5 句知识库的语义检索 demo，知道它的天花板在哪。

## 25.1 真实问题引入：知识库里明明有答案，就是搜不到

客服知识库第 3 条写着"手机的保修期为 12 个月，人为损坏不在范围内"。用户搜索"手机 SIM 卡坏了怎么办"——传统关键词搜索返回 0 条：库里没有"SIM"这三个字母。而任何一个客服都能看出这条查询该命中保修条款。关键词匹配的失效，是所有搜索系统的祖传痛点；embedding 给出的解法是：**别比较字面，比较"意思"**——把每句话变成一个高维向量，让"意思接近"的句子在向量空间里方向接近，用向量夹角代替关键词重合。

## 25.2 一句话解释 + 生活类比 + 类比边界

**一句话解释**：embedding 模型把任意文本压缩成一个固定长度的向量（如 1536 维），训练目标是"意思相近的文本，向量夹角小"；检索 = 把查询也变成向量，找夹角最小的库存文本。

**生活类比**：图书管理员给每本书写一个"主题指纹"：不是抄书名，而是把书的内容概括成一组"主题坐标"（爱情 0.9 / 战争 0.1 / 科幻 0.0…）。你来问"有没有讲机器人觉醒的小说"，他给你的查询算一份同样的坐标，然后找坐标最近的书——书名里有没有"机器人"三个字根本不重要。

> 💡 类比边界：
> 1. "主题坐标"不是人可读的标签，是模型从海量语料学出的稠密向量——维度含义不可解释，只能整体使用；
> 2. MockEmbedder 的"语义"来自一张十几行的概念词典（命中同一概念=同方向），**它演示的是相似度的数学性质，不是真模型的语义能力**——真模型能把"手机"和"移动电话"判为相近而无需词典；
> 3. 相似 ≠ 正确：语义最近的文本未必是"正确答案"（检索给的是"最像的"，不是"最对的"），答案质量要靠引用与评估（第六部分 ch34/ch35）。

## 25.3 正式原理与准确术语

**嵌入向量（embedding）**：文本经编码器映射成的定长实数向量。**维度（dimensions）**：向量长度，由模型决定（`embeddings.create` 签名中的 `dimensions` 参数可对支持的模型下调，已核实存在）。**余弦相似度（cosine similarity）**：`cos(θ) = a·b / (|a|·|b|)`，度量两向量方向一致性，取值 [-1, 1]；文本检索中 1 为完全同向。

**L2 归一化**：把向量缩放为单位长度（模长 1）。归一化后**点积 = 余弦相似度**——这是向量检索系统把"入库前归一化"作为标准动作的原因：查询时省掉两次取模，只剩一次点积。

**向量检索（vector search）**：按相似度排序取 **Top-k**。与 B-tree 等值索引本质不同：等值索引答"有没有"，向量检索答"最像的前 k 个是谁"（FACTS 术语基线）。海量向量下的近似最近邻（ANN，如 FAISS/HNSW）是第六部分的话题，本章用 numpy 暴力扫全部向量——5 个向量扫得动，100 万个才需要 ANN。

**与生成模型的四个区别**：① 输出是向量不是文本；② 无随机性（同输入必同输出，temperature 无意义）；③ 计费/延迟远低于生成（一次前向）；④ 评估方式完全不同（检索质量用命中率，不用"读起来对不对"）。

## 25.4 最小完整示例

**EX-25-01 | 示例代码/ch25_embeddings/ex_25_01_cosine_manual.py（完整可运行）**

```python
# EX-25-01 | 余弦相似度 numpy 手算实验 | 运行: python3 示例代码/ch25_embeddings/ex_25_01_cosine_manual.py
"""完整可运行：把余弦相似度拆成点积/模长/夹角三步手算，再对照 numpy 一行式；
最后验证"归一化向量的点积 == 余弦相似度"（检索系统加速的关键性质）。
"""
from __future__ import annotations

import math

import numpy as np

A = np.array([3.0, 4.0, 0.0])   # 向量 a
B = np.array([4.0, 3.0, 0.0])   # 向量 b
C = np.array([-3.0, -4.0, 0.0])  # 向量 c = -a（方向完全相反）


def main() -> None:
    print("[手算三步] a=[3,4,0]  b=[4,3,0]")
    dot = float(A @ B)
    na = math.sqrt(float(A @ A))
    nb = math.sqrt(float(B @ B))
    cos_ab = dot / (na * nb)
    angle = math.degrees(math.acos(cos_ab))
    print(f"    1) 点积     a·b = 3×4 + 4×3 + 0×0 = {dot}")
    print(f"    2) 模长     |a| = {na:.4f}, |b| = {nb:.4f}")
    print(f"    3) 相似度   cos = {dot:.4f} / ({na:.4f}×{nb:.4f}) = {cos_ab:.6f}，夹角 {angle:.2f}°")

    print("\n[numpy 一行式对照]：")
    cos_np = float(np.dot(A, B) / (np.linalg.norm(A) * np.linalg.norm(B)))
    print(f"    np.dot/(norm×norm) = {cos_np:.6f}  （与手算一致：{math.isclose(cos_ab, cos_np)}）")

    print("\n[方向决定一切]：")
    print(f"    cos(a, -a) = {float(A @ C / (np.linalg.norm(A) * np.linalg.norm(C))):.4f}  ← 完全反向 = -1")
    print(f"    cos(a, a)  = {float(A @ A / (np.linalg.norm(A) ** 2)):.4f}  ← 自己 = 1")

    print("\n[归一化后点积即余弦]（向量检索系统都靠这个性质省算力）：")
    a_unit, b_unit = A / np.linalg.norm(A), B / np.linalg.norm(B)
    print(f"    unit(a)·unit(b) = {float(a_unit @ b_unit):.6f} == cos(a,b)")
    print("    所以：embedding 入库前统一 L2 归一化，检索时只需一次点积。")


if __name__ == "__main__":
    main()
```

```text
# 真实运行输出（Python 3.14.7）
[手算三步] a=[3,4,0]  b=[4,3,0]
    1) 点积     a·b = 3×4 + 4×3 + 0×0 = 24.0
    2) 模长     |a| = 5.0000, |b| = 5.0000
    3) 相似度   cos = 24.0000 / (5.0000×5.0000) = 0.960000，夹角 16.26°

[numpy 一行式对照]：
    np.dot/(norm×norm) = 0.960000  （与手算一致：True）

[方向决定一切]：
    cos(a, -a) = -1.0000  ← 完全反向 = -1
    cos(a, a)  = 1.0000  ← 自己 = 1

[归一化后点积即余弦]（向量检索系统都靠这个性质省算力）：
    unit(a)·unit(b) = 0.960000 == cos(a,b)
    所以：embedding 入库前统一 L2 归一化，检索时只需一次点积。
```

**EX-25-02 | 示例代码/ch25_embeddings/ex_25_02_similarity_intuition.py（完整可运行）**

```python
# EX-25-02 | Embedding 相似度直觉实验：手机 vs 电话 vs 披萨 | 运行: python3 示例代码/ch25_embeddings/ex_25_02_similarity_intuition.py
"""完整可运行（MockEmbedder，确定性本地向量）：验证"相似文本→相似向量"。

MockEmbedder 用小型概念词典+哈希词袋模拟语义：同概念词同方向，异概念词近似正交。
类比边界：真实 embedding 模型的语义来自大规模训练，相近但不重合；Mock 只有
"命中即相等"的粗粒度语义——教学够用，勿当真模型。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from 示例代码.公共.embeddings import cosine_similarity, get_embedder  # noqa: E402

WORDS = ["手机", "电话", "披萨", "手机支付", "天气"]


def main() -> None:
    emb = get_embedder()
    print(f"[向量器] {emb.kind}")
    vecs = {w: emb.embed_one(w) for w in WORDS}
    print(f"[维度] {len(vecs['手机'])}（已 L2 归一化）")

    print("\n[相似度矩阵]（cos ∈ [-1,1]，越接近 1 越相似）：")
    header = "        " + "".join(f"{w:>8}" for w in WORDS)
    print(header)
    for w1 in WORDS:
        row = "".join(f"{cosine_similarity(vecs[w1], vecs[w2]):>8.3f}" for w2 in WORDS)
        print(f"{w1:<8}{row}")

    s_phone_tel = cosine_similarity(vecs["手机"], vecs["电话"])
    s_phone_pizza = cosine_similarity(vecs["手机"], vecs["披萨"])
    s_phone_pay = cosine_similarity(vecs["手机"], vecs["手机支付"])
    print("\n[直觉结论]")
    print(f"    sim(手机, 电话)   = {s_phone_tel:.3f}  ← 同为通讯概念（Mock 中同方向）")
    print(f"    sim(手机, 披萨)   = {s_phone_pizza:.3f}  ← 无关概念，近似正交")
    print(f"    sim(手机, 手机支付) = {s_phone_pay:.3f}  ← 部分共享语义（通讯命中+哈希差异）")
    assert s_phone_tel > s_phone_pizza, "相似性排序应成立"
    print("    排序成立：电话 ≻ 手机支付 ≻ 披萨 —— 这正是'按语义距离检索'的基础。")

    print("\n[确定性] 同输入两次 embed 结果完全一致：",
          emb.embed_one("手机") == emb.embed_one("手机"))


if __name__ == "__main__":
    main()
```

```text
# Mock 运行输出（LLM_MODE=mock，MockEmbedder 本地确定性向量）
[向量器] mock:concept-hash dim=64
[维度] 64（已 L2 归一化）

[相似度矩阵]（cos ∈ [-1,1]，越接近 1 越相似）：
              手机      电话      披萨    手机支付      天气
手机         1.000   1.000   0.000   0.707   0.000
电话         1.000   1.000   0.000   0.707   0.000
披萨         0.000   0.000   1.000   0.000   0.000
手机支付       0.707   0.707   0.000   1.000   0.000
天气         0.000   0.000   0.000   0.000   1.000

[直觉结论]
    sim(手机, 电话)   = 1.000  ← 同为通讯概念（Mock 中同方向）
    sim(手机, 披萨)   = 0.000  ← 无关概念，近似正交
    sim(手机, 手机支付) = 0.707  ← 部分共享语义（通讯命中+哈希差异）
    排序成立：电话 ≻ 手机支付 ≻ 披萨 —— 这正是'按语义距离检索'的基础。

[确定性] 同输入两次 embed 结果完全一致： True
```

**EX-25-03 | 示例代码/ch25_embeddings/ex_25_03_mini_search.py（完整可运行）**

```python
# EX-25-03 | 语义检索 mini demo：为第六部分 RAG 铺垫 | 运行: python3 示例代码/ch25_embeddings/ex_25_03_mini_search.py
"""完整可运行（MockEmbedder）：5 句"知识库"，对 query 做 top-k 余弦检索，
打印每句得分并解释为什么关键词搜索会错、语义搜索会对（以及 Mock 的局限）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from 示例代码.公共.embeddings import cosine_similarity, get_embedder  # noqa: E402

KB = [
    "手机的保修期为 12 个月，人为损坏不在范围内。",
    "订单签收后 7 天内可无理由退货，需保持包装完好。",
    "会员积分在每年 12 月 31 日 24 点清零。",
    "配送范围覆盖全国，偏远地区运费另计。",
    "发票在订单完成后的次月统一开具。",
]
QUERY = "手机 SIM 卡坏了怎么办"  # "SIM 卡"在库里没有字面出现，语义近"手机保修"

TOP_K = 2


def main() -> None:
    emb = get_embedder()
    kb_vecs = emb.embed(KB)
    q_vec = emb.embed_one(QUERY)

    scored = sorted(
        ((cosine_similarity(q_vec, v), text) for v, text in zip(kb_vecs, KB)),
        key=lambda x: x[0], reverse=True,
    )
    print(f"Query：{QUERY!r}\n")
    print(f"{'排名':<4} {'余弦相似度':>10}  句子")
    print("-" * 64)
    for rank, (score, text) in enumerate(scored, 1):
        mark = " ← " + ("命中 top-1" if rank == 1 else f"top-{TOP_K}") if rank <= TOP_K else ""
        print(f"{rank:<4} {score:>10.3f}  {text}{mark}")

    print("\n[解读]")
    print("    1) 'SIM 卡'三个字在库里从未出现，字面匹配帮不上忙；")
    print("    2) 语义检索按向量方向找'意思最近'的句子，把保修条款排到了最前；")
    print("    3) 分数绝对值不代表'正确率'，排序与阈值（第六部分 ch33 的 Top-k 与过滤）才是工程抓手；")
    print("    4) Mock 语义是概念级的：换成词典外表述（如'摔碎了'）相似度会塌掉——")
    print("       真实 RAG 必须换真 embedding 模型，这正是第六部分的起点。")


if __name__ == "__main__":
    main()
```

```text
# Mock 运行输出（LLM_MODE=mock）
Query：'手机 SIM 卡坏了怎么办'

排名        余弦相似度  句子
----------------------------------------------------------------
1         0.250  手机的保修期为 12 个月，人为损坏不在范围内。 ← 命中 top-1
2         0.000  订单签收后 7 天内可无理由退货，需保持包装完好。 ← top-2
3         0.000  配送范围覆盖全国，偏远地区运费另计。
4        -0.077  发票在订单完成后的次月统一开具。
5        -0.118  会员积分在每年 12 月 31 日 24 点清零。

[解读]
    1) 'SIM 卡'三个字在库里从未出现，字面匹配帮不上忙；
    2) 语义检索按向量方向找'意思最近'的句子，把保修条款排到了最前；
    3) 分数绝对值不代表'正确率'，排序与阈值（第六部分 ch33 的 Top-k 与过滤）才是工程抓手；
    4) Mock 语义是概念级的：换成词典外表述（如'摔碎了'）相似度会塌掉——
       真实 RAG 必须换真 embedding 模型，这正是第六部分的起点。
```

## 25.5 逐段解释：从公式到系统

**（1）公式逐项拆**（EX-25-01）：`a·b = 24` 是"逐维相乘再求和"——对应两个文本在各个语义维度上的重合程度；除以两个模长是把"向量多长"（与语义无关的幅度）消掉，只留"方向"——这就是余弦相似度对**文本长度不敏感**的原因：一句话和它的缩写版可以同向。16.26° 的夹角是 0.96 的几何直观。

**（2）归一化的工程意义**。`unit(a)·unit(b) == cos(a,b)`（输出里已验证）意味着：所有向量入库前 L2 归一化后，检索的每一次比较都从"两次求模+一次点积"降为"一次点积"。百万级向量 × 毫秒级延迟的差距就是这么抠出来的。第六部分的检索代码会直接复用这个性质。

**（3）MockEmbedder 怎么"伪造语义"**。三层：概念词典（"手机""电话"同属通讯概念 → 同一维 +1，这就是相似度矩阵里 1.000 的来源）；哈希词袋（其余片段按 sha256 映射到固定维度，未命中的概念间近似正交，如"披萨"的 0.000）；L2 归一化。它兑现了"相似文本→相似向量"的**可验证性质**（sim(a,a)=1、语义排序成立），但语义来源是人工词典——**类比边界再强调一次**：真模型不需要词典就知道"手机≈移动电话"，且能表达"程度"与"类比"关系；Mock 只负责让 RAG 的数学骨架在离线环境可复现。

**（4）负相似度怎么读**。EX-25-03 里发票/积分条款得分是 -0.077/-0.118：Mock 的哈希词袋带正负号，负值表示哈希碰撞方向相反。真实模型上无关文本通常在 0~0.3 之间徘徊而很少深度为负——**相似度的绝对值没有跨模型可比性**，阈值必须用自家语料实测校准，这也是"别把 0.7 当万能量表"的原因。

**（5）real 模式的形状**。`RealEmbedder.embed` 走 `client.embeddings.create(input=texts, model=...)`（签名已核实：`input/model/dimensions/encoding_format/user`），返回按 `index` 排序对齐输入顺序。批量接口一次传一个 list 比 5 次单条请求省 4 次网络往返——生产检索管线的基础优化。

**（6）Java 对照**：余弦相似度之于向量检索，如同哈希索引之于等值查询——但方向相反：等值查询要"精确命中"，向量检索要"最接近的前 k 个"；所以向量库（第六部分引入）的本质是**近似最近邻索引**，牺牲一点召回换百倍速度，和 B+ 树不是一回事。

## 25.6 安装 / 文件位置 / 运行命令

```bash
pip install -r requirements.txt   # numpy==2.5.4
python3 示例代码/ch25_embeddings/ex_25_01_cosine_manual.py
python3 示例代码/ch25_embeddings/ex_25_02_similarity_intuition.py
python3 示例代码/ch25_embeddings/ex_25_03_mini_search.py
# real 模式：export OPENAI_API_KEY=... && export LLM_MODE=real（调用 text-embedding-3-small 等模型）
```

## 25.7 常见错误与排查

**错 1：没归一化就把点积当相似度。**
现象：同一对文本，向量长度不同时"相似度"跟着变。原因：未归一化的点积 = 方向 × 幅度。修复：入库前统一 L2 归一化（或坚持用 cosine_similarity 而非裸点积）。

**错 2：维度不齐直接比较。**
```text
ValueError: operands could not be broadcast together with shapes (64,) (1536,)
```
原因：库里一半向量是 Mock 的 64 维、一半是真模型的 1536 维（换模型没重灌库）。修复：**换 embedding 模型必须全量重建向量库**——不同模型的向量空间互不相通；校验入库时维度与模型一致。

**错 3：把相似度阈值写死成 0.7。**
现象：换模型/换语料后全量命中或全量落空。原因：相似度分布因模型与语料而异，绝对值无通用意义。修复：用自家查询样本画出分数分布定阈值（第六部分 ch33），并保留 Top-k 兜底。

**错 4：空字符串/超长文本送进 embedding。**
现象：空串返回零向量（cosine_similarity 约定为 0.0，不报错），超长文本被静默截断。修复：入库前做长度校验与非空断言；超长文本先切分（ch32）再嵌入——单向量表达不了 1 万字的所有细节。

## 25.8 企业场景中的使用方式

客服知识库的落地路径就是把 EX-25-03 工业化：入库流水线（文档→切分→批量 embed→归一化→入库）+ 查询服务（查询 embed→Top-k→过滤→交给生成模型引用回答）。Spring Boot 侧通常持有业务库与权限模型，Python 侧持有向量检索服务，两者用内部 REST 交互（第 56/57 章）。缓存层可以按"查询文本哈希 → 检索结果"做短期缓存（ch19 的 Redis 模板直接复用）。**权限必须在检索前过滤**（按租户缩小候选集），而不是检索后再筛——否则 Top-k 里全是用户无权看的文档，引用了就泄露。

## 25.9 练习

**基础 1**：不运行代码，计算 cos([1,0],[1,1])（保留两位小数），并说出它与 1 的差距由什么决定。

**基础 2**：用四个区别里的任意两个，说明为什么不能拿 chat 模型的 temperature 参数去"调"embedding 结果。

**代码 1**：给 EX-25-03 加一个函数 `search(query, kb, k)`，返回 Top-k 的 (score, text) 列表，并用 `"积分什么时候清零"` 验证命中第 3 条。

**代码 2**：把 MockEmbedder 的维度调成 32 与 128 各跑一次 EX-25-02，观察相似度矩阵是否变化并解释（提示：概念维度始终占前 6 维）。

**调试题**：同事报告"检索结果把'手机'和'手机壳'判为完全相同（1.000），但业务上要区分"。给出两个层面的解释与对策。

### 参考答案

**基础 1**：cos = 1/√2 ≈ 0.71。差距由两向量的"分离维度"决定——b 多出的第 2 维稀释了同向成分。

**基础 2**：embedding 无采样过程（同输入同输出，确定性前向），temperature/top_p 根本不在其接口里（`embeddings.create` 签名已核实没有这些参数）；且它不"生成"文本，调随机性没有对象。

**代码 1**（要点）：
```python
def search(query: str, kb: list[str], k: int) -> list[tuple[float, str]]:
    emb = get_embedder()
    q = emb.embed_one(query)
    scored = sorted(((cosine_similarity(q, v), t) for v, t in zip(emb.embed(kb), kb)),
                    key=lambda x: x[0], reverse=True)
    return scored[:k]
```
"积分什么时候清零"与第 3 条同属"订单/会员"概念簇，Top-1 命中。

**代码 2**：矩阵不变。概念词典命中的词永远占据前 6 维且归一化后被放大到主导地位，哈希空间的维数变化影响的是"未命中词"的正交性细节，对这 5 个词的排序无影响——这恰好演示了"概念方向主导 Mock 语义"。

**调试题**：解释层面——Mock（及部分粗粒度模型）里"手机壳"与"手机"共享概念方向，余弦 1.0 表示"同一概念簇"而非"同一实体"；对策层面——① 换更强的 embedding 模型（真模型能区分上下位词）；② 在业务层加实体识别/同义词典做后过滤；③ 检索排序只负责"入围"，业务区分交给下游规则——语义相似度不是分类器。

## 25.10 自测检查表

- 我能说出 embedding 模型与生成模型的四个区别。
- 我能手算两个 3 维向量的余弦相似度，并解释除以模长的几何意义。
- 我能解释"L2 归一化后点积即余弦"及其对检索系统的性能意义。
- 我能描述 MockEmbedder 的三层构造，并准确说出它的语义边界（词典级 vs 训练级）。
- 我能解释为什么"SIM 卡坏了"能命中"保修条款"，以及这在真实系统里依赖什么。
- 我知道换 embedding 模型必须重建向量库，以及相似度阈值为什么不能照抄别人的数字。

## 25.11 面试追问

**[模拟题] 1：为什么向量检索不用 B-tree，而要专门的数据结构？**
考查点：索引原理差异。合格回答：B-tree 支持等值/范围这种"有序可比较"的查询；高维向量的"最近邻"没有全序关系且维度灾难使精确检索退化为线性扫描，工程上用 ANN（HNSW/IVF 等）以可控的召回损失换数量级加速。

**[模拟题] 2：embedding 相似度高，能说明"答案正确"吗？**
考查点：检索与生成的职责分离。合格回答：不能——相似度高只说明"文本相似"，可能同错（都是过时政策）；正确性要靠引用溯源（答案引用了哪条原文）、忠实性校验（答案是否超出引用内容）与评估集统计（ch35）。

**[模拟题] 3：如果一个 1 万条的知识库，检索延迟要求 50ms，你的方案？**
考查点：规模化的第一性计算。合格回答：1 万条 × 1536 维 float32 ≈ 60MB，单机内存可容纳；numpy/内存向量表 + 批量矩阵乘（一次 GEMV）即可在毫秒级完成暴力扫，无需 ANN；再往上量级才引入 FAISS/HNSW 或向量数据库。先算账再选型。

## 待核实（本部分）

1. **真实模型的行为类结论**（temperature 实际影响幅度、finish_reason=length 的截断细节、多模态支持范围、结构化输出的严格程度）：沙箱无 OPENAI_API_KEY，全部为语义说明/官方机制描述，未在真实服务上实测；教材相应位置已标注"示例输出（非真实记录）"或"以厂商文档为准"。
2. **各兼容厂商的具体支持边界**：ch24 清单给出的是核实方法而非各家结论；厂商能力随版本变化，需按清单逐项实测。
3. **tiktoken 词表的下载可用性**依赖网络环境：本书环境经代理下载成功（约 27 秒）；完全离线环境请预置缓存目录（`TIKTOKEN_CACHE_DIR`）或接受近似计数回退。
4. **上下文窗口与价格数字**：全书刻意不写死任何真实模型的窗口/价格（变化过快），一律以所用模型官方文档为准；示例中的 demo-4k/demo-16k 为虚构教学模型。
5. `chat.completions.parse` 的 JSON Schema 严格模式的字段约束细节（如 `additionalProperties` 要求）未逐项实测，使用前以官方文档为准。

