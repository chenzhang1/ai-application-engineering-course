# 运行记录：第八部分（LangGraph，ch43~ch51）+ 项目二（p2_log_triage）

> 环境与工具链（与既有部分一致）：Python 3.14.7（pyenv），langgraph 1.2.16，langchain-core 1.6.12，pytest 9.1.1，tz Asia/Shanghai。核实日期 2026-10-19。全部 LLM 相关输出为 Mock 模式（`LLM_MODE=mock` 默认，离线确定性），标注见各输出块。

## 1. API 事实核实（写教材前用 python3 -c 逐项探测）

| 探测项 | 结果 |
|---|---|
| `inspect.signature(StateGraph.add_conditional_edges)` | `(source, path, path_map=None)` |
| `StateGraph.add_node` 关键字参数 | `defer/metadata/input_schema/retry_policy/cache_policy/error_handler/destinations/timeout/trace_policy` |
| `StateGraph.compile` | `(checkpointer=None, *, cache, store, interrupt_before, interrupt_after, debug, name, transformers)` |
| `interrupt` 签名 | `(value, *, response_schema=None)` |
| `Command` 字段（dataclass） | `graph / update / resume / goto / PARENT(ClassVar)` |
| `Send` 签名 | `(node, arg, *, timeout=None)`；字段 `node/arg` |
| `ToolNode` 签名 | `(tools, *, name='tools', tags=None, handle_tool_errors=..., messages_key='messages', wrap_tool_call=None, awrap_tool_call=None)` |
| `RetryPolicy` 字段与默认 | `initial_interval=0.5, backoff_factor=2.0, max_interval=128.0, max_attempts=3, jitter=True, retry_on=default_retry_on`；从 `langgraph.types` 导入（`langgraph.pregel` 无此名） |
| `StateSnapshot` 字段 | `config/created_at/metadata/next/parent_config/tasks/values/interrupts/index/count` |
| `Interrupt` 字段 | `value/id/interrupt_id/response_schema` |
| `GraphRecursionError` | `from langgraph.errors`；文案 "Recursion limit of 5 reached without hitting a stop condition. ..." |
| `SqliteSaver` | 初始未安装；`pip install langgraph-checkpoint-sqlite` 成功装 3.1.2（pip 下载经代理正常），`from_conn_string(conn_string)` 为上下文管理器 |
| 关键报错全文 | `InvalidUpdateError: At key 'out': Can receive only one value per step. Use an Annotated key to handle multiple values.`；`ValueError: Checkpointer requires one or more of the following 'configurable' keys: thread_id, checkpoint_ns, checkpoint_id`；`RuntimeError: Cannot use Command(resume=...) without checkpointer`；path_map 缺路由值 → `KeyError` |
| 其他 | `get_stream_writer` 位于 `langgraph.config`（存在性核实，未演示用法）；`Durability = Literal['sync','async','exit']` 为 invoke/stream 关键字参数（取值核实，语义未逐项验证） |

## 2. 教学示例运行（全部真实运行，exit=0）

| 示例 | 命令 | 退出码 | 输出摘要 |
|---|---|---|---|
| EX-43-01 | `python3 examples/ch43_graph_intro/ex_43_01_chain_vs_graph.py` | 0 | v1 三通道分流；v2 敏感拦截/VIP 加急 |
| EX-43-02 | `python3 examples/ch43_graph_intro/ex_43_02_first_graph_preview.py` | 0 | auto/manual 双路由 + trace + 节点表（含 __start__/__end__） |
| EX-44-01 | `python3 examples/ch44_minimal_graph/ex_44_01_minimal_two_nodes.py` | 0 | 命中风险 findings=['身份证','act:转人工']（reducer 追加） |
| EX-44-02 | `python3 examples/ch44_minimal_graph/ex_44_02_reducer_semantics.py` | 0 | 覆盖丢失→['a2']；add_messages 追加；同 id 替换；去重 |
| EX-44-03 | `python3 examples/ch44_minimal_graph/ex_44_03_messages_state.py` | 0 | dict 输入自动转 HumanMessage；两轮互不记忆（无 checkpointer） |
| EX-45-01 | `python3 examples/ch45_conditional_routing/ex_45_01_conditional_route.py` | 0 | Mock 结构化分类三路由（Mock 运行输出） |
| EX-45-02 | `python3 examples/ch45_conditional_routing/ex_45_02_loop_and_recursion.py` | 0 | 第 3 轮通过；recursion_limit=5 熔断 GraphRecursionError |
| EX-45-03 | `python3 examples/ch45_conditional_routing/ex_45_03_send_fanout.py` | 0 | 3 份扇出 [2,16,7]；1 份自适应 [4]（hub 结构重构后复跑通过） |
| EX-46-01 | `python3 examples/ch46_tool_loop/ex_46_01_tool_loop.py` | 0 | 两轮工具调用，消息序列 6 条；call_001/call_002（修复过 id 重复） |
| EX-47-01 | `python3 examples/ch47_persistence/ex_47_01_persistence_memory.py` | 0 | 同 thread 4 条消息；跨 thread 隔离；6 检查点 next 序列 |
| EX-47-02 | `python3 examples/ch47_persistence/ex_47_02_persistence_sqlite.py` | 0 | SqliteSaver 3.1.2：新"进程"读到 4 条并续跑至 6 条 |
| EX-47-03 | `python3 examples/ch47_persistence/ex_47_03_time_travel.py` | 0 | 重放 ['step_one','step_two']；分叉 ['step_one','手工修正','step_one','step_two'] |
| EX-48-01 | `python3 examples/ch48_human_in_loop/ex_48_01_human_approval.py` | 0 | 暂停 next=('approve',)；resume=True 执行；False 拒绝 |
| EX-48-02 | `python3 examples/ch48_human_in_loop/ex_48_02_side_effect_idempotency.py` | 0 | 反面教材 2 次；正面（interrupt 前置+账本）从中断检查点重放仍 1 次，idempotent-skip |
| EX-49-01 | `python3 examples/ch49_parallel_subgraph/ex_49_01_parallel_merge.py` | 0 | findings 3 条归并；risk_score=5 |
| EX-49-02 | `python3 examples/ch49_parallel_subgraph/ex_49_02_subgraph.py` | 0 | schema 对齐与显式映射两路均通 |
| EX-50-01 | `python3 examples/ch50_streaming_errors/ex_50_01_stream_modes.py` | 0 | values 3 帧 / updates 2 帧 / messages 2 帧 |
| EX-50-02 | `python3 examples/ch50_streaming_errors/ex_50_02_retry_and_errors.py` | 0 | 第 3 次成功；耗尽抛 ValueError；错误即数据降级 |
| EX-51-01 | `python3 examples/ch51_graph_testing/ex_51_01_graph_testing.py` | 0 | 4 PASS（首跑暴露缺 resume 步骤，已修复） |
| 混订 stream | `stream_mode=['updates','values']` 探测 | 0 | (模式名, 内容) 元组交替，教材 50.4 收录 |

## 3. 项目二运行（projects/p2_log_triage）

| 命令 | 退出码 | 结果摘要 |
|---|---|---|
| `python3 scripts/build_data.py` | 0 | 生成 data/：3 类日志 + service_status.json + ops_inventory.sqlite |
| `python3 scripts/run_triage.py --scenario payment-outage --auto-approve` | 0 | 暂停于审批（审批单 JSON）→ resume=True → P1 结论：order-service 受 payment-service 故障影响（timeout），印证 3 条，restart executed；审计 17 条事件。首跑暴露 CLI 未挂 checkpointer（RuntimeError），已修复 |
| `python3 scripts/run_triage.py --scenario clean` | 0 | UNKNOWN + "证据不足，无法下结论" + 缺口清单 |
| `python3 scripts/resume_demo.py` | 0 | A：进程内拒绝（skipped_unapproved，账本 0 行）；B：SqliteSaver 跨"进程"恢复（executed）；C：从暂停检查点重放（already_done，executed 记录仍 1 条）。首跑含调试残留代码，已清理后复跑 |
| `python3 scripts/run_triage.py --scenario gateway-only` | 未单独跑 | 场景在 CLI 中定义，行为由 P2 测试组等价覆盖（connection_refused 路径） |

## 4. pytest（全书回归）

| 阶段 | 命令 | 结果 |
|---|---|---|
| 基线 | `python3 -m pytest tests/` | 184 passed |
| 新增部分测试（含并行作者中途加入的 ch38/40/41） | `python3 -m pytest tests/` | 311 passed（其中 ch43~51 共 40 个 + test_p2 14 个为本部分新增；修复记录：StateGraph(dict) 丢输入键、局部 reducer NameError、path_map 缺值 KeyError、缺 checkpointer/thread_id、reducer 通道类型冲突、EX-51-01 漏 resume、test_ch47 断言值笔误） |
| 最终复核 | `python3 -m pytest tests/` | 见本报告末尾"最终复核"行 |

## 5. 教材文本自检

- `textbook/part08_langgraph.md`：ch43~ch51 共 9 章，每章 11 小节（N.1~N.11）齐全；汉字数 27,7xx（另含代码/表格/英文标识符，总字符 83k+）；EX 编号 19 个与示例文件一一对应；输出块均为真实运行记录或显式标注 `# Mock 运行输出`；
- 文内"待核实"清单共 7 项（PostgresSaver/durability 细节/RemoveMessage/异步 API/子图内嵌 checkpointer/interrupt response_schema/ToolNode handle_tool_errors 回调协议），均声明未验证；
- 未改动：`_meta/`、`conftest.py`、`pytest.ini`、`requirements*.txt`、`examples/common/`、textbook 其他部分。

## 6. 依赖安装记录

- `pip install langgraph-checkpoint-sqlite` → 3.1.2（wheel 经代理下载成功后安装）。该包未写入 requirements*.txt（遵守不改基线文件约束）；tests/test_ch47.py 使用 `importorskip` 保护，未安装该包时仅跳过 SqliteSaver 用例，其余全部可跑。

## 最终复核

`cd /workspace/ai_application_course && python3 -m pytest tests/` → 311 passed（0 failed），耗时约 16s。
