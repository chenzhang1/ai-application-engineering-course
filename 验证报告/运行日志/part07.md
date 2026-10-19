# Part07 运行日志（第七部分 ch37~ch42 LangChain）

- 执行环境：沙箱 Linux，Python 3.14.7（pyenv），CI=true 非交互；依赖版本见 requirements.txt（langchain==1.4.6 / langchain-core==1.6.12 / langchain-openai==1.7.2 / langchain-community==0.4.2 / langchain-text-splitters==1.1.3 / langgraph==1.2.16 / langgraph-checkpoint==4.3.0 / langgraph-prebuilt==1.1.1 / langchain-classic==1.0.8）。
- 核实日期：2026-10-19。**沙箱无 OPENAI_API_KEY**：LangChain 主线全部用 langchain-core 内置 Fake 模型（官方测试做法）做确定性演示；ChatOpenAI 只做"构造与签名核实"，未发起真实请求。
- 教材交付：`textbook/part07_langchain.md`（28075 汉字，6 章，17 个新 EX，全部真实运行）。

## 0. API 签名与行为核实记录（全部 inspect/实测，非凭记忆）

### 0.1 langchain-core 1.6.12

| 核实点 | 结论 |
|---|---|
| `fake_chat_models` 可用类 | FakeChatModel / FakeListChatModel / FakeMessagesListChatModel / GenericFakeChatModel / ParrotFakeChatModel / SimpleChatModel（+异常类 FakeListChatModelError） |
| FakeListChatModel 字段 | responses: list[str]、sleep、i、error_on_chunk_number；**耗尽后循环回开头**（源码 docstring 原话 "cycle"） |
| GenericFakeChatModel 字段 | messages: Iterator[AIMessage \| str]；**耗尽抛 StopIteration**（direct invoke 实测；经 Runnable 层被 PEP 479 转成 RuntimeError "generator raised StopIteration"） |
| FakeMessagesListChatModel 字段 | responses: list[BaseMessage] |
| 消息导出 | HumanMessage/AIMessage/SystemMessage/ToolMessage/AIMessageChunk/AnyMessage/RemoveMessage/UsageMetadata/ToolCall 等；AIMessageChunk 支持 `+` 聚合；AIMessage.tool_calls 为结构化 dict（name/args/id/type） |
| `langchain_core.tools.tool` 签名 | (name_or_callable, runnable, *, description, return_direct=False, args_schema=None, infer_schema=True, response_format='content', parse_docstring=False, error_on_invalid_docstring=True, extras)；**不含 handle_tool_error**（传参实测 TypeError） |
| BaseTool.model_fields | name/description/args_schema/return_direct/verbose/callbacks/tags/metadata/**handle_tool_error**/**handle_validation_error**/response_format/extras；实例属性赋值 `tool.handle_tool_error = str/callable` 实测有效（None→抛 ToolException；str→返回文案；callable→函数加工） |
| tools 模块导出 | 含 ToolException/StructuredTool/BaseTool/render_text_description/render_text_description_and_args/create_retriever_tool/create_schema_from_function 等 |
| `RecursiveCharacterTextSplitter.__init__` | (separators=None, keep_separator=True, is_separator_regex=False, **kwargs)；kwargs 实测支持 chunk_size/chunk_overlap/length_function/keep_separator；中文分隔符 ["。",""] + length_function=len 实测通过 |
| langchain_core.vectorstores 导出 | InMemoryVectorStore / VectorStore / VectorStoreRetriever；InMemoryVectorStore 方法 add_documents/aadd_documents/similarity_search/similarity_search_with_score/from_texts/as_retriever；add_documents 返回 uuid 列表 |
| langchain_core.documents | Document(model_fields: id/metadata/page_content/type)；BaseRetriever 在 langchain_core.retrievers，子类实现 `_get_relevant_documents(query, *, run_manager)` 后 invoke/batch 免费获得（实测） |
| `Embeddings` 接口 | embed_documents(texts)/embed_query(text) 两方法；MockEmbedder 适配器实测通过 |
| output_parsers | StrOutputParser/JsonOutputParser/**PydanticOutputParser**（pydantic v2 兼容，实测链路成功+失败抛 OutputParserException） |
| ChatPromptTemplate | from_messages/invoke(→ChatPromptValue→to_messages)/format_messages/get_input_variables/partial；MessagesPlaceholder('history', optional=True) 实测 optional_variables=['history']；PromptTemplate.from_template 存在 |
| runnables 导出 | Runnable/RunnableSequence/RunnableLambda/RunnablePassthrough/RunnableParallel/RunnableConfig/RunnableBranch/RunnableWithFallbacks 等；`prompt|model|parser` → RunnableSequence（type 实测） |
| RunnableLambda.__init__ | func 支持 (x)/(x, RunnableConfig)/(x, run_manager, config) 及异步变体（签名核实） |
| RunnableConfig 实测键 | callbacks/configurable/metadata/recursion_limit/tags（invoke(config={"tags":...}) 贯穿每个节点，实测） |
| 异常传播 | 链中节点抛 ValueError/RuntimeError **原类型原信息冒泡**（同步与流式均实测） |
| astream_events | version='v2'，事件序列实测：on_chain_start/on_prompt_start/on_prompt_end/on_chat_model_start/on_chat_model_stream/on_parser_start…（20 个事件/简单三段链） |
| get_prompts / get_graph | 均可用；get_graph().print_ascii() **实测 ImportError（需 grandalf，沙箱未装）**，改用 nodes 节点表 |
| PydanticOutputParser.get_format_instructions | 正常产出 JSON schema 说明文本 |

### 0.2 langchain-openai 1.7.2（仅构造/签名核实，未联网）

| 核实点 | 结论 |
|---|---|
| 无 Key 构造 | 抛 `OpenAIError: Missing credentials. Please pass an api_key, workload_identity, admin_api_key, or set the OPENAI_API_KEY or OPENAI_ADMIN_KEY environment variable...`（EX-38-02 [2] 实测捕获） |
| dummy Key 离线构造 | 成功：ChatOpenAI(model='gpt-4o-mini', api_key='sk-dummy', temperature=0, max_retries=2, timeout=30) → model_name/temperature/max_retries 属性可读 |
| 字段名与构造参数别名 | 字段 request_timeout ↔ 构造参数 timeout=；字段 openai_api_key/openai_api_base ↔ 构造参数 api_key=/base_url=（pydantic 别名，构造实测可用；model_fields 断言通过） |
| `with_structured_output` 签名 | (schema=None, *, method='json_schema', include_raw=False, strict=None, tools=None, **kwargs) -> Runnable[LanguageModelInput, _DictOrPydantic]；method ∈ {function_calling, json_mode, json_schema} |
| `bind_tools` 签名 | (tools, *, tool_choice=None, strict=None, parallel_tool_calls=None, response_format=None, **kwargs) -> Runnable[LanguageModelInput, AIMessage] |
| Fake 模型 with_structured_output | `NotImplementedError: with_structured_output is not implemented for this model.`（实测） |

### 0.3 langchain 1.4.6（create_agent 主线）

| 核实点 | 结论 |
|---|---|
| `create_agent` 签名 | model（必填）；tools=None；keyword-only：system_prompt/middleware=()/response_format/state_schema/context_schema/checkpointer/store/interrupt_before/interrupt_after/debug=False/name/cache/transformers |
| 返回类型 | CompiledStateGraph（langgraph 编译图）；invoke 返回 {'messages': [...]} |
| `langchain.agents` 导出 | AgentState / create_agent / factory / middleware / structured_output |
| **AgentExecutor 位置** | `from langchain.agents import AgentExecutor` → **ImportError（实测）**；`from langchain_classic.agents import AgentExecutor, initialize_agent` → 可导入（langchain-classic 1.0.8） |
| bind_tools 调用时机 | 每次模型节点执行一次（工具轮+最终轮实测 2 次，通过记录型 Fake 子类验证）；未实现 bind_tools 的模型在模型节点抛 NotImplementedError（首次探测实测 traceback） |
| 工具异常默认行为 | 工具抛异常且未配 handle_tool_error 时，**整个 agent.invoke 失败**（langgraph-prebuilt 1.1.1 的 _default_handle_tool_errors 对非 ToolInvocationError 原样 raise，源码核实+实测 traceback） |
| 工具级 handle_tool_error | 在 create_agent 内实测有效：异常变 ToolMessage 文案回传，循环继续（EX-39-03/EX-42-03 相关测试） |
| `middleware` 导出（langchain.agents.middleware） | AgentMiddleware/ContextEditingMiddleware/FilesystemFileSearchMiddleware/HumanInTheLoopMiddleware/LLMToolSelectorMiddleware/ModelCallLimitMiddleware/ModelFallbackMiddleware/ModelRetryMiddleware/PIIMiddleware/ProviderToolSearchMiddleware/ShellToolMiddleware/SummarizationMiddleware/TodoListMiddleware/ToolCallLimitMiddleware/ToolErrorMiddleware/ToolRetryMiddleware |
| ModelCallLimitMiddleware 签名与行为 | (*, thread_limit=None, run_limit=None, exit_behavior='end'\|'error')；触发实测：error→`ModelCallLimitExceededError: Model call limits exceeded: run limit (2/2)`；end→追加收尾 AIMessage（同文案）并正常结束（EX-42-03 两种模式全真跑） |
| ToolRetryMiddleware 签名 | (*, max_retries=2, tools=None, retry_on=..., on_failure='continue', backoff_factor=2.0, initial_delay=1.0, max_delay=60.0, jitter=True)（仅签名核实，未实测运行） |
| SummarizationMiddleware 签名 | (model, *, trigger=..., keep=('messages', 20), token_counter=count_tokens_approximately, ...)（仅签名核实） |
| HumanInTheLoopMiddleware 签名 | (interrupt_on: dict[str, bool \| InterruptOnConfig], *, description_prefix=..., edit_notice=..., interrupt_mode='batched')（仅签名核实） |
| checkpointer | InMemorySaver（langgraph.checkpoint.memory）；同 thread_id 两次 invoke 共享状态；get_state(cfg).values['messages'] 实测 4 条 |
| stream 三模式 | values（全量状态）/ updates（节点增量，key=['model']）/ messages（逐 token chunk + metadata.langgraph_node）；astream 异步版实测通过 |
| init_chat_model 签名 | (model=None, *, model_provider=None, configurable_fields=None, config_prefix=None, **kwargs)（langchain.chat_models，签名核实） |

### 0.4 langchain-community 0.4.2

- `from langchain_community.document_loaders import TextLoader` 可用；**导入触发官方 DeprecationWarning（实测原文）**："`langchain-community` is being sunset and is no longer actively maintained. See https://github.com/langchain-ai/langchain-community/issues/674 for details and migration guidance toward standalone integration packages."；TextLoader(path, encoding='utf-8').load() → 1 个 Document（实测）。

## 1. 示例运行记录（17 个 EX 全部真实执行，退出码 0）

| EX | 文件 | 关键输出摘要 |
|---|---|---|
| EX-37-01 | examples/ch37_lc_boundary/ex_37_01_decision_table.py | 决策表 4 输出 ×5 判断案例；64 种特征组合自检完备（bare_sdk/components_only/full_langchain/langgraph） |
| EX-37-02 | examples/ch37_lc_boundary/ex_37_02_side_by_side.py | 裸 llm_client（usage 30+36 tokens）vs LangChain 管道（RunnableSequence）；"框架做了/没做"三清单 |
| EX-38-01 | examples/ch38_lc_core/ex_38_01_messages.py | 四类消息对象 ↔ role 映射；AIMessage.id=lc_run--...；usage_metadata=None（Fake）；chunk 聚合 6→'逐字流式输出' |
| EX-38-02 | examples/ch38_lc_core/ex_38_02_fake_and_chatopenai.py | FakeList 循环（第 3 次=第 1 条）vs Generic 耗尽（StopIteration）；ChatOpenAI 无 Key OpenAIError 实录；dummy key 构造成功；with_structured_output/bind_tools 签名；别名错位两处 |
| EX-38-03 | examples/ch38_lc_core/ex_38_03_prompt_structured.py | input_variables=['question','role']，optional=['history']；不传 history→2 条消息；with_structured_output 签名全文；Fake 不支持 NotImplementedError；PydanticOutputParser 成功（RefundCheck）+失败（OutputParserException） |
| EX-39-01 | examples/ch39_lc_tools/ex_39_01_tool_decorator.py | name/description/args_schema 自动提取；render_text_description 菜单文本；与裸 SDK 双份代码对照 |
| EX-39-02 | examples/ch39_lc_tools/ex_39_02_args_schema_error.py | WeatherArgs 枚举+默认值进 schema（required=['city']）；handle_tool_error 三策略实测（None 抛/str 文案/callable）；handle_validation_error 拦枚举外取值 |
| EX-39-03 | examples/ch39_lc_tools/ex_39_03_tool_render.py | 三工具菜单渲染（含 args）；return_direct 语义；create_agent 内工具错误恢复：ToolMessage=handle_tool_error 文案，循环继续 |
| EX-40-01 | examples/ch40_lcel/ex_40_01_pipe_chain.py | type(prompt\|model\|parser)=RunnableSequence；get_prompts()；get_graph() 5 节点（print_ascii 需 grandalf）；RunnableLambda 协议 |
| EX-40-02 | examples/ch40_lcel/ex_40_02_parallel_config.py | assign 旁路注入不丢键；RunnableParallel 合并；config.tags 贯穿（实测 seen=[('unnamed', ['tenant:acme','env:prod'])]） |
| EX-40-03 | examples/ch40_lcel/ex_40_03_batch_stream_async.py | batch 2 路；stream 10 chunk；ValueError/RuntimeError 原样冒泡（同步+流式）；ainvoke；astream_events 20 事件（前 6=on_chain_start/on_prompt_start/on_prompt_end/on_chat_model_start/on_chat_model_stream/on_parser_start） |
| EX-41-01 | examples/ch41_lc_rag_components/ex_41_01_loader_splitter.py | 切分实验 30/0→3 块[24,25,25]、30/10→3 块、60/10→2 块[49,25]；metadata 随块携带；TextLoader 实测 + sunset 警告原文捕获 |
| EX-41-02 | examples/ch41_lc_rag_components/ex_41_02_vector_retriever.py | Embeddings 适配器（embed_documents==embed_query for Mock）；InMemoryVectorStore top1=sim.md（score 0.3922）；as_retriever batch 实测 |
| EX-41-03 | examples/ch41_lc_rag_components/ex_41_03_custom_retriever.py | BaseRetriever 子类 invoke/batch；RAG 链端到端（itemgetter 类型对齐）；最终回答含引用 [warranty.md] |
| EX-42-01 | examples/ch42_lc_agent/ex_42_01_agent_minimal.py | 裸 bind_tools→NotImplementedError()；create_agent→CompiledStateGraph；消息序列 Human/AI(tool_calls)/Tool/AI；bind_calls=[['get_weather'], ['get_weather']] |
| EX-42-02 | examples/ch42_lc_agent/ex_42_02_agent_checkpoint_stream.py | thread_id 两轮记忆 + get_state 4 条；stream values/updates/messages 三模式；astream 异步 chunk@model |
| EX-42-03 | examples/ch42_lc_agent/ex_42_03_agent_limits_legacy.py | run_limit=2：error→ModelCallLimitExceededError / end→6 条消息优雅收尾；AgentExecutor ImportError 实测；langchain_classic 1.0.8 可导入；8 行迁移表 |

## 2. pytest 汇总

命令：`cd /workspace/ai_application_course && python3 -m pytest tests/ -q`

最终结果摘要行：

```
261 passed in 16.03s
```

分布：新增 test_ch37（4）/test_ch38（5）/test_ch39（4）/test_ch40（6）/test_ch41（4）/test_ch42（6）合计 29 个；此前全库 232 个（含 part05 交付后的 ch26~ch29）全部保持通过，未改动任何既有文件。覆盖：正常路径（管道输出/消息序列/向量命中/护栏 end 模式）、边界（Fake 循环与耗尽、切分长度约束、k 语义）、非法输入（缺 Key OpenAIError、枚举外参数 ValidationError、AgentExecutor ImportError、未实现 bind_tools 的 NotImplementedError、坏 JSON 的 OutputParserException）。

## 3. 失败与修复过程（真实踩坑记录）

1. **create_agent + GenericFakeChatModel 直接失败**：`NotImplementedError`（BaseChatModel.bind_tools 默认未实现），traceback 指向 `factory.py` 的 `_get_bound_model` → `model.bind_tools(final_tools, tool_choice=...)`。修复：教学用 `FakeToolChatModel(GenericFakeChatModel)` 子类实现 bind_tools（返回 self）——该报错与修复方案均作为教材教学点写入 42.3/42.5。
2. **`@tool(handle_tool_error=...)` TypeError**：写作时想当然把 handle_tool_error 当装饰器参数，`tool() got an unexpected keyword argument 'handle_tool_error'`。核实后确认它是 BaseTool 实例属性，改用属性赋值（EX-39-02 三策略实测），并写入 39.7 排错首位。
3. **FakeListChatModel "耗尽抛异常"的想当然被实测推翻**：第 3 次 invoke 没有抛错而是返回第 1 条——源码 docstring 明写 "cycle"。教材 EX-38-02 [1] 改为"循环 vs 耗尽"对比教学（GenericFakeChatModel 才是耗尽抛 StopIteration），test_ch38 的边界用例同步改写。
4. **Retriever 收到 dict**：EX-41-03 初版 `assign(context=retriever | ...)` 运行报 `AttributeError: 'dict' object has no attribute 'lower'`（assign 把整个 dict 传给 Retriever）。修复为标准解法 `itemgetter("question") | retriever | ...`，案发现场保留在示例注释与 41.5（2）。
5. **batch/stream 脚本条数**：test_ch40 初版脚本 2 条支撑"batch(2)+stream(1)"，因 FakeList 循环语义 stream 消费回'答 1'导致断言失败。修复：脚本补足 3 条（batch 2 条 + stream 1 条），注释注明消费计划。
6. **ChatOpenAI 字段名断言两次修正**：先假设 `timeout` 在 model_fields（实际是 request_timeout），再假设 `api_key`（实际 openai_api_key/openai_api_base）——两次 AssertionError 后以 pydantic 别名机制落笔（构造参数与字段名两套名字，均实测可用），写入 EX-38-02 [4]。
7. **切分块数断言过严**：test_ch41 初版 `len(docs) >= 3` 实际 2 块（第一二句合并后 23 字符 ≤ chunk_size=25 是合法行为）。修正断言为 >= 2 并保留 ≤chunk_size 的关键约束。
8. **grandalf 缺失**：get_graph().print_ascii() 实测 `ImportError: Install grandalf to draw graphs`——不改依赖，教材与示例统一用 nodes 节点表，排错条目记录。
9. **探测脚本自身的 StopIteration 坑**：流式探测脚本对同一 stream_agent 消费两次但脚本只备 1 条，得到 `RuntimeError: generator raised StopIteration`（PEP 479）——与正文 40.7 错 3 互证。

## 4. 未验证项（诚实清单）

1. **真实模型调用全链路**：`ChatOpenAI.invoke`（含 usage_metadata 的真实值）、`with_structured_output` 三种 method 的真实生成效果与兼容服务差异、`create_agent(response_format=...)` 在真实模型上的结构化输出——无 OPENAI_API_KEY，教材全部标注"形状经核实/需 Key 未实调"。
2. **ToolRetryMiddleware / HumanInTheLoopMiddleware / SummarizationMiddleware 的运行行为**：构造签名已核实，未实测（审批的 interrupt 交互属第八部分 ch48 主题）。
3. **`context_schema` / `store` / `state_schema` 自定义 / `interrupt_before/after`**：参数存在性核实，未演示。
4. **print_ascii/ASCII 图、RunnableBranch、with_fallbacks、astream_events 自定义事件**：存在性核实，未展开实测。
5. **InMemoryVectorStore 持久化接口、其他 VectorStore 实现的分数口径**：未实测。
6. **parse_docstring=True 对中文 docstring 的解析效果**：未实测。
