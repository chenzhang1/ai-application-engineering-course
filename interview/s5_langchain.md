# 面试专题 5：LangChain
> 本文件是 `textbook/part12_interview.md` 第 12.{n} 节的内容分片，与正文一致（正文为合并视角）；修订请改正文后重新生成分片。
> 全部题目均为[模拟题]（含本专题末尾的"30 分钟自测"）；总体使用方法与 30 天复习计划见 [interview/README.md](README.md)。

---

## 12.5 专题五：LangChain

> 对应正文：part07（ch37~ch42）。这个专题考的是"框架素养"：不是背 API，而是能说清**框架接手了什么、留下了什么、什么时候不该用它**——以及版本意识（0.x 与 1.x 是两套答案）。

### 题 5-1 [模拟题] 你们为什么用（不用）LangChain？什么时候不该用它？

**1. 问题与考查点**：选型论证——考"决策表"而不是"站队"；能否把"要不要用框架"变成可辩护、可重评的工程决策。

**2. 常见错误回答**："业界都用。""教程是这么写的。""我们全用裸 SDK，框架都是垃圾。"——三个都是情绪不是论证；共同缺陷是说不出框架接手了什么、留下了什么、什么场景它净收益为负。

**3. 简洁合格回答**：按决策表判定（EX-37-01，判定顺序=阻断性从高到低）：① 需要人工审批/中断恢复/持久化 → 这是**状态机需求**，链表达不了，直接 LangGraph；② 单轮+单步+无工具+不换模型 → 裸 SDK，框架是纯认知开销；③ 需要工具调用循环 → `create_agent`，框架收益最大的场景（消息回写/tool_call_id 配对/循环终止样板全部接走）；④ 需要检索/换模型/多步管道 → 组件级使用（切分器/Retriever/Runnable），不引入 Agent。因为需求会漂移，决策表要做成**可执行函数**，需求评审时重跑一遍，别依赖口头结论。

**4. 深入解释**：包分工要能报出来（1.x）：langchain-core 是地基（消息/Runnable/工具协议/Fake 模型），langchain 是门面（create_agent/中间件/init_chat_model），langchain-openai 是厂商集成，langchain-community 已宣布 sunset（导入时实测警告），langchain-classic 是兼容包（装 langchain 时带入，存着老 API）。"框架替你做了什么"的标准句式（EX-37-02）：消息对象化、模板注入、统一执行协议接走了；**token 统计、业务正确性、密钥管理从来都在你这边**。对"为了以后换厂商现在就上框架"的回应：换厂商需求强度要先核实；真需要抽象时最小手段是自建薄接口层（本书 llm_client 双模式即示范）或 `init_chat_model`，不必为假设的灵活性引入整个框架。

**5. 工程案例**：见 part07 ch37 判断案例 A/B/C（分类器→裸 SDK、知识库→组件级、运维助手→create_agent）；P1 是"组件级使用"样本（只用了 text-splitters，检索自实现），P2 是"LangGraph"样本——一个仓库里三种决策的活对照。

**6. 追问与回答边界**：
- 追问 1：LangChain 和 LangGraph 的边界？——要点：组件+简单链+标准 Agent 循环 vs 状态机（持久化/恢复/人工介入）；`create_agent` 内部就是一张 LangGraph 图——两者分层不竞争。
- 追问 2：0.x 教程代码现在还能跑吗？——要点：不能，1.x 入口变了（详见题 5-6）；看到老写法先"翻译"再动手。
- 边界：各包长期维护策略（community sunset 后续）以官方发布说明为准；本书只对锁定版本（langchain 1.4.6 / langchain-core 1.6.12）的实测行为负责。

### 题 5-2 [模拟题] LCEL 的 `|` 是什么？相比手写函数组合好在哪？什么时候手写更好？

**1. 问题与考查点**：协议思维——`|` 的本质（Runnable 协议组合）与"第二消费姿势"判断标准；类型错位的真实踩坑是加分证据。

**2. 常见错误回答**："就是函数链式调用的语法糖。"——错过协议价值（batch/stream/async/config 全部继承）；或反向把 LCEL 吹成性能优化（它不是）。

**3. 简洁合格回答**：`prompt | model | parser` 产生 RunnableSequence——本质是 Runnable 协议的组合：每段实现同一套执行入口（invoke/batch/stream/ainvoke/astream），**链自动继承**——所以"换消费姿势"（要流式了、要并发批了、要注入 tags/metadata 配置了）不用改代码。附加价值：可检视（`get_prompts()` 看真实下发的 prompt、`get_graph().nodes` 看结构）、生态组件即插即用（模型/解析器/Retriever 都是 Runnable）。判断标准一句话：**会不会需要第二种消费方式**——两次纯函数调用、永远同步直调，手写更直白。

**4. 深入解释**：LCEL 不做类型适配——真实踩坑：`assign` 把整个 dict 喂给吃 str 的 Retriever，`AttributeError: 'dict' object has no attribute 'lower'`，标准解法是 `itemgetter("question") | retriever` 先把 dict 降为 str（EX-41-03 的案发现场）。RunnableConfig 是横切关注的正规通道：tags/metadata 贯穿每个节点（函数签名带 config 自动注入），asyncio 下比 ThreadLocal 安全；`recursion_limit` 也在同一通道。异常原样冒泡不包装——业务代码沿用 ch08 的异常分层。`.with_retry()`/`.with_fallbacks()` 是管道级重试/降级，参数化强但策略可定制性弱于手写，按需选。调试三板斧：get_prompts / get_graph().nodes / astream_events。

**5. 工程案例**：见 part07 ch40 三个 EX（EX-40-01 管道本质与"链也是组件"、EX-40-02 assign+Parallel+config 贯穿实测、EX-40-03 异常传播与异步流式）；ch41.5 的类型错位踩坑记录；P1 的检索**没有**走 LCEL 是有意选择（内存检索+阈值逻辑用普通函数更可测）——"不用"也是决策。

**6. 追问与回答边界**：
- 追问 1：管道中间类型怎么防错？——要点：管道写完先手动 invoke 看中间类型；关键节点用 RunnableLambda 包类型注解齐全的函数；给每段标注输入输出类型。
- 追问 2：管道里一步很慢怎么控失败影响？——要点：该步内超时+降级值；管道级 with_retry/with_fallbacks；区分可重试（网络类）与不可重试（参数类）。
- 边界：RunnableBranch 与 astream_events 自定义事件未在本书实测（导出已核实存在），以官方文档为准。

### 题 5-3 [模拟题] with_structured_output 和裸 SDK 的 response_format 什么关系？怎么选？

**1. 问题与考查点**：结构化输出的多路线光谱（与题 3-4 呼应）+封装层的价值与边界——考"知道每个抽象底下是什么"。

**2. 常见错误回答**："LangChain 才能做结构化输出，裸 SDK 不行。"——方向反了：response_format/parse 是底层能力（ch24），with_structured_output 是封装；或以为"有了结构化输出就不需要校验"——任何一层都不是终点。

**3. 简洁合格回答**：`with_structured_output(PydanticModel)` 内部走的还是模型的结构化能力，method 参数对应不同约束强度——function_calling（复用工具协议）、json_schema（严格模式）、json_mode（仅保证合法 JSON）——取值与默认随版本与厂商而异，**以所用版本的官方文档为准**。选择原则：裸 SDK 直调场景用 response_format/parse；已在 LCEL 管道里、要和 Pydantic 类无缝衔接、要跨厂商换模型时用 with_structured_output。统一兜底不变：Pydantic 校验+失败回退链（题 3-5 的三层）。

**4. 深入解释**：封装换来的三样东西：错误形态统一（ValidationError 而非原始 JSON 解析错误，`errors()` 机器可读可喂回）、模型可换（同一 Pydantic 类在不同厂商模型间迁移）、Fake 可测（离线测试链路）。约束强度光谱与题 3-4 完全同构：提示词求 JSON（最弱）→ json_mode → function_calling → json_schema 严格模式（最强，需服务端支持）。兼容性核实纪律不变——换"OpenAI 兼容"厂商时 method 支持度必须实测（题 3-8 清单）。

**5. 工程案例**：见 part07 ch38 EX-38-03（PromptTemplate+结构化输出链）；ch45.8 的"分类三段式"（schema 枚举约束→校验失败重试一次→回退 general 通道打标 `classification_fallback=true`）是"结构化输出+路由兜底"的完整样板；P2 的 hypothesize 节点走 `chat_structured` 契约（README 第 4 节第 4 条），Mock/Real 双模式同 schema。

**6. 追问与回答边界**：
- 追问 1：流式+结构化输出能同时要吗？——要点：取决于厂商支持（增量结构化流是较新能力），逐家核实；本书未实测，如实声明。
- 追问 2：模型输出枚举外的值怎么办？——要点：Pydantic 先报错→喂回重试一次→回退通道打标；别让校验异常直接炸调用方。
- 边界：method 各取值在各厂商的覆盖面变化快——面试答"给方法+以实测为准"比背取值稳。

### 题 5-4 [模拟题] 工具执行失败怎么处理？为什么不能 try/except 包住整个 Agent？

**1. 问题与考查点**：错误语义分层——"预期内失败 vs 预期外异常"的两分法；API 细节（handle_tool_error 在哪配）是"真用过"的证据。

**2. 常见错误回答**："工具函数里 try/except 返回 None。"——模型拿到 None 不知道发生了什么，循环继续空转；或外层包一个大 try/except——把业务规则失败和 bug 混为一谈，既剥夺模型自纠机会，又吞掉告警信号。

**3. 简洁合格回答**：两分法：**预期内失败**（业务规则：金额超限、枚举非法、单据不存在）抛 `ToolException` 并配置 `handle_tool_error`（str 或 callable）——异常被转成模型可读文案、作为 ToolMessage 回传，模型可自纠参数或向用户澄清，循环继续；**预期外异常**（bug、基础设施故障）让它炸出来触发监控告警，绝不吞。参数校验类失败单独配 `handle_validation_error`（模型填错参数时的同构机制）。API 细节：`handle_tool_error` 是工具**实例属性**而不是 `@tool` 装饰器参数——写成装饰器参数会 `TypeError`（真实报错，EX-39-02 实测）。

**4. 深入解释**：为什么外层大 try/except 是反模式——所有失败长一个样（模型无法区分"改一下参数就能成"和"系统坏了"），且告警信号被吞。未配置任何错误处理时，工具在 create_agent 里抛异常会让**整次 run 失败**（ToolNode 默认原样抛出）——所以"每个工具的错误策略"是部署清单项不是可选项。错误文案是给模型读的提示词："转账失败：金额超限，建议拆分或转人工审批"比 "error" 有用得多。与 ch50"错误即数据"的同族性：LangGraph 里是捕获预期异常写状态+条件边走降级——失败是合法输出。

**5. 工程案例**：见 part07 ch39——EX-39-02（三种错误策略实测）、EX-39-03（Agent 内恢复链路：ToolException 文案变 ToolMessage、循环继续、最终回答）；P2 的白名单拒绝写审计 `tool_rejected`（拒绝也是信息，README 第 7 节失败路径表）；P1 的 LLMJudge 判定失败按拒答兜底（fail-closed，宁拒不编）。

**6. 追问与回答边界**：
- 追问 1：怎么判断一个失败归哪类？——要点：问"模型知道了能不能做得更好"：能（改参数/换工具/向用户澄清）→预期内；不能（代码 bug）→预期外。
- 追问 2：工具重试和错误回传冲突吗？——要点：重试适合瞬态故障（网络抖动），回传适合业务失败；中间件 ToolRetryMiddleware（默认 max_retries=2、backoff_factor=2.0、初始 1.0s、带抖动）只对"值得重试"的错误。
- 边界：`response_format='content_and_artifact'`（内容+制品分离）等高级形态本书未实测，以官方文档为准。

### 题 5-5 [模拟题] create_agent 替你做了什么？什么时候要展开手写 LangGraph？

**1. 问题与考查点**：六步闭环的"归属感"（每一步谁做的）+护栏意识（中间件）——判断"用过框架"还是"看过框架"。

**2. 常见错误回答**："create_agent 就是个 while 循环封装，没什么。"——说不出它接走了哪六步、护栏在哪配；或不知道它返回什么类型（是一个 LangGraph 编译图）。

**3. 简洁合格回答**：`create_agent(model, tools, system_prompt, middleware, checkpointer, response_format, ...)` 返回 `CompiledStateGraph`——一个 LangGraph 编译图。它替你接走裸 SDK 手写循环的六步（EX-42-01 [3] 的对照）：① 工具 schema 声明与自动 bind_tools；② tool_calls 解析（结构化 dict，不用 json.loads）；③ assistant 消息回写（裸 SDK 最易漏）；④ 按名分发执行；⑤ ToolMessage 生成并配对 tool_call_id；⑥ 循环终止判断。护栏走中间件：ModelCallLimitMiddleware（步数保险丝，exit_behavior 可选抛错或优雅收尾）、ToolRetryMiddleware、SummarizationMiddleware（对接 ch27）、HumanInTheLoopMiddleware（工具级审批）。checkpointer+thread_id 提供跨请求记忆；stream 三模式（values/updates/messages）覆盖调试与 SSE。你仍负责：工具实现本身、权限校验、超时与幂等——模型是"点菜的人"，不是"进厨房的人"。

**4. 深入解释**：何时展开手写图——**控制流要定制**时：tools 前插审批节点、agent 后加证据评估、不同工具不同重试策略（ch46.11 的标准答案）。两者状态结构兼容、迁移平滑，常见路径是"先 create_agent，出现定制控制流需求再展开成图"。bind_tools 是模型与框架的契约点：GenericFakeChatModel 没实现它 → `NotImplementedError`（实测）——教学里三行子类补齐，这个练习本身就是理解"框架与模型的契约在哪"的最快方式。

**5. 工程案例**：见 part07 ch42 三个 EX（EX-42-01 最小循环+六步对照、EX-42-02 checkpointer 多轮+三种流式实测、EX-42-03 护栏两种 exit_behavior+历史考古）；P2 故意不用 ToolNode 而是"先落取证计划、审查后执行"的白名单节点——取证需要 plan→audit→execute 三段，是"定制控制流"的活样本。

**6. 追问与回答边界**：
- 追问 1：怎么防模型刷工具？——要点：三层——recursion_limit 硬保险丝、业务轮次计数提前收尾返回部分结果、工具侧限流（题 6-6 详述）。
- 追问 2：create_agent 的多轮记忆从哪来？——要点：checkpointer+thread_id；没有它两次 invoke 互不相识（EX-42-02 实测 4 条消息快照）。
- 边界：store/cache/transformers 等参数本书未展开，以官方文档为准；中间件清单随版本演进，以 1.4.6 实测为准。

### 题 5-6 [模拟题] 网上教程全是 AgentExecutor 和 LLMChain，还能用吗？老代码怎么迁移？

**1. 问题与考查点**：版本意识与迁移能力——面试官用它判断"你的知识是哪个年代的"；能否给出有纪律的迁移路径而不是"全部重写"。

**2. 常见错误回答**："能跑就行。"——0.x 写法在 1.x 里导入直接失败：`ImportError: cannot import name 'AgentExecutor' from 'langchain.agents'`（EX-42-03 实测复现）；或反向"全部重写"——没有存量风险意识。

**3. 简洁合格回答**：不能直接用。1.x 的 `langchain.agents` 只有 `create_agent`/`middleware` 等新入口，老 API 全部搬进兼容包 langchain-classic（维护老代码可 `from langchain_classic.agents import AgentExecutor` 过渡，但**不在兼容包上叠加新功能**）；LLMChain/顺序链被 LCEL 管道替代（`prompt | model | parser`）；initialize_agent 的 ReAct 文本协议时代结束，迁移到 create_agent。迁移对照速查：LLMChain→prompt|model|parser；AgentExecutor→create_agent；@tool 基本平移；带状态/审批的老链→评估是否直接上 LangGraph。

**4. 深入解释**：迁移纪律五步：① 老代码在兼容包下先跑通、锁定当前行为；② 用评估集/golden set 锁输出（Prompt 变了要能看见）；③ 逐条替换为 1.x 入口（一次一条，别大爆炸）；④ 每步跑回归；⑤ 删除兼容依赖。"看到任何 0.x 教程先对照迁移表翻译再动手"是团队纪律；识别 0.x 的特征：`from langchain.chains import`、initialize_agent、zero_shot_react_description。

**5. 工程案例**：见 part07 ch37.7 错 1/错 2 与 ch42.7 的迁移表；EX-42-03 的真实 ImportError 与 langchain-classic 1.0.8 兼容导入实测——两个报错都是"写作过程真实踩中"，可以放心引用。

**6. 追问与回答边界**：
- 追问 1：为什么 1.x 做这么大的破坏性重构？——要点：给方向性答案（收敛到 LangGraph 执行引擎与 Runnable 协议、消除 0.x 多套并行的抽象），具体演进史以官方发布说明为准，不编造动机。
- 追问 2：锁定版本怎么升级？——要点：整组一起升（core/主包/厂商集成），契约测试先跑（ch51.8 的做法：锁关键报错文案与默认值，升级先红）。
- 边界：本书只对 1.4.6/1.6.12 实测行为负责；官方迁移指南以 docs.python.langchain.com 为准。

### 专题五 · 30 分钟自测（模拟口试）

> 用法：同前。本专题评分重点：每题都要出现"框架接手了什么/留下了什么"的归属分析——只报 API 名字不给归属的，按背题处理。

1. **[模拟题] 口头背出 ch37 决策表的四个输出与判定顺序，并解释排序理由。** 评分要点——审批恢复→单轮单步→工具循环→检索/换模型管道；理由是"成本从不可逆到可逆"（状态机需求链表达不了排最前）。
2. **[模拟题] 用"会不会需要第二种消费方式"分析你最近一个脚本该不该用 LCEL。** 评分要点——判断标准本身+协议清单（invoke/batch/stream/ainvoke/astream+config）；能讲 itemgetter 类型对齐的踩坑加分。
3. **[模拟题] handle_tool_error 三种取值各是什么行为？哪种让循环继续？** 评分要点——None（向上抛）/str（固定文案）/callable（加工文案）；str 与 callable 让失败变 ToolMessage、循环继续；补"handle_validation_error 拦参数类失败"与"实例属性不是装饰器参数"加分。
4. **[模拟题] create_agent 接走了六步里的哪六步？你保留的责任是什么？** 评分要点——schema+bind/解析/assistant 回写/分发/ToolMessage 配对/循环终止；保留：工具实现、权限校验、超时幂等；说出返回类型是 CompiledStateGraph。
5. **[模拟题] 给一段 0.x 代码（LLMChain+AgentExecutor），口头翻译成 1.x 等价写法。** 评分要点——LLMChain→prompt|model|parser；AgentExecutor→create_agent；迁移五步纪律（锁定行为→评估集→逐条替换→回归→删兼容包）。

---
