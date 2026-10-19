# 第一部分 整体认知与环境（ch01~ch03）

> 本部分回答三个问题：你要转成的这个岗位到底做什么（ch01）？动手环境怎么搭得干净、密钥怎么不进 git（ch02）？以及——从一台干净机器到程序真正跑起来，中间每一步长什么样、坏了怎么修（ch03）。
>
> 环境事实：本部分全部示例在 Python 3.14.7（沙箱）上实际运行验证，核实日期 2026-10-19；依赖版本锁定见 `requirements.txt`。代码兼容 Python 3.10+。

---

# 第 1 章 AI 应用工程师做什么

> **本章目标**：① 能向面试官说清 AI 应用工程师与算法工程师的边界；② 能背出大模型/RAG/工具调用/工作流/Agent 五种形态的区别并各举一个业务场景；③ 能对照自己的 Java 经验列出"直接迁移/需重塑/全新"三类清单。
> **前置知识**：无。本章不动手写 AI 代码。
> **学完你能做什么**：接到一个 AI 需求时，先用一张表判断它属于哪种形态、该找谁配合、大概要做什么，而不是上来就问"要不要微调"。

## 1.1 真实问题引入（Java 工程师视角的一个具体场景）

某电商平台（合成案例）的后端工程师老张，工龄 6 年，Spring Boot 熟手。周一站会，产品经理说："客服后台要加一个'智能问答'，用户问'年假怎么攒''订单到哪了'，系统要能自己答。下个月上线。"散会后老张面对一片空白：

1. 这是"调个 API"的活，还是要"训练模型"？团队没有算法同事，他要不要先学机器学习？
2. 他听说过的词——大模型、RAG、Agent、智能体、工作流、Function Calling——到底谁包含谁？先学哪个？
3. 这个功能最终的形态是什么？一个 Java 服务？一个 Python 服务？还是往现有订单系统里塞一段代码？
4. 哪些东西是"模型决定的"（他控制不了），哪些是"工程决定的"（他能控制、也必须负责）？

这四个问题，就是本章的全部内容。第 4 个问题尤其重要——它是这份工作的核心：**你控制不了模型想什么，但你必须控制程序做什么。**

## 1.2 一句话解释 + 生活类比 + 类比边界

**一句话解释**：AI 应用工程师，是把"输出不可控的模型能力"，用工程手段（检索、校验、流程、评估、监控）包装成"行为可预期的业务服务"的工程师。

**生活类比（一家餐厅）**：

- **大模型（LLM）**像一位天赋异禀的大厨：你报任何菜名他都能现做，但记性差（上下文窗口有限）、偶尔凭想象瞎编（幻觉）、按食材用量收费（token 计费）。
- **RAG（检索增强生成）**是给大厨配一个资料架：客人问到配方细节，帮厨先把菜谱翻出来递过去，大厨照着资料说，而不是凭记忆说——回答有据可查。
- **工具调用（Function Calling）**是大厨可以"点单"：他说"帮我查一下 A1001 订单"，**真正去查的是帮厨（你的程序）**，查完把小票递回去，大厨再根据小票组织语言。
- **工作流（Workflow）**是标准出餐 SOP：先冷菜后热菜、先质检后出餐，路线写在墙上的流程图里，谁当班都一样。
- **Agent（智能体）**是让大厨自己看整张任务单，自己决定先做什么后做什么、要不要叫帮厨，做完为止。

> 💡 类比边界：哪里像、哪里不像——
> ① 大厨情绪好会发挥更好，模型不是：同一输入的输出波动来自采样温度等概率机制，不是"状态好"；
> ② 资料架检索靠的是数学相似度（向量检索），不是图书馆的精确索引——"意思接近"也会被检索到，这是能力也是坑（ch33）；
> ③ Agent 的"自主"是在**有限循环内**按概率选择下一步，不是真有意图，循环必须有终止条件与预算上限（ch45/ch52）；
> ④ 工具调用的执行者是**你的程序**，模型只负责"点名"——这句话是安全设计的根基（见 1.5）。

把餐厅映射回老张的团队，分工立刻清晰：

| 餐厅角色 | 系统角色 | 谁负责 |
|---|---|---|
| 大厨 | 模型 API（服务方托管） | 模型厂商；你只能选型、调参 |
| 资料架与检索 | 向量库+检索代码 | **你**（RAG 管线的质量大头） |
| 帮厨执行 | 工具函数（查订单、查库存） | **你**（鉴权、校验、审计都在这层） |
| SOP 流程图 | 工作流编排代码 | **你**（确定性流程的可测试性） |
| 餐厅经理 | 评估、监控、降级、成本控制 | **你**（模型不可控的兜底） |

一句话记住：**模型那部分你只能"选与防"，其余全部是普通工程活——而普通工程活正是 Java 老手的主场。**

## 1.3 正式原理与准确术语

新术语按"中文（英文）+ 一句定义 + 一个例子"给出：

- **大语言模型（Large Language Model, LLM）**：在海量文本上训练出的生成式模型，按"下一个词元的概率"产出文本。例：把"把这句话翻译成英文：你好"发给模型，返回"Hello"。
- **上下文窗口（Context Window）**：模型单次能"看见"的最大 token 数上限。例：对话太长后最早的内容会被截掉，模型"忘了"开头。
- **词元（Token）**：模型处理文本的最小单位（不等于"字/词"），也是计费单位。例：一个汉字通常约 0.5~2 个 token，具体取决于分词器（ch21 实测）。
- **提示词（Prompt）**：你发给模型的全部输入内容（角色、约束、问题、资料的总和）。例："你是客服助手，仅根据以下资料回答……"。
- **检索增强生成（Retrieval-Augmented Generation, RAG）**：回答前先从知识库检索相关片段，把片段连同问题交给模型生成答案。例：把公司年假制度文档入库后，模型能答"年假可跨年结转 5 天"并给出出处。
- **工具调用（Function/Tool Calling）**：模型按你提供的函数清单，输出"函数名+参数"的结构化请求，由你的程序执行后把结果回传。例：模型输出 `query_order(order_id="A1001")`，程序查数据库后把"已发货"回传。
- **工作流（Workflow）**：步骤与分支预先由代码定义的执行路线（每步可以是普通函数，也可以是一次模型调用）。例："分类节点→按类别路由→生成节点"的工单处理流程。
- **智能体（Agent）**：以模型为决策核心的循环：观察→决策→执行工具→再观察，直到任务完成或触发终止条件。例：日志排障 Agent 自己决定"先查错误日志→再查部署记录→给出结论"。
- **幻觉（Hallucination）**：模型生成貌似合理但与事实不符内容的现象。例：一本正经地报出一个不存在的退货政策条款。

> ⚠️ 常见坑：术语混用。"Agent"在营销语境里几乎被用来称呼一切产品；本书按上面的严格定义使用——**路线是否由模型在运行时决定**是工作流与 Agent 的分水岭（ch52 给决策表）。

**学习路径与边界声明**（对应前言 0.3/0.4，这里落到本章开头老张的场景上）：

| 路径 | 顺序 | 适合谁 |
|---|---|---|
| 从头完整学习 | ch01→ch03→ch04~ch12 语言基础→ch13~ch20 工程化→卷二框架→项目 | Python 经验较少、时间充足 |
| Java 加速路径 | ch01→ch04~ch11 速读→ch13~ch20 精读→卷二全精读 | 老张这种情况：后端经验足，重点补 Python 对象模型、asyncio 与 AI 栈 |
| 面试前冲刺 | 每章 N.10/N.11→part12 全部→项目"面试讲法" | 求职窗口临近 |

边界声明三条，现在就说清楚：**① 本书不承诺任何就业结果**，目标是让你能开发、测试、讲清自己的 AI 应用；**② AI 应用工程师不是算法工程师**——预训练、SFT、LoRA 只讲到"能判断适用场景"的深度（第十一部分），不会训练模型；**③ 教学环境可运行 ≠ 生产可上线**——没有真实验证过的能力本书不会声称你有，上线差异集中在第十部分。老张接到需求的正确第一周：不学微调，先用 ch01 的对照表判断"智能问答"属于 RAG 形态，然后按 Java 加速路径推进。

## 1.4 最小完整示例：一张可背的对照表 + 五种形态的结构演示

先给可背的对照表（建议默写）：

| 形态 | 一句话定义 | 程序结构（输入→输出） | 什么时候用 | 本教材位置 |
|---|---|---|---|---|
| 大模型直调 | 提示词发给模型 API，拿回生成文本 | messages → 模型 → 回复 | 单步文本任务：改写、总结、翻译 | ch23~25 |
| RAG | 先检索资料，再把资料与问题一起交给模型 | 问题 → 检索 →（资料+问题）→ 带引用的回答 | 答案依赖私有/时效性知识 | ch30~36 |
| 工具调用 | 模型点名函数与参数，程序执行后回传结果 | 问题 → 模型点名工具 → 程序执行 → 结果回传 → 模型作答 | 需要查库、调接口、精确计算 | ch24/ch39 |
| 工作流 | 步骤与路线由代码写死（可含模型步骤） | 节点1 → 节点2 → …（路线固定） | 流程确定、要求可控可审计 | ch43~44 |
| Agent | 模型在循环里自行决定下一步直到完成 | while 未完成：决策 → 执行 → 观察 | 开放式任务、步骤无法事先写死 | ch52~56 |

下面用一个**不联网**的脚本把这五种形态的程序结构演示出来（`fake_llm` 是确定性规则函数，只示意"模型调用"的位置，没有真实模型）。

`EX-01-01 | 示例代码/ch01_concepts/ex_01_01_concept_sketches.py`（**节选**——展示核心三段，完整文件另含直调、工作流两段与 main；下方输出为完整文件的真实运行输出）：

```python
def fake_llm(messages: list[dict[str, str]]) -> str:
    """确定性假模型：永远回同样格式的字符串（仅示意调用形态）。"""
    return f"[模拟回复] 已收到：{messages[-1]['content'][:18]}…"


def demo_rag() -> None:
    """形态二：RAG。先检索资料，再把资料塞进提示词。"""
    knowledge_base: dict[str, str] = {"年假": "公司年假每年 15 天，可跨年结转 5 天。"}
    question = "年假可以跨年吗？"
    context = knowledge_base["年假"]  # 现实中是向量检索，这里是查字典示意
    reply = fake_llm([{"role": "user", "content": f"参考资料：{context}\n问题：{question}"}])
    print("   程序结构：问题 -> 检索 -> (资料+问题) -> 模型 -> 带引用的回答")
    print(f"   {reply}\n")


def demo_tool_call() -> None:
    """形态三：工具调用。模型点名要哪个函数，程序来执行。"""
    tools: dict[str, Callable[[str], str]] = {"query_order": lambda oid: f"订单 {oid}：已发货"}
    ask = "帮我查订单 A1001"
    chosen_tool, args = "query_order", "A1001"  # 现实中由模型输出，这里写死示意
    result = tools[chosen_tool](args)  # 执行者是程序，不是模型
    reply = fake_llm([{"role": "user", "content": f"工具结果：{result}\n问题：{ask}"}])
    print("   程序结构：问题 -> 模型点名工具 -> 程序执行 -> 结果回传 -> 模型作答")


def demo_agent() -> None:
    """形态五：Agent。模型在循环里自己决定下一步，直到任务完成。"""
    steps: list[str] = []
    done = False
    turn = 0
    while not done:  # 现实中有最大轮数、预算等终止条件
        turn += 1
        if turn == 1:
            steps.append("决定：调用 query_order(A1001)")
        else:
            steps.append("决定：信息够了，输出答案")
            done = True
    for s in steps:
        print(f"   第{steps.index(s) + 1}轮 {s}")
```

（此处为节选展示核心三段；文件中还有直调、工作流两段与 main，运行方式见 1.6。）真实运行输出：

```text
# 真实运行输出（python3 示例代码/ch01_concepts/ex_01_01_concept_sketches.py）
== 1. 大模型直调（LLM API）==
   程序结构：messages -> 模型 -> reply（一次往返）
   [模拟回复] 已收到：把这句话翻译成英文：你好…

== 2. RAG（检索增强生成）==
   程序结构：问题 -> 检索 -> (资料+问题) -> 模型 -> 带引用的回答
   检索到的资料：公司年假每年 15 天，可跨年结转 5 天。
   [模拟回复] 已收到：参考资料：公司年假每年 15 天，可…

== 3. 工具调用（Function Calling）==
   程序结构：问题 -> 模型点名工具 -> 程序执行 -> 结果回传 -> 模型作答
   模型点名：query_order(A1001)；执行结果：订单 A1001：已发货
   [模拟回复] 已收到：工具结果：订单 A1001：已发货
…

== 4. 工作流（Workflow）==
   程序结构：节点1 -> 节点2 -> …（路线固定，代码说了算）
   最终状态：{'ticket': '用户反馈：页面打不开', 'classify': '网络类', 'reply': '已按『网络类』走标准处理流程'}

== 5. Agent（智能体）==
   程序结构：while 未完成： 模型决定下一步 -> 执行 -> 回到循环
   第1轮 决定：调用 query_order(A1001)
   第2轮 决定：信息够了，输出答案
   目标：找出订单 A1001 的物流单号
```

## 1.5 逐段解释（关键代码段）

**`fake_llm`**：它只是占位，但它的函数签名——`messages 进、字符串出`——正是第四部分你会看到的真实模型调用形态（ch23 消息角色）。到那时，只把 `fake_llm` 换成真客户端，其余结构不变。

**`demo_rag`**：注意顺序——**先检索、后生成**。`context` 出现在发给模型的提示词里，这就是"增强生成"。真实系统里 `knowledge_base["年假"]` 换成向量检索（ch33），检索错了资料，答案必错，所以第六部分要花整整一章讲"为什么我的 RAG 答错"。

**`demo_tool_call`**：最关键的一行是 `result = tools[chosen_tool](args)`。**执行者是程序，不是模型。** 模型只输出"我想调 query_order，参数 A1001"这样的结构化意图；扣款、查库、发邮件都发生在你的代码里——所以鉴权、参数校验、审计日志都由你做（ch54），提示词里写"请不要乱调工具"不构成任何安全边界。

**`demo_agent`**：`while not done` 就是 Agent 的全部骨架。真实实现里，"决定"由模型输出，`done` 由终止条件（模型表态、最大轮数、预算）触发——没有终止条件的 Agent 是生产事故（递归限制见 ch45）。

## 1.6 安装/文件位置/运行命令（三件套）

- **安装**：无第三方依赖，纯标准库。
- **文件位置**：`示例代码/ch01_concepts/ex_01_01_concept_sketches.py`。
- **运行命令**：

```bash
cd ai_application_course
python3 示例代码/ch01_concepts/ex_01_01_concept_sketches.py
```

## 1.7 常见错误与排查

本章的"错误"更多是**认知错误**，症状出现在方案评审或上线之后：

| 症状 | 背后的错误认知 | 修复/正确认知 |
|---|---|---|
| 团队花两周标注数据想"训练个模型"做文档问答 | 把 RAG 当微调 | 先问：知识会常变吗？文档问答首选 RAG；微调解决的是"风格/格式/领域语感"，不是"新知识"（ch62 选择树） |
| 在 system prompt 里写"不得泄露内部资料"就认为安全 | 提示词=权限控制 | 提示词只是行为引导；权限过滤在代码层做（检索前过滤、接口鉴权，ch28/ch58） |
| 客服标准流程也用全自动 Agent | Agent 越自主越好 | 流程固定用工作流，可预测、可测试；Agent 只留给开放任务（ch52 决策表） |
| 把模型 API 当本地函数裸调，线上偶发拖垮线程池 | 网络调用=函数调用 | 超时、重试（指数退避）、限流、熔断是 LLM 客户端标配（ch15/ch59） |
| 期望两次调用返回一致结果做单元断言 | 模型输出=确定性函数 | 对模型输出做"结构断言"而非"内容断言"；temperature=0 也非绝对确定（ch21） |

## 1.8 企业场景中的使用方式（Spring Boot 集成视角）

在企业里，AI 能力通常做成**独立的 Python 服务**，Spring Boot 通过网络集成，而不是把模型调用塞进单体：

| 集成方式 | 适用场景 | Java 侧的对应感 |
|---|---|---|
| 同步 HTTP（REST） | 问答、分类等短任务，超时可接受 | `RestClient`/`WebClient` 调一个普通接口 |
| SSE 流式 | 打字机式回答，降低首字延迟感知 | `SseEmitter`/`WebFlux` 订阅 |
| 异步任务 + 状态查询 | 长文档入库、批量报告（分钟级） | 消息队列 + 任务表轮询的老套路 |

为什么用 Python 单独起服务而不是在 JVM 里直接封装 OpenAI HTTP 调用？技术上 JVM 当然也能调 REST API，但流式解析、工具调用循环、图编排（LangGraph）、结构化输出校验（Pydantic）等生态在 Python 侧最成熟，且模型推理相关库（如后续讲到的 embedding/检索工具链）以 Python 为第一公民。**架构分工：Java 管业务与权限，Python 管 AI 编排，中间是契约清晰的 HTTP/SSE 接口。** 这也是 P3 项目的真实形态。

> 📌 生产提示：跨服务集成时，把"模型超时、token 预算、拒答策略"写进接口契约（如 SSE 心跳、错误码），否则 Java 侧的熔断策略无从谈起（ch57/ch59）。

## 1.9 练习

基础题：

1. 用一句话分别解释五种形态，并给每种形态各写一个你所在行业（或熟悉业务）的真实候选场景。
2. 工具调用中，"执行函数的是谁"？为什么这个问题的答案决定了权限模型怎么设计？

代码题：

3. 修改 `ex_01_01_concept_sketches.py` 的 `demo_rag`：知识库再加一条"病假"记录，并让函数支持"检索不到时输出'资料库没有相关内容'"（提示：`dict.get`）。
4. 给 `demo_workflow` 增加"分类为'账务类'时先走人工审核节点"的分支逻辑（用普通 if 模拟路由）。

调试题：

5. 把 `demo_agent` 的 `while not done` 中 `turn == 1` 改成永远不满足任何 `done` 条件，运行并观察；说明真实系统里必须有哪些终止条件（至少说出 3 个）。

### 参考答案（章末折叠区）

<details>
<summary>点击展开参考答案</summary>

1. 参照 1.4 表格第二列；场景示例：直调——商品描述润色；RAG——内部制度问答；工具调用——查运单实时状态；工作流——报销单"初审→复审→支付"固定流程；Agent——"排查这个接口为什么变慢"式开放排障。
2. 执行者是**程序**（模型只点名）。因此：鉴权在函数入口做、参数用 Pydantic 校验、每次执行写审计日志、高危工具加人工审批——全部不依赖模型"自觉"。
3. 参考实现：`context = knowledge_base.get(topic)`；`if context is None: reply = "资料库没有相关内容"` 否则拼提示词。注意回答要区分"没检索到"与"检索到但答错"，二者排障方向不同（ch35）。
4. 在 `classify` 赋值后加 `if state["classify"] == "账务类": state["review"] = "人工审核"` 再进应答节点；要点：分支写死在代码里即工作流特征。
5. 程序将无限循环刷屏。真实终止条件至少：最大轮数（ch45 的 recursion_limit）、token/费用预算上限、模型明确输出"任务完成"、人工中断（ch48 interrupt）。
</details>

### 待核实

- 各形态对应的框架能力（工具调用参数 schema、Agent 循环实现细节）演进很快，选型结论请以 ch24/ch39/ch52 编写时的官方文档为准；本章不涉及具体版本 API。

## 1.10 自测检查表

- 我能不查资料说出五种形态各自的程序结构（输入→输出）。
- 我能说出工具调用里"谁执行函数"，并据此解释权限设计。
- 我能向非技术同事解释 RAG 为什么能回答"年假制度"而不用重新训练模型。
- 我能说出工作流与 Agent 的分水岭（路线由谁决定）。
- 我能列出至少 3 条"模型决定不了、必须工程兜底"的事项（超时、拒答、权限、审计……）。
- 我能说清本书的边界：学完不是算法工程师，不承诺就业（前言 0.4）。

## 1.11 面试追问

以下均为**[模拟题]**（非真题；辨认真题的方法见 part12）。

1. **[模拟题]** "给你一个企业微信机器人需求：员工发消息问制度，机器人回答。你说说你会怎么搭，每一步为什么这么选？"——考 RAG vs 直调 vs 微调的选择与成本意识。
2. **[模拟题]** "工具调用是不是模型自己去查数据库？"——考"模型点名、程序执行"的闭环与安全含义。
3. **[模拟题]** "什么情况下你会拒绝用 Agent，改用固定工作流？"——考边界意识与可测性。

---

# 第 2 章 开发环境：解释器、虚拟环境与工程配置

> **本章目标**：① 独立完成 venv 的创建/激活/退出，并说清"当前用的是哪个 Python"；② 掌握 pip 与最小 pyproject.toml、用 pydantic-settings 管理 .env 与密钥；③ 会 VSCode 断点调试，会用 logging 替代 print。
> **前置知识**：会用命令行；装好 Python 3.12+（本书在 3.14.7 上验证）。
> **学完你能做什么**：为任何新项目 3 分钟搭出隔离环境；密钥不进 git；日志有级别有格式，出事能查。

## 2.1 真实问题引入（Java 工程师视角的一个具体场景）

新人小马入职第一天，clone 了 AI 组的仓库，习惯性执行 `python3 main.py`：

```text
# 真实运行输出（本沙箱裸 venv 中复现）
Traceback (most recent call last):
  File "<string>", line 1, in <module>
    import pydantic
ModuleNotFoundError: No module named 'pydantic'
```

他去问同事，同事说"我这里好好的"。这就是 Java 世界"Maven 依赖在 pom 里写清就行"的经验失灵的时刻——Python 的默认状态是**所有包装进全局解释器**，同事的"好好的"是因为他全局里恰好装过。同一个下午，隔壁组出事故：某工程师把 `OPENAI_API_KEY=sk-xxxx` 硬编码在代码里提交，密钥进了 git 历史，被迫全部轮换并审计泄露面。本章就解决这两件事：**环境隔离**与**密钥保护**。

这两个问题在 Java 转型期特别高发，原因值得说透：Java 的依赖图由 Maven 在构建期统一仲裁，`mvn install` 产物自带完整依赖清单，"换个目录跑"感知不到；Python 没有构建期仲裁，"装在哪"由运行时的解释器决定——于是"我装过了"（装进 A 解释器）和"我运行它"（用的 B 解释器）可以毫无关系。心智切换的核心一句话：**Java 先想"构建"，Python 先想"解释器"。**

## 2.2 一句话解释 + 生活类比 + 类比边界

**一句话解释**：Python 用"解释器 + 虚拟环境 + 包索引"三件套回答"用哪个 Python、用哪套库、库从哪来"，而 `.env`/`pydantic-settings` 负责回答"密钥从哪读"。

**生活类比**：

- **虚拟环境（venv）**像给每个项目配一间**独立厨房**：灶台（解释器）、调料架（site-packages）整套拷贝，互不串味。Maven 则像全公司共用一个中央调料库（`~/.m2`），每个项目只带一张"采购清单"（pom）。
- **pip**是采购员，**PyPI**是中央批发市场（PyPI，Python Package Index）。
- **pyproject.toml**像 `pom.xml`：声明"我是谁、要什么料"，但 Python 世界**没有 Maven 那样统一的构建器**，构建后端（如 setuptools）另在 `[build-system]` 声明。
- **`.env` 文件**是员工门禁卡：卡片本身绝不能钉在墙上（提交进 git），离开公司（容器/CI）时改用门口统一发卡（环境变量注入）。

> 💡 类比边界：Maven 本地仓库是**缓存共享**——同一份 jar 全公司只存一份；venv 是**物理隔离**——每个环境各装一份完整副本，磁盘换确定性，这正是它解决"我这里好好的"的原因。pyproject.toml 只声明直接依赖，**不生成锁文件**；锁版本要靠 `pip freeze`/uv（ch03、ch20）。

再把 Maven 的心智一条条迁过来，标清"像"与"不像"：

| Maven 心智 | 迁到 Python 后 | 像不像 |
|---|---|---|
| `pom.xml` 声明依赖 | `pyproject.toml [project].dependencies` | 像（但无传递解析的统一仲裁） |
| `mvn package` 产物可移植 | Python 无统一打包，靠 venv+锁文件复刻"可移植" | 不像，需补动作 |
| `~/.m2/repository` 缓存共享 | 无共享仓库，venv 各装一份 | 不像（磁盘换确定性） |
| `mvn dependency:tree` | `pipdeptree`（ch03 实测） | 像 |
| BOM 锁版本 | `requirements-lock.txt`（pip freeze） | 像（粒度不同：BOM 管对齐，lock 管全量） |
| SNAPSHOT/版本范围 | 版本范围约束（`>=,<`） | 像（但 Python 侧建议一律 `==` 锁死） |

## 2.3 正式原理与准确术语

- **解释器（Interpreter）**：真正执行 .py 的程序本体。命令 `python3` 背后是某个具体路径下的二进制（`sys.executable` 可见）。
- **虚拟环境（Virtual Environment）**：一个目录（习惯名 `.venv`），内含指向基础解释器的链接、独立的 `site-packages` 与脚本。激活的本质是改 `PATH` 与提示符，**不修改解释器本身**。
- **site-packages**：当前环境安装第三方包的目录；`pip install` 的落点。
- **包管理器（pip）**：从包索引下载、解析依赖并安装的命令行工具。
- **包索引（Package Index）**：默认官方源 PyPI；国内可换镜像源（见 2.6，连通性未在本书环境验证）。
- **环境变量（Environment Variable）**：进程启动时由操作系统注入的键值对；`os.environ` 读取。
- **.env 文件**：按 `KEY=value` 逐行写的本地配置文件，由 pydantic-settings（依赖 python-dotenv 的解析能力）加载进进程环境语义。
- **pyproject.toml**：PEP 518/621 标准化的项目规格文件：元数据、依赖、构建后端（对应 `pom.xml` 的身份与依赖段）。
- **日志记录器（Logger）/处理器（Handler）/格式化器（Formatter）**：logging 三件套，对应 logback 的 Logger/Appender/Encoder，层级树与" propagated "机制相当于 logback 的 additivity。

两个容易混的东西先分清：**python-dotenv** 是"读 .env 文件、把键值放进进程环境"的底层库；**pydantic-settings** 在它之上做"类型转换、必填校验、优先级合并"——本书直接用后者（依赖清单里 python-dotenv 1.2.4 是它的传递依赖）。logging 的层级传播也提前说一句：子 logger（如 `demo.pay`）处理完默认会把记录**向上传播**给 `demo`、root，若 root 也配了 Handler 会出现重复行——原理同 logback 的 additivity，工程上要么只配 root，要么对子 logger `propagate = False`。

## 2.4 最小完整示例

### 2.4.1 先搞清楚"我是谁"——EX-02-01

`EX-02-01 | 示例代码/ch02_env/ex_02_01_where_am_i.py`（完整可运行）：

```python
# EX-02-01 | 运行命令: python3 示例代码/ch02_env/ex_02_01_where_am_i.py
"""确认"当前运行的是哪个解释器、哪个环境"。

排错第一步永远是先搞清楚：我调的是哪个 python、装在哪个目录、
在不在虚拟环境里。这个脚本就是把这件事打印出来。
"""
from __future__ import annotations

import sys
import sysconfig
from pathlib import Path


def describe() -> dict[str, str]:
    """收集当前解释器的关键信息。"""
    site_packages = Path(sysconfig.get_paths()["purelib"])
    return {
        "python版本": sys.version.split()[0],
        "解释器路径": sys.executable,
        "sys.prefix": sys.prefix,
        "base_prefix": sys.base_prefix,
        "是否在venv": "是" if sys.prefix != sys.base_prefix else "否（全局解释器）",
        "site-packages": str(site_packages),
    }


def main() -> None:
    for key, value in describe().items():
        print(f"{key:>14}: {value}")


if __name__ == "__main__":
    main()
```

在全局环境与 venv 内各跑一次（真实运行输出）：

```text
# 真实运行输出 1（全局环境）
      python版本: 3.14.7
         解释器路径: /root/.pyenv/versions/3.14.7/bin/python3
    sys.prefix: /root/.pyenv/versions/3.14.7
   base_prefix: /root/.pyenv/versions/3.14.7
       是否在venv: 否（全局解释器）
 site-packages: /root/.pyenv/versions/3.14.7/lib/python3.14/site-packages
```

```text
# 真实运行输出 2（/tmp/venv_demo 内）
      python版本: 3.14.7
         解释器路径: /tmp/venv_demo/bin/python
    sys.prefix: /tmp/venv_demo
   base_prefix: /root/.pyenv/versions/3.14.7
       是否在venv: 是
 site-packages: /tmp/venv_demo/lib/python3.14/site-packages
```

判定只看一行：`sys.prefix != sys.base_prefix` 即在 venv 中。**以后任何环境问题，第一步先跑它。**

### 2.4.2 venv 完整命令链（真实记录）

```bash
# 完整可运行（shell）
python3 -m venv /tmp/venv_demo
source /tmp/venv_demo/bin/activate
echo $VIRTUAL_ENV        # -> /tmp/venv_demo
which python             # -> /tmp/venv_demo/bin/python
python -m pip list
python 示例代码/ch02_env/ex_02_01_where_am_i.py
deactivate
echo $VIRTUAL_ENV        # -> 空
```

```text
# 真实运行输出（提示符为排版加入）
$ python3 -m venv /tmp/venv_demo
$ source /tmp/venv_demo/bin/activate
(venv_demo) $ echo $VIRTUAL_ENV
/tmp/venv_demo
(venv_demo) $ which python
/tmp/venv_demo/bin/python
(venv_demo) $ python -m pip list
Package Version
------- -------
pip     26.2.1
(venv_demo) $ python 示例代码/ch02_env/ex_02_01_where_am_i.py
      python版本: 3.14.7
         解释器路径: /tmp/venv_demo/bin/python
    sys.prefix: /tmp/venv_demo
   base_prefix: /root/.pyenv/versions/3.14.7
       是否在venv: 是
 site-packages: /tmp/venv_demo/lib/python3.14/site-packages
(venv_demo) $ deactivate
$ echo $VIRTUAL_ENV

```

注意 `pip list`：全新 venv 里**只有 pip 自己**（Python 3.12+ 的 venv 不再预装 setuptools），这解释了 2.1 的报错——依赖从来不会"自动有"。

**Windows 与 Linux/macOS 差异**（Windows 行未在本沙箱实测，命令以官方 venv 文档为准）：

| 操作 | Linux/macOS（bash/zsh） | Windows（cmd） | Windows（PowerShell） |
|---|---|---|---|
| 创建 | `python3 -m venv .venv` | `python -m venv .venv` | 同左 |
| 激活 | `source .venv/bin/activate` | `.venv\Scripts\activate.bat` | `.venv\Scripts\Activate.ps1` |
| 退出 | `deactivate` | `deactivate` | `deactivate` |

> ⚠️ 常见坑：PowerShell 首次激活常报"禁止运行脚本"，需 `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` 后重试（Windows 侧常见、未实测，以微软文档为准）；macOS `python` 命令可能指向旧版或不存在，统一用 `python3`。

venv 还有三个高频误区，一次说清：**① venv 能否搬走？** 不能——里面的激活脚本和元数据写死了绝对路径，换目录/换机器等于作废，正确做法是"锁文件跟着走、venv 重建"；**② 删掉 venv 安全吗？** 安全，它只是个目录，删了重装即可（依赖清单在 requirements.txt 里）——这正是"环境可再生"的设计目的；**③ `.venv` 要进 git 吗？** 绝不。进 git 的是 `requirements.txt` + `requirements-lock.txt`，他人 clone 后用三连（ch03）一分钟重建。

### 2.4.3 配置与密钥——EX-02-02（pydantic-settings 2.16.0）

`EX-02-02 | 示例代码/ch02_env/ex_02_02_settings_env.py`（完整可运行）：

```python
# EX-02-02 | 运行命令:
#   方式一（环境变量）: APP_APP_NAME=客服助手 APP_LLM_MODE=mock APP_API_KEY=demo-key-not-real python3 示例代码/ch02_env/ex_02_02_settings_env.py
#   方式二（.env 文件）: python3 示例代码/ch02_env/ex_02_02_settings_env.py 示例代码/ch02_env/.env.example
#   方式三（优先级演示）: APP_APP_NAME=命令行优先 python3 示例代码/ch02_env/ex_02_02_settings_env.py 示例代码/ch02_env/.env.example
"""用 pydantic-settings 读取配置与密钥（.env 文件 + 环境变量，密钥不进代码）。

依赖：pydantic-settings==2.16.0（见 requirements.txt）。
要点：
1. 密钥类型用 SecretStr，repr/str 自动打码，防止日志泄漏；
2. 环境变量优先级高于 .env 文件（CI/容器注入直接生效）；
3. 必填项缺失时启动即失败（fail fast），而不是跑到一半才炸。
"""
from __future__ import annotations

import sys
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置：环境变量（APP_ 前缀）> .env 文件 > 代码默认值。"""

    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=".env",  # 相对“当前工作目录”解析
        env_file_encoding="utf-8",
        extra="ignore",  # .env 里的无关变量不报错
    )

    app_name: str = "unknown-app"
    llm_mode: str = "mock"  # mock=不联网；real=真实调用
    api_key: SecretStr  # 必填：不给就拒绝启动

    def masked_key(self) -> str:
        """打码后的密钥，可以安全进日志。"""
        value = self.api_key.get_secret_value()
        return f"{value[:4]}****({len(value)} 位)"


def load_settings(env_file: Path | None = None) -> Settings:
    """加载配置；显式传入 env_file 时优先生效（用于演示与测试）。"""
    if env_file is not None:
        return Settings(_env_file=env_file)
    return Settings()


def main() -> None:
    env_file = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    settings = load_settings(env_file)
    print(f"应用名     : {settings.app_name}")
    print(f"运行模式   : {settings.llm_mode}")
    print(f"密钥打码   : {settings.masked_key()}")
    print(f"直接打印   : {settings.api_key}")  # SecretStr 自动打码


if __name__ == "__main__":
    main()
```

配套的 `.env.example`（模板，真实文件位于 `示例代码/ch02_env/.env.example`）：

```ini
# .env.example——复制为 .env 后按需修改；.env 永远不要提交进 git
APP_APP_NAME=客服助手
APP_LLM_MODE=mock
# 下面这行只是演示格式的假密钥，不是任何真实服务的密钥
APP_API_KEY=demo-key-not-real
```

三种加载方式的真实运行输出：

```text
# 真实运行输出 1：纯环境变量
$ APP_APP_NAME=客服助手 APP_LLM_MODE=mock APP_API_KEY=demo-key-not-real \
    python3 示例代码/ch02_env/ex_02_02_settings_env.py
应用名     : 客服助手
运行模式   : mock
密钥打码   : demo****(17 位)
直接打印   : **********
```

```text
# 真实运行输出 2：.env 文件
$ python3 示例代码/ch02_env/ex_02_02_settings_env.py 示例代码/ch02_env/.env.example
应用名     : 客服助手
运行模式   : mock
密钥打码   : demo****(17 位)
直接打印   : **********
```

```text
# 真实运行输出 3：优先级演示（环境变量覆盖 .env 中的同名项）
$ APP_APP_NAME=命令行优先 python3 示例代码/ch02_env/ex_02_02_settings_env.py 示例代码/ch02_env/.env.example
应用名     : 命令行优先
运行模式   : mock
密钥打码   : demo****(17 位)
直接打印   : **********
```

### 2.4.4 logging 基础——EX-02-03（对照 logback/slf4j）

`EX-02-03 | 示例代码/ch02_env/ex_02_03_logging_basics.py`（完整可运行）：

```python
# EX-02-03 | 运行命令: python3 示例代码/ch02_env/ex_02_03_logging_basics.py
"""logging 基础：级别、格式、惰性参数、异常堆栈记录（对照 logback/slf4j）。

注意两点与 Java 的差异：
1. logging 默认输出到 stderr（logback 的 ConsoleAppender 默认 stdout）；
2. 推荐惰性写法 logger.info("金额=%s", amount) 而不是 f-string：
   级别未开启时字符串拼接不会发生（等价于 slf4j 的 {} 占位符）。
"""
from __future__ import annotations

import logging

# Java: private static final Logger log = LoggerFactory.getLogger(PayService.class);
logger = logging.getLogger("demo.pay")


def configure_logging(level: int = logging.INFO) -> None:
    """一次性配置（等价于 logback.xml 做的事，这里用代码做）。"""
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )


def charge(amount: int) -> None:
    logger.debug("进入 charge，金额=%s", amount)  # 惰性 %s：级别不够时不开销
    if amount < 0:
        try:
            raise ValueError(f"金额不能为负: {amount}")
        except ValueError:
            logger.exception("下单失败，amount=%s", amount)  # 自动带堆栈
            raise
    logger.info("扣款成功 amount=%s", amount)


def main() -> None:
    configure_logging(logging.DEBUG)
    charge(100)
    try:
        charge(-1)
    except ValueError:
        logger.error("调用方收到失败，已按降级流程处理")


if __name__ == "__main__":
    main()
```

```text
# 真实运行输出（logging 默认写 stderr；时间戳为运行时刻）
01:26:14 | DEBUG    | demo.pay | 进入 charge，金额=100
01:26:14 | INFO     | demo.pay | 扣款成功 amount=100
01:26:14 | DEBUG    | demo.pay | 进入 charge，金额=-1
01:26:14 | ERROR    | demo.pay | 下单失败，amount=-1
Traceback (most recent call last):
  File "/workspace/ai_application_course/示例代码/ch02_env/ex_02_03_logging_basics.py", line 31, in charge
    raise ValueError(f"金额不能为负: {amount}")
ValueError: 金额不能为负: -1
01:26:14 | ERROR    | demo.pay | 调用方收到失败，已按降级流程处理
```

（堆栈由 `logger.exception` 自动附加，等价于 Java 里 `log.error("下单失败", e)`，但不会漏传异常对象；最后一行"调用方收到失败"是外层 `logger.error` 的普通输出——对照阅读两条 ERROR 的差别。）

与 logback/slf4j 的映射表：

| Java（slf4j/logback） | Python（logging） | 备注 |
|---|---|---|
| `LoggerFactory.getLogger(X.class)` | `logging.getLogger("demo.pay")` | 名字用点分层级 |
| `<appender>`（Console/File） | `Handler`（StreamHandler/FileHandler） | 默认 stderr，Java 默认 stdout |
| `<pattern>%d{HH:mm:ss} %-5level...` | `Formatter` 的 `%` 占位串 | `%(asctime)s` 等 |
| `{}` 占位（slf4j 惰性格式化） | `%s` 惰性参数 | 都避免无谓字符串拼接 |
| `MDC.put("traceId", ...)` | `extra`/`LoggerAdapter`/contextvars | ch17 中间件章节展开 |
| `log.error("x", e)` 打印堆栈 | `logger.exception("x")`（仅在 except 块内） | 自动附 `exc_info` |
| 级别 TRACE~ERROR | DEBUG~CRITICAL（无 TRACE） | 默认 root 级别 WARNING |

> ⚠️ 常见坑：反模式 `logger.info(f"金额={amount}")`——f-string 在**调用日志前**就完成拼接，级别未开启时白做功，还可能触发敏感值提前字符串化；工程代码一律 `%s` 惰性写法（示例中的 print 说明除外，见风格指南 C 节）。

### 2.4.5 VSCode 调试与断点思想——EX-02-04

断点的本质：让解释器在指定行把控制权交还给你，此时可查看**调用栈、每层帧的局部变量**，并可单步（Step Over/Into/Out）、继续、重启。Python 侧 VSCode 通过 debugpy 实现（Java 侧对应 JDWP/调试器）。三种必会技巧：

- **普通断点**：行号左侧点击出现红点，F5 启动。
- **条件断点**：右键断点→"编辑条件"，如 `window > len(values)`——循环里只停在可疑迭代（对应 IDEA 的 Condition 断点）。
- **日志点（Logpoint）**：不暂停只打印，如 `{i}: {result=}`——生产思维：先观察再拦截。

练习用脚本 `EX-02-04 | 示例代码/ch02_env/ex_02_04_debug_me.py`（完整可运行；文档与实现有一处**边界 bug**，先猜再用断点验证）：

```python
# EX-02-04 | 运行命令: python3 示例代码/ch02_env/ex_02_04_debug_me.py
"""VSCode 断点练习：这个程序有一处边界逻辑 bug，先读代码猜一猜，
再在 moving_average 里打断点验证你的猜想（练习题见教材 ch02 N.9）。

文档声称：window 大于序列长度时，返回"全体数据的平均"这一项。
实际行为是否一致？窗口=10 的输出会给你答案。
"""
from __future__ import annotations


def moving_average(values: list[float], window: int) -> list[float]:
    """滑动平均。window<=0 抛 ValueError；window 大于序列长度时
    按文档应返回全体平均（一项）——请用断点验证真实行为。"""
    if window <= 0:
        raise ValueError(f"window 必须为正整数，收到 {window}")
    result: list[float] = []
    for i in range(len(values) - window + 1):
        chunk = values[i : i + window]
        result.append(sum(chunk) / len(chunk))
    return result


def main() -> None:
    data = [3.0, 5.0, 8.0, 13.0, 21.0, 34.0]
    print("数据     :", data)
    print("窗口=1   :", moving_average(data, 1))
    print("窗口=2   :", moving_average(data, 2))
    print("窗口=10  :", moving_average(data, 10))


if __name__ == "__main__":
    main()
```

```text
# 真实运行输出
数据     : [3.0, 5.0, 8.0, 13.0, 21.0, 34.0]
窗口=1   : [3.0, 5.0, 8.0, 13.0, 21.0, 34.0]
窗口=2   : [4.0, 6.5, 10.5, 17.0, 27.5]
窗口=10  : []
```

窗口=10 的 `[]` 与文档"返回全体平均一项"矛盾——bug 留给 2.9 练习题 5，答案在章末（修复后真实输出也在那里）。VSCode 的 `launch.json` 参考（编辑器操作未在沙箱自动化验证，字段以 VSCode 官方文档为准）：

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "调试 moving_average",
      "type": "debugpy",
      "request": "launch",
      "program": "${workspaceFolder}/示例代码/ch02_env/ex_02_04_debug_me.py",
      "console": "integratedTerminal"
    }
  ]
}
```

## 2.5 逐段解释（关键代码段）

**EX-02-01 的判据行**：`sys.prefix` 是当前解释器认定的安装前缀；`sys.base_prefix` 是它的"基础解释器"前缀。venv 里二者不同（venv 目录 vs 真实解释器目录），全局运行时相同——这一行就是你判断"pip 装到哪去了"的探测器。

**EX-02-02 的 `SettingsConfigDict`**：
- `env_prefix="APP_"`：环境变量要带前缀（`APP_APP_NAME`→`app_name`），避免和系统变量撞名——等价于 `@ConfigurationProperties(prefix = "app")`。
- `env_file=".env"`：注意相对**当前工作目录**解析，不是相对源码文件；在项目根运行才找得到（排错见 2.7）。
- `api_key: SecretStr`：SecretStr 的 `repr`/`str` 恒为 `**********`（见真实输出），意外进日志也不泄露；取真值必须显式 `.get_secret_value()`——比 Java 里 `String apiKey` 多一道"有意泄露"的闸门。
- `api_key` 无默认值 ⇒ 必填：缺失时 `Settings()` 构造即抛 `ValidationError`，服务**起不来总比跑到一半拿 None 调 API 好**（fail fast）。
- 优先级：**环境变量 > .env 文件 > 字段默认值**（真实输出 3 演示了覆盖），对应 Java 里"启动参数 > application-{profile}.yml > 默认值"。

**EX-02-03 的两处要点**：
- `logging.getLogger("demo.pay")`：名字即层级树（`demo` 的子 logger），级别可逐层覆盖，等价 logback 的 `<logger name="demo.pay" level="...">`。
- `logger.exception(...)` 只在 `except` 块内合法使用——它读"当前异常"并附完整堆栈；等价 `log.error("msg", e)`，但更不容易漏传异常对象。

最后说"为什么 fail fast 值得当工程原则"。配置缺失有两种处理：启动时炸（pydantic-settings 的做法），或跑到第一次调用时炸（裸 `os.environ.get("API_KEY")` 返回 None 的做法）。后者意味着：错误暴露在流量里、堆栈离根因隔了 N 层、可能已经打了付费的模型调用甚至把 None 写进了下游。Java 世界你早就信奉同一件事——`@ConfigurationProperties` 的校验失败会让 Spring 启动失败，`fail fast` 不是风格，是把错误从"生产事故"挪回"开发时刻"。

## 2.6 安装/文件位置/运行命令（三件套）

**安装**（进项目目录后）：

```bash
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate.bat（未实测）
python -m pip install -r requirements.txt
```

**pip 常用命令**（全部在锁定环境中实际使用过）：

| 命令 | 作用 | 本书记录 |
|---|---|---|
| `pip install -r requirements.txt` | 按清单安装 | 全书依赖安装方式 |
| `pip install "pydantic>=2.7,<3"` | 带约束安装单个包 | 冲突演示使用过 |
| `pip list` / `pip show 包名` | 已装清单 / 单包详情 | venv 链演示 |
| `pip check` | 校验已装包的依赖一致性 | ch03 重点 |
| `pip freeze` | 导出精确版本清单 | ch03 生成锁文件 |
| `pip install -e .` | 按当前目录 pyproject 可编辑安装 | 下文演示 |

**换源**（国内加速；本书沙箱经代理直连官方 PyPI，镜像连通性**未验证**）：

```bash
# 一次性：pip install -i https://pypi.tuna.tsinghua.edu.cn/simple 包名
# 永久（写入用户级 pip 配置）：
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
```

**最小 pyproject.toml**（本教材项目采用的最小形态，在 /tmp 演示目录实测 `pip install -e .` 通过；对应 `pom.xml` 的坐标与依赖段）：

```toml
[build-system]
requires = ["setuptools>=61"]
build-backend = "setuptools.build_meta"

[project]
name = "greet"
version = "0.1.0"
description = "教材 ch02 的最小可安装包示例"
requires-python = ">=3.10"
dependencies = []
```

配合 `src/greet/__init__.py`（提供 `hello(name)` 函数），实测记录：

```text
# 真实运行输出（/tmp/pkg_demo，venv 内）
$ pip install -e .
Successfully built greet
Installing collected packages: greet
Successfully installed greet-0.1.0
$ python -c "from greet import hello; print(hello('Java 工程师'))"
你好，Java 工程师！来自 greet 包。
$ pip show greet
Name: greet
Version: 0.1.0
Summary: 教材 ch02 的最小可安装包示例
Location: /tmp/venv_demo/lib/python3.14/site-packages
Editable project location: /tmp/pkg_demo
```

`-e`（editable，可编辑安装）：装的是"指向源码的链接"而非拷贝，改源码立即生效——开发期标准姿势，对应 Maven 里"把模块加进 reactor"的体验。

**项目骨架**（本书后续沿用）：

```text
my_ai_app/
├── .venv/               # venv（绝不进 git）
├── .env                 # 本地密钥（绝不进 git）
├── .env.example         # 模板（进 git）
├── pyproject.toml
├── requirements.txt     # 直接依赖锁定
├── requirements-lock.txt # pip freeze 全量锁定
├── src/ 或 模块目录/
├── 测试/
└── 示例代码/
```

**uv 简介（选修○）**：uv 是近年流行的 Rust 实现的 Python 包/环境管理器，`pip install` 兼容命令快一个数量级，并原生支持锁文件。本书在演示日实测（版本以官方发布为准，uv 迭代快）：

```text
# 真实运行输出（沙箱演示记录，2026-10-19）
$ pip install uv && uv --version
uv 0.13.1 (x86_64-unknown-linux-gnu)
$ uv venv /tmp/uv_demo
Using CPython 3.14.7 interpreter at: /root/.pyenv/versions/3.14.7/bin/python
Creating virtual environment at: uv_demo
$ uv pip install --python /tmp/uv_demo/bin/python httpx==0.28.1
 + httpx==0.28.1
 + httpcore==1.0.9
 + idna==3.20
 + typing-extensions==4.16.0
$ /tmp/uv_demo/bin/python -c "import httpx; print(httpx.__version__)"
0.28.1
```

本书正文仍以 pip/venv 为基准（它是所有工具的公共底座），uv 可作为效率工具自行 adoption。

顺手记住 pip 的第一课，ch03 会正式展开：**相关包尽量在同一条 `pip install` 命令里一起装**（如 `pip install pydantic pydantic-settings`）——解析器只在这条命令的"事务"里保证互相兼容；分两次装，第二次就可能把第一次拖进不一致状态。

**EX 文件位置汇总**：`示例代码/ch02_env/`（含 `.env.example`）；运行命令见各 EX 首行注释。

## 2.7 常见错误与排查

**① ModuleNotFoundError（最高频）**

```text
# 真实运行输出（裸 venv 中 import pydantic）
Traceback (most recent call last):
  File "<string>", line 1, in <module>
    import pydantic
ModuleNotFoundError: No module named 'pydantic'
```

原因三选一：a) 没激活 venv（`pip` 装到了全局，运行时用的也是全局）；b) 激活的 venv 与运行用的解释器不是同一个（如 IDE 仍指向全局解释器）；c) 你的某个模块文件名恰好叫 `pydantic.py`，把真包遮蔽了。修复：先跑 EX-02-01 确认解释器与 site-packages；再 `which python && which pip`（venv 内应为 `/path/.venv/bin/…`）；最后查 `ls` 是否有同名遮蔽文件。

**② `activate: No such file or directory` / PowerShell 脚本被禁**

原因：路径打错（Windows 下是 `Scripts` 不是 `bin`），或 PowerShell 执行策略限制。修复：cmd 用 `.venv\Scripts\activate.bat`，PowerShell 先 `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`（Windows 侧命令未实测，以官方文档为准）。

**③ `ValidationError: 1 validation error for Settings / api_key: Field required`**

原因：环境变量与 `.env` 里都没有 `APP_API_KEY`。这**不是异常，是设计**：缺密钥就该拒绝启动。修复：本地复制 `.env.example` 为 `.env` 填好；CI/生产用环境变量注入。注意 `.env` 相对 CWD 解析——在错误目录运行也会"装作没找到"。

**④ pip 装到全局**

症状：明明在 venv 里 `pip install`，另一个终端 `python3 main.py` 还是 ModuleNotFoundError。定位（真实记录）：全局 `which pip3` → `/root/.pyenv/shims/pip3`，venv 激活后 → `/tmp/venv_demo/bin/pip3`。修复：养成 `python -m pip install` 写法，它保证用"当前 python"的 pip。

**⑤ 日志"不输出"**

症状：`logger.debug("...")` 没有任何输出。原因：root logger 默认级别 WARNING，DEBUG/INFO 被过滤（Java 世界里 logback root 默认 DEBUG，直觉相反）。修复：`logging.basicConfig(level=...)` 或按层级设置；且 `basicConfig` 在同一进程仅首次调用生效，重复调用不报错也不生效。

**⑥ f-string 日志（静默性能税）**

症状：高频路径 `logger.debug(f"{big_obj!r}")` 拖慢 P99。原因：字符串在级别判断前就格式化。修复：`logger.debug("%r", big_obj)` 惰性求值（见 2.4.4）。

## 2.8 企业场景中的使用方式（Spring Boot 集成视角）

| Spring Boot 习惯 | Python 侧对应 | 差异提醒 |
|---|---|---|
| `application.yml` + `@ConfigurationProperties` | `.env` + `pydantic-settings` 的 `Settings` | Python 无 profile 自动切换，用"环境变量覆盖"实现同等效果 |
| Maven profile（dev/prod） | 多个 `.env.dev/.env.prod` + 环境变量注入 | 生产推荐**只**用环境变量/KMS 注入，不用文件 |
| Jasypt/Vault 管密钥 | 环境变量 → 云 KMS/Secret Manager | SecretStr 只防"误打印"，不防"进程被读内存" |
| `logback-spring.xml` | `logging.config`（dictConfig 文件） | 多服务统一格式串，提前对齐 trace_id 字段（ch17/ch60） |
| CI 里 `mvn -B package` | CI 里 `pip install -r requirements.txt` + `pytest` | 必须在**新建 venv** 里装，防全局污染 |
| `~/.m2` 缓存共享 | 无共享缓存（可配 pip cache 目录加速） | venv 全量拷贝是设计不是缺陷 |

> 📌 生产提示：`.gitignore` 必须包含 `.env/`、`.venv/`、`__pycache__/`；`.env.example` 进 git 作为"配置契约"。密钥泄露的排查成本远高于预防成本。

多环境配置的实际组织方式，建议一步到位：仓库里只放 `.env.example`（契约）与 `requirements*.txt`（依赖契约）；本地每人一份不进 git 的 `.env`；测试/生产环境由 CI 与容器平台注入 `APP_*` 环境变量。老张团队后来把"新服务上线清单"里加了一条：检查生产容器内 `env | grep APP_`——用眼睛确认过密钥来源，比在代码里 grep `sk-` 靠谱得多。

## 2.9 练习

基础题：

1. 不运行代码，说出 `sys.prefix == sys.base_prefix` 说明什么；venv 激活改变了哪两个东西？
2. `.env` 文件与环境变量谁优先？这个设计为什么恰好适配"本地用文件、生产用注入"？

代码题：

3. 给 EX-02-02 的 `Settings` 增加字段 `request_timeout: float = 30.0`，并演示在 .env 里写 `APP_REQUEST_TIMEOUT=15.5` 后被读取（pydantic-settings 会自动做类型转换——故意写 `abc` 观察 `ValidationError`，把报错信息抄下来）。
4. 写一个 `configure_logging(level)` + `dictConfig` 等价的小实验：把 EX-02-03 改成输出到文件 `app.log`（提示 `FileHandler`），运行两次确认追加而非覆盖。

调试题：

5. 修复 EX-02-04：让 `window=10`（大于序列长度）时按文档返回全体平均一项，且 `window<=0` 仍抛 `ValueError`。修复后运行输出应为多少？

### 参考答案（章末折叠区）

<details>
<summary>点击展开参考答案</summary>

1. 相等说明"当前是全局解释器，不在 venv 中"。激活改变：`PATH`（venv 的 bin/Scripts 排到最前）与提示符前缀；解释器本体与已装包不受"激活"魔法影响——换环境本质是换了可执行文件。
2. 环境变量优先。本地开发者用 `.env` 图方便，CI/容器由平台注入环境变量——同一段代码无需改动即可跨越两种交付形态，和 Spring 的"配置外部化"同一个思想。
3. `request_timeout: float = 30.0`；写入 `APP_REQUEST_TIMEOUT=15.5` 后 `settings.request_timeout == 15.5`。写 `abc` 时报 `ValidationError`：`Input should be a valid number, unable to parse string as a number`（错误信息含字段名与输入值，这就是"运行时校验"与 Java 注解校验的区别：不启动就能在构造时发现）。
4. `logging.basicConfig(level=..., filename="app.log", format=...)` 或手动 `FileHandler("app.log", encoding="utf-8")`；FileHandler 默认追加模式（`mode="a"`），两次运行日志累积。
5. 在 `window <= 0` 判断后加：
   ```python
   if window > len(values):
       return [sum(values) / len(values)] if values else []
   ```
   修复后真实运行输出（已验证）：
   ```text
   # 真实运行输出（修复版）
   窗口=10（修复后）: [14.0]
   window=0 -> ValueError : window 必须为正整数，收到 0
   ```
   （14.0 = 六个数之和 84 ÷ 6。）
</details>

### 待核实

- Windows（cmd/PowerShell）激活命令与执行策略处理：本沙箱为 Linux，未实测，以 Python 官方 venv 文档与微软文档为准。
- pip 镜像源连通性未验证；`uv` 0.13.1 为 2026-10-19 演示快照，用法以 docs.astral.sh/uv 为准。
- VSCode debugpy 配置字段可能随编辑器版本变化，以 VSCode 官方文档为准。

## 2.10 自测检查表

- 我能 3 分钟内从零建出 venv 并装好 requirements.txt。
- 我能解释 `sys.prefix != sys.base_prefix` 的含义并跑 EX-02-01 验证。
- 我能写出最小 pyproject.toml 并用 `pip install -e .` 验证。
- 我能用 pydantic-settings 加载配置，说出三层优先级顺序。
- 我能解释 SecretStr 防什么、不防什么。
- 我能用条件断点在循环的特定迭代停下。
- 我能说出 logging 与 logback 的三个差异（默认流、占位符机制、级别集合）。

## 2.11 面试追问

均为**[模拟题]**。

1. **[模拟题]** "venv 的原理是什么？它拷贝了解释器吗？"——考 sys.prefix/base_prefix、PATH 修改、site-packages 隔离；答案要点：不拷贝解释器二进制，拷贝/链接的是环境骨架。
2. **[模拟题]** "为什么生产环境不用 .env 文件，而用环境变量注入？"——考配置外部化、密钥轮换、容器编排集成（K8s Secret）。
3. **[模拟题]** "`pip freeze` 出的锁文件和 pom 的依赖管理有什么本质区别？"——考"全量精确锁 vs 声明+传递解析"，以及 Python 侧为什么需要 venv+lock 双保险。
4. **[模拟题]** "`logger.exception` 和 `logger.error` 的区别？"——考 exc_info 与使用位置限制。

---

# 第 3 章 从干净环境跑通第一个程序

> **本章目标**：① 用一套可复制的命令序列，从干净环境到程序跑通；② 掌握 traceback 逐行阅读法；③ 会用 `pip check` 排查依赖冲突，并完整经历一次"制造冲突→定位→修复"。
> **前置知识**：ch02 的 venv/pip 操作。
> **学完你能做什么**：新机器 5 分钟跑通项目；看到任何 traceback 不慌，30 秒定位到"自己的第几行代码的什么操作"；遇到"昨天还能跑今天炸"的依赖问题有标准排查路径。**本部分验收标准**：不看资料完成"干净环境建 venv→跑程序→故意装错版本并修复"三连。

## 3.1 真实问题引入（Java 工程师视角的一个具体场景）

周五下午 5 点半，老张给 AI 服务加"导出报表"功能，顺手 `pip install pandas`（举例试验）。周一早上，客服问答服务起不来了——`ImportError`。原因：pandas 的安装把某个共享依赖拖到了不兼容版本，而**所有包装在同一个全局环境里**，谁先动谁负责。同样的剧情在 Java 世界要靠 Maven 依赖仲裁(enforcer)才能发生，在 Python 的"全局裸奔"模式下零门槛。本章给出三道防线：**隔离（venv）→ 锁定（lock）→ 校验（pip check + 体检脚本）**，以及阅读 traceback 的通用方法——因为上面所有防线失效时，你最终都要直面堆栈。

## 3.2 一句话解释 + 生活类比 + 类比边界

**一句话解释**："跑通"= 正确的解释器 × 完整的依赖 × 正确的入口，三件事都可以自动化验证；而 traceback 是异常发生时的**调用链回放**，读它的标准动作是"从最后一行往上找自己的代码"。

**生活类比**：

- **体检脚本**像飞机起飞前检查单（checklist）：不起飞任何一步含糊——Python 版本不够？依赖缺失？直接亮红灯（非零退出码），CI 拦下。
- **traceback**像电梯监控录像的逐帧回放：最底下（最后打印）的一帧是事故瞬间，往上每一帧是"前一秒谁把电梯带到这里"；`The above exception was the direct cause of...` 则是"事故引发的次生事故"回放。
- **依赖冲突**像两位房客各自要求同一间厨房装"需要 220V 的电器"和"只供 110V 的电器"——环境只有一套，先装的人赢了，后装的报警（pip 的 ERROR 提示），但**报警不等于阻止**。

> 💡 类比边界：Maven 对传递依赖会做"最近优先"仲裁并在冲突时告警，构建期就统一了版本；pip 的解析器在**同一次 install 命令内**保证一致，但**事后单独安装**与已装包的冲突只告警不阻止（本章 3.7 有真实证据）——所以 `pip check` 必须成为习惯动作。

## 3.3 正式原理与准确术语

- **traceback（调用栈回溯）**：异常发生时 Python 打印的帧序列；表头 `Traceback (most recent call last):` 表示帧按调用先后排列，**最近的在最后一行**。
- **帧（Frame）**：一次函数调用的执行现场（文件、行号、代码行、局部变量）。调试器暂停时你看到的"栈"就是它。
- **退出码（Exit Code）**：进程结束时返回 shell 的整数；0=成功，非 0=失败。CI 靠它决定流水线红绿。
- **直接依赖（Direct Dependencies）**：你在 requirements 里写明的包；**传递依赖（Transitive Dependencies）**：它们再拉进来的包。冲突绝大多数发生在传递依赖层。
- **依赖解析（Dependency Resolution）**：pip 在一次安装事务内为所有要求找一组互相兼容版本的过程；失败则整个事务中止。
- **版本约束**：`==` 精确锁、`>=,<` 区间约束；本书 requirements.txt 全部 `==` 锁定。
- **异常链（Exception Chaining）**：`raise NewError(...) from exc` 把原始异常挂到 `__cause__`，traceback 打印两段并以 `The above exception was the direct cause of the following exception:` 连接（深入语义在 ch08）。
- **当前工作目录（Current Working Directory, CWD）**：进程启动时所在的目录；代码里的相对路径（如 `"config.json"`）都以它为基准解析——**同一份代码在不同目录运行，行为可以完全不同**，这是"在我机器上跑得好好的"的经典来源之一，3.7 的 traceback 会再次见到它。

## 3.4 最小完整示例：环境体检 + 干净环境三连

`EX-03-01 | 示例代码/ch03_first_program/ex_03_01_env_check.py`（完整可运行，纯标准库）：

```python
# EX-03-01 | 运行命令: python3 示例代码/ch03_first_program/ex_03_01_env_check.py
"""第一个程序：环境体检（飞机起飞前检查单）。

做三件事：
1. 检查 Python 版本是否达到本书下限（3.10）；
2. 检查本书首批必需依赖是否装齐、各是什么版本；
3. 全部通过打印"体检通过"并以退出码 0 结束；任一失败打印缺失项
   并以退出码 1 结束（CI 与 shell 可据此拦截）。
纯标准库实现，任何 venv 里都能跑——包括"什么都没装"的干净 venv。
"""
from __future__ import annotations

import importlib.metadata
import sys

REQUIRED_MIN = (3, 10)
REQUIRED_PACKAGES = ["pydantic", "pydantic-settings", "httpx"]


def is_compatible(current: tuple[int, int], minimum: tuple[int, int]) -> bool:
    """纯函数：当前版本是否达到最低要求（元组逐位比较）。"""
    return current >= minimum


def collect_env_info(packages: list[str]) -> dict[str, str]:
    """收集解释器版本与各依赖包的安装版本；未安装记为"缺失"。"""
    info = {
        "python": ".".join(str(n) for n in sys.version_info[:3]),
        "executable": sys.executable,
    }
    for name in packages:
        try:
            info[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            info[name] = "缺失"
    return info


def main() -> int:
    info = collect_env_info(REQUIRED_PACKAGES)
    current = (sys.version_info.major, sys.version_info.minor)
    ok = True

    if not is_compatible(current, REQUIRED_MIN):
        print(f"[不通过] Python {current} 低于本书下限 {REQUIRED_MIN}")
        ok = False
    else:
        print(f"[通过] Python {info['python']} >= {REQUIRED_MIN[0]}.{REQUIRED_MIN[1]}")

    for name in REQUIRED_PACKAGES:
        version = info[name]
        if version == "缺失":
            print(f"[不通过] {name}: 缺失（请先 pip install -r requirements.txt）")
            ok = False
        else:
            print(f"[通过] {name}: {version}")

    if ok:
        print("体检通过：可以开始跑本书示例了。")
        return 0
    print("体检未通过：请先补齐上面的缺失项。")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
```

**干净环境三连**（本部分验收流程，全部真实执行过）：

```bash
# 完整可运行（shell）——从零开始的标准动作
python3 -m venv /tmp/venv_demo            # ① 建 venv
source /tmp/venv_demo/bin/activate        # ② 激活
python -m pip install -r requirements.txt # ③ 按锁定清单装依赖（联网步骤）
python 示例代码/ch03_first_program/ex_03_01_env_check.py   # ④ 体检
python 示例代码/ch03_first_program/ex_03_02_traceback_demo.py  # ⑤ 跑第一个程序（预期失败的教学脚本）
```

体检脚本两种环境的真实运行输出：

```text
# 真实运行输出 1（依赖齐全的项目环境）——退出码 0
[通过] Python 3.14.7 >= 3.10
[通过] pydantic: 2.14.1
[通过] pydantic-settings: 2.16.0
[通过] httpx: 0.28.1
体检通过：可以开始跑本书示例了。
```

```text
# 真实运行输出 2（全新 venv，只装了 pip）——退出码 1
[通过] Python 3.14.7 >= 3.10
[不通过] pydantic: 缺失（请先 pip install -r requirements.txt）
[不通过] pydantic-settings: 缺失（请先 pip install -r requirements.txt）
[不通过] httpx: 缺失（请先 pip install -r requirements.txt）
体检未通过：请先补齐上面的缺失项。
```

同一脚本、同一台机器，退出码 0/1 精确反映环境状态——这就是 CI 集成的接口。

为什么退出码值得单独讲？Java 世界里 `mvn package` 失败会非零退出，大家习惯了"命令行工具自报红绿"；但 Python 圈大量脚本默认**永远退出 0**——哪怕逻辑早已失败。老张把体检脚本接进 CI 后才意识到：`python check.py` 后面不加 `&& next_step` 的假设在 Python 里不成立，必须**显式地** `raise SystemExit(非零)` / `sys.exit(1)`。反过来说，你写的一切工程脚本（体检、迁移、数据校验）都要补上这一课：**退出码是脚本对外的唯一可靠契约**。

逐条解释三连里每条命令的目的与失败现象：

| 步骤 | 命令 | 目的 | 典型失败现象 |
|---|---|---|---|
| ① | `python3 -m venv /tmp/venv_demo` | 创建隔离环境 | 目录已存在→加 `--clear`；python3 不存在→装解释器 |
| ② | `source .../activate` | 修改当前 shell 的 PATH | 路径打错/Windows 用错脚本（ch02 表） |
| ③ | `pip install -r requirements.txt` | 按锁定清单安装 | 代理不通/版本冲突解析失败（整事务中止） |
| ④ | `python ex_03_01_env_check.py` | 体检（版本+依赖） | 退出码 1 + 明确列出缺失项 |
| ⑤ | `python ex_03_02_traceback_demo.py` | 跑通入口脚本 | 预期失败教学：退出码 1 + traceback（3.7 逐行讲） |

## 3.5 逐段解释（关键代码段）

- `is_compatible((3, 14), (3, 10))`：元组**逐位比较**（先比主版本再比次版本），恰好是版本号语义；写成纯函数（输入决定输出）是为了让 pytest 无需真环境即可测全边界（测试/test_ch03.py 正是这么做的）。
- `collect_env_info`：`importlib.metadata.version(name)` 是"查已装元数据"的标准库入口；包不存在抛 `PackageNotFoundError`，体检脚本把它翻译成 `"缺失"` 而不是崩溃——**工具脚本必须兜住预期的失败**。
- `main() -> int` + `raise SystemExit(main())`：把业务结果翻译成进程退出码，`&&`/CI/脚本都能消费；比裸 `sys.exit()` 多了可测试性（直接调用 `main()` 拿返回值断言）。
- 脚本顶部 `REQUIRED_PACKAGES` 只列"首批必需"——本书后续各部分示例会按需增补，这是"检查单跟着机型走"的思想。

## 3.6 安装/文件位置/运行命令（三件套）

- **安装**：无新增第三方依赖（体检脚本纯标准库；探针 EX-03-03 同）。
- **文件位置**：`示例代码/ch03_first_program/`（EX-03-01 体检、EX-03-02 traceback 教学、EX-03-03 导入探针）。
- **运行命令**：

```bash
python3 示例代码/ch03_first_program/ex_03_01_env_check.py
echo $?    # 0=通过；1=不通过
```

辅助工具 pipdeptree（选修○，本书在演示 venv 中实测安装 pipdeptree 4.2.8）：

```text
# 真实运行输出（venv_conflict 内）
$ python -m pipdeptree -p pydantic-settings
pydantic-settings==2.16.0
├── pydantic [required: >=2.7.0, installed: 2.14.1]
│   ├── annotated-types [required: >=0.6.0, installed: 0.8.0]
│   ├── pydantic_core [required: ==2.50.1, installed: 2.50.1]
│   │   └── typing_extensions [required: >=4.16.0, installed: 4.16.0]
│   ├── typing_extensions [required: >=4.16.0, installed: 4.16.0]
│   └── typing-inspection [required: >=0.4.4, installed: 0.4.4]
│       └── typing_extensions [required: >=4.15.0, installed: 4.16.0]
├── python-dotenv [required: >=1.2.2, installed: 1.2.4]
├── typing_extensions [required: >=4.0.0, installed: 4.16.0]
└── typing-inspection [required: >=0.4.0, installed: 0.4.4]
    └── typing_extensions [required: >=4.15.0, installed: 4.16.0]
```

对照记忆：`mvn dependency:tree` ↔ `pipdeptree`；`mvn enforcer` ↔ `pip check`；`mvn versions:display-dependency-updates` 无直接对等（pip 的 `pip list --outdated` 只列直接安装）。

## 3.7 常见错误与排查（本章重头戏）

### 3.7.1 真实 traceback 逐行阅读法

`EX-03-02 | 示例代码/ch03_first_program/ex_03_02_traceback_demo.py` 是一个**预期失败**的教学脚本（完整可运行，按 CWD 下有没有 config.json 触发三种失败）：

```python
# EX-03-02 | 运行命令: python3 示例代码/ch03_first_program/ex_03_02_traceback_demo.py
#            （本脚本预期失败，退出码 1——它是用来练习读 traceback 的）
"""教学用：制造一个真实 traceback，学会逐行阅读。

运行结果取决于当前工作目录（CWD）下有没有 config.json：
- 没有 config.json          -> FileNotFoundError（ch03 正文逐行讲解的就是它）
- config.json 内容不是 JSON -> ConfigError（异常链：raise ... from 的真实样子）
- 一切正常                  -> 又会触发除零错误（另一类经典 traceback）

请在专门的练习目录里运行，不要在项目根目录放 config.json。
"""
from __future__ import annotations

import json
from pathlib import Path


class ConfigError(Exception):
    """配置文件不可用。"""


def load_config(path: str) -> dict[str, int]:
    text = Path(path).read_text(encoding="utf-8")  # 文件不存在在这里炸
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        # 异常链：原始原因挂在 __cause__ 上，traceback 会打印两段
        raise ConfigError(f"配置文件 {path} 不是合法 JSON") from exc
    return {"timeout": int(data["timeout"])}


def ratio(timeout: int, limit: int) -> float:
    return timeout / limit


def main() -> None:
    cfg = load_config("config.json")  # 相对 CWD 解析——ch03 讲它为什么重要
    print(ratio(cfg["timeout"], 0))  # 分母写死 0：第二颗雷


if __name__ == "__main__":
    main()
```

场景 1（练习目录无 config.json）的真实运行输出：

```text
# 真实运行输出（退出码 1）
Traceback (most recent call last):
  File "/tmp/tb_practice/ex_03_02_traceback_demo.py", line 42, in <module>
    main()
    ~~~~^^
  File "/tmp/tb_practice/ex_03_02_traceback_demo.py", line 37, in main
    cfg = load_config("config.json")  # 相对 CWD 解析——ch03 讲它为什么重要
  File "/tmp/tb_practice/ex_03_02_traceback_demo.py", line 23, in load_config
    text = Path(path).read_text(encoding="utf-8")  # 文件不存在在这里炸
  File "/root/.pyenv/versions/3.14.7/lib/python3.14/pathlib/__init__.py", line 787, in read_text
    with self.open(mode='r', encoding=encoding, errors=errors, newline=newline) as f:
         ~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/root/.pyenv/versions/3.14.7/lib/python3.14/pathlib/__init__.py", line 771, in open
    return io.open(self, mode, buffering, encoding, errors, newline)
           ~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
FileNotFoundError: [Errno 2] No such file or directory: 'config.json'
```

逐行拆解（从下往上读）：

| 行 | 内容 | 含义 |
|---|---|---|
| 最后一行 | `FileNotFoundError: [Errno 2] No such file or directory: 'config.json'` | **先读这行**：异常类型 + 系统错误码 + 消息。90% 的排障从这里已经有答案 |
| 倒数第二帧 | `pathlib/__init__.py ... in open → io.open(...)` | 标准库内部帧——**不是你的错**，只是"案发现场" |
| 中间帧 | `ex_03_02_traceback_demo.py, line 23, in load_config → Path(path).read_text` | **第一处你的代码**：文件名、行号、源码行三件套齐了 |
| 顶部帧 | `line 42, in <module> → main()` | 调用链起点：脚本入口 |

三点通用要领：① `Traceback (most recent call last):` 提醒你**最近的调用在最下面**，所以从下往上读；② 跳过标准库/第三方库的帧，找第一个**你自己文件**的帧；③ `~~~~^^^` 是 Python 3.11+ 的**精确位置指示**（标出出错的表达式片段；3.10 及以下的输出没有这些波浪线，属正常差异）。

把要领固化成**四步法**，任何堆栈都这么读：

1. **读最后一行**：异常类型 + 消息，先问"这个类型告诉我什么"（FileNotFound→路径；ModuleNotFound→环境；ValidationError→数据）；
2. **往上找自己的第一个帧**：跳过所有库帧，锁定自己文件的"文件名+行号+源码行"；
3. **核对边界假设**：出错行的输入值从哪来？参数、环境、文件是否存在、类型对不对（在断点或临时 print 处验证，别猜）；
4. **有链读链**：出现 `The above exception...` 分隔句时，先看上半段找根因，再看下半段找语义。

第 3 步是 Java 老手最容易跳过的一步——堆栈只告诉你"在哪炸"，不告诉你"为什么值是那个值"，而 AI 应用里"值是模型给的"更是常态，后面第六部分的"为什么我的 RAG 答错"用的还是这套方法论。

### 3.7.2 异常链 traceback（两段式）

场景 2（config.json 内容是 `{不是json`）的真实输出：

```text
# 真实运行输出（退出码 1）
Traceback (most recent call last):
  File "/tmp/tb_practice/ex_03_02_traceback_demo.py", line 25, in load_config
    data = json.loads(text)
  ...
json.decoder.JSONDecodeError: Expecting property name enclosed in double quotes: line 1 column 2 (char 1)

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "/tmp/tb_practice/ex_03_02_traceback_demo.py", line 42, in <module>
    main()
  File "/tmp/tb_practice/ex_03_02_traceback_demo.py", line 28, in load_config
    raise ConfigError(f"配置文件 {path} 不是合法 JSON") from exc
ConfigError: 配置文件 config.json 不是合法 JSON
```

结构：**上半段是根因（JSONDecodeError），分隔句之后是业务异常（ConfigError）**，对应代码里的 `raise ... from exc`（`__cause__` 挂链）。读法不变：最终异常在最下，但要顺手扫一眼上半段找根因。没有 `from exc` 的裸 `raise ConfigError(...)` 会打印"During handling of the above exception, another exception occurred:"（隐式链），根因仍在，但语义不如显式 `from` 清楚——ch08 将展开异常链的全部规则。

场景 3（合法 JSON、分母写死 0）验证第三类经典：`ZeroDivisionError: division by zero`，退出码 1——traceback 也可能"直奔主题"没有链。

什么时候值得用异常链？判断标准一句话：**你把底层异常"翻译"成业务语义向上抛时**。`JSONDecodeError` 对调用方毫无意义（调用方关心的是"配置坏了"），直接吞掉又丢证据——`raise ConfigError(...) from exc` 同时保留语义与证据，等价于 Java 里常见的 `catch (SQLException e) { throw new OrderServiceException("下单失败", e); }`，只是 Python 里链是**语言内建**的（不写 `from` 也有隐式链），且 traceback 原生打印两段。

### 3.7.3 依赖冲突：制造→定位→修复全过程

以下全程真实执行（专用 venv `/tmp/venv_conflict`，先装好 `pydantic==2.14.1` 与 `pydantic-settings==2.16.0`，`pip check` 干净）。

**第一步：故意装旧版**（pydantic 2.14.1 声明要求 `typing-extensions>=4.16.0`，这里故意降到 4.10.0）：

```text
# 真实运行输出
$ /tmp/venv_conflict/bin/pip install typing-extensions==4.10.0
Collecting typing-extensions==4.10.0
  Downloading typing_extensions-4.10.0-py3-none-any.whl.metadata (3.0 kB)
Downloading typing_extensions-4.10.0-py3-none-any.whl (33 kB)
Installing collected packages: typing-extensions
  Attempting uninstall: typing-extensions
    Found existing installation: typing_extensions 4.16.0
    Uninstalling typing_extensions-4.16.0:
      Successfully uninstalled typing_extensions-4.16.0
ERROR: pip's dependency resolver does not currently take into account all the packages that are installed. This behaviour is the source of the following dependency conflicts.
typing-inspection 0.4.4 requires typing-extensions>=4.15.0, but you have typing-extensions 4.10.0 which is incompatible.
pydantic 2.14.1 requires typing-extensions>=4.16.0, but you have typing-extensions 4.10.0 which is incompatible.
pydantic-core 2.50.1 requires typing-extensions>=4.16.0, but you have typing-extensions 4.10.0 which is incompatible.
Successfully installed typing-extensions-4.10.0
```

注意两个教学点：命令**退出码是 0**，且最后一行写着 `Successfully installed`——**pip install 成功 ≠ 依赖一致**。ERROR 段是"事后告警"，正是 3.1 周五事故的机制。

为什么会这样？理解 pip 的**事务边界**就懂了：依赖解析只在"同一条 pip 命令"内部保证一致——这一次命令涉及的包，解析器会一起算；但"本次命令要装的包"与"环境里早已存在的其他包"之间，解析器只做**事后核对并打印告警**，不做阻止（这与 Maven 在整个 reactor 范围内统一仲裁不同）。本次演示里 `typing-extensions==4.10.0` 是新装的，而 pydantic/pydantic-core/typing-inspection 是"早已存在"，于是出现"装成功了+三条 ERROR"并存。这也解释了为什么老张周五装 pandas 没报错、周一服务才炸——炸的是"早已存在的包"在运行时的导入。

**第二步：`pip check` 定位**（退出码 1）：

```text
# 真实运行输出
$ /tmp/venv_conflict/bin/pip check
typing-inspection 0.4.4 has requirement typing-extensions>=4.15.0, but you have typing-extensions 4.10.0.
pydantic 2.14.1 has requirement typing-extensions>=4.16.0, but you have typing-extensions 4.10.0.
pydantic-core 2.50.1 has requirement typing-extensions>=4.16.0, but you have typing-extensions 4.10.0.
```

**第三步：确认运行时症状**。探针脚本 `EX-03-03 | 示例代码/ch03_first_program/ex_03_03_import_probe.py`（完整可运行，纯标准库）：

```python
# EX-03-03 | 运行命令: python3 示例代码/ch03_first_program/ex_03_03_import_probe.py
"""依赖冲突探针：逐个导入关键包，打印版本或失败原因。

用法：在"怀疑装坏了"的解释器上运行它，一次看清哪些包能导入、
版本是多少。排查思路：pip check 管元数据一致性，本探针管真实导入。
探针本身必须兜住一切异常——它就是在烂环境里跑的工具。
"""
from __future__ import annotations

import importlib
import importlib.metadata

PROBE = ["pydantic", "pydantic_settings"]


def probe(names: list[str]) -> list[str]:
    lines: list[str] = []
    for name in names:
        try:
            module = importlib.import_module(name)
            version = importlib.metadata.version(name)
            lines.append(f"[OK]   {name} {version}（模块 {module.__name__}）")
        except Exception as exc:  # noqa: BLE001 排查工具必须兜底
            lines.append(f"[FAIL] {name}: {type(exc).__name__}: {exc}")
    return lines


def main() -> None:
    for line in probe(PROBE):
        print(line)


if __name__ == "__main__":
    main()
```

在坏环境中的真实输出：

```text
# 真实运行输出（探针兜住异常，自身退出码 0）
[FAIL] pydantic: ImportError: cannot import name 'Sentinel' from 'typing_extensions' (/tmp/venv_conflict/lib/python3.14/site-packages/typing_extensions.py)
[FAIL] pydantic_settings: ImportError: cannot import name 'Sentinel' from 'typing_extensions' (/tmp/venv_conflict/lib/python3.14/site-packages/typing_extensions.py)
```

症状与元数据对上了：`cannot import name 'Sentinel'` 是"旧版 typing_extensions 缺少新版 pydantic 需要的符号"——**元数据检查（pip check）管一致性，探针管真实导入**，两者互补。

**第四步：修复并复查**：

```text
# 真实运行输出
$ /tmp/venv_conflict/bin/pip install typing_extensions==4.16.0
Successfully installed typing_extensions-4.16.0
$ /tmp/venv_conflict/bin/pip check
No broken requirements found.
$ /tmp/venv_conflict/bin/python 示例代码/ch03_first_program/ex_03_03_import_probe.py
[OK]   pydantic 2.14.1（模块 pydantic）
[OK]   pydantic_settings 2.16.0（模块 pydantic_settings）
```

**排查决策表**：

| 症状 | 第一动作 | 工具 |
|---|---|---|
| import 某包失败 | 看最后异常行是否 ImportError/ModuleNotFoundError | 探针脚本 EX-03-03 |
| 疑似版本不匹配 | 全环境一致性体检 | `pip check`（退出码可进 CI） |
| 需要画出"谁依赖谁" | 依赖树 | `pipdeptree -p 包名`（○选修） |
| 修复后要留证据 | 导出精确版本 | `pip freeze > requirements-lock.txt` |

修复后 `pip freeze` 的真实输出（这就是锁文件的来源）：

```text
# 真实运行输出
$ /tmp/venv_conflict/bin/pip freeze
annotated-types==0.8.0
pydantic==2.14.1
pydantic-settings==2.16.0
pydantic_core==2.50.1
python-dotenv==1.2.4
typing-inspection==0.4.4
typing_extensions==4.16.0
```

> ⚠️ 常见坑：`pip check` 只核对"声明的要求 vs 实际安装版本"的**元数据**一致性，不能证明运行时行为正确（例如两个包各自兼容但组合起来有 bug）；它也可能漏报通过 `.pth`/`sys.path` 注入的包。它是**低成本必做项，不是充分条件**。

## 3.8 企业场景中的使用方式（Spring Boot 集成视角）

- **CI fail-fast**：流水线第一个 Python 步骤固定为"新建 venv → `pip install -r requirements.txt` → 体检脚本 + `pip check` → pytest"，任何非零退出码即红灯——对应 Java 项目里"`mvn validate` + enforcer 规则"的位置。
- **锁文件双件套**：`requirements.txt`（直接依赖、带注释）+ `requirements-lock.txt`（`pip freeze` 全量快照）——对应 `pom.xml` 与 BOM 的关系感；Docker 构建用 lock 保证"今天构建=三个月前构建"（ch20）。
- **镜像内不用全局**：容器里也建 venv 再安装，防系统 Python 被污染（与 ch02 企业场景同源）。
- **发布前体检**：把 EX-03-01 扩展为"启动前自检"（Python 版本、核心包、密钥存在性、磁盘可写），失败即拒绝启动并输出结构化原因——这是"fail fast"从脚本到服务的自然延伸（ch61 上线检查清单的一项）。

CI 里的落点示意（伪代码，流程说明用；具体语法随 CI 平台而异）：

```yaml
# 伪代码：Python 项目 CI 的前三个步骤（fail fast 三连）
steps:
  - "python -m venv .venv && source .venv/bin/activate"
  - "python -m pip install -r requirements.txt"
  - "python 示例代码/ch03_first_program/ex_03_01_env_check.py"   # 退出码 1 即红灯
  - "pip check"                                                   # 冲突即红灯
  - "python -m pytest 测试/ -q"
```

## 3.9 练习

基础题：

1. `Traceback (most recent call last):` 的含义是什么？为什么读 traceback 要从最后一行开始？
2. `pip install` 显示 `Successfully installed` 且退出码 0，依赖就一定一致吗？用什么命令验证？

代码题：

3. 给 EX-03-01 增加第三项体检：环境变量 `APP_API_KEY` 存在性检查（提示 `os.environ`），缺失计入"不通过"——写完在"未设置变量的 shell"里跑一遍，贴出退出码。
4. 写一个 10 行以内的探针脚本 `probe_fastapi.py`，检查 `fastapi` 与 `uvicorn` 的导入与版本，仿照 EX-03-03 的 `[OK]/[FAIL]` 输出格式。

调试题：

5. 某同事的 traceback 最后一行是 `ImportError: cannot import name 'Field' from 'pydantic' (…/site-packages/pydantic/__init__.py)`，`pip check` 无输出且退出码 0。给出至少两条可能原因与对应验证动作。

### 参考答案（章末折叠区）

<details>
<summary>点击展开参考答案</summary>

1. 表头声明下方帧按调用先后排列、最近调用在最后（最下）。异常类型与消息在最后一行，信息密度最高；从下往上第一处"自己文件"的帧即修复现场。
2. 不一定。同一次安装事务内 pip 保证一致；但对"已安装的其他包"只事后告警不阻止（3.7.3 真实证据：退出码 0 与三条 ERROR 并存）。验证：`pip check`（退出码 0 且无输出才算干净）。
3. 在 `main()` 中加：
   ```python
   import os
   if not os.environ.get("APP_API_KEY"):
       print("[不通过] APP_API_KEY 未设置")
       ok = False
   else:
       print("[通过] APP_API_KEY 已设置")
   ```
   未设置时运行输出含 `[不通过] APP_API_KEY 未设置`，退出码 1（`echo $?` 验证）。
4. 结构同 EX-03-03：`PROBE = ["fastapi", "uvicorn"]` 改名即可复用其 `probe()` 逻辑；也可以直接 `from 示例代码.ch03_first_program.ex_03_03_import_probe import probe` 后 `print` 结果——复用优于复制。
5. 可能原因：a) 某处**遮蔽**——项目里有 `pydantic/` 目录或 `pydantic.py`，验证：`python3 -c "import pydantic; print(pydantic.__file__)"` 看路径是否指向项目目录；b) 装了极旧或非官方 `pydantic` 版本但元数据声明恰好满足其他包要求（pip check 查不出"符号缺失"这种运行期差异），验证：`pip show pydantic` 看版本与来源，配合 `python3 -c "import pydantic, importlib.metadata as m; print(m.version('pydantic'))"` 对照；（c 附）重装/按 requirements.txt 锁定版本后复查。此题说明 pip check 的边界——元数据一致 ≠ 运行正确。
</details>

### 待核实

- pipdeptree 的输出格式与参数随版本变化（本书实测 4.2.8）；`pip check` 的告警行为随 pip 版本可能演进（本书实测 pip 26.2.1 下"告警但安装成功"），以官方文档为准。
- `pipdeptree --warn` 模式在演示环境中混入了宿主残留包（记录于 验证报告/运行日志/part01.md），本书只采用 `-p` 过滤输出。

## 3.10 自测检查表

- 我能默写"干净环境三连"：建 venv→装依赖→体检。
- 我拿到任何 traceback，能说出三步读法（最后一行→自己的第一个帧→精确行号）。
- 我能区分"元数据冲突（pip check 报）"与"导入失败（探针报）"并说出两者关系。
- 我能制造一个依赖冲突，并用 pip check + pip freeze 完整走完"定位→修复→留证"。
- 我能解释退出码在 CI 中的作用，并写出以非零码退出的脚本。
- 我能说出 `The above exception was the direct cause of...` 对应代码里的什么写法。

## 3.11 面试追问

均为**[模拟题]**。

1. **[模拟题]** "`pip install` 成功但 `import` 失败，可能有哪些原因？"——考 3.7.1/3.9-5 的全套：没装进当前解释器、遮蔽、符号级不兼容（pip check 查不出）、CWD/命名冲突。
2. **[模拟题]** "traceback 很长，你的阅读顺序是什么？`raise ... from ...` 会改变 traceback 的结构吗？"——考从下往上 + 异常链两段式与 `__cause__`。
3. **[模拟题]** "你们项目怎么保证'三个月后的构建和今天一致'？"——考 venv + 锁文件 + CI 体检的组合拳，并能说出 pip check 的局限。
4. **[模拟题]** "体检脚本为什么要写成返回退出码的纯函数+薄 main，而不是一坨顺序语句？"——考可测试性与 CI 集成意识（测试/test_ch03.py 即示范）。
