# 第七部分 LangChain（ch37~ch42）

> 资料核实日期：2026-10-19。本部分全部示例在本教材约定的沙箱环境实际运行（Python 3.14.7；锁定版本：langchain==1.4.6、langchain-core==1.6.12、langchain-openai==1.7.2、langchain-text-splitters==1.1.3、langchain-community==0.4.2、langgraph==1.2.16，见 `requirements.txt`）。
> 运行模式约定（与全书一致）：沙箱没有 `OPENAI_API_KEY`，因此 LangChain 主线使用 langchain-core 自带的 **Fake 模型**（`FakeListChatModel` / `GenericFakeChatModel`，官方测试用途的确定性假模型）做可复现演示——这也是 LangChain 官方测试自己的做法，诚实且专业；涉及 `ChatOpenAI` 的真实调用一律给出"形状经 `inspect` 核实"的代码并明确标注"需 API Key，未实调"。所有 import 路径均在 1.4.6/1.6.12 上实测（运行记录见 `验证报告/运行日志/part07.md`）。
> 前置知识：第四部分（裸 SDK 消息/工具闭环——本部分处处对照"框架替你做了什么"）、ch10（装饰器——`@tool` 的语言基础）、ch16（Pydantic——schema 与校验）、ch13（asyncio——`ainvoke/astream`）。
> 学完你能做什么：
> 1. 给任何一个 AI 需求做"要不要用 LangChain"的选型判断，并给出可辩护的理由（ch37 决策表）；
> 2. 用消息对象、Prompt 模板、结构化输出、`@tool`、LCEL 管道搭出可测试的推理链，并说清每一层比裸 SDK 少写了什么（ch38~41）；
> 3. 用 `create_agent` 构建生产可用的工具调用循环（护栏、持久化、流式、异步），并能把团队里的 AgentExecutor 老代码迁移到 1.x（ch42）。

---

# 第 37 章 LangChain 的定位与边界：先回答"要不要用"

> **本章目标**：建立"框架是成本"的决策意识——先判断需不需要，再学怎么用。
> **前置知识**：第四部分裸 SDK 全流程（ch21~ch25）。
> **学完你能做什么**：用决策表给真实需求做选型；说出 LangChain 各包的分工与版本现状；向团队解释"我们为什么用/不用它"。

## 37.1 真实问题引入：一次让调试变慢的"技术升级"

某电商平台的 Java 团队（合成案例）接到一个智能客服需求。小组里刚转 AI 方向的工程师小周在教程里看到 LangChain，三天下了个决定："上框架，大家都说快。"两个月后复盘：客服场景其实只有"单轮问答 + 固定 prompt + 一个查询接口"，小周用框架搭了三层抽象，结果出现一个线上 bug 时，调用栈从他的业务代码跳进了三层框架包装，堆栈比业务逻辑长三倍；改一个 prompt 要先弄懂框架的注入机制。而隔壁组同样场景用裸 openai SDK 十几行搞定，出问题直接看 HTTP 请求日志。

小周踩的不是 LangChain 的坑，是"跳过选型直接上框架"的坑。**框架的价值完全取决于场景**：它替你做的事情（工具循环、消息配对、组件协议）在某些场景是数周的工程量，在另一些场景是纯粹的认知负担。本章先把"什么时候不需要 LangChain"讲透——这比"怎么用"更重要，也是第七部分所有后续章节的前提。

## 37.2 一句话解释 + 生活类比 + 类比边界

**一句话解释**：LangChain 是一组"把模型调用工程化"的可选组件库——消息对象、提示词模板、工具协议、检索组件、Agent 循环；每一件都对应你在裸 SDK 里亲手写过的一段样板代码，场景里没有那段样板，就没有引入它的理由。

**生活类比**：LangChain 之于模型 API，就像 Spring 之于 Servlet API。裸 Servlet 能写 Web 应用，Spring 提供了依赖注入、事务、MVC 等抽象让工程变大变规范。你不会给一个两接口的小工具上 Spring 全家桶——同理，也不该给一个单轮问答上 Agent 框架。

> 💡 类比边界：
> 1. Spring 的抽象背后是**类型系统**（`@Autowired` 注入的是编译期可检查的 Bean）；LangChain 的 `Runnable` 管道靠**运行时约定**对齐类型，输错类型要到执行时才炸（40.5 详述）——"框架兜底"的安全感要打折；
> 2. Spring 几乎是 Java Web 的事实标准，LangChain 在 Python AI 生态里是**选项之一**：裸 SDK、厂商 SDK、LangGraph（状态机）、自研编排都是正当选择，本书第八部分就专门讲 LangGraph 什么时候替代 LangChain；
> 3. 框架不替你管知识正确性：幻觉、时效、权限问题，用不用框架都一样存在（ch21 的三兄弟不变）。

## 37.3 正式原理与准确术语

先厘清"LangChain"这个词在 1.x 时代指什么。本书锁定的版本（FACTS 库，2026-10-19 核实）与各包分工如下：

| 包名 | 本书版本 | 装什么 |
|---|---|---|
| langchain-core | 1.6.12 | 地基：消息、Runnable/LCEL、工具协议、文档、向量店接口、Fake 模型 |
| langchain | 1.4.6 | 门面：`create_agent`、中间件、`init_chat_model` 等高层入口 |
| langchain-openai | 1.7.2 | 厂商集成：`ChatOpenAI`（需 API Key 才能真实调用） |
| langchain-text-splitters | 1.1.3 | 文档切分器（第六部分 ch32 已用过） |
| langchain-community | 0.4.2 | 历史大杂烩集成包：官方已宣布 sunset（导入时实测警告，41.3 引用原文） |
| langchain-classic | 1.0.8 | 兼容包：装 langchain 时作为依赖带入，存着老 API（`AgentExecutor` 等） |

**链（Chain）**：多个步骤按序组合成的调用单元。1.x 中一切链都是 **Runnable**（可运行对象，ch40 展开），用 `|` 拼接。

**Agent**：让模型自主决定"调哪个工具、调几次"的循环结构。1.x 的推荐构建方式是 `langchain.agents.create_agent`（ch42），它内部生成一个 LangGraph 图。

**LangGraph**：与 LangChain 同生态的状态机/图编排库。当需求涉及人工审批、中断恢复、复杂分支时，它是比"链"更对的表达工具（第八部分主题）。

**Fake 模型**：langchain-core 内置的测试用聊天模型，按预置脚本返回消息。本书用它做离线确定性演示——类比 Java 世界的 WireMock（HTTP 桩）与 Mockito（对象桩）：**测的是你的接线，不是模型的智力**。

## 37.4 最小完整示例：决策表与"同一任务两条实现线"

**EX-37-01 | 示例代码/ch37_lc_boundary/ex_37_01_decision_table.py（完整可运行）**

```python
# EX-37-01 | 什么时候不需要 LangChain：决策表自检 | 运行: python3 示例代码/ch37_lc_boundary/ex_37_01_decision_table.py
"""完整可运行（不联网、不依赖模型）：把"要不要上 LangChain"的判断标准写成可执行的
决策函数——输入一个场景特征包，输出"裸 SDK / 组件级使用 / 全家桶 / 换 LangGraph"建议。

这不是玩具：上线评审时把新 AI 需求的特征填进来跑一遍，比开会拍脑袋有据可依。
"""
from __future__ import annotations

from typing import Literal

# 每个特征都对应一章学过的能力：成本（ch21）、工具闭环（ch24/42）、检索（ch25/41）……
Advice = Literal["bare_sdk", "components_only", "full_langchain", "langgraph"]


def advise(
    *,
    single_turn: bool,            # 是否单轮问答（无多步状态）
    steps: int,                   # 流水线步骤数（1=直接调用，2~3=简单管道）
    needs_tools: bool,            # 是否需要模型点名工具（查库/调内部 API）
    needs_model_switch: bool,     # 是否需要频繁换厂商 / 多模型 A/B
    needs_retrieval: bool,        # 是否需要检索增强（RAG）
    needs_hitl_or_resume: bool,   # 是否需要人工审批 / 中断恢复 / 持久化
) -> Advice:
    """按第七部分的决策表给出建议。判定顺序 = 阻断性从高到低。"""
    if needs_hitl_or_resume:
        # 人工介入/中断恢复是状态机需求：LangChain（链）表达不了，直接 LangGraph
        return "langgraph"
    if single_turn and steps == 1 and not needs_tools and not needs_model_switch:
        # 裸 SDK 十行代码搞定，框架在这类场景是纯认知开销（37.2 案例 1）
        return "bare_sdk"
    if needs_tools:
        # create_agent 替你处理消息回写/tool_call_id 配对/循环终止（对照 EX-24-03）
        return "full_langchain"
    if needs_retrieval or needs_model_switch:
        # 用文档组件 / Retriever / Runnable 抽象，但别上重型 Agent
        return "components_only"
    if steps >= 2:
        # 简单管道：手写函数组合即可；想要统一 batch/stream/ainvoke 再引入 LCEL
        return "components_only"
    return "bare_sdk"


ADVICE_CN: dict[str, str] = {
    "bare_sdk": "裸 SDK（第四部分）——框架是纯开销",
    "components_only": "组件级使用（Prompt/文档/Retriever）——不引入 Agent",
    "full_langchain": "LangChain 全流程（create_agent + 工具）",
    "langgraph": "LangGraph（第八部分）——这是状态机需求，链表达不了",
}

CASES: list[tuple[str, dict[str, bool | int]]] = [
    ("案例 1：客服 FAQ 单轮问答，prompt 固定", dict(single_turn=True, steps=1, needs_tools=False,
                                                    needs_model_switch=False, needs_retrieval=False,
                                                    needs_hitl_or_resume=False)),
    ("案例 2：文档知识库问答（检索+生成）", dict(single_turn=True, steps=2, needs_tools=False,
                                                  needs_model_switch=False, needs_retrieval=True,
                                                  needs_hitl_or_resume=False)),
    ("案例 3：查订单+查物流后作答（两个内部 API）", dict(single_turn=True, steps=1, needs_tools=True,
                                                        needs_model_switch=False, needs_retrieval=False,
                                                        needs_hitl_or_resume=False)),
    ("案例 4：运维审批流——高危操作要人确认，可中断恢复", dict(single_turn=False, steps=3, needs_tools=True,
                                                          needs_model_switch=True, needs_retrieval=False,
                                                          needs_hitl_or_resume=True)),
    ("案例 5：多厂商 A/B 灰度，调用前要做脱敏预处理", dict(single_turn=True, steps=2, needs_tools=False,
                                                        needs_model_switch=True, needs_retrieval=False,
                                                        needs_hitl_or_resume=False)),
]


def main() -> None:
    print("决策表（判定顺序 = 阻断性从高到低）：")
    print("  1) 需要人工审批/中断恢复/持久化  → LangGraph")
    print("  2) 单轮 + 单步 + 无工具 + 不换模型 → 裸 SDK")
    print("  3) 需要工具调用循环              → create_agent（LangChain）")
    print("  4) 需要检索/换模型/简单管道       → 组件级使用\n")

    for title, feats in CASES:
        advice = advise(**feats)  # type: ignore[arg-type]
        print(f"{title}\n    → 建议：{ADVICE_CN[advice]}")

    # 边界自检：参数组合必须总有结论（决策表不许有"查无此项"）
    import itertools

    count = 0
    for combo in itertools.product([True, False], repeat=5):
        for steps in (1, 3):
            advise(single_turn=combo[0], steps=steps, needs_tools=combo[1],
                   needs_model_switch=combo[2], needs_retrieval=combo[3],
                   needs_hitl_or_resume=combo[4])
            count += 1
    print(f"\n[自检] {count} 种特征组合全部有唯一结论，决策表完备。")


if __name__ == "__main__":
    main()
```

```text
# 真实运行输出（Python 3.14.7，不联网）
决策表（判定顺序 = 阻断性从高到低）：
  1) 需要人工审批/中断恢复/持久化  → LangGraph
  2) 单轮 + 单步 + 无工具 + 不换模型 → 裸 SDK
  3) 需要工具调用循环              → create_agent（LangChain）
  4) 需要检索/换模型/简单管道       → 组件级使用

案例 1：客服 FAQ 单轮问答，prompt 固定
    → 建议：裸 SDK（第四部分）——框架是纯开销
案例 2：文档知识库问答（检索+生成）
    → 建议：组件级使用（Prompt/文档/Retriever）——不引入 Agent
案例 3：查订单+查物流后作答（两个内部 API）
    → 建议：LangChain 全流程（create_agent + 工具）
案例 4：运维审批流——高危操作要人确认，可中断恢复
    → 建议：LangGraph（第八部分）——这是状态机需求，链表达不了
案例 5：多厂商 A/B 灰度，调用前要做脱敏预处理
    → 建议：组件级使用（Prompt/文档/Retriever）——不引入 Agent

[自检] 64 种特征组合全部有唯一结论，决策表完备。
```

**EX-37-02 | 示例代码/ch37_lc_boundary/ex_37_02_side_by_side.py（完整可运行）**

```python
# EX-37-02 | 同一任务对照：裸 llm_client vs LangChain 链 | 运行: python3 示例代码/ch37_lc_boundary/ex_37_02_side_by_side.py
"""完整可运行（Mock，不联网）：同一个任务——"客服风格回答 + 打印 token 统计"——
分别用第四部分的裸 llm_client 与 LangChain（Fake 模型）实现，逐项对比"框架替你做了什么"。

诚实声明：LangChain 侧用的是 langchain-core 的 FakeListChatModel（官方测试用途的
确定性假模型，无需 API Key），回答是脚本预置的；裸 llm_client 是全书自研的规则 Mock。
两者的"回答文本"都是确定性的，比较的是【工程接口】，不是模型智力。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # 仓库根

from 示例代码.公共.llm_client import MockLLM, count_tokens  # noqa: E402

from langchain_core.language_models import FakeListChatModel  # noqa: E402
from langchain_core.output_parsers import StrOutputParser  # noqa: E402
from langchain_core.prompts import ChatPromptTemplate  # noqa: E402

QUESTION = "退货政策是什么？"


def bare_sdk_version() -> tuple[str, dict[str, int]]:
    """裸 SDK 版本（EX-24 的形态）：手写 system prompt、手拼消息 dict、手取字段。"""
    llm = MockLLM()
    messages = [
        {"role": "system", "content": "你是电商客服助手，用简洁中文回答。"},
        {"role": "user", "content": QUESTION},
    ]
    result = llm.chat(messages)
    usage = {
        "prompt_tokens": result.usage["prompt_tokens"],
        "completion_tokens": result.usage["completion_tokens"],
    }
    return result.content, usage


def langchain_version() -> tuple[str, str]:
    """LangChain 版本：模板声明式组装，prompt | model | parser 三段管道。"""
    prompt = ChatPromptTemplate.from_messages([
        ("system", "你是电商客服助手，用简洁中文回答。"),
        ("human", "{question}"),
    ])
    model = FakeListChatModel(responses=["（Fake）您好，7 天内可无理由退货，运费由商家承担。"])
    chain = prompt | model | StrOutputParser()
    answer: str = chain.invoke({"question": QUESTION})
    return answer, type(chain).__name__


def main() -> None:
    print("[对照 A] 裸 llm_client（第四部分接口）：")
    answer, usage = bare_sdk_version()
    n, method = count_tokens(QUESTION)
    print(f"    回答：{answer}")
    print(f"    usage：{usage}  （count_method={method}，查询本身 {n} tokens）")
    print("    你亲手写的：消息 dict 拼装、system 关键词匹配、usage 统计\n")

    print("[对照 B] LangChain（FakeListChatModel + LCEL 管道）：")
    answer, chain_type = langchain_version()
    print(f"    回答：{answer}")
    print(f"    管道类型：{chain_type}")
    print("    框架替你做的：消息对象化、模板变量注入、输出解析、统一的 invoke/batch/stream")

    print("\n[框架没替你做的——这两个实现里都有你的活]：")
    print("    1) token 统计：FakeListChatModel 不提供 usage，要自己接（真实 ChatOpenAI 响应里有 usage_metadata）")
    print("    2) 行为正确性：Mock/Fake 的回答都是脚本预置，业务正确性永远由你的测试保证")
    print("    3) 密钥与网络策略：无论裸 SDK 还是框架，Key 管理都在你这边（ch02/ch58）")

    print("\n[判断] 这个任务该用谁？")
    print("    单轮 + 单步 + 不换模型 → 裸 SDK 足够（EX-37-01 决策表建议 bare_sdk）；")
    print("    但如果明天要加'检索到政策原文再回答'，LangChain 的组件（ch41）就开始省事了。")


if __name__ == "__main__":
    main()
```

```text
# 真实运行输出（LLM_MODE=mock，不联网）
[对照 A] 裸 llm_client（第四部分接口）：
    回答：（Mock·客服）您好，已收到您的问题「退货政策是什么？」，工号 007 为您服务。
    usage：{'prompt_tokens': 30, 'completion_tokens': 36}  （count_method=tiktoken:cl100k_base，查询本身 10 tokens）
    你亲手写的：消息 dict 拼装、system 关键词匹配、usage 统计

[对照 B] LangChain（FakeListChatModel + LCEL 管道）：
    回答：（Fake）您好，7 天内可无理由退货，运费由商家承担。
    管道类型：RunnableSequence
    框架替你做的：消息对象化、模板变量注入、输出解析、统一的 invoke/batch/stream

[框架没替你做的——这两个实现里都有你的活]：
    1) token 统计：FakeListChatModel 不提供 usage，要自己接（真实 ChatOpenAI 响应里有 usage_metadata）
    2) 行为正确性：Mock/Fake 的回答都是脚本预置，业务正确性永远由你的测试保证
    3) 密钥与网络策略：无论裸 SDK 还是框架，Key 管理都在你这边（ch02/ch58）

[判断] 这个任务该用谁？
    单轮 + 单步 + 不换模型 → 裸 SDK 足够（EX-37-01 决策表建议 bare_sdk）；
    但如果明天要加'检索到政策原文再回答'，LangChain 的组件（ch41）就开始省事了。
```

## 37.5 逐段解释：决策表怎么用，判断案例怎么长

**（1）决策表的判定顺序就是"成本从不可逆到可逆"**。人工审批/中断恢复排在第一位，因为它需要**状态在请求之间存活并可恢复**——这是状态机能力，链表达不了（第八部分会讲 LangGraph 的 `interrupt`/`checkpointer`）。单轮单步排第二：这种场景裸 SDK 是"最少依赖、最短调用栈"，框架不会让它更好用。工具循环排第三：这正是框架收益最大的地方——EX-24-03 里那六步手写样板（assistant 回写、tool 配对、循环终止）全部交给 `create_agent`。检索与换模型排第四：用组件（ch41 的 Retriever、ch38 的模型抽象），不必引入 Agent。

**（2）三个真实判断案例的展开**（合成案例，用于示范推理过程）：

- **判断案例 A（选裸 SDK）**：内部工单系统要"把用户问题分类到 12 个类目"。单轮、单步、prompt 稳定、类目集合是配置不是检索。结论：裸 SDK + `response_format`（EX-24-02 的形态）+ 一个 prompt 回归测试集（ch28）。上框架的收益为零，成本是多一层依赖。
- **判断案例 B（选组件级）**：文档知识库问答（项目 P1 的形态）。有检索、有切分、有引用溯源，但不需要模型"自主多步"。结论：用 `RecursiveCharacterTextSplitter`（其实第六部分就在用）+ 自写 Retriever 套上 LangChain 接口（ch41）+ LCEL 组装管道，**不引入 create_agent**——因为"检索→生成"是固定流程，Agent 的自主性反而是风险。
- **判断案例 C（选 create_agent）**：运维助手要"根据告警决定查哪个指标接口、可能连环查、最后给结论"。步骤数不可预知、工具多于一个、模型要自己规划调用顺序。结论：`create_agent` + `@tool` + 步数护栏中间件（ch42），并且从第一天就配上 `ModelCallLimitMiddleware`——真实世界里"模型抽风狂点工具"不是假设，是会用掉的账单。

> ⚠️ 常见坑：决策会随需求漂移。案例 A 半年后加了"顺带查物流"就变成了案例 C——所以本书把它做成**可执行的函数**（EX-37-01），需求评审时重跑一遍，别依赖当初的口头结论。

**（3）"框架替你做了什么"是全书的对照主线**。EX-37-02 的输出里有一句值得背下来：框架给你消息对象化、模板注入、统一执行协议；**token 统计、业务正确性、密钥管理从来都在你这边**。后面五章的每个示例都在重复这个句式——学框架不是学"它能做什么"，是学"它接手了你手写过的哪一段、留下了哪一段"。

## 37.6 安装 / 文件位置 / 运行命令

```bash
# 安装（项目根目录；第七部分依赖已全部在 requirements.txt 内）
pip install -r requirements.txt
# 核心三件：langchain==1.4.6 / langchain-core==1.6.12 / langchain-openai==1.7.2

# 运行
python3 示例代码/ch37_lc_boundary/ex_37_01_decision_table.py
python3 示例代码/ch37_lc_boundary/ex_37_02_side_by_side.py

# 测试
python3 -m pytest 测试/test_ch37.py -q
```

## 37.7 常见错误与排查

**错 1：`ImportError: cannot import name 'AgentExecutor' from 'langchain.agents'`。**
真实报错（EX-42-03 实测复现）。原因：1.x 的 `langchain.agents` 只有 `create_agent`/`middleware` 等新入口，老 API 全部搬进兼容包 `langchain-classic`。修复：新代码一律 `create_agent`；维护老代码时 `from langchain_classic.agents import AgentExecutor`（仅为过渡，迁移表见 42.7）。

**错 2：教程代码用 `from langchain.chains import LLMChain`，1.4.6 里导入失败。**
原因：0.x 时代的 `chains` 模块在 1.x 里不再是主线（`langchain.chains` 的老入口随 langchain-classic 保留），LCEL 管道是替代品。修复：`prompt | model | parser`（ch40）；看到任何 0.x 教程先对照本书 42.7 的迁移表"翻译"再动手。

**错 3：`ChatOpenAI()` 直接抛 `OpenAIError: Missing credentials...`。**
原因：langchain-openai 真实调用需要 Key（沙箱/CI 没有）。修复：本地开发 `export OPENAI_API_KEY=...`；离线教学/测试用 Fake 模型（38.4 实测两种 Fake 的行为差异），生产用密钥管理服务注入（ch58）。

**错 4：装了 langchain 但 `pip list` 里冒出十几个 langchain-\* 包，怀疑装错了。**
原因：这是正常的——langchain 1.x 依赖 langchain-core/langchain-classic/langgraph 等一组包。修复：以 `requirements-lock.txt` 为准核对版本；升级时整组一起升，避免 core 与主包版本错配。

## 37.8 企业场景中的使用方式

Spring Boot 团队做技术选型评审时，建议把 EX-37-01 的 `advise()` 函数搬进**架构决策记录（ADR）**：每个 AI 需求立项时跑一遍，把输出贴进 ADR，附上"预计哪一段样板代码被框架接走、哪一段仍然自研"。这比"业界都在用 LangChain"式的论证可辩护得多。另一个企业视角是**依赖治理**：LangChain 生态版本演进快（本书锁定 1.4.6 是刻意选择），AI 服务的 Dockerfile 应当和业务服务一样走版本锁定 + 定期升级窗口（ch20/ch61），而不是"随手 pip install langchain 拉最新"。

## 37.9 练习

**基础 1**：说出决策表的四个输出与判定顺序，并解释为什么"需要人工审批"被排在最前。

**基础 2**：EX-37-02 里框架"没替你做"的三件事分别对应第几章的知识？

**代码 1**：给 `advise()` 增加 `needs_streaming: bool` 参数（强实时流式需求时，若同时 steps==1 直接建议 bare_sdk），补两个测试用例进 `测试/test_ch37.py` 的思路并至少写出一个。

**代码 2**：把判断案例 B（知识库问答）写成 `advise(...)` 的调用，验证输出为 `components_only`；再改成"还要支持多轮追问且依赖历史状态"，看结论如何变化并解释。

**调试题**：新同事说"我照 0.x 教程写的 `initialize_agent` 在 1.4.6 里行为怪异/报错"。给出排查路径与最终建议。

### 参考答案

**基础 1**：bare_sdk / components_only / full_langchain / langgraph；顺序为审批恢复→单轮单步→工具循环→检索换模型管道。审批恢复排最前，因为它需要跨请求的状态持久与恢复语义，是"链"结构无法表达的能力，继续留在 LangChain 只会绕路。

**基础 2**：token 统计对应 ch21（计数与预算）；业务正确性对应 ch18/ch28（测试与 Prompt 回归）；密钥管理对应 ch02（环境变量）与 ch58（安全）。

**代码 1**（要点）：在 `advise` 签名加 `needs_streaming: bool = False`；首个分支前插入 `if needs_streaming and single_turn and steps == 1 and not needs_tools: return "bare_sdk"`；测试：`advise(..., needs_streaming=True)` 的单轮单步场景返回 `bare_sdk`，含工具时仍返回 `full_langchain`。

**代码 2**：`advise(single_turn=True, steps=2, needs_tools=False, needs_model_switch=False, needs_retrieval=True, needs_hitl_or_resume=False)` → `components_only`；改成多轮历史状态后 `single_turn=False`，若不涉审批则进入 `steps>=2` 分支仍为 `components_only`——解释：多轮对话历史管理用 messages 列表/checkpointer 即可，还没到状态机级别；若再加"可中断恢复"就会翻到 `langgraph`。

**调试题**：先复现最小 import（`from langchain_classic.agents import initialize_agent` 是否可用）定位它在兼容包；再确认行为怪异来自 ReAct 文本协议解析（0.x 特性）而非模型问题；最终建议按 42.7 迁移表改写为 `create_agent`，不要在兼容包上叠加新功能。

## 37.10 自测检查表

- 我能不看资料画出 ch37 决策表（四个输出 + 判定顺序），并解释排序理由。
- 我能说出 langchain-core / langchain / langchain-openai / langchain-community 四个包的分工与版本现状（含 community sunset 事实）。
- 我能对一个具体需求做选型并给出可辩护理由，而不是"教程用了所以我也用"。
- 我能说出框架接手了什么（消息对象、模板注入、执行协议、工具循环样板）、留下了什么（token 预算、正确性、密钥）。
- 我能识别 0.x 教程代码（AgentExecutor/LLMChain/initialize_agent）并给出 1.x 替代方向。
- 我能解释 Fake 模型在教学与测试中的定位，以及它和 WireMock/Mockito 的对应关系。

## 37.11 面试追问

**[模拟题] 1：你们项目为什么用（或不用）LangChain？如果不用，用什么替代了它的哪部分？**
考查点：选型论证。合格回答：按决策表逐项说——场景里是否有工具循环/组件复用需求；不用的场景说明裸 SDK 的具体行数与调用栈优势；用了的场景说清框架接走了哪些样板（消息配对、循环终止、组件协议），以及护栏（步数限制、错误恢复）怎么加。

**[模拟题] 2：LangChain 和 LangGraph 的边界在哪里？**
考查点：生态认知。合格回答：LangChain 的强项是"组件 + 简单链 + 一个标准 Agent 循环"；LangGraph 是状态机/图，状态可持久化、可恢复、支持人工介入。需要跨请求状态、审批流、复杂分支时用 LangGraph；`create_agent` 内部其实就是一张 LangGraph 图——两者不是竞争而是分层。

**[模拟题] 3：有人建议"为了以后换模型厂商，现在就把所有裸 SDK 调用改成 LangChain"，你怎么回应？**
考查点：成本收益。合格回答：换厂商的需求强度要核实（真会发生 vs 假设会发生）；若真需要抽象，最小手段是自建一个薄接口（本书 llm_client 就是示范）或 `init_chat_model`，不必为假设的灵活性引入整个框架；若团队同时要工具循环/组件，框架的抽象才有额外收益。

> 📌 本章待核实项：LangChain 官方对各集成包的长期维护策略仍在演进（如 community 的 sunset 后续），选型时以官方发布说明为准；本书只对锁定版本（1.4.6/1.6.12）的实测行为负责。

---

# 第 38 章 核心抽象：消息、模型、Prompt 与结构化输出

> **本章目标**：把第四部分的"dict 消息 + 手拼 prompt"升级为 LangChain 的四个核心抽象，并保持裸 SDK 对照视角。
> **前置知识**：ch23（消息角色）、ch24（SDK 结构化输出）、ch16（Pydantic）。
> **学完你能做什么**：用消息对象写类型清晰的对话代码；用 ChatPromptTemplate 管理提示词；用 `with_structured_output` 与 PydanticOutputParser 两条路线拿到强类型结果；用 Fake 模型搭可离线测试的模型层。

## 38.1 真实问题引入：一份谁都不敢改的 prompt 组装函数

某团队的 Java 转型小组（合成案例）把第四部分的裸 SDK 代码交给了新同事。两周后新同事提了两个问题：第一，`{"role": "system", ...}` 这种 dict 拼错了 role 字符串（`"System"`）运行时不报错，直到模型 API 返回 400 才发现；第二，prompt 是一个巨大的 f-string，变量名改一个字母要全文搜替换，而且没有人知道这个 prompt 需要哪些变量——直到运行时 `KeyError`。老王意识到：**消息结构和提示词在该团队里是"字符串约定"，不是"类型契约"**。

LangChain 的前两个抽象正是针对这两点：消息对象（`HumanMessage` 等）把 role 变成类型；Prompt 模板把变量声明成模板的一部分。加上"模型"（统一封装各厂商调用）与"结构化输出"（schema 即类型），就构成了 1.x 的核心抽象四件套。

## 38.2 一句话解释 + 生活类比 + 类比边界

**一句话解释**：LangChain 把"对话"建模为**消息对象列表**、把"提示词"建模为**带变量声明的模板**、把"模型调用"建模为 **Runnable 的 ChatModel**、把"要 JSON"建模为 **schema 驱动的结构化输出**——四者都是可组合的组件。

**生活类比**：消息对象之于裸 dict，就像 Java 的强类型 DTO 之于 `Map<String, Object>`；PromptTemplate 之于 f-string，就像 MyBatis 的 SQL 模板之于手工拼 SQL——变量有声明、有校验、可复用；`with_structured_output` 之于手动 `json.loads`，就像 Jackson `readValue(clazz)` + Bean Validation 之于手写解析。

> 💡 类比边界：
> 1. 消息对象是**运行时 Pydantic 模型**，不是编译期检查——`AIMessage(content=123)` 这种类型错误照样要到执行时才发现（Pydantic 会校验，但"拼错 role 字符串"这类问题被类型消灭了）；
> 2. PromptTemplate 变量缺失抛 `KeyError`（运行时），没有"MyBatis XML 启动期校验"——变量清单要靠 `prompt.input_variables` 自检（38.4 实测）；
> 3. 结构化输出的 json_schema 模式依赖**服务端支持**，OpenAI 兼容服务常被裁剪（ch24 清单同样适用）——schema 约束不是银弹，校验回退永远是必备。

## 38.3 正式原理与准确术语

**消息模型（messages）**：`langchain_core.messages` 提供与 OpenAI 角色一一对应的消息类——`SystemMessage`（system）、`HumanMessage`（user）、`AIMessage`（assistant）、`ToolMessage`（tool）。`AIMessage.tool_calls` 是结构化的工具调用请求列表（`{id, name, args, type}`），模型返回时框架已把 JSON 字符串解析成 dict。流式场景用 `AIMessageChunk`，支持 `+` 聚合。

**聊天模型（ChatModel）**：`BaseChatModel` 的子类，是 Runnable（`invoke/batch/stream/ainvoke` 全套协议）。`ChatOpenAI`（langchain-openai 1.7.2）是最常用的真实模型；`FakeListChatModel`/`GenericFakeChatModel`（langchain-core 1.6.12 内置）是测试用假模型。

**提示词模板**：`ChatPromptTemplate`（对话消息模板，支持 `MessagesPlaceholder` 历史占位）与 `PromptTemplate`（纯文本模板）。`invoke` 后得到 `ChatPromptValue`（消息列表的包装），`input_variables` 声明所需变量。

**结构化输出**：两条路线——① `ChatOpenAI.with_structured_output(Schema)`：签名已核实为 `(schema=None, *, method='json_schema', include_raw=False, strict=None, tools=None, **kwargs)`，返回 `Runnable[LanguageModelInput, Schema实例]`，method 可选 `json_schema`（服务端约束，默认）/`function_calling`（靠工具调用协议）/`json_mode`；② `PydanticOutputParser`：把"模型输出的 JSON 文本 → Pydantic 校验"做成管道一环，Fake 模型可用，失败抛 `OutputParserException`。

**Fake 模型的两种消费语义**（1.6.12 实测，EX-38-02 为证）：`FakeListChatModel(responses=[...])` 按序消费、**耗尽后循环回开头**（源码注释原话 "cycle"）；`GenericFakeChatModel(messages=iter([...]))` 按迭代器消费、**耗尽抛 `StopIteration`**。要"循环应答"选前者，要"精确控制第 N 轮"（工具循环脚本）选后者。

**Java 对照**：消息类 ≈ 消息 DTO 层次结构（`SystemMessage`/`UserMessage` 各自有类型，而不是 role 字符串 + switch）；ChatPromptTemplate ≈ 带参数声明的消息模板引擎；`with_structured_output` ≈ `ObjectMapper.readValue(json, RefundCheck.class)` 加 Bean Validation，且校验失败自动把错误交回给你决定重试。

## 38.4 最小完整示例：消息、双模式模型、模板与结构化链

**EX-38-01 | 示例代码/ch38_lc_core/ex_38_01_messages.py（完整可运行）**

```python
# EX-38-01 | 消息模型：LangChain 消息对象与裸 SDK dict 的映射 | 运行: python3 示例代码/ch38_lc_core/ex_38_01_messages.py
"""完整可运行（离线）：构造 HumanMessage/AIMessage/SystemMessage/ToolMessage，
对比第四部分裸 SDK 的 dict 形态；演示 FakeListChatModel 的 invoke 与 AIMessageChunk 流式聚合。
"""
from __future__ import annotations

from langchain_core.language_models import FakeListChatModel
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)


def main() -> None:
    print("[1] 四类消息对象 vs 裸 SDK dict（字段对照）：")
    msgs: list = [
        SystemMessage(content="你是电商客服助手。"),
        HumanMessage(content="北京天气怎么样？"),
        AIMessage(content="", tool_calls=[{
            "id": "call_001", "name": "get_weather",
            "args": {"city": "北京"}, "type": "tool_call",
        }]),
        ToolMessage(content='{"city": "北京", "weather": "晴"}', tool_call_id="call_001"),
    ]
    for m in msgs:
        extra = ""
        if isinstance(m, AIMessage) and m.tool_calls:
            extra = f" tool_calls={m.tool_calls}"
        if isinstance(m, ToolMessage):
            extra = f" tool_call_id={m.tool_call_id}"
        print(f"    {type(m).__name__:<13} content={m.content!r}{extra}")
    print("    裸 SDK dict 对照：{'role': 'system'|'user'|'assistant'|'tool', 'content': ...}")
    print("    → LangChain 把 dict 换成了带类型的对象；发给模型 API 时框架负责序列化回 dict")

    print("\n[2] 模型返回值：invoke 一次 Fake 模型：")
    model = FakeListChatModel(responses=["北京今天晴，26℃。（Fake 预置）"])
    ai = model.invoke([HumanMessage(content="北京天气怎么样？")])
    print(f"    type = {type(ai).__name__}")
    print(f"    content = {ai.content!r}")
    print(f"    id 前 8 位 = {ai.id[:8]}...  （框架自动生成消息 id）")
    print(f"    usage_metadata = {ai.usage_metadata}  （Fake 模型无 usage：None/空，真实模型有值）")

    print("\n[3] 流式：AIMessageChunk 用 + 号聚合（对照 ch23 手工拼接 delta）：")
    model2 = FakeListChatModel(responses=["逐字流式输出"])
    chunks: list[AIMessageChunk] = list(model2.stream("任意输入（Fake 不看输入）"))
    print(f"    chunk 数 = {len(chunks)}，类型 = {type(chunks[0]).__name__}")
    merged = chunks[0]
    for c in chunks[1:]:
        merged = merged + c  # AIMessageChunk 支持相加，自动合并 content/id
    print(f"    聚合后 content = {merged.content!r}")
    print("    → 裸 SDK 里你手写的 'full += delta' 循环，框架里是一个 + 运算符")


if __name__ == "__main__":
    main()
```

```text
# 真实运行输出（离线，langchain-core 1.6.12）
[1] 四类消息对象 vs 裸 SDK dict（字段对照）：
    SystemMessage content='你是电商客服助手。'
    HumanMessage  content='北京天气怎么样？'
    AIMessage     content='' tool_calls=[{'name': 'get_weather', 'args': {'city': '北京'}, 'id': 'call_001', 'type': 'tool_call'}]
    ToolMessage   content='{"city": "北京", "weather": "晴"}' tool_call_id=call_001
    裸 SDK dict 对照：{'role': 'system'|'user'|'assistant'|'tool', 'content': ...}
    → LangChain 把 dict 换成了带类型的对象；发给模型 API 时框架负责序列化回 dict

[2] 模型返回值：invoke 一次 Fake 模型：
    type = AIMessage
    content = '北京今天晴，26℃。（Fake 预置）'
    id 前 8 位 = lc_run--...  （框架自动生成消息 id）
    usage_metadata = None  （Fake 模型无 usage：None/空，真实模型有值）

[3] 流式：AIMessageChunk 用 + 号聚合（对照 ch23 手工拼接 delta）：
    chunk 数 = 6，类型 = AIMessageChunk
    聚合后 content = '逐字流式输出'
    → 裸 SDK 里你手写的 'full += delta' 循环，框架里是一个 + 运算符
```

**EX-38-02 | 示例代码/ch38_lc_core/ex_38_02_fake_and_chatopenai.py（完整可运行）**

```python
# EX-38-02 | Fake 模型（离线确定性）与 ChatOpenAI（真实形状核实） | 运行: python3 示例代码/ch38_lc_core/ex_38_02_fake_and_chatopenai.py
"""完整可运行（不发起真实网络请求）：
[1] Fake 模型两兄弟：脚本消费语义差异（循环 vs 耗尽）——选型依据；
[2] ChatOpenAI：无 Key 构造的真实报错、带 dummy Key 的离线构造、关键方法签名 inspect 核实。
真实调用的代码形状在教材 38.5 给出（需 OPENAI_API_KEY，本沙箱未实调）。
"""
from __future__ import annotations

import inspect

from langchain_core.language_models import FakeListChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_openai import ChatOpenAI


def main() -> None:
    print("[1] Fake 模型两兄弟的行为差异（langchain-core 1.6.12 实测，官方测试用途）：")
    fl = FakeListChatModel(responses=["第一次回答（Fake 预置）", "第二次回答（Fake 预置）"])
    q = [HumanMessage(content="问题是什么？")]
    r1, r2, r3 = fl.invoke(q), fl.invoke(q), fl.invoke(q)
    print(f"    FakeListChatModel 按序消费：{r1.content[:6]}... → {r2.content[:6]}...")
    print(f"    第 3 次 invoke → {r3.content[:6]}...（脚本耗尽后【循环回开头】，源码注释原话：cycle）")
    from langchain_core.language_models import GenericFakeChatModel

    gf = GenericFakeChatModel(messages=iter([AIMessage(content="唯一一条（会耗尽）")]))
    print(f"    GenericFakeChatModel 第 1 次 → {gf.invoke(q).content}")
    try:
        gf.invoke(q)
    except StopIteration:
        print("    第 2 次 invoke → StopIteration（脚本耗尽即报错，绝不静默循环）")
    print("    → 测试脚本选型：要'循环应答'用 FakeList；要'精确控制第 N 轮'（如工具循环）用 Generic。")

    print("\n[2] ChatOpenAI（langchain-openai 1.7.2）：无 Key 的真实报错：")
    try:
        ChatOpenAI(model="gpt-4o-mini")  # 沙箱无 OPENAI_API_KEY
    except Exception as e:
        print(f"    {type(e).__name__}: {str(e)[:100]}...")

    print("\n[3] 带 dummy Key 离线构造成功（不发起请求，只在 invoke 时才真正联网）：")
    m = ChatOpenAI(model="gpt-4o-mini", api_key="sk-dummy-not-used",
                   temperature=0, max_retries=2, timeout=30)
    print(f"    type={type(m).__name__}, model_name={m.model_name}, "
          f"temperature={m.temperature}, max_retries={m.max_retries}")

    print("\n[4] 关键方法签名核实（inspect 实测，教材 38.3 引用）：")
    wso = inspect.signature(ChatOpenAI.with_structured_output)
    print(f"    with_structured_output 参数：{list(wso.parameters.keys())}")
    print(f"      method 默认值 = {wso.parameters['method'].default}")
    bt = inspect.signature(ChatOpenAI.bind_tools)
    print(f"    bind_tools 参数：{list(bt.parameters.keys())}")
    init_params = list(ChatOpenAI.model_fields.keys())
    for name in ["model_name", "temperature", "max_retries", "request_timeout", "openai_api_key",
                 "openai_api_base", "streaming", "max_tokens"]:
        assert name in init_params, name
    print(f"    字段表含 model_name/temperature/max_retries/request_timeout/openai_api_key/...：True")
    print("    注意两处命名错位（pydantic 别名机制，构造参数实测可用）：")
    print("      字段 request_timeout ↔ 构造参数 timeout=（[3] 已实测）；")
    print("      字段 openai_api_key / openai_api_base ↔ 构造参数 api_key= / base_url=（[3] 已实测）。")


if __name__ == "__main__":
    main()
```

```text
# 真实运行输出（不发起网络请求；[2] 为真实报错，[3][4] 为离线构造与签名核实）
[1] Fake 模型两兄弟的行为差异（langchain-core 1.6.12 实测，官方测试用途）：
    FakeListChatModel 按序消费：第一次回答（... → 第二次回答（...
    第 3 次 invoke → 第一次回答（...（脚本耗尽后【循环回开头】，源码注释原话：cycle）
    GenericFakeChatModel 第 1 次 → 唯一一条（会耗尽）
    第 2 次 invoke → StopIteration（脚本耗尽即报错，绝不静默循环）
    → 测试脚本选型：要'循环应答'用 FakeList；要'精确控制第 N 轮'（如工具循环）用 Generic。

[2] ChatOpenAI（langchain-openai 1.7.2）：无 Key 的真实报错：
    OpenAIError: Missing credentials. Please pass an `api_key`, `workload_identity`, `admin_api_key`, or set the `OPE...

[3] 带 dummy Key 离线构造成功（不发起请求，只在 invoke 时才真正联网）：
    type=ChatOpenAI, model_name=gpt-4o-mini, temperature=0.0, max_retries=2

[4] 关键方法签名核实（inspect 实测，教材 38.3 引用）：
    with_structured_output 参数：['self', 'schema', 'method', 'include_raw', 'strict', 'tools', 'kwargs']
      method 默认值 = json_schema
    bind_tools 参数：['self', 'tools', 'tool_choice', 'strict', 'parallel_tool_calls', 'response_format', 'kwargs']
    字段表含 model_name/temperature/max_retries/request_timeout/openai_api_key/...：True
    注意两处命名错位（pydantic 别名机制，构造参数实测可用）：
      字段 request_timeout ↔ 构造参数 timeout=（[3] 已实测）；
      字段 openai_api_key / openai_api_base ↔ 构造参数 api_key= / base_url=（[3] 已实测）。
```

**EX-38-03 | 示例代码/ch38_lc_core/ex_38_03_prompt_structured.py（完整可运行）**

```python
# EX-38-03 | PromptTemplate / ChatPromptTemplate 与结构化输出 | 运行: python3 示例代码/ch38_lc_core/ex_38_03_prompt_structured.py
"""完整可运行（不联网）：
[1] ChatPromptTemplate：变量注入、MessagesPlaceholder、format_messages 与 invoke 的区别；
[2] with_structured_output：真实 ChatOpenAI 的调用形状（签名核实，需 Key 未实调）；
[3] 确定性替代：PydanticOutputParser 组成的"JSON 文本 → Pydantic 对象"链在 Fake 模型上真实跑通。
"""
from __future__ import annotations

import inspect

from langchain_core.language_models import FakeListChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel, Field


class RefundCheck(BaseModel):
    """退款预检结果（与 EX-24-02 同一套 schema，方便对照）。"""

    order_id: str = Field(description="订单号，格式 ORD-数字")
    eligible: bool = Field(description="是否符合自动退款条件")
    reason: str = Field(default="无", description="不符合时的原因")


def main() -> None:
    print("[1] ChatPromptTemplate：声明式模板（对照裸 SDK 手拼 f-string）：")
    prompt = ChatPromptTemplate.from_messages([
        ("system", "你是{role}，用简洁中文回答。"),
        MessagesPlaceholder("history", optional=True),  # 可选的历史占位（ch27 对话历史）
        ("human", "{question}"),
    ])
    print(f"    input_variables = {prompt.input_variables}")
    print(f"    optional_variables = {prompt.optional_variables}")
    value = prompt.invoke({
        "role": "电商客服",
        "question": "退货政策是什么？",
        "history": [HumanMessage(content="之前问过发票"), AIMessage(content="已回答")],
    })
    print(f"    invoke 返回类型 = {type(value).__name__}")
    for m in value.to_messages():
        print(f"      {type(m).__name__}: {m.content[:30]}")
    # 不传 history（optional 生效，不报 KeyError）
    value2 = prompt.invoke({"role": "电商客服", "question": "只问一句"})
    print(f"    不传 history → {len(value2.to_messages())} 条消息（optional 占位自动省略）")

    print("\n[2] PromptTemplate（纯文本模板，非对话）：")
    pt = PromptTemplate.from_template("把这句话翻译成英文：{text}")
    print(f"    pt.invoke({{'text': '你好'}}).to_string() = {pt.invoke({'text': '你好'}).to_string()!r}")

    print("\n[3] with_structured_output 的真实形状（ChatOpenAI，需 Key 未实调，签名已核实）：")
    from langchain_openai import ChatOpenAI

    sig = inspect.signature(ChatOpenAI.with_structured_output)
    print(f"    签名：with_structured_output{sig}")
    print("    真实用法：llm = ChatOpenAI(model='gpt-4o-mini', api_key=...)")
    print("              structured = llm.with_structured_output(RefundCheck)")
    print("              obj = structured.invoke('帮我判断 ORD-1001 能否自动退款')")
    print("    → 返回 Runnable[LanguageModelInput, RefundCheck]：直接产出 Pydantic 实例")
    print("    method 默认 json_schema（服务端 schema 约束），可选 function_calling / json_mode")
    fake = FakeListChatModel(responses=["x"])
    try:
        fake.with_structured_output(RefundCheck)
    except NotImplementedError as e:
        print(f"    Fake 模型不支持（真实报错）：NotImplementedError: {e}")

    print("\n[4] 确定性替代链：Fake 模型输出 JSON 文本 → PydanticOutputParser 校验（真实运行）：")
    parser = PydanticOutputParser(pydantic_object=RefundCheck)
    chain = ChatPromptTemplate.from_messages([
        ("human", "抽取退款预检字段：{text}\n{format_instructions}"),
    ]) | FakeListChatModel(responses=[
        '{"order_id": "ORD-1001", "eligible": true, "reason": "无"}',
        '这句话根本不是 JSON',
    ]) | parser
    ok = chain.invoke({"text": "订单号 ORD-1001 符合条件", "format_instructions": parser.get_format_instructions()})
    print(f"    成功路径：type = {type(ok).__name__}, obj = {ok.model_dump()}")
    try:
        chain.invoke({"text": "失效输出演示", "format_instructions": parser.get_format_instructions()})
    except Exception as e:
        print(f"    失败路径：{type(e).__name__}（输出不是 JSON → 解析失败原样抛出，由你决定重试策略）")


if __name__ == "__main__":
    main()
```

```text
# 真实运行输出（离线；[3] 的"真实用法"为形状说明，未实调）
[1] ChatPromptTemplate：声明式模板（对照裸 SDK 手拼 f-string）：
    input_variables = ['question', 'role']
    optional_variables = ['history']
    invoke 返回类型 = ChatPromptValue
      SystemMessage: 你是电商客服，用简洁中文回答。
      HumanMessage: 之前问过发票
      AIMessage: 已回答
      HumanMessage: 退货政策是什么？
    不传 history → 2 条消息（optional 占位自动省略）

[2] PromptTemplate（纯文本模板，非对话）：
    pt.invoke({'text': '你好'}).to_string() = '把这句话翻译成英文：你好'

[3] with_structured_output 的真实形状（ChatOpenAI，需 Key 未实调，签名已核实）：
    签名：with_structured_output(self, schema: '_DictOrPydanticClass | None' = None, *, method: "Literal['function_calling', 'json_mode', 'json_schema']" = 'json_schema', include_raw: 'bool' = False, strict: 'bool | None' = None, tools: 'list | None' = None, **kwargs: 'Any') -> 'Runnable[LanguageModelInput, _DictOrPydantic]'
    真实用法：llm = ChatOpenAI(model='gpt-4o-mini', api_key=...)
              structured = llm.with_structured_output(RefundCheck)
              obj = structured.invoke('帮我判断 ORD-1001 能否自动退款')
    → 返回 Runnable[LanguageModelInput, RefundCheck]：直接产出 Pydantic 实例
    method 默认 json_schema（服务端 schema 约束），可选 function_calling / json_mode
    Fake 模型不支持（真实报错）：NotImplementedError: with_structured_output is not implemented for this model.

[4] 确定性替代链：Fake 模型输出 JSON 文本 → PydanticOutputParser 校验（真实运行）：
    成功路径：type = RefundCheck, obj = {'order_id': 'ORD-1001', 'eligible': True, 'reason': '无'}
    失败路径：OutputParserException（输出不是 JSON → 解析失败原样抛出，由你决定重试策略）
```

## 38.5 逐段解释：四件套各自接手了什么

**（1）消息对象接手了"role 字符串约定"**。EX-38-01 的对照表就是本节结论：`SystemMessage`→`system`、`HumanMessage`→`user`、`AIMessage`→`assistant`、`ToolMessage`→`tool`，`.type` 属性即裸 SDK 的 role（测试/test_ch38.py 断言过这个映射）。更重要的是 `AIMessage.tool_calls`：EX-24-03 里你要 `json.loads(tc.function.arguments)` 才能拿到参数 dict，框架已把它解析成 `{'name': ..., 'args': {...}}`。流式的 `AIMessageChunk + AIMessageChunk` 聚合，对应 ch23 手写的 `full += delta`——框架连"拼接"都给了类型。

**（2）模型层接手了"厂商差异"**。`ChatOpenAI(model=..., api_key=..., temperature=..., max_retries=..., timeout=...)` 的构造参数与裸 `OpenAI()` 一一对应（EX-38-02 [3][4] 核实）；换厂商 = 换一个 ChatModel 类或用 `langchain.chat_models.init_chat_model`（签名已核实：`(model=None, *, model_provider=None, configurable_fields=None, config_prefix=None, **kwargs)`），你的管道代码不动。**真实模式代码形状**（需 API Key，未实调，形状经签名核实）：

```python
# 示例输出（非真实记录）——真实模式代码形状，需 OPENAI_API_KEY
import os
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

llm = ChatOpenAI(
    model="gpt-4o-mini",
    api_key=os.environ.get("OPENAI_API_KEY"),   # 缺失时构造即抛 OpenAIError（EX-38-02 [2] 实测）
    base_url=os.environ.get("OPENAI_BASE_URL"), # OpenAI 兼容服务按厂商文档核实（≠功能一致）
    temperature=0, max_retries=2, timeout=30,
)
ai = llm.invoke([SystemMessage(content="你是电商客服"), HumanMessage(content="退货政策是什么？")])
print(ai.content, ai.usage_metadata)             # usage_metadata 是 token 统计（EX-37-02 提到的缺口在此补上）
```

**（3）模板接手了"变量契约"**。`ChatPromptTemplate.from_messages([...])` 声明消息结构；`input_variables` 是模板的"必填参数表"（EX-38-03 [1] 实测 `['question', 'role']`）；`MessagesPlaceholder('history', optional=True)` 是对话历史的插槽——传了就插、不传就省（38.7 的错 2 就是它不加 optional 的下场）。Java 对照：这就是把"手工拼 SQL"升级成"MyBatis 模板"，变量有声明、可检查、可复用。

**（4）结构化输出的两条路线怎么选**。`with_structured_output` 强在**约束发生在服务端**（json_schema 模式在解码层限制 token 选择，EX-38-03 [3] 的签名核实 `method='json_schema'` 为默认），弱在依赖服务端支持且 Fake 模型直接 `NotImplementedError`（实测）；`PydanticOutputParser` 强在**任何能吐文本的模型都能用**（Fake 模型实测跑通），弱在约束只靠提示词（`get_format_instructions()` 生成的说明注入 prompt），失败抛 `OutputParserException`。生产姿势与 ch24 相同：**约束优先、校验兜底、失败重试**——两条路线的失败都要进你的重试逻辑，而不是 500。

> ⚠️ 常见坑：Fake 模型的输出与输入完全无关（脚本驱动），别在 Fake 上测"模型是否理解了 prompt"——那不是它能回答的问题。Fake 测接线，真实模型验效果，ch28 的 Prompt 回归测试两步都不能省。

## 38.6 安装 / 文件位置 / 运行命令

```bash
pip install -r requirements.txt   # langchain-core==1.6.12 / langchain-openai==1.7.2 已含

python3 示例代码/ch38_lc_core/ex_38_01_messages.py
python3 示例代码/ch38_lc_core/ex_38_02_fake_and_chatopenai.py
python3 示例代码/ch38_lc_core/ex_38_03_prompt_structured.py

python3 -m pytest 测试/test_ch38.py -q
```

## 38.7 常见错误与排查

**错 1：`OpenAIError: Missing credentials. Please pass an api_key ...`。**
原因：`ChatOpenAI()` 未拿到 Key（环境变量未设）。真实报错全文见 EX-38-02 [2]。修复：本地 `export OPENAI_API_KEY=...`；CI 注入 secret；测试一律用 Fake 模型（不要为了"过测试"把真 Key 提交进代码——ch58 红线）。

**错 2：`KeyError: 'history'`——模板变量没传全。**
原因：`MessagesPlaceholder("history")` 未加 `optional=True` 时是必填占位。修复：非必填历史加 `optional=True`（EX-38-03 [1] 实测）；上线前用 `prompt.input_variables` 对照你的输入 dict 做启动期自检（这就是"类型契约"的用法）。

**错 3：`OutputParserException`：模型输出不是合法 JSON。**
原因：PydanticOutputParser 路线里模型没守约（Fake 下就是你脚本里的文本本身不合法）。修复：把 `get_format_instructions()` 注入 prompt；解析失败捕获后把错误信息拼回 user 消息重试（ch26 的回退循环）；对强约束需求切 `with_structured_output` 的 json_schema 模式（服务端支持时）。

**错 4：`NotImplementedError: with_structured_output is not implemented for this model.`。**
真实报错（EX-38-03 [3] 实测）。原因：该方法依赖模型实现（需要 bind_tools 或 json_schema 协议），Fake 模型/部分自研模型没有实现。修复：真实模型上按厂商文档核实支持情况；教学/测试走 PydanticOutputParser 路线；自定义模型类按协议实现 `with_structured_output`。

## 38.8 企业场景中的使用方式

Spring Boot 团队通常在 Python AI 服务里做**三层接线**：模型层（`ChatOpenAI`，密钥从环境/密钥管理注入，测试用 Fake 替换——正是 Mockito 的"替换实现"思路）、模板层（`ChatPromptTemplate` 集中管理，prompt 版本随代码走 git，ch28 的回归测试盯住它）、输出层（`with_structured_output` 的 schema 与 Java 侧 DTO 字段一一对应，跨语言契约由 JSON Schema 描述文件共享）。这套接线的价值在**评审**：prompt 是模板对象不是散落字符串，schema 是 Pydantic 类不是口头约定，代码评审能看出"这次改了 prompt 的哪个变量"。

## 38.9 练习

**基础 1**：写出四种消息对象与裸 SDK role 的对应表，并说出 `AIMessage.tool_calls` 的四个键。

**基础 2**：`FakeListChatModel` 与 `GenericFakeChatModel` 的脚本消费语义有何不同？分别适合什么测试场景？

**代码 1**：基于 EX-38-03 的 prompt，把 `history` 从 optional 改为必填，运行并捕获报错；再加回 optional 并用 `prompt.optional_variables` 断言修复。把这段写成 `测试/test_ch38.py` 的第三个测试。

**代码 2**：写一个"多轮结构化抽取"链：FakeListChatModel 依次输出两条 JSON（第一条缺 reason，第二条完整），`RefundCheck.reason` 有默认值，验证第一条也能通过校验并解释默认值的作用。

**调试题**：同事的链 `prompt | model | parser` 偶发在 `parser` 处抛 `OutputParserException`，且重试仍失败。给出至少三个排查方向。

### 参考答案

**基础 1**：SystemMessage↔system、HumanMessage↔user、AIMessage↔assistant、ToolMessage↔tool；`tool_calls[i]` 的键为 `id / name / args / type`。

**基础 2**：FakeList 循环（耗尽回开头），适合"模型随便被调多少次都给合理回复"的冒烟测试；Generic 耗尽抛 `StopIteration`，适合"第 N 轮必须返回特定内容"的精确脚本（如工具循环：第 1 轮工具调用、第 2 轮最终回答）。

**代码 1**（要点）：必填时不传 history 抛 `KeyError: 'history'`（模板渲染期）；修复后 `assert prompt.optional_variables == ['history']`；顺带可用 `input_variables` 断言必填清单。

**代码 2**（要点）：`FakeListChatModel(responses=['{"order_id": "ORD-1", "eligible": true}', '{"order_id": "ORD-2", "eligible": false, "reason": "超期"}'])`；第一条缺 reason 时 Pydantic 用默认值"无"填充——默认值是 schema 的一部分，等价于 DTO 字段默认值；注意缺**必填**字段（order_id/eligible）则抛校验异常。

**调试题**：方向一，看 prompt 是否把 format_instructions 注进去了（打印模板渲染结果，别靠猜）；方向二，模型侧是否因为 temperature 高/长输出截断（finish_reason=length 导致 JSON 断尾）；方向三，重试是否把"错误信息"回传给了模型（只重试不喂错误，模型大概率再犯同样的错）；方向四，兼容服务是否支持 json 模式（对照 ch24 核实清单）。

## 38.10 自测检查表

- 我能默写四类消息对象与 role 的映射，并解释消息对象比 dict 强在哪里（类型/结构化 tool_calls/流式聚合）。
- 我能写出 ChatOpenAI 的常用构造参数，说出无 Key 时的真实报错形态。
- 我能说出字段名与构造参数的两处别名错位（request_timeout↔timeout、openai_api_key↔api_key）。
- 我能用 ChatPromptTemplate 声明模板，解释 input_variables 与 optional 占位。
- 我能对比 `with_structured_output`（服务端约束）与 PydanticOutputParser（提示词约束）的适用条件与失败语义。
- 我能解释 Fake 模型的两种消费语义，并据此选择测试脚本模型。
- 我能说出 Fake 测什么（接线）、不测什么（模型智力与效果）。

## 38.11 面试追问

**[模拟题] 1：with_structured_output 的三种 method 有什么区别？**
考查点：约束机制。合格回答：json_schema 用服务端 schema 约束解码（最强，默认，需服务端支持）；function_calling 复用工具调用协议让模型"填参数"（兼容面广，但本质是函数签名约束）；json_mode 只保证输出是合法 JSON、不保证符合 schema（最弱，必须配自校验）。任何 method 都要配 Pydantic 校验与重试兜底。

**[模拟题] 2：为什么 LangChain 要把消息做成对象而不是保留 dict？这层抽象的成本是什么？**
考查点：抽象评估。合格回答：收益是类型消灭 role 字符串错误、tool_calls 结构化、流式 chunk 可聚合、框架统一序列化；成本是多一层对象模型（序列化/调试时多一个心智环节）、以及与裸 SDK 字段演进存在时间差（新字段要等框架版本）。

**[模拟题] 3：你们的 CI 没有 API Key，怎么做 LangChain 代码的测试？**
考查点：工程实践。合格回答：Fake 模型（core 内置，测接线与控制流）+ 对 ChatOpenAI 只测构造与签名形状（不联网）+ 真实效果放打 Key 的预发环境跑抽检；这正是本书第七部分的全部示例做法（EX-38-02/03 实测输出为证）。

> 📌 本章待核实项：`with_structured_output` 的 `include_raw/strict` 参数在不同厂商实现上的行为差异未逐一实测（签名已核实）；json_schema 严格模式对各兼容服务的覆盖面以厂商文档为准。Fake 模型列表取自 1.6.12 的 `fake_chat_models` 模块实测（FakeChatModel/FakeListChatModel/FakeMessagesListChatModel/GenericFakeChatModel/ParrotFakeChatModel/SimpleChatModel），其他版本可能增删。

# 第 39 章 工具：@tool 装饰器、参数 schema 与错误处理

> **本章目标**：把"手写 JSON Schema + 手写分发"变成 `@tool` 一行声明，并掌握工具的错误处理策略。
> **前置知识**：ch10（装饰器）、ch16（Pydantic 与 JSON Schema）、ch24（工具调用闭环六步）。
> **学完你能做什么**：用 `@tool` 与 `args_schema` 生成模型可用的工具；用 ToolException 与 `handle_tool_error` 表达"预期内失败"；解释工具描述质量为什么是 API 设计。

## 39.1 真实问题引入：两份必须同步的"工具代码"

回到 EX-24-03 的闭环：同一个 `get_weather` 要写**两份代码**——一份 JSON Schema 声明（name/description/parameters，发给模型看），一份本地实现 + 手动分发（模型点名后你执行）。真实项目里工具一多（某运维平台 40 多个工具，合成案例），事故就来了：有人改了实现的参数忘了同步 schema，模型按旧 schema 填参，运行时 `TypeError`；更隐蔽的是描述与实现脱节——schema 写"查询天气"，实现早就不支持海外城市，模型还在往里填"纽约"。

根因是**声明与实现是两个事实源**。`@tool` 装饰器把两者合成一份：函数签名即参数 schema（经 Pydantic），docstring 即描述，函数体即实现，名字即路由键。本章讲清它的机制、参数约束的升级写法（`args_schema` 自定义 Pydantic），以及最重要的：工具"预期内失败"该怎么表达。

## 39.2 一句话解释 + 生活类比 + 类比边界

**一句话解释**：`@tool` 把一个类型注解齐全的函数变成 `BaseTool`——自动生成参数 JSON Schema、自动提取描述、自动按名路由；`ToolException` 表达"模型能理解并据此调整的失败"，`handle_tool_error` 决定失败变成异常还是错误文案。

**生活类比**：Spring 里你用 `@Bean` / `@RequestMapping` 把一个 Java 方法暴露成服务，框架负责参数绑定与路由；`@tool` 做的是同一件事，只是"调用方"从 HTTP 客户端换成了大模型——框架把函数签名翻译成 JSON Schema 放进请求，把模型的调用意图翻译回函数执行。

> 💡 类比边界：
> 1. Spring MVC 的调用方是**确定性代码**（编译期类型安全的代理接口），而模型的调用是**概率行为**：参数可能缺失、幻觉出枚举外的值、甚至点名不存在的工具——所以 `args_schema` 的校验和错误文案是生产必备，Spring 参数绑定失败顶多 400，这里失败会污染模型的下一步决策；
> 2. `@Bean` 暴露的是进程内服务，`@tool` 暴露的是**能力描述**：模型看到的是 schema 文本（EX-39-03 的"工具菜单"），它从不 import 你的代码——工具的权限校验仍发生在你的函数体里，模型说调 ≠ 授权（ch24 红线不变）；
> 3. docstring 即 prompt：描述写得含糊，模型就会含糊地调用——工具描述是 API 文档 + 提示词的双重身份。

## 39.3 正式原理与准确术语

**BaseTool 与 StructuredTool**：`@tool` 返回 `StructuredTool`（已实测），核心字段（`model_fields` 实测）：`name`（函数名）、`description`（docstring 首段）、`args_schema`（Pydantic 模型，自动生成或显式指定）、`return_direct`、`handle_tool_error`、`handle_validation_error`、`response_format`（`content` 或 `content_and_artifact`）。工具本身是 Runnable：`tool.invoke({...})`。

**@tool 的参数**（签名实测）：`name_or_callable`、`description`、`return_direct=False`、`args_schema`（可传自定义 Pydantic 模型）、`infer_schema=True`、`response_format='content'`、`parse_docstring=False`、`error_on_invalid_docstring=True`、`extras`。**注意 `handle_tool_error` 不是装饰器参数**（实测 `TypeError: tool() got an unexpected keyword argument`），它是工具实例的属性，用赋值设置（EX-39-02 实测三种策略）。

**ToolException**：langchain_core.tools 里表达"预期内业务失败"的异常类型。三种处理策略（全部实测）：① `handle_tool_error=None`（默认）→ 异常直接抛给调用方；② 设为字符串 → 异常被吞，`invoke` 返回该字符串；③ 设为函数 → 函数收到异常对象，返回给模型的提示文本。同类：`handle_validation_error` 处理**参数校验失败**（模型填了枚举外的值等）。

**工具渲染**：`render_text_description([tools])` / `render_text_description_and_args([tools])` 把工具列表渲染成"模型视角的菜单"文本——调试描述质量的直接手段。

**Java 对照**：`args_schema` ≈ 用 Bean Validation 注解声明的 DTO（描述进 schema 给"调用方"看）；`ToolException` + `handle_tool_error` ≈ 自定义业务异常 + 统一异常处理器（`@ControllerAdvice`）——区别是"异常处理器"的输出对象是模型，文案要按"模型读得懂"来写。

## 39.4 最小完整示例：从 @tool 到 Agent 内的错误恢复

**EX-39-01 | 示例代码/ch39_lc_构建工具/ex_39_01_tool_decorator.py（完整可运行）**

```python
# EX-39-01 | @tool 装饰器：函数变工具，schema 自动生成 | 运行: python3 示例代码/ch39_lc_构建工具/ex_39_01_tool_decorator.py
"""完整可运行（离线）：@tool 把普通函数变成 BaseTool——docstring 变描述、类型注解变
参数 schema；对照第四部分裸 SDK 里"手写 JSON Schema + 手写执行分发"两份代码。
"""
from __future__ import annotations

from langchain_core.tools import tool, render_text_description


@tool
def get_weather(city: str) -> dict:
    """查询指定城市当日天气。"""
    db = {"北京": {"weather": "晴", "temp": 26}, "上海": {"weather": "小雨", "temp": 22}}
    if city not in db:
        raise ValueError(f"暂不支持城市：{city}")
    return {"city": city, **db[city]}


def main() -> None:
    print("[1] @tool 生成的 BaseTool 元数据（自动提取，零手写）：")
    print(f"    name        = {get_weather.name!r}   ← 函数名")
    print(f"    description = {get_weather.description!r}   ← docstring 第一句")
    print(f"    类型        = {type(get_weather).__name__}（StructuredTool）")
    print(f"    args_schema 生成 JSON Schema properties：")
    props = get_weather.args_schema.model_json_schema()["properties"]
    for k, v in props.items():
        print(f"      {k}: {v}")
    print(f"    required = {get_weather.args_schema.model_json_schema().get('required')}")

    print("\n[2] 工具就是 Runnable：invoke 传 dict，返回值即函数返回值：")
    result = get_weather.invoke({"city": "北京"})
    print(f"    invoke({{'city': '北京'}}) → {result}")
    print(f"    直接函数调用也行（绕过 schema，仅调试用）：{get_weather.func('上海')}")

    print("\n[3] 发给模型看的'工具清单'长什么样（render_text_description）：")
    print("    " + render_text_description([get_weather]))

    print("\n[4] 对照裸 SDK（EX-24-03）：同一工具要写两份代码——")
    print("    ① JSON Schema 声明（手写 name/description/parameters）")
    print("    ② 本地函数实现 + if/elif 分发（模型点 name，你手动路由）")
    print("    LangChain 用 @tool 把两份合成一份：schema 自动生成，name 自动路由。")


if __name__ == "__main__":
    main()
```

```text
# 真实运行输出（离线）
[1] @tool 生成的 BaseTool 元数据（自动提取，零手写）：
    name        = 'get_weather'   ← 函数名
    description = '查询指定城市当日天气。'   ← docstring 第一句
    类型        = StructuredTool（StructuredTool）
    args_schema 生成 JSON Schema properties：
      city: {'title': 'City', 'type': 'string'}
    required = ['city']

[2] 工具就是 Runnable：invoke 传 dict，返回值即函数返回值：
    invoke({'city': '北京'}) → {'city': '北京', 'weather': '晴', 'temp': 26}
    直接函数调用也行（绕过 schema，仅调试用）：{'city': '上海', 'weather': '小雨', 'temp': 22}

[3] 发给模型看的'工具清单'长什么样（render_text_description）：
    get_weather(city: 'str') -> 'dict' - 查询指定城市当日天气。

[4] 对照裸 SDK（EX-24-03）：同一工具要写两份代码——
    ① JSON Schema 声明（手写 name/description/parameters）
    ② 本地函数实现 + if/elif 分发（模型点 name，你手动路由）
    LangChain 用 @tool 把两份合成一份：schema 自动生成，name 自动路由。
```

**EX-39-02 | 示例代码/ch39_lc_构建工具/ex_39_02_args_schema_error.py（完整可运行）**

```python
# EX-39-02 | args_schema 自定义 Pydantic 与 ToolException 三种错误策略 | 运行: python3 示例代码/ch39_lc_构建工具/ex_39_02_args_schema_error.py
"""完整可运行（离线）：
[1] args_schema 挂自定义 Pydantic 模型：字段描述进 schema、默认值、枚举约束；
[2] ToolException：工具"预期内失败"的表达方式，三种 handle_tool_error 策略实测；
[3] 对照裸 SDK：EX-24-03 里 try/except 转错误 JSON 的手写样板。
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from langchain_core.tools import ToolException, tool


class WeatherArgs(BaseModel):
    """get_weather 的参数模型（描述会写进 JSON Schema 给模型看）。"""

    city: str = Field(description="城市名，如 北京")
    unit: Literal["celsius", "fahrenheit"] = Field(default="celsius", description="温度单位")


@tool(args_schema=WeatherArgs)
def get_weather(city: str, unit: str = "celsius") -> dict:
    """查询指定城市当日天气。"""
    if city == "火星":
        raise ToolException("暂不支持城市：火星（数据库里没有该城市的观测站）")
    return {"city": city, "temp_c": 26, "unit": unit}


def main() -> None:
    print("[1] args_schema 生效：schema 来自 Pydantic 模型（含枚举与默认值）：")
    schema = get_weather.args_schema.model_json_schema()
    print(f"    properties = {schema['properties']}")
    print(f"    required   = {schema.get('required')}（有默认值的 unit 不必填）")
    print(f"    invoke 合法参数 → {get_weather.invoke({'city': '北京'})}")

    print("\n[2] 策略一：handle_tool_error 默认 None → ToolException 直接抛出（调用方处理）：")
    try:
        get_weather.invoke({"city": "火星"})
    except ToolException as e:
        print(f"    捕获 ToolException: {e}")

    print("\n[3] 策略二：handle_tool_error = 定制文案（str）→ 异常被吞，invoke 返回字符串：")
    get_weather.handle_tool_error = "工具内部出错，请稍后重试或联系值班工程师。"
    r = get_weather.invoke({"city": "火星"})
    print(f"    invoke → {r!r}（type = {type(r).__name__}）")

    print("\n[4] 策略三：handle_tool_error = Callable → 函数拿到异常，返回给模型的提示：")
    def to_model_msg(e: Exception) -> str:
        return f"工具执行失败：{e}。建议：换个国内城市名再试一次。"
    get_weather.handle_tool_error = to_model_msg
    print(f"    invoke → {get_weather.invoke({'city': '火星'})!r}")

    print("\n[5] 对照裸 SDK：EX-24-03 的错误样板（真实代码摘录）：")
    print('    try:')
    print('        result = get_weather(**tc.arguments)')
    print('        tool_content = json.dumps(result, ensure_ascii=False)')
    print('    except Exception as e:')
    print('        tool_content = json.dumps({"error": str(e)}, ensure_ascii=False)')
    print("    LangChain 把这段 if/else 收敛成一个 handle_tool_error 属性；")
    print("    关键不变量相同：错误要变成'模型读得懂的话'回传，而不是让整个请求 500。")

    print("\n[6] 非法参数（schema 校验失败）默认抛 ValidationError，可设 handle_validation_error：")
    try:
        get_weather.invoke({"city": "北京", "unit": "开尔文"})  # 枚举外取值
    except Exception as e:
        print(f"    默认：{type(e).__name__}")
    get_weather.handle_validation_error = "参数不合法：unit 只能是 celsius 或 fahrenheit"
    print(f"    设置 handle_validation_error 后 → {get_weather.invoke({'city': '北京', 'unit': '开尔文'})!r}")


if __name__ == "__main__":
    main()
```

```text
# 真实运行输出（离线）
[1] args_schema 生效：schema 来自 Pydantic 模型（含枚举与默认值）：
    properties = {'city': {'description': '城市名，如 北京', 'title': 'City', 'type': 'string'}, 'unit': {'default': 'celsius', 'description': '温度单位', 'enum': ['celsius', 'fahrenheit'], 'title': 'Unit', 'type': 'string'}}
    required   = ['city']（有默认值的 unit 不必填）
    invoke 合法参数 → {'city': '北京', 'temp_c': 26, 'unit': 'celsius'}

[2] 策略一：handle_tool_error 默认 None → ToolException 直接抛出（调用方处理）：
    捕获 ToolException: 暂不支持城市：火星（数据库里没有该城市的观测站）

[3] 策略二：handle_tool_error = 定制文案（str）→ 异常被吞，invoke 返回字符串：
    invoke → '工具内部出错，请稍后重试或联系值班工程师。'（type = str）

[4] 策略三：handle_tool_error = Callable → 函数拿到异常，返回给模型的提示：
    invoke → '工具执行失败：暂不支持城市：火星（数据库里没有该城市的观测站）。建议：换个国内城市名再试一次。'

[5] 对照裸 SDK：EX-24-03 的错误样板（真实代码摘录）：
    try:
        result = get_weather(**tc.arguments)
        tool_content = json.dumps(result, ensure_ascii=False)
    except Exception as e:
        tool_content = json.dumps({"error": str(e)}, ensure_ascii=False)
    LangChain 把这段 if/else 收敛成一个 handle_tool_error 属性；
    关键不变量相同：错误要变成'模型读得懂的话'回传，而不是让整个请求 500。

[6] 非法参数（schema 校验失败）默认抛 ValidationError，可设 handle_validation_error：
    默认：ValidationError
    设置 handle_validation_error 后 → '参数不合法：unit 只能是 celsius 或 fahrenheit'
```

**EX-39-03 | 示例代码/ch39_lc_构建工具/ex_39_03_tool_render.py（完整可运行）**

```python
# EX-39-03 | 工具的完整生命周期：schema→渲染→调用→错误→Agent 中的恢复 | 运行: python3 示例代码/ch39_lc_构建工具/ex_39_03_tool_render.py
"""完整可运行（离线）：
[1] 多工具 + render_text_description_and_args：模型菜单的真实形态；
[2] @tool 的 return_direct 选项；
[3] 在 create_agent 循环里验证：工具抛 ToolException 后，handle_tool_error 让循环继续
    （错误变成 ToolMessage 回传模型）——这是 39 章与 42 章的接缝。
"""
from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Any

from langchain.agents import create_agent
from langchain_core.language_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import ToolException, render_text_description_and_args, tool


class FakeToolChatModel(GenericFakeChatModel):
    """GenericFakeChatModel + bind_tools（42.3 详解为什么需要这个子类）。"""

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> Any:
        return self


@tool
def query_order(order_id: str) -> dict:
    """按订单号查询订单状态。"""
    return {"order_id": order_id, "status": "已签收"}


@tool(return_direct=True)  # return_direct=True：结果不经模型复述，直接返回给调用方
def risk_flag(user_id: str) -> bool:
    """标记高危用户（演示 return_direct：结果直接透出）。"""
    return user_id.startswith("R")


@tool
def divide(a: int, b: int) -> float:
    """两数相除。"""
    if b == 0:
        raise ToolException("除数不能为 0，请换一个除数")
    return a / b


def main() -> None:
    print("[1] render_text_description_and_args（模型能看到的'工具菜单'）：")
    print(render_text_description_and_args([query_order, risk_flag, divide]))

    print("\n[2] return_direct 语义（属性核实）：")
    print(f"    query_order.return_direct = {query_order.return_direct}")
    print(f"    risk_flag.return_direct   = {risk_flag.return_direct}")
    print("    → True 的工具结果会原样成为最终答案（适合计算器/查分类等'答案即结果'场景）")

    print("\n[3] create_agent 循环中的工具错误恢复（真实运行，Fake 脚本驱动）：")
    divide.handle_tool_error = "计算失败：除数不能为 0。请换一个非零除数重试，或直接告知用户无法计算。"
    script = iter([
        AIMessage(content="", tool_calls=[
            {"id": "c1", "name": "divide", "args": {"a": 1, "b": 0}, "type": "tool_call"}]),
        AIMessage(content="1 除以 0 在数学上没有定义，工具也返回了同样的错误提示。"),
    ])
    agent = create_agent(model=FakeToolChatModel(messages=script),
                         tools=[query_order, risk_flag, divide], system_prompt="计算助手")
    result = agent.invoke({"messages": [HumanMessage(content="帮我算 1 除以 0")]})
    for m in result["messages"]:
        print(f"    {type(m).__name__:<12} {str(m.content)[:60]}")
    print("    → 第 3 条 ToolMessage 就是 handle_tool_error 的文案：异常没炸掉循环，")
    print("      而是变成'模型读得懂的话'，模型基于它给出最终回答。这就是框架替你做的错误恢复。")


if __name__ == "__main__":
    main()
```

```text
# 真实运行输出（离线，Fake 脚本驱动）
[1] render_text_description_and_args（模型能看到的'工具菜单'）：
query_order(order_id: 'str') -> 'dict' - 按订单号查询订单状态。, args: {'order_id': {'title': 'Order Id', 'type': 'string'}}
risk_flag(user_id: 'str') -> 'bool' - 标记高危用户（演示 return_direct：结果直接透出）。, args: {'user_id': {'title': 'User Id', 'type': 'string'}}
divide(a: 'int', b: 'int') -> 'float' - 两数相除。, args: {'a': {'title': 'A', 'type': 'integer'}, 'b': {'title': 'B', 'type': 'integer'}}

[2] return_direct 语义（属性核实）：
    query_order.return_direct = False
    risk_flag.return_direct   = True
    → True 的工具结果会原样成为最终答案（适合计算器/查分类等'答案即结果'场景）

[3] create_agent 循环中的工具错误恢复（真实运行，Fake 脚本驱动）：
    HumanMessage 帮我算 1 除以 0
    AIMessage    
    ToolMessage  计算失败：除数不能为 0。请换一个非零除数重试，或直接告知用户无法计算。
    AIMessage    1 除以 0 在数学上没有定义，工具也返回了同样的错误提示。
    → 第 3 条 ToolMessage 就是 handle_tool_error 的文案：异常没炸掉循环，
      而是变成'模型读得懂的话'，模型基于它给出最终回答。这就是框架替你做的错误恢复。
```

## 39.5 逐段解释：schema、描述与错误的三层设计

**（1）自动 schema 的边界**。`@tool` 从类型注解生成 schema（EX-39-01：`city: string`，required=[city]），基本类型够用；需要枚举、默认值、嵌套结构时挂 `args_schema=WeatherArgs`（EX-39-02 [1]：`enum`、`default` 全部进入 schema）。原则：**schema 面向模型**——`Field(description=...)` 的每句话都是模型读的"参数说明"，像写 API 文档一样写它。一个只有 `title` 的参数和一句"城市名，如 北京"的参数，模型填对率天差地别。

**（2）描述质量是提示词工程的一部分**。EX-39-03 [1] 打印的就是模型菜单的原文——`query_order(order_id: 'str') -> 'dict' - 按订单号查询订单状态。`。模型决定调不调、怎么调，依据全在这一行。工程约定（ch54 展开）：工具名用动词短语、描述写清"做什么+什么时候用+不适用什么"、参数描述给例子。`render_text_description` 是你自检"模型视角"的镜子——评审工具时先看这行渲染结果。

**（3）错误策略决策表**（EX-39-02 实测 + EX-39-03 Agent 内实测）：

| 场景 | 配置 | 行为 |
|---|---|---|
| 失败应中断调用方 | 默认（None） | ToolException 向上抛，invoke 方处理 |
| 失败应回传模型继续 | `handle_tool_error = str` | 异常被吞，invoke 返回定制文案 |
| 需要按异常内容生成提示 | `handle_tool_error = callable` | 函数加工异常 → 返回提示文本 |
| 参数不合法（模型填错） | `handle_validation_error` | 同上三种形态，针对 ValidationError |
| 答案即结果的工具 | `@tool(return_direct=True)` | 结果直接作为最终答案，不再过模型 |

**（4）Agent 内的恢复链路是本章的落点**。EX-39-03 [3] 的消息序列证明：`handle_tool_error` 的文案变成 `ToolMessage` 回到模型，循环继续、模型给出最终回答。反面的重要性同样要记住——**没有配置 `handle_tool_error` 时，工具在 create_agent 里抛异常会让整次运行失败**（实测：langgraph 的 ToolNode 默认对未知异常原样抛出，整个 `agent.invoke` 崩溃）。所以"预期内失败用 ToolException + handle_tool_error，预期外异常让它炸出来报警"是清晰的两分法：前者是模型能理解的业务反馈，后者是应该触发监控的 bug。

**（5）与裸 SDK 对照的收束**。EX-24-03 的六步样板中，②⑤⑥（解析、回传、循环）在 ch42 展开；①④（声明、分发）被 `@tool` 收编。你保留的责任：函数体里的**权限校验、幂等、超时**（模型无权绕过——它是"点菜的人"，不是"进厨房的人"）。

## 39.6 安装 / 文件位置 / 运行命令

```bash
pip install -r requirements.txt   # langchain==1.4.6 / langchain-core==1.6.12

python3 示例代码/ch39_lc_构建工具/ex_39_01_tool_decorator.py
python3 示例代码/ch39_lc_构建工具/ex_39_02_args_schema_error.py
python3 示例代码/ch39_lc_构建工具/ex_39_03_tool_render.py

python3 -m pytest 测试/test_ch39.py -q
```

## 39.7 常见错误与排查

**错 1：`TypeError: tool() got an unexpected keyword argument 'handle_tool_error'`。**
真实报错（写作过程实测踩中）。原因：`handle_tool_error` 是 BaseTool 的实例属性，不是 `@tool` 装饰器参数。修复：`my_tool.handle_tool_error = "..."`（实例属性赋值，EX-39-02 实测有效）；批量设置用函数封装"声明 + 配置"两步。

**错 2：改了函数签名，模型还在按旧参数调用。**
原因：模型看到的 schema 在 `bind_tools` 时才固化（ch42），而某些调用方缓存了工具声明；更常见的是多进程部署中部分实例还在跑旧版本。修复：工具声明纳入版本管理，变更工具签名视同 API 变更走评审；部署后用 `render_text_description` 抽查线上实例的菜单一致性。

**错 3：`ValidationError`：模型填了枚举外的 `unit="kelvin"`。**
原因：`args_schema` 的 Literal 枚举校验生效（好事），但默认行为是把异常抛进循环（没有 handle_validation_error 时会让 run 失败）。修复：设 `handle_validation_error` 为模型可读文案（"unit 只能是 celsius 或 fahrenheit"），或信任模型自纠 + 步数护栏兜底（ch42）。

**错 4：docstring 写了多段，`description` 只剩第一句？**
原因：`@tool` 默认取 docstring 首段作为描述；`parse_docstring=False` 时不解析 Google 风格参数文档。修复：把关键信息压缩进首段；或 `@tool(parse_docstring=True)` 按 Google 风格解析 Args 段（参数级描述进 schema）；改完用 `render_text_description_and_args` 验证。

## 39.8 企业场景中的使用方式

在 Spring Boot 生态里，工具往往对应**内部服务调用**。生产做法是给每个 `@tool` 函数加三层横切：鉴权（当前租户能否调这个工具——在函数体第一行校验，绝不信任模型）、审计（工具名+参数+结果摘要+trace_id 落结构化日志，ch60）、超时与幂等（HTTP 工具统一走 ch15 的超时三件套；写操作必须幂等键）。工具注册表（名字→端点→权限等级→SLA）作为配置资产集中管理——`@tool` 解决"声明与实现同步"，注册表解决"工具组合的治理"，两层缺一不可（ch54 展开治理细节）。

## 39.9 练习

**基础 1**：说出 `@tool` 从函数自动提取的三样东西，以及必须手工补充的一样。

**基础 2**：`handle_tool_error` 三种取值各自的行为是什么？哪种对应"让 Agent 循环继续"？

**代码 1**：给 EX-39-02 的 `WeatherArgs` 增加一个 `date: str` 字段（描述"YYYY-MM-DD，默认今天"），运行 EX-39-01 风格的 schema 打印验证描述进入 JSON Schema，并给 `测试/test_ch39.py` 补一个断言 `date` 在 properties 里的测试。

**代码 2**：写一个 `transfer_money(amount: float)` 工具：amount > 10000 时抛 ToolException("金额超限，需要人工审批")，并设置 handle_tool_error 为含"建议"的文案；用 pytest 验证 invoke 返回文案而非抛异常。

**调试题**：线上发现模型总是给 `divide` 传 `a="一"`（字符串"一"而不是数字）。列出至少三个改进方向。

### 参考答案

**基础 1**：name（函数名）、description（docstring 首段）、args_schema（类型注解生成）；必须手工补充/精修的是**描述文案**（含参数 description），必要时显式 `args_schema`。

**基础 2**：None→异常向上抛（调用方处理）；str→返回固定文案；callable→按异常生成文案。后两种（str/callable）让失败变成 ToolMessage、循环继续。

**代码 1**（要点）：`date: str = Field(default="", description="查询日期，YYYY-MM-DD，空为今天")`；schema properties 中出现 `date` 且 description 同步；测试断言 `"date" in tool.args_schema.model_json_schema()["properties"]`。

**代码 2**（要点）：
```python
@tool
def transfer_money(amount: float) -> str:
    """向指定账户转账（演示超限拦截）。"""
    if amount > 10_000:
        raise ToolException("金额超限：单笔上限 10000 元")
    return f"已转账 {amount} 元"

transfer_money.handle_tool_error = "转账失败：{error}。建议：拆分金额或转人工审批。".format
# 更清晰的可调用写法：
transfer_money.handle_tool_error = lambda e: f"转账失败：{e}。建议：拆分金额或转人工审批。"
```
测试：`assert "人工审批" in transfer_money.invoke({"amount": 20000})`。

**调试题**：① 参数 description 加格式示例（"整数，如 6"）；② schema 用 `int` 并在描述里强调"阿拉伯数字"；③ 设 handle_validation_error，把"参数 a 应为整数"回传模型自纠；④ 上步数护栏防自纠失败时的死循环（ch42）。根本思路：让"喂给模型的信息"包含模型纠正自己所需的一切。

## 39.10 自测检查表

- 我能用 `@tool` 写一个工具并解释 name/description/args_schema 的来源。
- 我能用自定义 Pydantic `args_schema` 表达枚举、默认值与参数描述，并解释为什么描述面向模型。
- 我能说出 `handle_tool_error` 三种策略的行为差异与适用场景。
- 我能解释 `handle_validation_error` 与 `handle_tool_error` 分别拦截什么。
- 我能说出工具在 create_agent 中未配错误处理时的默认行为（炸出整个 run）。
- 我能用 `render_text_description` 自检"模型视角的工具菜单"。
- 我能解释"模型点名工具 ≠ 执行授权"在代码层的落点（函数体内的权限校验）。

## 39.11 面试追问

**[模拟题] 1：@tool 的 schema 自动生成是怎么工作的？什么时候必须放弃自动、手写 args_schema？**
考查点：机制理解。合格回答：装饰器把函数签名交给 Pydantic（create_schema_from_function 思路）生成模型，类型注解映射 JSON Schema 类型，docstring 变描述；需要枚举、嵌套模型、默认值、字段级描述时升级为自定义 args_schema——注意自动生成的 schema 也要过模型这一关，描述质量是自动生成的盲区。

**[模拟题] 2：工具执行失败的"正确姿势"是什么？为什么不能只靠 try/except 包住整个 Agent？**
考查点：错误语义分层。合格回答：预期内失败（业务规则）用 ToolException+handle_tool_error 变成模型可读反馈，模型可自纠或向用户澄清；预期外异常（bug、基础设施故障）应该炸出来触发监控告警。外层 try/except 会把两类失败混在一起，既剥夺了模型的自纠机会，也吞掉了告警信号。

**[模拟题] 3：如果把内部 REST API 直接批量包成工具给模型，会有什么风险？**
考查点：工具治理。合格回答：攻击面放大（提示注入诱导模型调高危接口，ch28/ch58）、参数校验缺位、审计缺失、无幂等保障的写操作被重复调用。对策：白名单筛选、只读优先、权限分层、写操作加审批（LangGraph interrupt，第八部分）、每个工具独立超时与审计日志。

> 📌 本章待核实项：`parse_docstring=True` 的 Google 风格解析对中文 docstring 的兼容性未实测；`response_format='content_and_artifact'`（工具返回内容+制品分离）在 create_agent 内的完整行为未实测，需要时以官方文档与实测为准。

# 第 40 章 LCEL 与 Runnable：管道语法、执行协议与调试

> **本章目标**：理解 `|` 管道的本质（Runnable 协议），掌握 batch/stream/async 三套"免费"执行入口、异常传播语义与配置贯穿，学会两个调试入口。
> **前置知识**：ch08（异常链）、ch13（asyncio）、ch09（生成器——stream 的语言基础）。
> **学完你能做什么**：把"裸 SDK 手写组装函数"升级为可检视、可流式、可并发的 LCEL 管道；说出每种执行入口的语义；管道出问题时知道从哪里下手。

## 40.1 真实问题引入：同一个 pipeline 写了三遍

老王的团队（合成案例）在裸 SDK 上做了一个"分类→生成→格式化"流水线。第一版只有同步调用；上线后运营要批量跑历史数据，团队给每个函数补了 `for` 循环版；再后来前端要打字机效果，又给每个函数补了"逐段 yield"版。三份代码干一件事，修 bug 修三遍。更难受的是新同事接手时问："这些函数的输入输出类型是什么？"——答案是"看代码猜"。

LCEL（LangChain Expression Language）针对的正是这个问题：**把"组合"从函数调用升级为对象协议**。每个组件都实现 `invoke/batch/stream/ainvoke/astream`（加上配置与回调约定），组合起来的链自动继承全部入口——三份手写代码变成一个 `|` 表达式，输入输出类型成为管道的显式结构。

## 40.2 一句话解释 + 生活类比 + 类比边界

**一句话解释**：一切组件（prompt/模型/解析器/普通函数/Retriever）都是 `Runnable`，`|` 是 `Runnable.__or__` 运算符——`prompt | model | parser` 产生一个 `RunnableSequence`，它本身还是 Runnable，自动拥有每个成员的全部执行协议。

**生活类比**：Java 的 `Stream.of(x).map(a).map(b)` 或者 Servlet Filter 责任链——声明式地把处理步骤串起来。区别在于：Stream API 的管道只有"顺序执行"一种消费方式，而 Runnable 管道的每一段都自带**同步/批量/流式/异步**四种执行方式与**配置/回调**两个横切通道——它是给"一次调用可能要三五种消费姿势"的 LLM 场景设计的协议。

> 💡 类比边界：
> 1. Java Stream 的中间操作是**惰性求值**，终结操作触发执行；RunnableSequence 是**即时组合、按需执行**——`prompt | model` 构造时就分配好了节点结构，`invoke` 才真正跑；
> 2. 责任链（Filter 链）的每个节点可以决定"是否继续传递"，Runnable 序列是**线性传递**（上一个的输出就是下一个的输入），分支/条件要用 `RunnableParallel`/`RunnableBranch` 显式表达；
> 3. 类型安全靠**运行时约定**：把 `str` 管道接到吃 `dict` 的组件上，编译器不拦你，运行时才炸（41.5 的 `itemgetter` 教训是真实案例）。

## 40.3 正式原理与准确术语

**Runnable 协议**：`langchain_core.runnables.Runnable` 定义的统一接口——同步 `invoke/batch/stream`、异步 `ainvoke/abatch/astream`、事件 `astream_events`、配置 `with_config/with_retry/with_fallbacks`。`RunnableSequence`（`|` 的产物）、`RunnableLambda`（包装普通函数）、`RunnablePassthrough`（透传，`.assign(k=v)` 旁路注入新键）、`RunnableParallel`（同一输入喂多分支、按 key 合并）都是它的实现。

**RunnableConfig**：贯穿管道的配置对象——实测字段包括 `callbacks / configurable / metadata / tags / recursion_limit`。`chain.invoke(x, config={"tags": [...], "run_name": ...})` 从入口一路传到每个节点（EX-40-02 [3] 实测），是 trace_id、租户标签等横切信息的标准通道（对照 ch17 的中间件思想）。

**异常传播语义**（实测）：链中任一节点抛出的异常**保持原类型原信息**向上冒泡，不被框架包装——`ValueError` 进 `ValueError` 出（EX-40-03 [3]）；流式同理，异常在消费者迭代时抛出。你的 `try/except` 业务语义与裸写完全一致。

**调试手段**（实测）：`chain.get_prompts()` 把链里所有提示词模板捞出来；`chain.get_graph()` 拿到节点/边结构（`print_ascii()` 需要 grandalf 包，本书沙箱未装，实测 ImportError——用节点表替代）；`astream_events(version='v2')` 逐事件观察执行过程（`on_chain_start / on_prompt_start / on_chat_model_start / on_chat_model_stream / on_parser_start ...`）。

**Java 对照**：`Runnable` ≈ 一个只有 `Function` 语义但自带执行策略与配置通道的接口；`RunnableSequence` ≈ `Function.andThen()` 链；`RunnableParallel` ≈ `CompletableFuture.allOf`（但分支共享同一输入）；`RunnableConfig` ≈ `@Async` 场景里用 ThreadLocal 传 trace_id 的正规化版本。

## 40.4 最小完整示例：管道、并行与协议

**EX-40-01 | 示例代码/ch40_lcel/ex_40_01_pipe_chain.py（完整可运行）**

```python
# EX-40-01 | LCEL 管道：prompt | model | parser 的本质是 RunnableSequence | 运行: python3 示例代码/ch40_lcel/ex_40_01_pipe_chain.py
"""完整可运行（离线）：把"裸 SDK 手写组装函数"升级成 LCEL 管道，对比两种写法在
类型、组合、调试上的差异；get_graph() / get_prompts() 两个调试入口实测。
"""
from __future__ import annotations

from langchain_core.language_models import FakeListChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableLambda, RunnableSequence


def bare_compose(question: str) -> str:
    """裸 SDK 时代的组装：一个函数包住所有步骤（对比用，不调用模型）。"""
    system = "你是电商客服，用简洁中文回答。"          # 步骤 1：手拼 prompt
    fake_reply = f"（预置回答）关于「{question}」……"   # 步骤 2：调用模型（此处为桩）
    return f"{system}{fake_reply}"                     # 步骤 3：手工拼接输出


def main() -> None:
    prompt = ChatPromptTemplate.from_messages([
        ("system", "你是{role}，用简洁中文回答。"),
        ("human", "{question}"),
    ])
    model = FakeListChatModel(responses=["（Fake）7 天内可无理由退货。"])
    chain: Runnable = prompt | model | StrOutputParser()

    print("[1] | 管道的本质（类型核实）：")
    print(f"    type(prompt | model)             = {type(prompt | model).__name__}")
    print(f"    type(prompt | model | parser)    = {type(chain).__name__}")
    print(f"    isinstance(chain, Runnable)      = {isinstance(chain, Runnable)}")
    print("    → | 不是魔法运算符，是 Runnable.__or__：链本身也是 Runnable，可继续 |")

    print("\n[2] 同一任务两种写法（输出等价）：")
    print(f"    裸组装：{bare_compose('退货政策')!r}")
    print(f"    LCEL  ：{chain.invoke({'role': '电商客服', 'question': '退货政策'})!r}")

    print("\n[3] LCEL 换来的三件事（裸函数没有）：")
    print("    a) 统一执行协议：invoke/batch/stream/ainvoke 全链自动获得（EX-40-03）")
    print("    b) 统一配置协议：RunnableConfig（tags/metadata/callbacks）贯穿每个节点（EX-40-02）")
    print("    c) 可检视：链是数据，能画出结构、取出 prompt 模板")

    print("\n[4] 调试入口一：get_prompts() 把链里所有 prompt 模板捞出来：")
    for p in chain.get_prompts():
        print(f"    {type(p).__name__}: messages 结构已还原（模板变量 {p.input_variables}）")

    print("\n[5] 调试入口二：get_graph() 拿到节点/边（print_ascii 需 grandalf，本书用节点表）：")
    g = chain.get_graph()
    for node_id, node in g.nodes.items():
        print(f"    节点 {type(node).__name__:<24} name={node.name}")

    print("\n[6] RunnableLambda 包普通函数，让它获得同样的协议：")
    upper = RunnableLambda(lambda s: s.upper())
    print(f"    upper.invoke('abc') = {upper.invoke('abc')!r}")
    print(f"    upper.batch(['a', 'b']) = {upper.batch(['a', 'b'])}")
    print(f"    复合：upper.pipe(RunnableLambda(len)).invoke('abc') = {upper.pipe(RunnableLambda(len)).invoke('abc')}")
    print("    → Java 对照：prompt | model | parser ≈ Stream.of(x).map(a).map(b) 的责任链，")
    print("      但每个环节都带统一的调用/流式/异步/配置协议（Stream API 没有这层约定）。")


if __name__ == "__main__":
    main()
```

```text
# 真实运行输出（离线）
[1] | 管道的本质（类型核实）：
    type(prompt | model)             = RunnableSequence
    type(prompt | model | parser)    = RunnableSequence
    isinstance(chain, Runnable)      = True
    → | 不是魔法运算符，是 Runnable.__or__：链本身也是 Runnable，可继续 |

[2] 同一任务两种写法（输出等价）：
    裸组装：'你是电商客服，用简洁中文回答。（预置回答）关于「退货政策」……'
    LCEL  ：'（Fake）7 天内可无理由退货。'

[3] LCEL 换来的三件事（裸函数没有）：
    a) 统一执行协议：invoke/batch/stream/ainvoke 全链自动获得（EX-40-03）
    b) 统一配置协议：RunnableConfig（tags/metadata/callbacks）贯穿每个节点（EX-40-02）
    c) 可检视：链是数据，能画出结构、取出 prompt 模板

[4] 调试入口一：get_prompts() 把链里所有 prompt 模板捞出来：
    ChatPromptTemplate: messages 结构已还原（模板变量 ['question', 'role']）

[5] 调试入口二：get_graph() 拿到节点/边（print_ascii 需 grandalf，本书用节点表）：
    节点 Node                     name=PromptInput
    节点 Node                     name=ChatPromptTemplate
    节点 Node                     name=FakeListChatModel
    节点 Node                     name=StrOutputParser
    节点 Node                     name=StrOutputParserOutput

[6] RunnableLambda 包普通函数，让它获得同样的协议：
    upper.invoke('abc') = 'ABC'
    upper.batch(['a', 'b']) = ['A', 'B']
    复合：upper.pipe(RunnableLambda(len)).invoke('abc') = 3
    → Java 对照：prompt | model | parser ≈ Stream.of(x).map(a).map(b) 的责任链，
      但每个环节都带统一的调用/流式/异步/配置协议（Stream API 没有这层约定）。
```

**EX-40-02 | 示例代码/ch40_lcel/ex_40_02_parallel_config.py（完整可运行）**

```python
# EX-40-02 | RunnablePassthrough.assign / RunnableParallel / RunnableConfig | 运行: python3 示例代码/ch40_lcel/ex_40_02_parallel_config.py
"""完整可运行（离线）：RAG 风格的"检索注入"管道（context 旁路注入 + 问题透传）、
并行分支（RunnableParallel 显式构造）、RunnableConfig 的 tags/metadata 贯穿。
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
```

```text
# 真实运行输出（离线）
[1] RunnablePassthrough.assign：往 dict 里'旁路注入'新键（RAG 标准姿势）：
    输入 {'question': '退货政策是什么？'}
    输出 {'question': '退货政策是什么？', 'context': '《退货政策》7 天内可无理由退货，运费由商家承担。'}
    → 原键原样透传（question 没丢），新键 context 是检索结果；
      裸写法需要手工 copy dict，assign 是声明式的。

[2] RunnableParallel：同一输入喂给多个分支，结果按 key 合并：
    invoke('你好') → {'answer': '回答分支收到：你好', 'length': 2}
    batch(['a', 'bc']) → [{'answer': '回答分支收到：a', 'length': 1}, {'answer': '回答分支收到：bc', 'length': 2}]
    → dict 走 | 时也会被自动包装成 RunnableParallel（本书显式写，意图更清楚）
    Java 对照 ≈ CompletableFuture.allOf(...) 聚合，但分支共享同一输入。

[3] RunnableConfig：tags/metadata 从 invoke 一路传到每个节点：
    结果：已处理 发票问题
    每个节点看到的 config.tags = [('unnamed', ['tenant:acme', 'env:prod'])]
    → trace_id/租户标签这类横切信息不再靠参数层层透传（对照 ch17 中间件思想）

[4] assign 的值也可以是完整链（检索注入 + 生成的雏形，EX-41-03 接上真实检索）：
    最终喂给模型的文本：
    背景资料：《退货政策》7 天内可无理由退货，运费由商家承担。
问题：退货政策是什么？
```

**EX-40-03 | 示例代码/ch40_lcel/ex_40_03_batch_stream_async.py（完整可运行）**

```python
# EX-40-03 | batch / stream / ainvoke / astream_events 与异常传播链 | 运行: python3 示例代码/ch40_lcel/ex_40_03_batch_stream_async.py
"""完整可运行（离线，asyncio 真实运行）：
[1] 一条链免费获得 batch/stream/ainvoke/astream（裸 SDK 要给每个入口手写包装）；
[2] 异常在链中的传播：原类型原样向上抛（不被框架吞掉或包一层）；
[3] astream_events：流式事件的"发动机舱"视图——ch42 的 agent 流式就是它的应用。
"""
from __future__ import annotations

import asyncio

from langchain_core.language_models import FakeListChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda


def build_chain(script: list[str]) -> RunnableLambda | object:
    """构造 prompt | model | parser 三段链（Fake 模型按 script 顺序消费）。"""
    prompt = ChatPromptTemplate.from_messages([("human", "{q}")])
    model = FakeListChatModel(responses=script)
    return prompt | model | StrOutputParser()


def main() -> None:
    chain = build_chain(["回答 A", "回答 B1", "回 答 C 按字流出", "回答 D"])

    print("[1] batch：并发跑多个输入（Fake 串行消费脚本，真实模型并发发请求）：")
    print(f"    {chain.batch([{'q': '问题一'}, {'q': '问题二'}])}")

    print("\n[2] stream：增量输出，parser 逐段生效：")
    print(f"    chunks = {[c for c in chain.stream({'q': '问题三'})]}")
    print("    → 裸 SDK 里你手写 'full += delta'（EX-23-03）；这里链内自动完成逐段传递")

    print("\n[3] 异常传播链（真实抛出）：链中任一节点抛异常，原类型原样冒泡：")
    def boom(_: dict) -> str:
        raise ValueError("下游业务异常：订单库连接超时")
    bad = RunnableLambda(boom) | RunnableLambda(lambda s: s.upper())
    try:
        bad.invoke({"q": "x"})
    except ValueError as e:
        print(f"    捕获到 {type(e).__name__}: {e}")
        print("    → 没有被包成框架异常：try/except 业务语义不变（对照 ch08 异常链）")
    # 流式中的异常同样在迭代处抛出
    def boom_stream(_: dict):
        yield "先吐一段"
        raise RuntimeError("流到一半炸了")
    streamy = RunnableLambda(boom_stream) | RunnableLambda(str.upper)
    try:
        for _ in streamy.stream({"q": "x"}):
            pass
    except RuntimeError as e:
        print(f"    流式同样：{type(e).__name__}: {e}（消费者在迭代时收到）")

    print("\n[4] ainvoke / astream_events（asyncio 真实运行）：")
    asyncio.run(async_demo(chain))
    print("\n[小结] LCEL 的价值公式：写一次管道 = 免费得到 batch/stream/async/config 四套协议；")
    print("       裸 SDK 每套都要手写循环（第四部分每个 EX 都在为此付费）。")


async def async_demo(chain) -> None:
    print(f"    ainvoke = {await chain.ainvoke({'q': '异步问题'})}")
    events: list[str] = []
    async for ev in chain.astream_events({"q": "事件流"}, version="v2"):
        events.append(ev["event"])
    print(f"    astream_events 前 6 个事件 = {events[:6]}")
    print(f"    共 {len(events)} 个事件：链的每一段（prompt/model/parser）的 start/end/stream")
    print("    都是独立事件 → 给 ch42 的 agent 流式与可观测性打底。")


if __name__ == "__main__":
    main()
```

```text
# 真实运行输出（离线，asyncio 真实运行）
[1] batch：并发跑多个输入（Fake 串行消费脚本，真实模型并发发请求）：
    ['回答 A', '回答 B1']

[2] stream：增量输出，parser 逐段生效：
    chunks = ['回', ' ', '答', ' ', 'C', ' ', '按', '字', '流', '出']
    → 裸 SDK 里你手写 'full += delta'（EX-23-03）；这里链内自动完成逐段传递

[3] 异常传播链（真实抛出）：链中任一节点抛异常，原类型原样冒泡：
    捕获到 ValueError: 下游业务异常：订单库连接超时
    → 没有被包成框架异常：try/except 业务语义不变（对照 ch08 异常链）
    流式同样：RuntimeError: 流到一半炸了（消费者在迭代时收到）

[4] ainvoke / astream_events（asyncio 真实运行）：
    ainvoke = 回答 D
    astream_events 前 6 个事件 = ['on_chain_start', 'on_prompt_start', 'on_prompt_end', 'on_chat_model_start', 'on_chat_model_stream', 'on_parser_start']
    共 20 个事件：链的每一段（prompt/model/parser）的 start/end/stream
    都是独立事件 → 给 ch42 的 agent 流式与可观测性打底。

[小结] LCEL 的价值公式：写一次管道 = 免费得到 batch/stream/async/config 四套协议；
       裸 SDK 每套都要手写循环（第四部分每个 EX 都在为此付费）。
```

## 40.5 逐段解释：协议、类型与调试

**（1）`|` 的本质与"链也是组件"**。EX-40-01 [1] 用 `type()` 证明了 `prompt | model` 产生 `RunnableSequence`，且它是 `Runnable` 的实例——所以链可以继续 `|`、可以被 `.with_config()`、可以被当函数传。这带来一个工程习惯：**把链当值传递**（存变量、做参数、按租户组装不同链），而不是把"调用逻辑"藏进函数体。40.1 里"三份手写代码"的根本病因，就是逻辑藏在函数里而不可组合。

**（2）输入输出类型是"约定"不是"检查"**。管道每段的类型契约（41 章会再次用到）：`ChatPromptTemplate.invoke(dict) -> ChatPromptValue`；`ChatModel.invoke(消息列表) -> AIMessage`；`StrOutputParser.invoke(消息) -> str`。框架不做编译期检查——`RunnablePassthrough.assign` 喂给 `Retriever` 一个 dict 就会在运行时炸（真实踩坑记录见 41.5）。工程对策：管道写完先手动 `invoke` 一次看中间类型，或给关键节点用 `RunnableLambda` 包一层类型注解齐全的函数。

**（3）`assign` 与 `Parallel` 是 RAG 管道的两块积木**。`assign(k=v)`（EX-40-02 [1]）在**不丢原键**的前提下注入新键——RAG 的"检索结果旁路注入"标准姿势；`RunnableParallel`（[2]）把同一输入分给多分支（真实场景：同时取向量检索与 BM25 结果）。裸写法的 `d2 = {**d1, "context": ...}` 不是不行，而是**不可流式、不可批量、不可配置**——协议的价值只有在需要换消费姿势时才显现，这正是 40.1 三份代码的教训。

**（4）RunnableConfig 是横切关注的正规通道**。EX-40-02 [3] 实测：`invoke(..., config={"tags": [...]})` 后，管道内每个节点的函数（签名带 `config: RunnableConfig` 的自动注入）都能读到同一份 tags。对照 Java：这等于框架替你维护了"调用上下文"（trace_id、租户），不需要 ThreadLocal，也不需要把 config 参数层层透传。`recursion_limit` 也在 config 里（ch42 的 Agent 循环防失控用得上）。

**（5）异常语义与调试入口**。异常原样冒泡（EX-40-03 [3]）意味着你可以沿用 ch08 的异常分层设计；`.with_retry()` / `.with_fallbacks()` 是管道级的重试/降级装饰（对应 EX-24-04 的手写退避，参数化更强但策略可定制性弱于手写——按 ch59 的原则选）。调试三板斧：`get_prompts()`（线上排查"到底发了什么 prompt"）、`get_graph().nodes`（结构自查，print_ascii 需额外安装 grandalf）、`astream_events`（时序观察，生产里接可观测系统的入口，ch60）。

> ⚠️ 常见坑：`batch` 的并发语义——真实模型下 `batch` 是并发的（线程池），Fake 下按脚本顺序串行消费；测试脚本条数要按"batch 大小"准备，否则会踩到 Fake 模型的循环/耗尽语义（38.3 的两兄弟差异）。

## 40.6 安装 / 文件位置 / 运行命令

```bash
pip install -r requirements.txt   # langchain-core==1.6.12

python3 示例代码/ch40_lcel/ex_40_01_pipe_chain.py
python3 示例代码/ch40_lcel/ex_40_02_parallel_config.py
python3 示例代码/ch40_lcel/ex_40_03_batch_stream_async.py

python3 -m pytest 测试/test_ch40.py -q
```

## 40.7 常见错误与排查

**错 1：`KeyError: 'context'`（或管道下游取不到某键）。**
原因：`assign` 的键名与下游模板变量不一致（大小写、拼写），或上游根本没产出该键。修复：用 EX-40-02 的方式把中间结果 `print` 出来逐段核对；模板的 `input_variables` 与 assign 的键对齐后再上线。

**错 2：`AttributeError: 'dict' object has no attribute 'lower'`（真实踩坑）。**
原因：把吃 `str` 的组件接到了 `dict` 输入后面——管道类型错位。修复：在中间插入 `itemgetter("question")` 或 `RunnableLambda(lambda x: x["question"])` 做类型对齐（EX-41-03 的标准解法）；把"每段输入类型"写进管道旁的注释。

**错 3：`RuntimeError: generator raised StopIteration`。**
真实报错（探测过程实测）。原因：脚本模型（GenericFakeChatModel）在 Runnable 内部被消费到耗尽，`StopIteration` 在生成器上下文中按 PEP 479 转成 RuntimeError。修复：按"调用次数"备足脚本；要循环语义换 `FakeListChatModel`（38.3 实测差异）。

**错 4：`ImportError: Install grandalf to draw graphs: pip install grandalf`。**
真实报错（EX-40-01 [5] 探测实测）。原因：`get_graph().print_ascii()` 依赖可选包 grandalf。修复：教学/轻量调试用 `get_graph().nodes` 节点表（本书做法）；确需 ASCII 图就 `pip install grandalf`（注意纳入依赖清单）。

## 40.8 企业场景中的使用方式

在"AI 服务 + Spring Boot 业务服务"的架构里（ch57），LCEL 管道通常作为 Python 侧 AI 服务的**内部组织单元**：一条管道对应一个业务能力（如"工单分类"），`with_config(tags=["tenant:acme"])` 在入口注入租户，`astream_events` 接观测（每次 token/延迟/成本事件落结构化日志），`with_fallbacks` 做厂商降级。管道定义集中在一个模块里，像 Spring 的 `@Configuration` 一样可审阅；Java 侧只见 REST/SSE 接口，不感知管道存在——这层边界让"改 prompt/换模型"不必动 Java 代码。

## 40.9 练习

**基础 1**：说出 Runnable 的五个执行入口与两个横切通道（配置/回调），并解释"链自动继承协议"意味着什么。

**基础 2**：EX-40-03 中 `ValueError` 为什么没有变成框架异常？这个设计对业务代码意味着什么？

**代码 1**：把 EX-40-02 的 `probe` 函数改为读取 `config.get("metadata")` 并传入 `metadata={"trace_id": "t-1"}`，验证 metadata 同样贯穿；在 `测试/test_ch40.py` 中补断言。

**代码 2**：组装一条"两路并行 → 合并"管道：`RunnableParallel(classify=..., summarize=...)`，输入同一段文本，输出 `{"classify": ..., "summarize": ...}`；用 Fake 模型跑通并断言输出键。

**调试题**：一条 `prompt | model | parser` 管道在流式模式下前几个 chunk 正常、随后抛 `RuntimeError: generator raised StopIteration`。给出原因与两种修复。

### 参考答案

**基础 1**：invoke / batch / stream / ainvoke / astream（含 astream_events）；横切通道是 RunnableConfig（tags/metadata/callbacks/configurable/recursion_limit）与回调体系。"自动继承"= 组合产物 RunnableSequence 实现同一协议，成员怎么被调用，链就怎么被调用。

**基础 2**：框架在 `_call_with_config` 中只负责调度、不吞异常，异常对象原样 raise；业务代码可以继续用原生异常类型做分层捕获（ch08 的语义），不需要学习框架的异常体系。

**代码 1**（要点）：config 支持 `metadata` 键；`seen.append(dict(config.get("metadata") or {}))`，断言 `seen[0][0]["trace_id"] == "t-1"`。

**代码 2**（要点）：
```python
chain = RunnableParallel(
    classify=RunnableLambda(lambda s: f"分类:{s[:6]}"),
    summarize=RunnableLambda(lambda s: f"摘要:{s[-6:]}"),
)
assert chain.invoke("这是一段待处理文本") == {"classify": "分类:这是一段待处", "summarize": "摘要:待处理文本"}
```

**调试题**：原因是脚本模型耗尽（流式消费的轮数超过脚本条数），StopIteration 在生成器里被转成 RuntimeError。修复一：补足脚本条数；修复二：改用 FakeListChatModel 获得循环语义。另检查是否在流式中途重新创建模型实例导致脚本指针重置。

## 40.10 自测检查表

- 我能解释 `|` 的机制（`Runnable.__or__` → RunnableSequence）并说出"链也是 Runnable"的三个用途。
- 我能写出管道各段的输入输出类型表，并说出类型错位的真实症状与修复（itemgetter 对齐）。
- 我能用 `assign` 做 RAG 检索注入、用 `RunnableParallel` 做多路分支，并解释两者与裸写法的差别（协议）。
- 我能演示异常在同步与流式管道中的传播语义。
- 我能用 `get_prompts` / `get_graph().nodes` / `astream_events` 三个入口调试一条链。
- 我能说出 RunnableConfig 的实测字段并演示 tags 贯穿。
- 我能说出 batch 在真实模型与 Fake 模型下的并发差异，以及脚本条数怎么备。

## 40.11 面试追问

**[模拟题] 1：LCEL 相比"手写函数组合"到底解决了什么？什么时候手写更好？**
考查点：抽象价值评估。合格回答：解决了执行协议复用（batch/stream/async/config）、可检视（get_prompts/get_graph）、生态组件即插即用（模型/解析器/Retriever 都实现 Runnable）；当管道只是两次纯函数调用、不需要多消费姿势、团队对框架不熟时，手写更直白。判断标准是"会不会需要第二种消费方式"。

**[模拟题] 2：RunnableConfig 的设计与 Java 里 MDC/ThreadLocal 传 trace_id 相比有什么优劣？**
考查点：横切设计。合格回答：LCEL 显式传 config，无线程耦合、异步安全（asyncio 里 ThreadLocal 是坑），且框架把 config 送到每个节点；代价是节点函数签名多了约定（多参函数自动注入 config）。MDC 在同步线程模型下最省事，但在线程池/协程切换时容易丢上下文。

**[模拟题] 3：管道里某一步要调用一个很慢的外部接口，你怎么在 LCEL 里控制它的失败影响？**
考查点：韧性设计。合格回答：该步用 `RunnableLambda` 包出超时（`asyncio.wait_for` 或线程池超时）与降级值；管道级 `.with_retry(可重试异常)` 或 `.with_fallbacks([降级链])`；区分可重试错误（网络类）与不可重试（参数类）；最终对照 ch59 的超时/重试/熔断参数表给数值。

> 📌 本章待核实项：`RunnableBranch`（条件分支）与 `with_fallbacks` 的完整参数行为未在本书示例中展开实测（导出列表已核实存在）；`astream_events` 的自定义事件（`adispatch_custom_event`）未演示，需要时按官方文档核实版本要求。

# 第 41 章 文档组件：加载、切分与检索的"框架化"对照

> **本章目标**：把第六部分手写的"加载→切分→向量检索→拼接 prompt"逐段映射到 LangChain 文档组件，并保持手写实现的对照视角。
> **前置知识**：ch25（embedding 与余弦相似度）、第六部分 ch30~ch34 的 RAG 主线（切分、检索、引用）、ch16（Pydantic）。
> **学完你能做什么**：用 Document/TextSplitter/VectorStore/Retriever 组装 RAG 管道；把自研检索逻辑包成 BaseRetriever 而不重写算法；说清每个组件对应第六部分手写的哪一段。

## 41.1 真实问题引入：手写 RAG 的三笔"隐形成本"

第六部分（ch30~ch36）你手写过 RAG：自己切块（ch32）、自己算余弦（EX-25-03、ch33）、自己拼上下文（ch34）。手写让你真正理解了机制——这是对的顺序。但把它搬进生产时，老王的团队（合成案例）遇到三笔隐形成本：**类型成本**——`(text, meta)` 元组在函数间传递，新人不知道 meta 里该有什么；**协议成本**——检索模块没有统一接口，批量检索要再写一层 for；**替换成本**——从"内存暴力余弦"换到 FAISS 时，调用方代码要跟着改。

LangChain 的文档组件正是这三笔成本的解法：`Document` 统一"文本+元数据"的类型；`Retriever` 是 Runnable（批量/流式/配置免费获得）；`VectorStore` 是接口，InMemory/FAISS/云服务可替换。本章的价值不在"学新算法"（算法你在第六部分都写过了），而在**把已会的东西接进可替换的接口**。

## 41.2 一句话解释 + 生活类比 + 类比边界

**一句话解释**：LangChain 把 RAG 前半程拆成四个组件——`Document`（内容+元数据的信封）、`TextSplitter`（切分器，第六部分已在用）、`Embeddings`（嵌入接口，embed_documents/embed_query 两方法）、`VectorStore`/`Retriever`（存取与检索，都是 Runnable）——每个组件都对应你手写过的一段代码，只是加上了类型与协议。

**生活类比**：`Document` 之于裸元组，就像 JDBC 的 `ResultSet` 之于 `Object[]`；`VectorStore` 接口之于 InMemoryVectorStore，就像 `DataSource` 接口之于内存测试数据源——实现可换，调用方不动；`BaseRetriever` ≈ Spring Data 的 `Repository` 接口：业务代码依赖接口，实现随便换。

> 💡 类比边界：
> 1. JDBC 查询是**等值/范围条件**（B-tree 索引，精确匹配），向量检索是**相似度排序**（Top-k，没有"命中/不命中"的绝对语义）——把 `similarity_search` 当 SQL `WHERE` 写需求（"必须查到"）会在召回不足时翻车（ch33/ch35 的评估意识）；
> 2. `InMemoryVectorStore` 是**进程内暴力检索**（每查询全量算相似度），和第六部分手写的实现同级——它替代的是你的 20 行样板，不是你的向量数据库选型；上量仍要专业向量库（ch33 的 FAISS○/云服务）；
> 3. 接口统一≠效果一致：不同 VectorStore 的相似度口径、过滤能力、元数据索引差异很大，换实现要重新验证评估集（ch35）。

## 41.3 正式原理与准确术语

**Document**（langchain_core.documents，实测字段 `id / metadata / page_content / type`）：RAG 的最小信封。第六部分你自建的 `(text, meta)` 结构就是它。

**加载器（loaders）**：核心包**不提供**加载器。集成加载器在 langchain-community（如 `TextLoader`）与各独立集成包中。**版本现状（实测）**：`from langchain_community.document_loaders import TextLoader` 可用，但导入即触发官方 DeprecationWarning——"`langchain-community` is being sunset and is no longer actively maintained"（EX-41-01 [4] 实测捕获原文）。选型建议：简单文本自己读（`pathlib.read_text` 包成 Document），复杂格式按官方迁移指引选独立集成包；解析策略本身见 ch31。

**切分器（TextSplitter）**：`langchain_text_splitters.RecursiveCharacterTextSplitter`（第六部分 ch32 已实测过），构造签名实测：`(separators=None, keep_separator=True, is_separator_regex=False, **kwargs)`，kwargs 常用 `chunk_size / chunk_overlap / length_function / add_start_index`。语义：按分隔符列表**自上而下递归**切分，尽量在语义边界断开。`create_documents([text], metadatas=[...])` 产出带元数据的 Document 列表。

**Embeddings 接口**（langchain_core.embeddings，实测）：两个方法——`embed_documents(texts)`（批量，入库时给文档算向量）与 `embed_query(text)`（单条，查询时给问题算向量）。全书基座 `MockEmbedder` 的接口是 `embed/embed_one`，需要一层**适配器**（Adapter 模式）才能接入（EX-41-02 实测）。

**VectorStore 与 Retriever**：`InMemoryVectorStore(embedding=...)`（langchain_core.vectorstores.in_memory，实测方法 `add_documents / similarity_search / similarity_search_with_score / as_retriever / from_texts`）；`as_retriever(search_kwargs={"k": n})` 返回 `VectorStoreRetriever`（Runnable）。自研检索可继承 `BaseRetriever`，只需实现 `_get_relevant_documents(query, *, run_manager)`（EX-41-03 实测），即可免费获得 invoke/batch 协议。

**Java 对照**：这一章的组件图就是一张"仓储层"设计——Document 是实体，Embeddings 是外部服务网关，VectorStore 是 Repository，Retriever 是领域服务；你第六部分手写的"服务实现"，这一章给它套上标准接口。

## 41.4 最小完整示例：切分实验、向量店与自写 Retriever

**EX-41-01 | 示例代码/ch41_lc_rag_components/ex_41_01_loader_splitter.py（完整可运行）**

```python
# EX-41-01 | Document 与 RecursiveCharacterTextSplitter：复用第六部分的切分知识 | 运行: python3 示例代码/ch41_lc_rag_components/ex_41_01_loader_splitter.py
"""完整可运行（离线）：
[1] Document：RAG 世界的"信封"（page_content + metadata），与第六部分手写的切片对照；
[2] langchain-text-splitters 的 RecursiveCharacterTextSplitter 参数实验（中文分隔符）；
[3] loaders 简介与选型边界（langchain-community 已宣布 sunset 的实测证据）。
"""
from __future__ import annotations

import pathlib
import tempfile
import warnings

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


def main() -> None:
    print("[1] Document：最小信封（两个核心字段）：")
    doc = Document(page_content="蓝牙耳机保修 12 个月。", metadata={"source": "warranty.md", "page": 3})
    print(f"    page_content = {doc.page_content!r}")
    print(f"    metadata     = {doc.metadata}")
    print("    → 第六部分手写检索时你自建的 (text, meta) 元组，就是它（EX-25-03 的 KB 结构）")

    print("\n[2] RecursiveCharacterTextSplitter 参数实验（第六部分 ch32 的同一套直觉）：")
    text = "第一条：七天无理由退货。第二条：运费由商家承担。第三条：签收后请及时验货。" * 2
    print(f"    原文长度 = {len(text)} 字符")
    for size, overlap in [(30, 0), (30, 10), (60, 10)]:
        sp = RecursiveCharacterTextSplitter(
            chunk_size=size, chunk_overlap=overlap,
            separators=["。", "，", " ", ""],   # 中文标点优先，英文默认以 \n\n 打头
            length_function=len,                # 中文必须用 len 而非默认的 token 函数假设
            keep_separator="end",
        )
        docs = sp.create_documents([text], metadatas=[{"source": "policy.md"}])
        lens = [len(d.page_content) for d in docs]
        print(f"    chunk_size={size:>2} overlap={overlap:>2} → {len(docs)} 块，长度 {lens}")
    print("    规则：从分隔符列表自上而下找第一个'切得开'的层级，递归到块长 ≤ chunk_size；")
    print("    overlap 让相邻块共享一段尾巴，防止答案正好被切在边界上（对照 ch32 重叠切分）。")

    print("\n[3] metadata 会随块携带（引用溯源 ch34 的基础）：")
    sp = RecursiveCharacterTextSplitter(chunk_size=30, chunk_overlap=0, separators=["。", ""], keep_separator="end")
    for d in sp.create_documents([text], metadatas=[{"source": "policy.md", "tenant": "acme"}])[:2]:
        print(f"    {d.metadata} → {d.page_content[:18]}...")

    print("\n[4] loaders 简介与选型边界（诚实声明）：")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        from langchain_community.document_loaders import TextLoader  # noqa: F401

        deprecation = [str(w.message) for w in caught if "sunset" in str(w.message)]
    print(f"    from langchain_community.document_loaders import TextLoader 导入成功，")
    print(f"    但触发官方警告：{deprecation[0][:76] if deprecation else '（本次未捕获到警告）'}...")
    tmp = pathlib.Path(tempfile.mkdtemp()) / "note.txt"
    tmp.write_text("第一行文本\n第二行文本", encoding="utf-8")
    loaded = TextLoader(str(tmp), encoding="utf-8").load()
    print(f"    TextLoader.load() → {len(loaded)} 个 Document：{loaded[0].page_content!r}")
    print("    选型建议：核心包只提供 Document 与切分器；加载器按需选独立集成包，")
    print("    或者干脆自己写（第六部分 ch31 的加载/清洗代码移植性好，不锁定框架）。")


if __name__ == "__main__":
    main()
```

```text
# 真实运行输出（离线；[4] 的警告文本为实测捕获）
[1] Document：最小信封（两个核心字段）：
    page_content = '蓝牙耳机保修 12 个月。'
    metadata     = {'source': 'warranty.md', 'page': 3}
    → 第六部分手写检索时你自建的 (text, meta) 元组，就是它（EX-25-03 的 KB 结构）

[2] RecursiveCharacterTextSplitter 参数实验（第六部分 ch32 的同一套直觉）：
    原文长度 = 74 字符
    chunk_size=30 overlap= 0 → 3 块，长度 [24, 25, 25]
    chunk_size=30 overlap=10 → 3 块，长度 [24, 25, 25]
    chunk_size=60 overlap=10 → 2 块，长度 [49, 25]
    规则：从分隔符列表自上而下找第一个'切得开'的层级，递归到块长 ≤ chunk_size；
    overlap 让相邻块共享一段尾巴，防止答案正好被切在边界上（对照 ch32 重叠切分）。

[3] metadata 会随块携带（引用溯源 ch34 的基础）：
    {'source': 'policy.md', 'tenant': 'acme'} → 第一条：七天无理由退货。第二条：运费...
    {'source': 'policy.md', 'tenant': 'acme'} → 第三条：签收后请及时验货。第一条：七...

[4] loaders 简介与选型边界（诚实声明）：
    from langchain_community.document_loaders import TextLoader 导入成功，
    但触发官方警告：`langchain-community` is being sunset and is no longer actively maintained. ...
    TextLoader.load() → 1 个 Document：'第一行文本\n第二行文本'
    选型建议：核心包只提供 Document 与切分器；加载器按需选独立集成包，
    或者干脆自己写（第六部分 ch31 的加载/清洗代码移植性好，不锁定框架）。
```

**EX-41-02 | 示例代码/ch41_lc_rag_components/ex_41_02_vector_retriever.py（完整可运行）**

```python
# EX-41-02 | InMemoryVectorStore：把 MockEmbedder 适配成 LangChain Embeddings | 运行: python3 示例代码/ch41_lc_rag_components/ex_41_02_vector_retriever.py
"""完整可运行（离线）：
[1] 适配器模式：全书 MockEmbedder（embed/embed_one）→ LangChain Embeddings 接口
    （embed_documents/embed_query），两个方法的分工对应"入库"与"查询"；
[2] InMemoryVectorStore（langchain-core 1.6.12 自带，无需向量库服务）增查实测；
[3] as_retriever()：向量店一步变 Runnable，直接接进 LCEL 管道。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # 仓库根

from 示例代码.公共.embeddings import MockEmbedder  # noqa: E402

from langchain_core.documents import Document  # noqa: E402
from langchain_core.embeddings import Embeddings  # noqa: E402
from langchain_core.vectorstores import InMemoryVectorStore  # noqa: E402


class MockLangChainEmbeddings(Embeddings):
    """适配器（Adapter）：把全书基座 MockEmbedder 包装成 LangChain 接口。

    Embeddings 接口只有两个方法（已核实 langchain_core.embeddings.Embeddings）：
        embed_documents(texts)  —— 批量：入库阶段给文档算向量；
        embed_query(text)       —— 单条：查询阶段给用户问题算向量。
    真实 embedding 模型接口也是这两个方法（如 OpenAIEmbeddings），换模型只换这一层。
    """

    def __init__(self, dim: int = 64) -> None:
        self._inner = MockEmbedder(dim=dim)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._inner.embed(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._inner.embed_one(text)


DOCS = [
    Document(page_content="蓝牙耳机保修 12 个月，人为损坏除外。", metadata={"source": "warranty.md"}),
    Document(page_content="披萨买一送一，活动到月底。", metadata={"source": "promo.md"}),
    Document(page_content="手机 SIM 卡激活需要实名认证。", metadata={"source": "sim.md"}),
]


def main() -> None:
    emb = MockLangChainEmbeddings()
    print("[1] 适配器接口实测（MockEmbedder 语义不变）：")
    print(f"    embed_documents(['手机'])[:3] = {[round(x, 3) for x in emb.embed_documents(['手机'])[0][:3]]}...")
    print(f"    与 embed_query('手机') 一致 = {emb.embed_documents(['手机'])[0] == emb.embed_query('手机')}")

    print("\n[2] InMemoryVectorStore：入库 + 相似度检索（纯内存，进程重启即失）：")
    store = InMemoryVectorStore(embedding=emb)
    ids = store.add_documents(DOCS)
    print(f"    add_documents → 生成 {len(ids)} 个内部 id（示例：{ids[0][:8]}...）")
    hits = store.similarity_search("手机 SIM 卡坏了怎么办", k=2)
    for d in hits:
        print(f"    命中：{d.metadata['source']:<12} {d.page_content}")
    scored = store.similarity_search_with_score("手机 SIM 卡坏了怎么办", k=1)
    print(f"    带分数：{scored[0][0].metadata['source']} score={scored[0][1]:.4f}")
    print("    → 对照 EX-25-03 手写的 8 行 numpy 检索：InMemoryVectorStore 内部就是")
    print("      'embedding + 暴力余弦 + 排序'，量小够用；上量换 FAISS/云服务，接口不变。")

    print("\n[3] as_retriever()：向量店一步变 Runnable（可进管道、可 batch）：")
    retriever = store.as_retriever(search_kwargs={"k": 1})
    docs = retriever.invoke("SIM 卡激活流程")
    print(f"    invoke → {[d.page_content for d in docs]}")
    print(f"    batch(['耳机保修', '披萨']) → {[[d.page_content for d in ds] for ds in retriever.batch(['耳机保修', '披萨'])]}")
    print(f"    type = {type(retriever).__name__}（VectorStoreRetriever，是 Runnable）")


if __name__ == "__main__":
    main()
```

```text
# 真实运行输出（离线，MockEmbedder 确定性向量）
[1] 适配器接口实测（MockEmbedder 语义不变）：
    embed_documents(['手机'])[:3] = [1.0, 0.0, 0.0]...
    与 embed_query('手机') 一致 = True

[2] InMemoryVectorStore：入库 + 相似度检索（纯内存，进程重启即失）：
    add_documents → 生成 3 个内部 id（示例：9b5bae5f...）
    命中：sim.md       手机 SIM 卡激活需要实名认证。
    命中：warranty.md  蓝牙耳机保修 12 个月，人为损坏除外。
    带分数：sim.md score=0.3922
    → 对照 EX-25-03 手写的 8 行 numpy 检索：InMemoryVectorStore 内部就是
      'embedding + 暴力余弦 + 排序'，量小够用；上量换 FAISS/云服务，接口不变。

[3] as_retriever()：向量店一步变 Runnable（可进管道、可 batch）：
    invoke → ['手机 SIM 卡激活需要实名认证。']
    batch(['耳机保修', '披萨']) → [['蓝牙耳机保修 12 个月，人为损坏除外。'], ['披萨买一送一，活动到月底。']]
    type = VectorStoreRetriever（VectorStoreRetriever，是 Runnable）
```

**EX-41-03 | 示例代码/ch41_lc_rag_components/ex_41_03_custom_retriever.py（完整可运行）**

```python
# EX-41-03 | 自写 Retriever（BaseRetriever 子类）并接进 RAG 生成链 | 运行: python3 示例代码/ch41_lc_rag_components/ex_41_03_custom_retriever.py
"""完整可运行（离线）：
[1] 继承 BaseRetriever：第六部分手写的"embed + 余弦 + Top-k"变成框架组件；
[2] Retriever 是 Runnable：batch / 进管道 / 与 RunnablePassthrough.assign 组合成 RAG 链；
[3] 全链真实运行：检索注入 → ChatPromptTemplate → Fake 模型 → 最终回答。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # 仓库根

from 示例代码.公共.embeddings import MockEmbedder, cosine_similarity  # noqa: E402

from langchain_core.callbacks import CallbackManagerForRetrieverRun  # noqa: E402
from langchain_core.documents import Document  # noqa: E402
from langchain_core.language_models import FakeListChatModel  # noqa: E402
from langchain_core.output_parsers import StrOutputParser  # noqa: E402
from langchain_core.prompts import ChatPromptTemplate  # noqa: E402
from langchain_core.retrievers import BaseRetriever  # noqa: E402
from langchain_core.runnables import RunnableLambda, RunnablePassthrough  # noqa: E402


class MockRetriever(BaseRetriever):
    """语义检索 Retriever：核心逻辑 = EX-25-03 手写检索，外壳 = LangChain 接口。

    只需实现一个方法：_get_relevant_documents(query, run_manager) -> list[Document]。
    （Pydantic 子类：docs/k 作为字段声明，不要放进 __init__ 手动赋值。）
    """

    docs: list[Document]
    k: int = 2

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> list[Document]:
        emb = MockEmbedder()
        qv = emb.embed_one(query)
        scored = sorted(
            self.docs,
            key=lambda d: cosine_similarity(qv, emb.embed_one(d.page_content)),
            reverse=True,
        )
        return scored[: self.k]


DOCS = [
    Document(page_content="蓝牙耳机保修 12 个月。", metadata={"source": "warranty.md"}),
    Document(page_content="披萨买一送一。", metadata={"source": "promo.md"}),
    Document(page_content="手机 SIM 卡激活需要实名认证。", metadata={"source": "sim.md"}),
]


def format_docs(docs: list[Document]) -> str:
    """把检索结果拼成可放进 prompt 的文本（引用溯源在这里埋点）。"""
    return "\n".join(f"[{d.metadata['source']}] {d.page_content}" for d in docs)


def build_rag_chain(retriever: BaseRetriever) -> RunnablePassthrough:
    """RAG 链：检索注入 → 模板 → Fake 模型 → 解析（main 与测试共用同一构造）。"""
    prompt = ChatPromptTemplate.from_messages([
        ("system", "只依据提供的背景资料回答，资料里没有就明确说不知道。"),
        ("human", "背景资料：\n{context}\n\n问题：{question}"),
    ])
    model = FakeListChatModel(responses=[
        "根据 [warranty.md]：蓝牙耳机保修 12 个月。（Fake 预置）",
    ])
    from operator import itemgetter

    return (
        RunnablePassthrough.assign(
            # 类型对齐关键点：assign 收到的输入是 dict，Retriever 只吃 str——
            # 必须先用 itemgetter 取出 question 字符串（41.5 逐段解释的高频坑）
            context=itemgetter("question") | retriever | RunnableLambda(format_docs)
        )
        | prompt
        | model
        | StrOutputParser()
    )


def main() -> None:
    retriever = MockRetriever(docs=DOCS, k=1)
    print("[1] 自写 Retriever 的 Runnable 协议（免费获得，不是巧合——基类已经实现）：")
    print(f"    invoke('耳机保修多久') → {[d.page_content for d in retriever.invoke('耳机保修多久')]}")
    print(f"    batch(['耳机保修', '披萨优惠']) → "
          f"{[[d.page_content for d in ds] for ds in retriever.batch(['耳机保修', '披萨优惠'])]}")
    print(f"    type = {type(retriever).__name__}（BaseRetriever 子类，天然是 Runnable）")

    print("\n[2] RAG 链组装：检索注入 → 模板 → Fake 模型 → 解析（全链真实运行）：")
    rag_chain = build_rag_chain(retriever)
    answer = rag_chain.invoke({"question": "耳机保修多久？"})
    print(f"    最终回答：{answer}")
    print("\n[3] 管道里各环节的输入输出类型（教材 41.4 的类型表）：")
    print("    {'question': str} → assign(context=str) → ChatPromptValue → AIMessage → str")
    print("    → 裸 SDK 版（EX-25-03）到 retrieve() 后就'手工拼字符串'了；")
    print("      LCEL 把检索、格式化、模板、生成接成一条有类型的流水线。")


if __name__ == "__main__":
    main()
```

```text
# 真实运行输出（离线，Fake 模型脚本驱动）
[1] 自写 Retriever 的 Runnable 协议（免费获得，不是巧合——基类已经实现）：
    invoke('耳机保修多久') → ['蓝牙耳机保修 12 个月。']
    batch(['耳机保修', '披萨优惠']) → [['蓝牙耳机保修 12 个月。'], ['披萨买一送一。']]
    type = MockRetriever（BaseRetriever 子类，天然是 Runnable）

[2] RAG 链组装：检索注入 → 模板 → Fake 模型 → 解析（全链真实运行）：
    最终回答：根据 [warranty.md]：蓝牙耳机保修 12 个月。（Fake 预置）

[3] 管道里各环节的输入输出类型（教材 41.4 的类型表）：
    {'question': str} → assign(context=str) → ChatPromptValue → AIMessage → str
    → 裸 SDK 版（EX-25-03）到 retrieve() 后就'手工拼字符串'了；
      LCEL 把检索、格式化、模板、生成接成一条有类型的流水线。
```

## 41.5 逐段解释：组件映射与两个真实踩坑

**（1）与第六部分手写实现的逐项对照**（本章的对照主线，建议对照着 EX-25-03 与 ch32 复习）：

| RAG 环节 | 第六部分手写 | LangChain 组件 | 框架接手了什么 |
|---|---|---|---|
| 数据结构 | `(text, meta)` 元组 | `Document(page_content, metadata)` | 类型 + 全链传递 |
| 切分 | 手写按句切分 | `RecursiveCharacterTextSplitter` | 递归分层算法 + overlap + 元数据复制 |
| 嵌入 | `MockEmbedder.embed/embed_one` | `Embeddings` 接口（适配器一层） | 接口统一，实现可换 |
| 检索 | numpy 暴力余弦 + 排序（8 行） | `InMemoryVectorStore` / 自写 `BaseRetriever` | 相似度计算与 Top-k 样板 |
| 拼装 | 手工 f-string 拼上下文 | `RunnablePassthrough.assign` + 模板 | 类型对齐的管道 |

**（2）踩坑一：Retriever 的输入必须是 str**（写作过程真实踩中，EX-41-03 的注释就是案发现场）。第一次组装时写成了 `assign(context=retriever | ...)`——`assign` 把整个 dict 传给了 Retriever，`MockEmbedder.embed_one` 收到 dict 直接 `AttributeError: 'dict' object has no attribute 'lower'`。修复是标准解法：`itemgetter("question") | retriever | ...`——先用取键 Runnable 把 dict 降为 str。这条经验泛化成一句话：**LCEL 不做类型适配，每段之间要自己保证"上段输出 = 下段输入"**。

**（3）踩坑二：BaseRetriever 子类的字段要声明为类属性**。`MockRetriever` 的 `docs: list[Document]` 和 `k: int` 写在类体（Pydantic 字段），而不是 `__init__` 里手工赋值——`BaseRetriever` 是 Pydantic 模型，字段声明才能被校验与序列化，`MockRetriever(docs=..., k=...)` 的构造语法也来自这里。写错位置不会立刻报错，但会在 batch 并发或配置传递时出现诡异行为。

**（4）Embeddings 的两个方法为什么必须分开**。`embed_documents`（入库，批量）与 `embed_query`（查询，单条）在真实模型上可能是**两次不同的 API 调用**，甚至对前缀/参数有不同要求（厂商文档各异）；Mock 两者一致只是巧合（EX-41-02 [1] 实测 `True`）。适配器把这层差异封装在一处——换真实 Embeddings 时只改这个类，检索链一行不动。

**（5）检索组件的正确打开方式是"包接口"而不是"换算法"**。你的第六部分算法（余弦、Top-k、将来的 BM25/重排）原样保留，只是外套 `BaseRetriever`。什么时候值得直接用 `InMemoryVectorStore`？文档量小、想要开箱即用的原型——注意它把向量存在进程内存（实测 `add_documents` 返回内部 uuid），**进程重启即失**，持久化要靠外部向量库（接口不变，配置换）。

## 41.6 安装 / 文件位置 / 运行命令

```bash
pip install -r requirements.txt   # langchain-core==1.6.12 / langchain-text-splitters==1.1.3
# langchain-community==0.4.2 仅为 [4] 的 loader 演示存在；生产加载器按官方迁移指引选独立包

python3 示例代码/ch41_lc_rag_components/ex_41_01_loader_splitter.py
python3 示例代码/ch41_lc_rag_components/ex_41_02_vector_retriever.py
python3 示例代码/ch41_lc_rag_components/ex_41_03_custom_retriever.py

python3 -m pytest 测试/test_ch41.py -q
```

## 41.7 常见错误与排查

**错 1：`AttributeError: 'dict' object has no attribute ...`（Retriever/Embedder 收到 dict）。**
真实踩坑（41.5（2））。原因：管道类型错位，dict 被直接喂给吃 str 的组件。修复：`itemgetter("key")` 对齐；写管道时为每段标注输入输出类型。

**错 2：`ImportError`/弃用警告与加载器相关。**
现象：`langchain_community` 导入触发 `DeprecationWarning ... being sunset`（实测原文见 EX-41-01 [4]）。原因：community 包已宣布日落维护。修复：教学演示可用；生产按官方迁移指引选独立集成包，或自己实现加载逻辑（ch31 的清洗代码 + `Document` 包装最可控）。

**错 3：中文切分后块长明显超过 chunk_size？或切得稀碎？**
原因：默认分隔符面向英文（`\n\n`、`\n`、空格），中文文本找不到切点，退化到字符级；`length_function` 默认按字符/token 假设也可能与你的预算口径不一致。修复：显式传 `separators=["。", "，", " ", ""]` 与 `length_function=len`（EX-41-01 [2] 实测三组参数对比）；口径与 ch32 的 token 预算对齐。

**错 4：检索结果总是"差一点"——命中同主题但不是目标条款。**
原因：这不是框架问题：Mock 向量只有"概念词典命中"的粗粒度语义（基座文档的类比边界），真实 embedding 也有召回天花板。修复：按 ch35 的评估思路定位——先看 embedding 质量（换模型）、再看切分（目标句是否被切碎）、最后上重排/混合检索（ch33）；用评估集量化每次改动，别凭感觉调。

## 41.8 企业场景中的使用方式

企业文档知识库（项目 P1 的形态）中，这四个组件对应**四个可独立评审的资产**：`Document.metadata` 的 schema（source/tenant/权限标签——检索前权限过滤的载体，ch34/ch58）、切分参数（每类文档一组，随评估集回归）、Embeddings 适配器（模型切换的唯一改动点）、Retriever（算法迭代区）。Spring Boot 侧通过 REST 调用 Python 检索服务时，返回的就是 Document 列表的 JSON 序列化（`page_content + metadata`）——元数据设计直接决定 Java 侧能否实现"按租户过滤后展示引用"。

## 41.9 练习

**基础 1**：说出 RAG 四组件各自对应第六部分手写的哪一段代码。

**基础 2**：`embed_documents` 与 `embed_query` 的分工是什么？为什么接口要拆成两个方法？

**代码 1**：给 `MockRetriever` 加一个 `metadata_filter: dict | None` 字段：检索前按 metadata 等值过滤（如 `{"tenant": "acme"}`），实现"检索前权限过滤"（ch34 思想），并用两个租户的文档写测试验证隔离。

**代码 2**：用 `RecursiveCharacterTextSplitter` 分别以 `separators=["。", ""]` 和默认分隔符切一段中文长文本，比较块数与块长分布，把结论写成注释放进 `测试/test_ch41.py`。

**调试题**：`as_retriever()` 拿到的检索结果与直接调 `similarity_search` 的 k 不一致。给出至少两个可能原因。

### 参考答案

**基础 1**：见 41.5（1）对照表——元组→Document；手写切分→TextSplitter；embed/embed_one→Embeddings 适配器；numpy 余弦→VectorStore/BaseRetriever；f-string 拼装→assign+模板。

**基础 2**：入库批量 vs 查询单条，是两个不同的调用阶段，真实服务上参数与计费都可能不同；拆开才能把"文档侧"与"查询侧"的差异（前缀、缓存、模型版本）封装在实现里，调用方无感。

**代码 1**（要点）：
```python
class FilteredRetriever(MockRetriever):
    tenant: str = ""
    def _get_relevant_documents(self, query, *, run_manager):
        pool = [d for d in self.docs if not self.tenant or d.metadata.get("tenant") == self.tenant]
        ...  # 复用父类打分逻辑，池换成 pool
```
测试：tenant="acme" 时 tenant="other" 的文档永不出现在结果里。

**代码 2**（要点）：默认分隔符下中文段落若无换行/空格，会退化成字符级硬切（块长≈chunk_size、断在词中间）；中文分隔符下块边界落在句号处、块长参差但语义完整。结论：切分器的默认值是英文优先，中文必须显式传分隔符。

**调试题**：① `as_retriever(search_kwargs={"k": n})` 的 k 与 `similarity_search(query, k=m)` 的 m 传了不同值（search_kwargs 才是 retriever 的生效配置）；② 检索链路中 query 被上游改写/截断（如模板变量注入前后不同）；③ 实现差异：某些 VectorStore 的 retriever 默认带分数阈值过滤或 mmr 搜索类型，与直接 similarity_search 口径不同。

## 41.10 自测检查表

- 我能画出 RAG 四组件与第六部分手写代码的对照表。
- 我能解释为什么 LCEL 管道里要用 `itemgetter` 对齐类型，并复述真实报错形态。
- 我能写一个 `Embeddings` 适配器把任意自研向量器接入 LangChain。
- 我能继承 `BaseRetriever` 实现自定义检索，并说出字段声明（Pydantic）与 `__init__` 赋值的区别。
- 我能说出 `InMemoryVectorStore` 的适用边界（进程内、暴力检索、重启即失）。
- 我能解释切分器三个关键参数（chunk_size/overlap/separators）对中文文本的影响并实测验证。
- 我能把"检索前权限过滤"落到 metadata 设计与 Retriever 实现。

## 41.11 面试追问

**[模拟题] 1：你们自研了检索算法，为什么还要包一层 LangChain 的 BaseRetriever？**
考查点：接口思维。合格回答：不是为了算法（算法不变），是为了协议——获得 Runnable 的 batch/流式/配置与 LCEL 组装能力，让检索和生成在一条可检视的管道里；同时把"算法实现"与"调用约定"解耦，换向量库或加重排不动调用方。反之若团队只用裸函数、无组装需求，包一层是过度设计。

**[模拟题] 2：向量检索和 SQL 查询的本质区别是什么？工程上分别怎么保证"查得对"？**
考查点：检索本质。合格回答：SQL 是等值/范围条件的确定性匹配（有就有一没有就没有），向量检索是相似度排序的 Top-k（永远返回 k 条，只有"相关程度"没有"命中"）；SQL 靠索引与约束保证，向量检索靠评估集（召回率/忠实性）与阈值、重排保证。把向量检索需求当 SQL 写（"必须返回那条"）是需求误述。

**[模拟题] 3：文档元数据（metadata）里应该放什么？放错了会怎样？**
考查点：RAG 工程化。合格回答：至少来源（溯源与引用）、租户/权限标签（检索前过滤）、时间（时效排序）；错放（如把正文塞进 metadata）会让切块携带大量冗余、检索分数被稀释；漏放权限标签则可能出现跨租户泄漏——metadata 是 RAG 的"二级数据模型"，值得专门评审。

> 📌 本章待核实项：`InMemoryVectorStore` 的持久化接口（serialize/dump）未实测；`similarity_search_with_score` 的分数口径（距离还是相似度）随实现而异，本书仅对 InMemory 实现实测（0.3922 为相似度方向）；langchain-community sunset 后官方推荐的加载器迁移路径仍在演进，以官方发布说明为准。

# 第 42 章 create_agent：当前推荐的 Agent 构建方式

> **本章目标**：用 1.x 的 `create_agent` 构建生产可用的工具调用 Agent——护栏、持久化、流式、异步；并用"裸 SDK 六步对照"说清框架接手了什么；最后做一次历史考古（AgentExecutor 时代 → 迁移表）。
> **前置知识**：ch24（工具调用闭环六步）、ch39（@tool 与错误处理）、ch13（asyncio）、ch17（SSE）。
> **学完你能做什么**：为一个业务 Agent 写出含步数护栏、错误恢复、多轮记忆与 SSE 流式的完整实现；把团队里的 AgentExecutor 老代码按迁移表升级；判断"这个需求该 create_agent 还是该上 LangGraph"。

## 42.1 真实问题引入：EX-24-03 的循环在生产里活不过一周

第四部分的 EX-24-03 帮你写透了工具调用的六步闭环，也留下了隐患：那段 `while` 循环是教学最小版——没有最大轮数（模型抽风狂点工具时，账单跟着失控）、错误处理只有 try/except 转字符串、没有多轮记忆（每次请求历史从零拼）、没有流式（用户盯着空屏）。某团队的日志排障助手（合成案例）上线第一周就发生了三次"同参数重复调用 20+ 次"的事故，值班同学靠手动杀进程止血。

这不是裸 SDK 的错——是**这些横切关注点（护栏/记忆/恢复/流式）每一项都值得正确实现一次，但不值得在每个项目里手写一次**。`create_agent`（langchain 1.4.6 的当前推荐方式）把六步闭环与这四类横切做成了一个入口。本章以"裸 SDK 对照"展开它。

## 42.2 一句话解释 + 生活类比 + 类比边界

**一句话解释**：`create_agent(model, tools, system_prompt, middleware, checkpointer, ...)` 返回一个 LangGraph 编译图——模型节点与工具节点循环，直到模型不再点名工具；中间件提供护栏，checkpointer 提供跨请求记忆，stream 提供三种流式粒度。

**生活类比**：对比 Spring 的状态机/工作流引擎：`create_agent` 相当于"预置了一张'模型↔工具'的两节点状态机"，你声明参与者（模型、工具），它管状态流转；`middleware` ≈ Filter/Interceptor 横切层；`checkpointer` ≈ 会话状态持久化（Spring Session 的思路）。

> 💡 类比边界：
> 1. 工作流引擎的转移条件是你**显式声明**的（XML/注解），Agent 的"下一步"由**概率模型**决定——所以护栏（步数上限、审批）不是可选项而是默认配置；
> 2. `create_agent` 返回的对象就是 LangGraph 图（类型实测 `CompiledStateGraph`），第八部分手写图时你会认出所有零件——它不是另一个世界，是"常用图的快捷方式"；
> 3. checkpointer 只解决**状态存取**，多租户隔离靠 thread_id 纪律（谁的会话用谁的 id），权限仍在工具层——框架不会替你做鉴权。

## 42.3 正式原理与准确术语

**create_agent 的完整签名**（inspect 实测，2026-10-19，langchain 1.4.6）：

| 参数 | 默认 | 作用（本书用到加粗） |
|---|---|---|
| model | 必填 | 模型实例或 `"openai:gpt-..."` 字符串（走 init_chat_model） |
| tools | None | **@tool 工具列表**；空则退化为纯对话节点 |
| system_prompt | None | **系统提示词**（str） |
| middleware | () | **中间件列表**（护栏/重试/摘要/人工审批） |
| response_format | None | 结构化最终输出（Pydantic schema；需模型支持） |
| state_schema | None | 自定义状态 schema（默认 AgentState：messages） |
| context_schema | None | 运行时上下文 schema（依赖注入给中间件） |
| checkpointer | None | **持久化**（InMemorySaver 起步） |
| store | None | 跨会话长期存储 |
| interrupt_before / interrupt_after | None | 中断点（人工介入，第八部分） |
| debug | False | 调试日志 |
| name / cache / transformers | None | 图名 / 缓存 / 变换器 |

返回值实测为 `CompiledStateGraph`（一个 LangGraph 编译图）：`.invoke / .stream / .astream / .get_state` 全套可用。

**bind_tools 契约**：create_agent 在每次模型节点执行时调用 `model.bind_tools(tools, tool_choice=...)`（EX-42-01 实测调用了 2 次：工具轮与最终轮各一次）。这就是为什么通用 Fake 模型不能直接当 Agent 的模型——`GenericFakeChatModel` 没实现 `bind_tools`，真实报错 `NotImplementedError`（实测）；本书教学用三行子类补齐（`FakeToolChatModel`），这本身示范了"模型与框架的契约点"在哪里。

**中间件体系**（langchain.agents.middleware，模块导出实测）：`ModelCallLimitMiddleware`（步数护栏，实测 `run_limit/thread_limit/exit_behavior='end'|'error'`）、`ToolRetryMiddleware`（工具重试，实测参数 `max_retries=2, backoff_factor=2.0, initial_delay=1.0, jitter=True, on_failure='continue'`）、`SummarizationMiddleware`（历史摘要压缩，对接 ch27 思想）、`HumanInTheLoopMiddleware`（工具级人工审批，对接第八部分 interrupt）、`ModelRetryMiddleware / ModelFallbackMiddleware / ToolCallLimitMiddleware / ToolErrorMiddleware` 等。护栏触发行为实测：`exit_behavior='error'` 抛 `ModelCallLimitExceededError`；`'end'` 写一条收尾 AIMessage 优雅结束（EX-42-03 [1] 两种模式全真跑）。

**checkpointer 与线程**：`checkpointer=InMemorySaver()` + `config={"configurable": {"thread_id": "..."}}`——同 thread_id 的多次 invoke 共享消息状态，`get_state(cfg)` 拿状态快照（EX-42-02 实测 4 条消息）。

**流式三种粒度**（实测）：`stream_mode="values"`（每步推全量状态）、`"updates"`（每节点推增量写入）、`"messages"`（逐 token chunk + 节点元数据）；异步版 `astream(..., stream_mode="messages")` 是 SSE 服务的直接素材。

**Java 对照**：`create_agent` ≈ 一个预置好的"模型-工具"状态机模板（Spring StateMachine 里你也要先画图再填节点）；middleware ≈ HandlerInterceptor；thread_id ≈ sessionId；`stream_mode="messages"` ≈ SSE 的事件源。

## 42.4 最小完整示例：循环、持久化、流式、护栏与考古

**EX-42-01 | 示例代码/ch42_lc_agent/ex_42_01_agent_minimal.py（完整可运行）**

```python
# EX-42-01 | create_agent 最小工具循环：框架替你做了什么 | 运行: python3 示例代码/ch42_lc_agent/ex_42_01_agent_minimal.py
"""完整可运行（离线，Fake 脚本驱动）：
用 langchain 1.4.6 的 create_agent（当前推荐方式）跑通"模型点名工具→执行→回传→最终回答"，
逐条打印消息序列；对照 EX-24-03 裸 SDK 手写的六步循环，逐项标出框架接管的步骤。

为什么需要 FakeToolChatModel 子类：create_agent 会调用 model.bind_tools(tools)，
而 GenericFakeChatModel 没实现 bind_tools（真实报错见本文件 [0]）——
这本身就是教学点：绑定工具是"模型与框架的契约"，Fake 模型要显式声明支持。
"""
from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Any

from langchain.agents import create_agent
from langchain_core.language_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool


class FakeToolChatModel(GenericFakeChatModel):
    """教学用假模型：按脚本顺序吐 AIMessage（官方测试模型 + bind_tools 支持）。

    bind_tools 返回 self：表示"工具已声明"（真实模型会在此把工具 schema 注入请求）。
    """

    bind_calls: list[list[str]] = []

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> Any:
        self.bind_calls.append([getattr(t, "name", str(t)) for t in tools])
        return self


@tool
def get_weather(city: str) -> dict:
    """查询指定城市当日天气。"""
    db = {"北京": {"weather": "晴", "temp": 26}}
    return {"city": city, **db[city]}


def main() -> None:
    print("[0] 不实现 bind_tools 会怎样（真实报错，42.3 详述）：")
    naked = GenericFakeChatModel(messages=iter([AIMessage(content="x")]))
    try:
        naked.bind_tools([get_weather])
    except NotImplementedError as e:
        print(f"    NotImplementedError（异常消息为空——基类只声明契约，不解释）：{e!r}")

    print("\n[1] create_agent（当前推荐方式，签名含 model/构建工具/system_prompt/middleware/...")
    print("    response_format/state_schema/checkpointer 等——运行记录见 part07.md）：")
    script = iter([
        AIMessage(content="", tool_calls=[
            {"id": "call_001", "name": "get_weather", "args": {"city": "北京"}, "type": "tool_call"}]),
        AIMessage(content="北京今天晴，26℃，适合出行。"),
    ])
    model = FakeToolChatModel(messages=script)
    agent = create_agent(
        model=model,
        tools=[get_weather],
        system_prompt="你是天气助手，回答简洁。",
    )
    print(f"    返回类型 = {type(agent).__name__}（一个 LangGraph 编译图，第八部分的主角）")
    result = agent.invoke({"messages": [HumanMessage(content="北京天气怎么样？")]})
    print(f"    state keys = {list(result.keys())}")
    print(f"    bind_tools 调用记录 = {model.bind_calls}（每次模型节点执行都会绑定一次）")

    print("\n[2] 最终消息序列（框架维护的对话状态）：")
    for m in result["messages"]:
        tc = getattr(m, "tool_calls", None)
        extra = f" tool_calls={[c['name'] for c in tc]}" if tc else ""
        if type(m).__name__ == "ToolMessage":
            extra = f" tool_call_id={m.tool_call_id}"
        print(f"    {type(m).__name__:<12} {str(m.content)[:44]}{extra}")

    print("\n[3] 对照 EX-24-03（裸 SDK 六步手写循环）——框架替你做了什么：")
    print("    ① 声明工具        ：@tool 自动生成 schema，create_agent 自动 bind_tools（本例 bind 调用了 2 次）")
    print("    ② 解析 tool_calls ：AIMessage.tool_calls 已是结构化 dict（裸 SDK 要 json.loads arguments）")
    print("    ③ assistant 回写  ：框架自动把'发起调用的消息'写回状态（裸 SDK 手动 append，最易漏）")
    print("    ④ 执行工具        ：框架按 name 路由并调用（裸 SDK 手写 if/elif 分发）")
    print("    ⑤ tool 消息回传   ：框架生成 ToolMessage 并配对 tool_call_id（裸 SDK 手动构造 dict）")
    print("    ⑥ 循环与终止      ：框架判断'模型不再要点名工具'才停（裸 SDK 手写 while + finish_reason 判断）")
    print("    你仍然负责的：工具实现本身、参数权限校验、工具超时/幂等（ch54 工具治理）。")


if __name__ == "__main__":
    main()
```

```text
# 真实运行输出（离线，Fake 脚本驱动）
[0] 不实现 bind_tools 会怎样（真实报错，42.3 详述）：
    NotImplementedError（异常消息为空——基类只声明契约，不解释）：NotImplementedError()

[1] create_agent（当前推荐方式，签名含 model/构建工具/system_prompt/middleware/...
    response_format/state_schema/checkpointer 等——运行记录见 part07.md）：
    返回类型 = CompiledStateGraph（一个 LangGraph 编译图，第八部分的主角）
    state keys = ['messages']
    bind_tools 调用记录 = [['get_weather'], ['get_weather']]（每次模型节点执行都会绑定一次）

[2] 最终消息序列（框架维护的对话状态）：
    HumanMessage 北京天气怎么样？
    AIMessage     tool_calls=['get_weather']
    ToolMessage  {"city": "北京", "weather": "晴", "temp": 26} tool_call_id=call_001
    AIMessage    北京今天晴，26℃，适合出行。

[3] 对照 EX-24-03（裸 SDK 六步手写循环）——框架替你做了什么：
    ① 声明工具        ：@tool 自动生成 schema，create_agent 自动 bind_tools（本例 bind 调用了 2 次）
    ② 解析 tool_calls ：AIMessage.tool_calls 已是结构化 dict（裸 SDK 要 json.loads arguments）
    ③ assistant 回写  ：框架自动把'发起调用的消息'写回状态（裸 SDK 手动 append，最易漏）
    ④ 执行工具        ：框架按 name 路由并调用（裸 SDK 手写 if/elif 分发）
    ⑤ tool 消息回传   ：框架生成 ToolMessage 并配对 tool_call_id（裸 SDK 手动构造 dict）
    ⑥ 循环与终止      ：框架判断'模型不再要点名工具'才停（裸 SDK 手写 while + finish_reason 判断）
    你仍然负责的：工具实现本身、参数权限校验、工具超时/幂等（ch54 工具治理）。
```

**EX-42-02 | 示例代码/ch42_lc_agent/ex_42_02_agent_checkpoint_stream.py（完整可运行）**

```python
# EX-42-02 | checkpointer 持久化（thread_id 多轮）与三种流式 | 运行: python3 示例代码/ch42_lc_agent/ex_42_02_agent_checkpoint_stream.py
"""完整可运行（离线，asyncio 真实运行）：
[1] checkpointer=InMemorySaver + thread_id：跨 invoke 的对话记忆与 get_state 快照；
[2] stream 三模式实测：values（全量状态）/ updates（节点增量）/ messages（逐 token）；
[3] astream（异步逐条）——SSE 服务的直接素材（对照 ch17 SSE StreamingResponse）。
"""
from __future__ import annotations

import asyncio
from collections.abc import Iterator, Sequence
from typing import Any

from langchain.agents import create_agent
from langchain_core.language_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver


class FakeToolChatModel(GenericFakeChatModel):
    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> Any:
        return self


def main() -> None:
    print("[1] checkpointer：无它，两次 invoke 互不相识；有它，同 thread_id 共享状态：")
    agent = create_agent(
        model=FakeToolChatModel(messages=iter([
            AIMessage(content="已记住你的城市是北京。"),
            AIMessage(content="你上一轮说住在北京。"),
        ])),
        tools=[],
        system_prompt="记忆助手",
        checkpointer=InMemorySaver(),  # 内存版：教学/测试用，生产换持久化 Saver
    )
    cfg = {"configurable": {"thread_id": "user-42"}}
    r1 = agent.invoke({"messages": [HumanMessage(content="我住在北京")]}, cfg)
    print(f"    第 1 轮回答：{r1['messages'][-1].content}")
    r2 = agent.invoke({"messages": [HumanMessage(content="我刚才说住哪？")]}, cfg)
    print(f"    第 2 轮回答：{r2['messages'][-1].content}")
    snap = agent.get_state(cfg)
    print(f"    get_state 快照：{len(snap.values['messages'])} 条消息（2 人问 + 2 答都在）")
    print("    → 裸 SDK 的'历史管理'（ch27 手动截断/拼 messages）框架做成了线程状态；")
    print("      thread_id 换一个，就是另一个用户的会话（多租户隔离从配置开始）。")

    print("\n[2] stream 三模式（无工具 agent，脚本 1 条回答）：")
    stream_agent = create_agent(
        model=FakeToolChatModel(messages=iter([AIMessage(content="完整回答文本")]*3)),
        tools=[], system_prompt="x",
    )
    for state in stream_agent.stream({"messages": [HumanMessage(content="hi")]}, stream_mode="values"):
        pass  # values：每步推整个状态
    print(f"    values   ：最后一步 state.messages[-1] = {state['messages'][-1].content!r}")
    for update in stream_agent.stream({"messages": [HumanMessage(content="hi")]}, stream_mode="updates"):
        print(f"    updates  ：节点 {list(update.keys())}（增量：该节点写入的状态）")
    msg_chunks = [
        str(c.content)
        for c, _meta in stream_agent.stream({"messages": [HumanMessage(content="hi")]},
                                            stream_mode="messages")
        if str(c.content)
    ]
    print(f"    messages ：逐 token chunk = {msg_chunks}")

    print("\n[3] astream（异步流式）——SSE 接口的素材：")
    asyncio.run(astream_demo())
    print("    → FastAPI 里把每个 chunk 包装成 SSE 事件下发即可（ch17 的 StreamingResponse；")
    print("      真实模型上 chunk 是 token 级，前端打字机效果由此而来）。")


async def astream_demo() -> None:
    agent = create_agent(
        model=FakeToolChatModel(messages=iter([AIMessage(content="异步流式回答")])),
        tools=[], system_prompt="x",
    )
    chunks: list[str] = []
    async for chunk, meta in agent.astream(
        {"messages": [HumanMessage(content="hi")]}, stream_mode="messages"
    ):
        if str(chunk.content):
            chunks.append(f"{chunk.content}@{meta.get('langgraph_node')}")
    print(f"    收到：{chunks}")


if __name__ == "__main__":
    main()
```

```text
# 真实运行输出（离线，asyncio 真实运行）
[1] checkpointer：无它，两次 invoke 互不相识；有它，同 thread_id 共享状态：
    第 1 轮回答：已记住你的城市是北京。
    第 2 轮回答：你上一轮说住在北京。
    get_state 快照：4 条消息（2 人问 + 2 答都在）
    → 裸 SDK 的'历史管理'（ch27 手动截断/拼 messages）框架做成了线程状态；
      thread_id 换一个，就是另一个用户的会话（多租户隔离从配置开始）。

[2] stream 三模式（无工具 agent，脚本 1 条回答）：
    values   ：最后一步 state.messages[-1] = '完整回答文本'
    updates  ：节点 ['model']（增量：该节点写入的状态）
    messages ：逐 token chunk = ['完整回答文本']

[3] astream（异步流式）——SSE 接口的素材：
    收到：['异步流式回答@model']
    → FastAPI 里把每个 chunk 包装成 SSE 事件下发即可（ch17 的 StreamingResponse；
      真实模型上 chunk 是 token 级，前端打字机效果由此而来）。
```

**EX-42-03 | 示例代码/ch42_lc_agent/ex_42_03_agent_limits_legacy.py（完整可运行）**

```python
# EX-42-03 | 中间件护栏 + 历史考古：AgentExecutor 时代与迁移表 | 运行: python3 示例代码/ch42_lc_agent/ex_42_03_agent_limits_legacy.py
"""完整可运行（离线）：
[1] ModelCallLimitMiddleware：给工具循环加"步数护栏"（模型抽风狂点工具的保险丝）；
    exit_behavior='error'（抛异常）与 'end'（优雅收尾）两种模式实测；
[2] 历史考古：langchain.agents 里已没有 AgentExecutor（真实 ImportError 实测）；
    老版本经 langchain-classic 1.0.8 仍可导入（仅兼容用途）；给出迁移对照表。
"""
from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import ModelCallLimitMiddleware
from langchain_core.language_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool


class FakeToolChatModel(GenericFakeChatModel):
    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> Any:
        return self


@tool
def query_order(order_id: str) -> dict:
    """按订单号查询订单状态。"""
    return {"order_id": order_id, "status": "已签收"}


def tool_call_msg(i: int) -> AIMessage:
    """脚本条目：模型坚持再次调用同一工具（模拟真实世界的'抽风循环'）。"""
    return AIMessage(content="", tool_calls=[
        {"id": f"c{i}", "name": "query_order", "args": {"order_id": "ORD-1"}, "type": "tool_call"}])


def main() -> None:
    print("[1] 步数护栏：模型想连调 4 次工具，run_limit=2 拦下：")

    print("    exit_behavior='error'（护栏触发 → 抛异常，让调用方处理）：")
    agent_err = create_agent(
        model=FakeToolChatModel(messages=iter([tool_call_msg(i) for i in range(1, 5)])),
        tools=[query_order], system_prompt="x",
        middleware=[ModelCallLimitMiddleware(run_limit=2, exit_behavior="error")],
    )
    try:
        agent_err.invoke({"messages": [HumanMessage(content="查订单 ORD-1")]})
    except Exception as e:
        print(f"      {type(e).__name__}: {e}")

    print("    exit_behavior='end'（护栏触发 → 写一条收尾消息优雅结束）：")
    agent_end = create_agent(
        model=FakeToolChatModel(messages=iter([tool_call_msg(i) for i in range(1, 5)])),
        tools=[query_order], system_prompt="x",
        middleware=[ModelCallLimitMiddleware(run_limit=2, exit_behavior="end")],
    )
    r = agent_end.invoke({"messages": [HumanMessage(content="查订单 ORD-1")]})
    for m in r["messages"]:
        tc = getattr(m, "tool_calls", None)
        print(f"      {type(m).__name__:<12} {str(m.content)[:58]}{[c['name'] for c in tc] if tc else ''}")
    print("    → 裸 SDK 时代这个 while 循环要自己写 max_rounds（EX-24-03 没写，教材调试题里才补）；")
    print("      中间件把它变成一行声明式配置。同类还有 ToolRetryMiddleware/SummarizationMiddleware。")

    print("\n[2] 历史考古（真实导入实测，非凭记忆）：")
    try:
        from langchain.agents import AgentExecutor  # type: ignore[attr-defined]
        print("      langchain.agents.AgentExecutor 竟然可导入（请报告：环境异常）")
    except ImportError as e:
        print(f"      from langchain.agents import AgentExecutor → ImportError: {str(e)[:60]}...")
    import langchain
    import langchain_classic

    print(f"      langchain {langchain.__version__} + langchain-classic {langchain_classic.__version__}:")
    from langchain_classic.agents import AgentExecutor, initialize_agent  # noqa: F401

    print("      from langchain_classic.agents import AgentExecutor, initialize_agent → 导入成功")
    print("      （langchain-classic 是 1.x 为老代码保留的兼容包，新项目禁止新用）")

    print("\n[3] 迁移对照表（教材 42.7 完整版）：")
    rows = [
        ("AgentExecutor(agent, tools, max_iterations=..)", "create_agent(model, tools, middleware=[ModelCallLimitMiddleware(...)])"),
        ("initialize_agent(tools, llm, agent=ZERO_SHOT_REACT...)", "create_agent(...)（工具调用由模型原生协议驱动，不再靠 ReAct 文本协议）"),
        ("AgentType.TOOLS / StructuredChatAgent", "create_agent + @tool（结构化参数走 schema，不走文本解析）"),
        ("load_tools([...])", "按需显式构造工具列表（@tool / 各集成包自带的 toolkit）"),
        ("agent.run(input) / agent.exec(...)", "agent.invoke({'messages': [HumanMessage(content=...)]})"),
        ("AgentExecutor(return_intermediate_steps=True)", "result['messages'] 全程可见（消息即中间步骤）"),
        ("langchain.chains.ConversationChain", "create_agent + checkpointer（持久化记忆），或 messages 列表自管"),
        ("老 create_react_agent（langgraph.prebuilt）", "langchain.agents.create_agent（1.x 的统一入口）"),
    ]
    for old, new in rows:
        print(f"      {old}\n        → {new}")


if __name__ == "__main__":
    main()
```

```text
# 真实运行输出（离线，Fake 脚本驱动；导入行为实测）
[1] 步数护栏：模型想连调 4 次工具，run_limit=2 拦下：
    exit_behavior='error'（护栏触发 → 抛异常，让调用方处理）：
      ModelCallLimitExceededError: Model call limits exceeded: run limit (2/2)
    exit_behavior='end'（护栏触发 → 写一条收尾消息优雅结束）：
      HumanMessage 查订单 ORD-1
      AIMessage    ['query_order']
      ToolMessage  {"order_id": "ORD-1", "status": "已签收"}
      AIMessage    ['query_order']
      ToolMessage  {"order_id": "ORD-1", "status": "已签收"}
      AIMessage    Model call limits exceeded: run limit (2/2)
    → 裸 SDK 时代这个 while 循环要自己写 max_rounds（EX-24-03 没写，教材调试题里才补）；
      中间件把它变成一行声明式配置。同类还有 ToolRetryMiddleware/SummarizationMiddleware。

[2] 历史考古（真实导入实测，非凭记忆）：
      from langchain.agents import AgentExecutor → ImportError: cannot import name 'AgentExecutor' from 'langchain.agents' (...
      langchain 1.4.6 + langchain-classic 1.0.8:
      from langchain_classic.agents import AgentExecutor, initialize_agent → 导入成功
      （langchain-classic 是 1.x 为老代码保留的兼容包，新项目禁止新用）

[3] 迁移对照表（教材 42.7 完整版）：
      AgentExecutor(agent, tools, max_iterations=..)
        → create_agent(model, tools, middleware=[ModelCallLimitMiddleware(...)])
      initialize_agent(tools, llm, agent=ZERO_SHOT_REACT...)
        → create_agent(...)（工具调用由模型原生协议驱动，不再靠 ReAct 文本协议）
      AgentType.TOOLS / StructuredChatAgent
        → create_agent + @tool（结构化参数走 schema，不走文本解析）
      load_tools([...])
        → 按需显式构造工具列表（@tool / 各集成包自带的 toolkit）
      agent.run(input) / agent.exec(...)
        → agent.invoke({'messages': [HumanMessage(content=...)]})
      AgentExecutor(return_intermediate_steps=True)
        → result['messages'] 全程可见（消息即中间步骤）
      langchain.chains.ConversationChain
        → create_agent + checkpointer（持久化记忆），或 messages 列表自管
      老 create_react_agent（langgraph.prebuilt）
        → langchain.agents.create_agent（1.x 的统一入口）
```

## 42.5 逐段解释：六步对照、护栏哲学与流式接线

**（1）六步对照表——本部分的收官结论**。EX-42-01 [3] 把 ch24 的六步样板逐项标了归属：②⑤⑥（解析、回写、循环）全部框架化；①④（声明、分发）在 ch39 被 `@tool` 收编。两个细节值得从输出里读出来：`bind_tools` 每次模型节点执行都会发生（实测 2 次）——这意味着工具 schema 是"每轮都发给模型"的，工具越多每轮 prompt 越贵（ch21 的滚雪球又多了一个来源）；最终消息序列里 `AIMessage → ToolMessage → AIMessage` 的顺序由框架保证，EX-24-03 里"最易漏的两步"（assistant 回写、tool 配对）在这里根本不存在出错的可能。

**（2）护栏哲学：默认值应该保守**。EX-42-03 [1] 的两种模式给出了生产语义：`exit_behavior='error'` 把失控变成一次可捕获的异常（调用方决定降级/告警）；`'end'` 把失控变成一条给用户/模型的收尾消息（优雅但可能掩盖问题）。本书建议：**对内（可重试/有监控的调用）用 error，对外（直接面向用户的会话）用 end + 记录**。工具级的另一个护栏是 ch39 的 `handle_tool_error`——两者正交：步数护栏管"循环次数"，错误处理管"单次失败"。裸 SDK 时代这些是散落的 if；现在是一行中间件。

**（3）checkpointer 改变了"历史管理"的形状**。ch27 你手动管理消息列表（截断/摘要/预算），ch42 的 checkpointer 把它变成**框架维护的线程状态**：thread_id 是会话键，`get_state` 是快照读取。注意两个仍属于你的问题：①摘要/截断策略仍要主动配置（`SummarizationMiddleware`，参数实测 `trigger/keep=('messages', 20)`），不会自动发生；②InMemorySaver 重启即失，生产换持久化 Saver（第八部分 ch47 展开 SqliteSaver 等）。

**（4）流式与异步的接线**。`stream_mode="messages"` 给的是 `(chunk, metadata)` 对（EX-42-02 [3] 实测 `异步流式回答@model`），metadata 的 `langgraph_node` 告诉你 chunk 来自哪个节点——SSE 服务里可以据此给"工具执行中/生成中"两种前端状态。`astream_events`（ch40）则是细粒度观测入口。异步侧没有新概念：`ainvoke/astream` 与 ch13 的 asyncio 语义一致，FastAPI 的 async 端点直接 `await agent.ainvoke(...)`。

**（5）response_format 的诚实边界**。签名核实它接受 Pydantic schema（生成结构化最终结果），但**需要模型实现 `with_structured_output` 协议**——Fake 模型不具备（38.3 实测 NotImplementedError；探测中脚本耗尽形态的报错也复现了这一点），因此本书只对"参数形状"负责，全链路效果请在真实模型上验证。生产建议：结构化输出优先在"模型层"解决（`with_structured_output`，ch38），Agent 层的 response_format 用于"多轮工具调用后输出 schema 化结论"的场景。

## 42.6 安装 / 文件位置 / 运行命令

```bash
pip install -r requirements.txt   # langchain==1.4.6 / langgraph==1.2.16（create_agent 依赖）

python3 示例代码/ch42_lc_agent/ex_42_01_agent_minimal.py
python3 示例代码/ch42_lc_agent/ex_42_02_agent_checkpoint_stream.py
python3 示例代码/ch42_lc_agent/ex_42_03_agent_limits_legacy.py

python3 -m pytest 测试/test_ch42.py -q
```

## 42.7 历史考古：AgentExecutor 时代与 1.x 迁移

0.x 时代的 Agent 是这样构建的（**只作考古，1.4.6 里 `from langchain.agents import AgentExecutor` 是真实 ImportError**，EX-42-03 [2] 实测；兼容包 langchain-classic 1.0.8 可导入，仅过渡用）：

```python
# 历史写法（0.x 时代；当前版本经 langchain_classic 兼容包可用，禁止新项目使用）
from langchain_classic.agents import initialize_agent, AgentType  # 老路径：langchain.agents

agent = initialize_agent(
    tools, llm, agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION, verbose=True,
)
agent.run("北京天气怎么样？")  # 老 API：run/exec
```

迁移对照表（EX-42-03 [3] 实测输出即此表）：

| 0.x 写法（历史） | 1.x 替代（本书基准） |
|---|---|
| AgentExecutor(agent, tools, max_iterations=..) | create_agent + ModelCallLimitMiddleware |
| initialize_agent(..., agent=ZERO_SHOT_REACT...) | create_agent（原生工具调用协议，不再 ReAct 文本解析） |
| AgentType.TOOLS / StructuredChatAgent | create_agent + @tool（schema 驱动参数） |
| load_tools([...]) | 显式构造工具列表（@tool / 集成包 toolkit） |
| agent.run(input) | agent.invoke({"messages": [HumanMessage(...)]}) |
| return_intermediate_steps=True | result["messages"] 全程可见（消息即步骤） |
| langchain.chains.ConversationChain | create_agent + checkpointer（或自管 messages） |
| langgraph.prebuilt 老版 create_react_agent | langchain.agents.create_agent（1.x 统一入口） |

考古的三点认知价值：①老 Agent 靠 **ReAct 文本协议**（让模型在文本里写"Thought/Action"，框架用正则解析）——理解它你就理解了为什么原生 function calling 出现后文本协议被淘汰（解析脆弱、token 浪费）；②`max_iterations` 的存在证明"循环失控"从来不是新问题，只是 1.x 把它中间件化了；③`ConversationChain` 的消失说明"记忆"从链组件变成了状态持久化（checkpointer）——ch27 的手动历史管理思想没有过时，只是有了系统级载体。

## 42.8 企业场景中的使用方式

把 EX-42-02/03 拼起来就是一个可上线的最小生产形态（项目 P2/P3 的骨架）：FastAPI async 端点 → `agent.astream(..., stream_mode="messages")` → SSE 下发；请求头里的用户身份映射成 `thread_id`（会话隔离）与工具层的租户校验；middleware 列表固化四件套——`ModelCallLimitMiddleware`（步数）、`ToolRetryMiddleware`（网络抖动重试，实测参数含退避与抖动）、`SummarizationMiddleware`（长会话压缩）、`HumanInTheLoopMiddleware`（高危工具审批，接第八部分 interrupt）。Java 侧照旧只见 REST/SSE；运维侧用 `astream_events` 把每轮模型调用、每次工具执行落成结构化日志（ch60 的成本与观测）。

## 42.9 练习

**基础 1**：默写 create_agent 的六个核心参数（本书用到的）与返回类型。

**基础 2**：`bind_tools` 在一次 agent.invoke 里被调用几次？为什么？

**代码 1**：把 EX-42-02 的记忆实验改造成 pytest：同 thread_id 问两次，断言第 2 次回答基于第 1 轮内容；换 thread_id 断言"互不相识"。

**代码 2**：给 EX-42-01 的 agent 加 `ModelCallLimitMiddleware(run_limit=1, exit_behavior="end")`，脚本让模型先点一次工具再收尾——运行并解释：为什么这次护栏没有触发？（提示：护栏统计的是"模型调用次数"还是"工具调用次数"？用 run_limit 与 thread_limit 两个参数的文档语义验证你的理解。）

**调试题**：生产上 agent 偶发把同一个工具以相同参数调用 3 次后才收尾。给出至少三个排查方向与对应对策。

### 参考答案

**基础 1**：model / tools / system_prompt / middleware / checkpointer / response_format（另有 state_schema/context_schema/store/interrupt_*/debug/name/cache/transformers）；返回 `CompiledStateGraph`。

**基础 2**：与"模型节点执行次数"一致（本例 2 次：工具轮 + 最终轮）——每次执行都要把（可能变化的）工具清单与配置重新绑定进请求。

**代码 1**（要点）：复用 EX-42-02 构造；`assert "北京" in r2[...].content`；新 thread_id 下第 1 轮脚本重启（注意 Fake 脚本是模型实例级的，新会话要新实例或循环模型）。

**代码 2**（要点）：未触发。`run_limit` 限制的是**模型调用次数**，"点一次工具 + 收尾"共 2 次模型调用，超限值是 1 时其实会触发——若你的实验没触发，说明脚本只有 1 次模型调用（工具轮与回答合并）；把 run_limit 设为 2 观察 `error` 模式在第 3 次模型调用前抛 `ModelCallLimitExceededError`。thread_limit 则按"整个线程生命周期"计数。

**调试题**：① 工具返回信息含糊（模型"再试一次看看"）——把错误结构化为"原因+建议"；② 工具偶发超时被重试放大——ToolRetryMiddleware 的退避参数核对 + 上游幂等键；③ 模型温度过高/指令不清导致重复规划——降温、强化 system_prompt 的"同一参数勿重复调用"；④ 护栏缺失或 run_limit 过大——降到业务可承受值并接告警；⑤ 每轮结果未正确进状态（极罕见，框架已处理）——升级版本并跑本书测试基线。

## 42.10 自测检查表

- 我能默写 create_agent 的参数表与返回类型，并解释每个本书用到参数的作用。
- 我能逐项说出"六步闭环"中框架接手的部分与我保留的部分（工具实现/权限/幂等）。
- 我能解释 bind_tools 的调用时机与 Fake 模型需要子类补齐它的原因。
- 我能配置 ModelCallLimitMiddleware 的两种 exit_behavior 并说出各自的适用场景。
- 我能用 checkpointer + thread_id 实现多轮记忆与快照读取，说出 InMemorySaver 的边界。
- 我能演示三种 stream 模式并说出 messages 模式与 SSE 的接线方式。
- 我能按迁移表把 AgentExecutor 代码升级到 create_agent，并说出 ReAct 文本协议被淘汰的原因。

## 42.11 面试追问

**[模拟题] 1：create_agent 和直接手写 LangGraph 图，怎么选？**
考查点：抽象层次。合格回答：标准"模型↔工具循环"用 create_agent（少写一张图、护栏开箱即用）；需要自定义节点/条件分支/并行/人工介入复杂语义时手写图（第八部分）。两者可共存：create_agent 的产物就是图，可以先快捷后展开，`state_schema` 参数还能注入自定义状态。

**[模拟题] 2：Agent 的循环失控在你们架构里是怎么防的？（多层护栏）**
考查点：纵深防御。合格回答：第一层 ModelCallLimitMiddleware（步数/调用数硬上限，error 模式告警）；第二层工具级 handle_tool_error 把可恢复失败回传模型自纠；第三层 recursion_limit（config）；第四层外围——幂等工具、审批型工具（HumanInTheLoop）、成本观测（usage 逐轮落表）。强调"模型侧降温/提示词"只是软手段，硬护栏必须在代码层。

**[模拟题] 3：把 Agent 的每次执行做成可恢复的，需要哪些要素？**
考查点：持久化语义（为第八部分铺垫）。合格回答：checkpointer（每步状态快照）+ thread_id（会话键）+ 幂等的工具（恢复时可能重放副作用）+ 中断点（interrupt_before/after，审批场景）。恢复语义的细节（resume、状态回放、时间旅行）是 LangGraph 的主题——本部分只要求说清"状态在框架手里、恢复才有可能"。

> 📌 本章待核实项：`response_format` 在 Fake 模型上无法全链路验证（Fake 未实现结构化输出协议），真实模型行为以官方文档与实测为准；`context_schema` 依赖注入与 `store` 的用法未在本书演示；`interrupt_before/after` 的人工介入语义属第八部分（ch48）内容，此处仅列参数。

---

# 第七部分小结：一张"框架替你做了什么"总账

| 能力 | 裸 SDK（第四部分） | LangChain（本部分） | 章节 |
|---|---|---|---|
| 消息结构 | 手拼 dict，role 靠字符串 | 消息对象 + 结构化 tool_calls | ch38 |
| 提示词 | f-string 手拼 | 模板对象（变量声明 + 可选占位） | ch38 |
| 结构化输出 | response_format + 手动回退 | with_structured_output / PydanticOutputParser | ch38 |
| 工具声明与分发 | JSON Schema + if/elif 双份代码 | @tool 一份声明 | ch39 |
| 工具错误 | 手写 try/except 转 JSON | handle_tool_error 三策略 | ch39 |
| 组合方式 | 手写组装函数 | LCEL 管道（batch/stream/async/config 免费获得） | ch40 |
| RAG 组件 | 全手写 | Document/Splitter/VectorStore/Retriever | ch41 |
| 工具循环 | 六步手写 while | create_agent（一步构建 + 中间件护栏） | ch42 |
| 多轮记忆 | 手动管理 messages | checkpointer + thread_id | ch42 |

**仍然永远属于你的**：token 预算与成本（ch21/ch60）、工具权限与审计（ch24/ch54/ch58）、业务正确性与评估（ch18/ch28/ch35）、密钥管理（ch02/ch58）。框架接走的是样板，不是责任。

**下一步**：`create_agent` 的返回值是 LangGraph 编译图——第八部分你将亲手拆开这个图：State/Node/Edge、条件路由、interrupt 恢复、时间旅行。本部分学到的每个概念（消息状态、工具节点、checkpointer、thread_id）都会在那里以"可编程积木"的形态重逢。

# 第七部分统一待核实清单（诚实声明汇总）

1. **真实模型全链路未验证**：沙箱无 `OPENAI_API_KEY`，`ChatOpenAI.invoke`、`with_structured_output`（三种 method 的实际生成效果）、`create_agent(response_format=...)` 的真实模型行为均只有"签名/形状核实"，无真实运行记录；相应代码在教材中均已标注。
2. **`ModelRetryMiddleware` / `HumanInTheLoopMiddleware`**：构造签名已核实，运行行为未实测（retry 的退避时序、审批的 interrupt 交互属第八部分主题），使用前请按官方文档与本地实测确认。
3. **`print_ascii` / grandalf、`RunnableBranch`、`with_fallbacks`**：存在性核实，完整行为未展开实测。
4. **langchain-community sunset 后的生态迁移路径**：随官方演进，本书只对锁定版本的实测行为负责。
5. **Fake 模型行为差异**（FakeListChatModel 循环 / GenericFakeChatModel 耗尽）：对 langchain-core==1.6.12 实测；升级版本时以源码/官方发布说明复核。




