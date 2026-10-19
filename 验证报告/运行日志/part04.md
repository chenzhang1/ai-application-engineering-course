# Part04 运行日志（第四部分 ch21~ch25 大模型与模型 API + 全书 LLM 基座）

- 执行环境：沙箱 Linux，Python 3.14.7（pyenv），CI=true 非交互；依赖版本见 requirements.txt（openai 3.35.1 / tiktoken 0.14.0 / pydantic 2.14.1 / numpy 2.5.4 / pytest 9.1.1）。
- 核实日期：2026-10-19。**沙箱无 OPENAI_API_KEY**：所有模型回答为 Mock 或"示例输出（非真实记录）"；代码层事实（SDK 签名）全部 inspect 实测。

## 0. 全书 LLM 基座（examples/common/）— 交付说明

| 文件 | 内容 |
|---|---|
| examples/common/__init__.py | 包说明与双模式约定 |
| examples/common/llm_client.py | ChatResult/ToolCall/StructuredOutputError、MockLLM（script 脚本驱动 + USE_TOOL 规则触发 + chat_structured）、RealLLM（openai 3.35.1）、get_llm 工厂、count_tokens（tiktoken 优先/近似回退） |
| examples/common/embeddings.py | MockEmbedder（概念词典+哈希词袋+L2 归一化，dim=64）、RealEmbedder、cosine_similarity、get_embedder |
| tests/test_common_llm.py | 17 个测试（普通回复/脚本工具循环/规则触发/结构化成功与失败/脚本耗尽/real 缺 key/usage 回退/流式拼接/respx 不适用后改用 httpx.MockTransport 验证 real 转换路径/相似度性质） |

**关键签名核实结论（openai 3.35.1，inspect 实测，EX-24-01 真实输出为证）**：
- `OpenAI.__init__` 参数含 api_key / base_url / timeout / max_retries / http_client / with_options 可用；**max_retries 默认 2**（实例化 `client.max_retries == 2`）；
- `chat.completions.create` 含 messages / model / temperature / top_p / max_tokens / max_completion_tokens / stream / stream_options / tools / tool_choice / response_format / parallel_tool_calls / seed / stop / n；
- `chat.completions.parse` **存在**于 3.35.1：参数含 response_format，**不含 stream**；
- `embeddings.create` 前置参数：input / model / dimensions / encoding_format / user；
- `ChatCompletionMessage` 字段含 content / refusal / role / annotations / audio / function_call / tool_calls。
- 注：respx 0.23.1 无法拦截 openai SDK 的内部 httpx 客户端（SDK 自建 client），real 路径测试改用 SDK 官方支持的 `OpenAI(http_client=httpx.Client(transport=httpx.MockTransport(...)))` 注入——已在 `RealLLM.__init__` 暴露 http_client 参数。

**tiktoken 词表实测**：首次 `get_encoding("cl100k_base")` 经代理下载词表 **27s**（cl100k_base，n_vocab=100277），缓存于 `/tmp/data-gym-cache` 后二次加载 **0.14s**；下载失败时 `count_tokens` 回退 `approx:chars//4` 并在返回值第二项如实标注。

## 1. 示例运行记录（16 个 EX 全部真实执行，退出码 0）

| EX | 文件 | 关键输出摘要 |
|---|---|---|
| EX-21-01 | examples/ch21_tokens/ex_21_01_tiktoken_count.py | 中文 13 字符=13 token（近似法只给 3）；'订单查询'=2 个 token [51510, 52254]，往返无损 |
| EX-21-02 | examples/ch21_tokens/ex_21_02_context_budget.py | 6 条消息 164 token；剩余预算 2908；滚雪球 30→164 |
| EX-21-03 | examples/ch21_tokens/ex_21_03_mock_determinism.py | Mock 3 次输出一致；temperature=1.5 与 0.0 输出相同（接受并忽略）；缺 Key RuntimeError 指引 |
| EX-22-01 | examples/ch22_transformer/ex_22_01_dot_attention.py | 4×4 权重矩阵（'查询'↔'订单' 0.357/0.355）；每行和=1、非负验证通过 |
| EX-22-02 | examples/ch22_transformer/ex_22_02_retrieval_analogy.py | score('查询'→'订单')=1.989；权重 0.443/0.438；新向量 [0.060,0.836,0.836,0.060]；三阶段流水线 |
| EX-23-01 | examples/ch23_chat/ex_23_01_roles.py | finish_reason=tool_calls；完整 messages JSON（assistant.tool_calls + tool 回传）；二次调用 usage prompt=50 |
| EX-23-02 | examples/ch23_chat/ex_23_02_params_demo.py | 四组参数输出完全相同（True）——Mock 契约声明 |
| EX-23-03 | examples/ch23_chat/ex_23_03_stream.py | 44 chunks；拼接==整体 True；逐 token decode 真实出现 U+FFFD 乱码；中途停止 |
| EX-23-04 | examples/ch23_chat/ex_23_04_multimodal_structure.py | 手工 PNG 69 字节、魔数校验 True；图文分段数组结构打印；真实调用未验证（无 Key，如实标注） |
| EX-24-01 | examples/ch24_sdk/ex_24_01_auth_baseurl.py | 缺 Key RuntimeError 全文；3.35.1 签名清单（max_retries=2、parse 存在无 stream、embeddings 参数） |
| EX-24-02 | examples/ch24_sdk/ex_24_02_structured_output.py | Pydantic 对象 model_dump/dump_json；StructuredOutputError 真实抛出（missing + bool_parsing 两个错误） |
| EX-24-03 | examples/ch24_sdk/ex_24_03_tool_loop.py | 完整闭环：tool_calls→get_weather 执行→tool 回传→最终回答；两轮 usage 合计 95 |
| EX-24-04 | examples/ch24_sdk/ex_24_04_retry_backoff.py | 2 次模拟 429 →退避 0.12s/0.23s→第 3 次成功；SDK 默认 max_retries=2 对照 |
| EX-25-01 | examples/ch25_embeddings/ex_25_01_cosine_manual.py | 手算 cos=0.960000 夹角 16.26°；numpy 对照一致；归一化点积==余弦 |
| EX-25-02 | examples/ch25_embeddings/ex_25_02_similarity_intuition.py | sim(手机,电话)=1.000 > sim(手机,手机支付)=0.707 > sim(手机,披萨)=0.000 |
| EX-25-03 | examples/ch25_embeddings/ex_25_03_mini_search.py | 'SIM 卡坏了' top-1 命中保修条款（0.250）；无关条款 0.000/-0.077/-0.118 |

## 2. pytest 汇总

命令：`cd /workspace/ai_application_course && python3 -m pytest tests/ -q`

最终结果摘要行：

```
184 passed in 14.51s
```

分布：新增 test_common_llm 17 个、ch21 9 个、ch22 4 个、ch23 5 个、ch24 5 个、ch25 5 个（合计 63 个）；既有 ch02~ch19 测试 121 个全部保持通过（未改动任何既有文件）。

## 3. 失败与修复过程（真实踩坑记录）

1. **respx 拦不住 openai SDK**：`test_real_llm_conversion_via_respx` 报 `APIConnectionError`（SDK 自建 httpx client，respx 的全局 mock 不生效）。修复：`RealLLM` 增加 `http_client` 参数（openai 官方签名含此参数），测试注入 `httpx.MockTransport`，同时验证了鉴权头/payload/响应转换。
2. **流式逐 token 解码乱码**：`test_mock_stream_chunks_join_back` 失败（U+FFFD）——tiktoken 单 token 可能是半个多字节字符。修复：`chat_stream` 改用 `codecs.getincrementaldecoder("utf-8")` 字节缓冲；该坑作为 ch23 教学重点保留（EX-23-03 真实复现）。
3. **Mock 工具结果轮死循环隐患**：规则模式下回传 tool 消息后 `USE_TOOL` 仍会命中最后一次 user 消息导致空转。修复：`_respond` 增加"最后一条为 tool 消息→整合结果回答（finish_reason=stop）"分支；ch23/ch28 测试断言不产生新工具调用。
4. **f-string 双大括号 KeyError**（真实踩进教学点）：EX-26-01/EX-28-01 模板含 JSON 示例时 `.format()` 抛 `KeyError: '"category"'` / `KeyError: '"label"'`。修复：字面大括号改 `{{ }}`；写进 ch26 排错节首位。
5. **EX-22-02 zip 错位**：`TypeError: 'numpy.float64' object is not iterable`——`zip(scores.items(), w)` 误对 vec 解包。修复：`(word, _)` 只取键。
6. **EX-23-04 PNG 魔数误报 False**：f-string 里 `b'\\x89PNG...'` 双重转义导致字节比较失真。修复：比较提为独立变量 `is_png` 并加 assert。
7. **EX-29-02 信号 1 核查器的意外收获**：断言 `bad == ["api_version"]` 失败——实际 `['api_version', 'max_retries']`：**max_retries 属于 OpenAI 客户端构造参数，create 不收**。将错就错成为教学素材（"参数张冠李戴"形态），修正断言与文案。
8. **EX-29-03 dedupe 修复版自身有 bug**：`x.items()` 对 str 崩（AttributeError）。修复：先 try 直接当 key、except（unhashable）再走 dict 内容签名；输出"3/3 全绿"。
9. **tests/test_ch21 边界修正**：空字符串在 tiktoken 路径精确返回 0（合法），原断言 `>=1` 错误；改为"非空必正 + 空串精确 0"两个用例（近似路径的 max(1,·) 兜底另有说明）。
10. **EX-25-03 查询词调整**："SIM 卡坏了怎么保修"改"手机 SIM 卡坏了怎么办"，确保概念词典可命中"手机"方向（top-1 保修条款 0.250）。

## 4. 未验证项（诚实清单）

1. 真实模型调用全链路（temperature 实际效果、finish_reason=length 截断、多模态识别效果、response_format 严格模式、兼容服务行为差异）：无 OPENAI_API_KEY，教材相应位置全部标注"语义说明/以厂商文档为准"。
2. EX-23-04 的真实多模态发送：仅验证消息结构与 base64 可逆性（PNG 魔数校验），未发送。
3. RealLLM/RealEmbedder 仅验证"对 SDK 响应形状的转换逻辑"（MockTransport 注入），未对真实服务发起请求。
4. 上下文窗口/价格数字：全书使用虚构教学模型 demo-4k/demo-16k，未写任何真实产品数字。
