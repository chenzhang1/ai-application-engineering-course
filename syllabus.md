# 教学大纲（syllabus）

> 读者：有 Spring Boot/SQL/后端工程经验的 Java 开发者。目标：可维护的 Python AI 应用开发 + 面试能力。
> 标注：★必学 / ☆建议掌握 / ○进阶选修。章号 N 对应 textbook/partNN_*.md、examples/chNN_*、tests/test_chNN*。

## 卷一 打地基（第一~三部分）

### 第一部分 整体认知与环境（part01，约 12k 字）
- ch01 AI 应用工程师做什么：职责边界、与算法工程师区别、大模型/RAG/Agent/工作流/工具调用一张对照表、Java 经验迁移地图、学习路径与边界声明
- ch02 开发环境：python/venv/pyproject.toml（含 uv 简介○）、.env 与密钥、pip 换源、项目骨架、VSCode 调试断点、logging 基础
- ch03 从零跑通第一个程序 + 异常堆栈阅读法 + 依赖冲突排查（pip check、pipdeptree○）
- 验收：不看资料完成"干净环境建 venv→跑程序→故意装错版本并修复"三连。

### 第二部分 Python 语言基础（part02，约 30k 字）★全书最厚基础章
- ch04 变量与对象模型：一切皆对象、名字绑定、动态类型、可变性、==与is、浅/深拷贝、垃圾回收概念
- ch05 内置数据结构：list/tuple/dict/set、推导式、切片、unpacking、可哈希性（dict key 与 set 的底层含义）
- ch06 函数与作用域：默认参数陷阱、*args/**kwargs、keyword-only、闭包、lambda、LEGB
- ch07 面向对象：类、__init__、魔术方法（__repr__/__eq__/__len__/__getitem__/__enter__）、@property、dataclass、组合优于继承、Protocol 与结构化子类型
- ch08 异常体系：EAFP 风格、自定义异常、异常链 raise ... from ...、with/上下文管理器（contextlib）
- ch09 迭代器与生成器：yield、生成器表达式、惰性求值在流式 LLM 输出的应用
- ch10 装饰器：闭包实现原理、functools.wraps、带参装饰器、在重试/计时/鉴权中的实战
- ch11 模块与工程化基础：__name__、包结构、import 机制、类型注解系统（typing、Generic、TypedDict、Protocol）
- ch12 标准库实战：json、pathlib、datetime/timezone、re、logging、argparse；小项目：调用一个 HTTP 接口做数据清洗报告（httpx + json）
- Java↔Python 对照贯穿（对照表 + 差异警告，不逐行翻译）
- 验收：写出含 dataclass+装饰器+生成器+异常链的 CLI 工具并通过给定 pytest。

### 第三部分 Python 工程化与服务开发（part03，约 22k 字）
- ch13 asyncio：事件循环、协程与 await、gather/wait_for/超时取消、Semaphore 并发限制、异步上下文管理、sync 阻塞对事件循环的伤害（time.sleep 对比 asyncio.sleep 实验）
- ch14 线程/进程/GIL：IO 密集 vs CPU 密集选型表、ThreadPoolExecutor、多进程代价；GIL 按版本事实陈述
- ch15 HTTP 客户端工程化：httpx 超时三件套（connect/read/pool）、重试+指数退避+抖动、幂等性、连接池
- ch16 Pydantic v2：BaseModel、field_validator、model_config、Settings（pydantic-settings）、与 JSON Schema
- ch17 FastAPI：路径/查询/Body、Pydantic 请求响应模型、依赖注入 Depends、后台任务、SSE StreamingResponse、异常处理器、中间件与 trace_id
- ch18 测试与质量：pytest（fixture/参数化/MonkeyPatch）、pytest-asyncio、respx Mock HTTP、lint/format/mypy 一条龙○
- ch19 数据与缓存：sqlite3 参数化查询与只读账户思想、fakeredis/Redis 缓存与限流（固定窗口计数器）
- ch20 部署基础：Dockerfile 多阶段构建（静态检查）、uvicorn 生产参数、健康检查端点、requirements 锁定
- 综合演练：一个"订单查询+风控限流"FastAPI 服务（含测试）
- 验收：从零写出含 SSE+依赖注入+限流+pytest 的服务并全绿。

## 卷二 模型与框架（第四~九部分）

### 第四部分 大模型与模型 API（part04，约 20k 字）
- ch21 Token 与上下文窗口：tiktoken 计数实验、计费与限制、模型不确定性/幻觉/知识时效
- ch22 Transformer 直觉：注意力通俗图解（类比"全文检索+加权拼接"）、预训练/SFT/对齐一句话各自做什么（不深入数学）
- ch23 Chat Completions：消息角色、temperature/top_p/max_tokens、流式 chunk 拼接、多模态图片输入
- ch24 openai SDK 全流程：BaseURL 兼容层说明与支持边界、429/超时/重试（SDK 内建 retry 说明）、结构化输出（response_format + Pydantic）、工具调用完整闭环（模型请求工具→程序执行→Tool 结果回传）
- ch25 Embedding 与检索基础：embedding 与生成模型区别、余弦相似度 numpy 手算实验
- 先裸 SDK 后框架；`examples/common/llm_client.py`（Mock/Real 双模式）在此章定义并全书复用
- 验收：不查资料写出"结构化输出+一次工具调用循环"的可运行脚本（Mock 模式）。

### 第五部分 Prompt 与上下文工程（part05，约 14k 字）
- ch26 Prompt 工程：结构化模板（角色/约束/输入数据分离）、Zero/Few-shot、输出格式约束与校验回退
- ch27 对话历史管理：窗口截断、摘要压缩、上下文预算计算（token 预算表）
- ch28 Prompt 版本管理与回归测试（golden set 思想）、Prompt 注入基础与防护边界（为什么提示词≠权限控制）
- ch29 与 AI 协作开发：让模型解释代码/写测试/找 bug，如何识别模型错误输出
- 验收：为一个歧义任务写出可回归测试的 Prompt 并演示改写前后输出差异。

### 第六部分 RAG 从原理到生产（part06，约 22k 字）
- ch30 为什么 RAG、什么时候不用（对照长上下文/微调/工具查询）
- ch31 文档处理：加载/清洗/解析（markdown、网页、PDF 文本层；扫描件 OCR 说明）
- ch32 切分：固定长度/重叠/语义边界、元数据设计（用 langchain-text-splitters 实测）
- ch33 检索：embedding、余弦相似度 numpy 自实现 → 引入 FAISS○（若安装顺利）；BM25 原理与混合检索思想、重排序与查询改写概念、Top-k/阈值
- ch34 生成与引用：上下文拼接、引用溯源、拒答策略、检索前权限过滤（多租户）
- ch35 评估：自建评估集、召回率/忠实性/引用正确性的可计算定义、自动评估局限
- ch36 RAG 完整小项目（项目一雏形）：入库→检索→问答→引用 FastAPI 服务（详见 projects/p1）
- 验收：解释"为什么我的 RAG 答错"并给出至少 3 类定位手段。

### 第七部分 LangChain（part07，约 16k 字）
- ch37 定位与边界：什么时候不需要 LangChain（决策表）
- ch38 核心抽象：消息、ChatOpenAI、PromptTemplate、with_structured_output
- ch39 工具：@tool、参数 schema、错误处理
- ch40 LCEL/Runnable：管道语法、输入输出类型、异常传播、调试（比手写 SDK 对照）
- ch41 文档加载/切分/检索组件（与第六部分手写实现对照）
- ch42 create_agent 与当前推荐 Agent 构建、流式与异步、历史 API 考古（AgentExecutor 等→替代方式）
- 验收：同一任务分别用裸 SDK 与 LangChain 实现，说出框架替你做了什么。

### 第八部分 LangGraph（part08，约 24k 字）★全书重点
- ch43 为什么需要图：链 vs 状态机 vs 图（Java 状态机/工作流对照）
- ch44 最小两节点图：State/Node/Edge、StateGraph、START/END、reducer（add_messages）
- ch45 条件路由与循环：conditional edges、Send、终止条件、递归限制 recursion_limit
- ch46 工具调用循环：ToolNode、绑定工具、消息状态演进
- ch47 持久化：InMemorySaver→SqliteSaver○、thread_id、get_state、时间旅行调试○
- ch48 人工介入：interrupt、Command(resume=)、恢复语义、副作用幂等性
- ch49 并行与子图：并行分支结果合并、子图封装
- ch50 流式与错误处理：stream 模式（values/updates/messages）、节点内重试 RetryPolicy
- ch51 测试 LangGraph：单节点测试、整图测试、断言状态快照
- 循序渐进五例：两节点→条件分支→工具循环→持久化恢复→人工审批（五个 EX 全部真实验证）
- 验收：不查资料手写"带审批+恢复+持久化"的三节点图。

### 第九部分 Agent、MCP 与复杂应用（part09，约 16k 字）
- ch52 Workflow vs Agent：决策表、Agent loop 外部可观察行为、任务拆解/规划/验证
- ch53 单 Agent vs 多 Agent：取舍表、通信/共享状态/失败处理；不堆概念，给判断标准
- ch54 工具治理：描述质量、参数校验、权限、审计日志
- ch55 MCP：定位（协议不是框架）、host/client/server、tools/resources、传输方式（以当前官方规范为准核实后写）、与 REST API/工具调用关系、langchain-mcp-adapters○（安装成功则演示）
- ch56 对接已有 Java 服务：HTTP 工具封装、长任务/任务队列/状态查询/取消模式
- 验收：为一个业务系统设计"哪些环节用 Workflow、哪些用 Agent"并说明理由。

## 卷三 生产与实战（第十~十二部分 + 项目）

### 第十部分 企业级架构、安全与运维（part10，约 18k 字）
- ch57 架构边界：AI 服务与业务服务、Python AI 服务 ↔ Spring Boot 集成模式（同步/SSE/异步任务）
- ch58 安全：鉴权 RBAC 多租户、脱敏、密钥管理、只读 DB 账户+白名单+参数化 SQL、工具审批与沙箱边界、Prompt 注入防线纵深
- ch59 稳定性：超时/重试/限流/熔断/降级在 LLM 场景的具体参数、背压与并发控制、缓存与语义缓存边界
- ch60 成本与可观测：token/延迟/成本统计表、结构化日志+trace_id、离线评估/在线反馈/回归
- ch61 上线：CI/CD 流水线设计、健康检查、K8s 需要懂什么○、上线检查清单（15 项）、3 个故障排查案例
- 验收：给一个 AI 功能做上线评审，列出风险与对策。

### 第十一部分 微调与算法边界（part11，约 8k 字）
- ch62 预训练/SFT/LoRA/偏好优化各自解决什么（一张表）、RAG vs Prompt vs 微调选择树
- ch63 微调做不了什么（知识时效、幻觉、权限）、数据质量与评估成本、应用工程师的知识边界声明
- 验收：给 3 个业务诉求选择正确技术路线并说理。

### 第十二部分 面试与求职（part12/interview/，约 24k 字）
- 8 个专题：Python 基础与工程化 / 异步与性能 / 模型 API 与结构化输出 / RAG / LangChain / LangGraph / Agent 与 MCP / 系统设计与项目深挖
- 每题六段式：考查点→常见错误回答→合格回答→深入解释→工程案例→追问 2-3 个→回答边界
- Java 转 AI：经验迁移话术、能力缺口补齐计划、简历真实表达（不编造）
- 全部题目标注[模拟题]；真题辨认方法说明
- 验收：30 分钟内白板讲清 RAG 评估方案 + LangGraph 恢复语义。

## 综合项目（projects/）

- P1 企业文档知识库（p1_doc_kb）：入库→切分→numpy 向量检索→重排○→引用问答→权限过滤→FastAPI+SSE→评估集→pytest（Mock 模式全流程可复现）
- P2 生产日志排障助手（p2_log_triage）：合成 Java 日志→LangGraph 编排（识别→取证据→受限只读工具→结论分级）→证据不足拒答→高风险操作人工确认→InMemorySaver 持久化+恢复→审计日志
- P3 Java+Python 协作业务 Agent（p3_java_python_agent）：Java(JDK 内置 HttpServer，含 Spring Boot 集成说明) 模拟生产计划 API；Python Agent 参数校验/权限/幂等/审批/异步任务状态查询/超时重试/Docker 化（静态检查）/完整测试

每项目必含 md 文档（业务目标与非目标/架构/分步实现/数据/启动命令/请求响应示例/正常与失败路径/测试/成本安全讨论/排障/面试讲法/扩展方向）。

## 学习路径（正文章节完成后细化成表）

1. 从头完整路径：P1→P2→P3→P4→P5→P6→P7→P8→P9→P10→P11→P12 + 项目随学随做
2. Java 加速路径：ch01→ch04~ch11(速读+练习)→ch13~ch20(精读)→卷二全精读→项目
3. 面试前冲刺：每章 N.10 自测+N.11 追问→part12 全部→项目"面试讲法"
4. 项目驱动路径：P1 前置 ch04~ch08+ch16~ch18+卷二第四六部分→做 P1→…
