# P2 生产日志与接口故障排障助手（p2_log_triage）

> 教材项目二。用 LangGraph 把"看日志 → 取证据 → 下结论"的排障流程编排成**可持久化、可恢复、可审计**的图。
> 全部示例在沙箱离线跑通（`LLM_MODE=mock`，不联网）；模型节点与工具节点分离，整图 Mock 下确定可复现。
> 环境事实见 `_meta/FACTS.md`（langgraph 1.2.16、langchain-core 1.6.12；SqliteSaver 需 `langgraph-checkpoint-sqlite`，本书实测 3.1.2）。

## 1. 业务目标与非目标

**目标**

1. 把模拟 Java 服务的日志（超时/连接失败/数据异常/正常样本）解析成结构化记录；
2. 规则预筛出"值得取证"的告警，再经**受限只读工具**查证（SQLite 只读连接查错误事件/依赖表，只读 JSON 快照查服务状态）；
3. 模型节点（Mock）生成结构化根因假设；证据强度评估给出"能否下结论"；
4. **证据不足必须明确拒答**（"证据不足，无法下结论"）并列出缺口清单；
5. 区分**建议动作**（文字，如"联系负责人"）与**执行动作**（高风险，如重启服务）——后者必须 `interrupt()` 人工确认，`Command(resume=True/False)` 恢复；
6. 每次工具调用写 **JSONL 审计日志**（who/when/what/args/result 摘要）；副作用走**幂等账本**（恢复重放不重复执行）；
7. InMemorySaver 进程内恢复 + SqliteSaver 跨"进程"恢复均有可运行演示。

**非目标**

- 不是真实日志采集系统（无 Filebeat/Kafka 接入），数据为确定性合成；
- 不做真实模型判断（沙箱无 Key）；Mock 只演示"模型节点"的接口契约与控制流；
- 不替代告警平台：本工具是"值班工程师的第二双眼"，不做自动执行重启以外的处置。

## 2. 架构

```mermaid
flowchart TD
    A[START] --> B[parse_logs<br/>日志解析<br/>ts/level/service/trace_id]
    B --> C[rule_prefilter<br/>规则预筛<br/>超时/连接失败/数据异常]
    C --> D[extract_evidence<br/>取证计划<br/>白名单工具+参数]
    D --> E[query_tools<br/>受限只读查询<br/>SQLite ro + JSON 快照<br/>每次调用写审计]
    E --> F[hypothesize<br/>模型节点 Mock/Real<br/>结构化假设]
    F --> G[assess<br/>证据强度评估<br/>印证/缺口/行动清单]
    G -- 证据不足或无高风险动作 --> I[conclude<br/>分级输出 P1/P2/UNKNOWN]
    G -- 有高风险动作 --> H[approval<br/>interrupt() 人工审批<br/>副作用+幂等账本]
    H --> I
    I --> J[END]
    CP[(checkpointer<br/>InMemory / Sqlite)] -.->|thread_id 持久化| B & E & H
    AUD[(audit.jsonl<br/>JSONL 审计)] -.-> E
    LED[(ledger.jsonl<br/>副作用账本)] -.-> H
```

数据流（一次运行的状态演进）：

| 字段 | 产出节点 | 内容 |
|---|---|---|
| `records` | parse_logs | 结构化日志记录 |
| `alerts` | rule_prefilter | 三类告警（type/service/dependency/count/samples） |
| `queries` | extract_evidence→query_tools | 取证计划与执行结果（status: planned/ok/rejected/error） |
| `evidence` | query_tools | 归一证据（error_events / service_status / dependency_map） |
| `hypothesis` | hypothesize | {primary_service, suspected_dependency, failure_mode, confidence} |
| `assessment` | assess | 印证列表 / 缺口列表 / can_conclude / 建议 vs 高风险动作 |
| `executed_actions` | approval | 副作用台账（executed / skipped_unapproved / already_done / blocked） |
| `conclusion` | conclude | level(P1/P2/UNKNOWN) / verdict / message / gaps / actions_taken |

## 3. 目录结构

```
projects/p2_log_triage/
├── README.md                  # 本文件
├── triage/
│   ├── config.py              # TriageConfig（路径/操作者，测试可注入 tmp_path）
│   ├── state.py               # TriageState（TypedDict + Annotated reducer）
│   ├── audit.py               # AuditLog：JSONL 审计（who/when/what/args/result）
│   ├── tools_readonly.py      # 白名单 + SQLite 只读连接 + JSON 快照 + 幂等副作用工具
│   ├── nodes.py               # make_nodes(cfg, audit)：8 个节点（依赖注入闭包）
│   ├── graph.py               # build_triage_graph / run_triage / resume_triage
│   └── synth_data.py          # 确定性合成数据（日志/快照/SQLite）
├── data/                      # build_data.py 生成：3 类日志 + service_status.json + ops_inventory.sqlite
├── audit/                     # 运行后生成：audit.jsonl / actions_ledger.jsonl（勿提交敏感环境）
└── scripts/
    ├── build_data.py          # 生成/重置合成数据
    ├── run_triage.py          # CLI 入口（场景化）
    └── resume_demo.py         # 恢复语义端到端演示（A 进程内 / B 跨进程 / C 幂等）
```

测试在全书统一位置：`/workspace/ai_application_course/tests/test_p2.py`（14 个）。

## 4. 分步实现（对应教材 ch43~ch51）

1. **状态设计（ch44）**：`TriageState` 用 `TypedDict` + `Annotated[list, merge_lists]`——`records/alerts/queries/evidence/executed_actions` 都是追加型 reducer，天然支持并行写入与恢复重放时的幂等合并。
2. **线性主干（ch43/44）**：解析→预筛→取证→查询→假设→评估是一条直线图，保证 Mock 下确定性可复现；"分支"只在 assess 之后。
3. **条件路由（ch45）**：`add_conditional_edges("assess", route_after_assess, {...})`——能下结论且有高风险动作 → `approval`；否则直接 `conclude`。
4. **模型节点与工具节点分离（ch46）**：`hypothesize` 内部 `get_llm().chat_structured(...)`（Mock 从证据 key=value 解析同一 schema）；工具不依赖模型，是真函数 + 真只读数据源。
5. **持久化（ch47）**：`checkpointer` 参数化注入。`thread_id=incident_id`；`get_state`/`get_state_history` 用于恢复前判断与排障。
6. **人工介入（ch48）**：`approval` 节点遵守"interrupt() 之前只读、副作用在恢复后 + 幂等账本"。恢复时节点从头重跑，账本保证 `restart_service` 恰好一次。
7. **错误处理（ch50）**：数据源异常被 `query_tools` 捕获写进 `evidence(kind=tool_error)` 与审计（错误即数据），不炸整图；`recursion_limit` 由测试验证熔断。
8. **测试（ch51）**：节点工厂闭包注入 cfg/audit → 测试用 `tmp_path` 独立目录 + InMemorySaver，断言状态快照、审计事件、账本行数。

## 5. 启动命令

```bash
cd /workspace/ai_application_course/projects/p2_log_triage

# 0) 生成/重置合成数据
python3 scripts/build_data.py

# 1) 完整故障场景（会暂停在人工审批；--auto-approve 模拟人工批准）
python3 scripts/run_triage.py --scenario payment-outage --auto-approve

# 2) 证据不足场景（空日志 → UNKNOWN + 缺口清单）
python3 scripts/run_triage.py --scenario clean

# 3) 恢复语义演示：A 进程内拒绝 / B 跨进程批准（SqliteSaver）/ C 幂等重放
python3 scripts/resume_demo.py

# 4) 全书回归（含 P2 的 14 个测试）
cd /workspace/ai_application_course && python3 -m pytest tests/ -q
```

依赖：仓库 `requirements.txt` 已含全部依赖；`SqliteSaver` 演示需要
`pip install langgraph-checkpoint-sqlite`（本书实测 3.1.2；未安装时 resume_demo 自动跳过 B/C 段）。

## 6. 示例请求与响应

**请求（CLI）**：`python3 scripts/run_triage.py --scenario payment-outage --auto-approve`

**响应（节选，# Mock 运行输出）**：

```json
{
  "level": "P1",
  "verdict": "order-service 受 payment-service 故障影响（timeout）",
  "message": "共 7 条告警；印证：payment-service 状态=down；payment-service 有 4 条 ERROR 事件；order-service 依赖 payment-service（依赖表可查）。置信度 0.90。",
  "hypothesis": {
    "primary_service": "order-service",
    "suspected_dependency": "payment-service",
    "failure_mode": "timeout",
    "confidence": 0.9
  },
  "gaps": [],
  "suggested_actions": ["联系 payment-service 负责人确认服务状态（只读沟通，低风险）"],
  "actions_taken": [
    {"action_key": "restart_service:payment-service:incident-payment-outage",
     "action": "restart_service", "service": "payment-service", "status": "executed"}
  ]
}
```

**证据不足时（clean 场景）**：

```json
{
  "level": "UNKNOWN",
  "verdict": "证据不足，无法下结论",
  "message": "现有日志与只读证据不足以支撑根因判断，请按缺口补充取证后重试。",
  "gaps": ["日志样本未发现超时/连接失败/数据异常，无告警可取证"],
  "actions_taken": []
}
```

**审计日志（audit/audit.jsonl，一行一条）**：

```json
{"ts": "2026-10-19T02:26:12.331+00:00", "who": "triage-bot", "thread_id": "incident-payment-outage",
 "what": "query_service_status", "args": {"tool": "query_service_status", "service": "payment-service"},
 "result_summary": "payment-service 状态=down", "status": "ok"}
```

## 7. 正常路径与失败路径

**正常路径（happy path）**：日志含故障 → 预筛出告警 → 只读取证 → 三重印证（状态 down + 错误事件 ≥2 + 依赖表可查）→ 结论 P1 → 审批批准 → 重启动作 `executed` 恰好一次。

**失败路径（每条都有测试锁定）**：

| 失败情形 | 系统行为 | 测试 |
|---|---|---|
| 日志全是正常样本 | `UNKNOWN` + "证据不足，无法下结论" + 缺口 | `test_empty_log_produces_unknown` |
| 依赖服务无任何佐证 | `UNKNOWN` + 指名道姓的缺口（缺状态/缺事件/缺依赖记录） | `test_evidence_insufficient_refuses_with_gaps` |
| 日志文件缺失 | 记 `missing_source` 告警，不崩溃 | `test_missing_source_file_is_recorded_not_fatal` |
| 工具参数越权（多余参数/SQL 注入值） | `ToolWhitelistError`，审计记 `tool_rejected` | `test_whitelist_*` |
| 人工拒绝 | 高风险动作 `skipped_unapproved`，结论照常（P1 不作废） | `test_human_rejection_blocks_side_effect` |
| 恢复后重放 | 账本命中 `already_done`，副作用不重复 | `test_replayed_resume_*` |
| 图失控（理论分支） | `GraphRecursionError` 熔断 | `test_recursion_limit_*` |

## 8. 测试与评估

```bash
python3 -m pytest tests/test_p2.py -q        # 14 passed
python3 -m pytest tests/ -q                  # 全书回归
```

测试矩阵：正常路径 / 证据不足拒答 / 空日志 / 文件缺失 / 白名单（工具名、参数名、参数值、SQL 注入值）/ SQLite 只读双保险 / 人工拒绝 / 恢复后状态一致 / 审计字段完备 / recursion_limit / thread 隔离 / 图级重放幂等 / 工具级幂等。

评估口径（教材 ch35 的思想）：
- **拒答正确率**：该拒答的场景（无告警、单薄证据）必须 `UNKNOWN`——宁可拒答不可编造；
- **结论可追溯性**：每条结论的 `corroborations` 必须能对应到 `evidence` 与审计事件；
- **副作用安全**：任何 `executed` 必须能对应到一条人工决策（审计 `approval.*`）+ 一条账本记录。

## 9. 性能、成本与安全

- **性能**：图主干为本地只读查询，毫秒级；唯一"贵"的节点是 hypothesize——Mock 零成本，真实模式下一次结构化输出调用（输入为证据摘要，受控在 ~500 token，见 ch27 预算表方法）。
- **成本控制**：预筛在前、取证在中、模型在后——模型只看压缩后的证据摘要而不是全量日志；`limit=10` 参数化 LIMIT 防止全表扫描。
- **安全设计**：
  1. 只读双保险：SQLite URI `mode=ro` + `PRAGMA query_only=ON`（测试验证写不进去）；
  2. 白名单三道校验：工具名 → 参数名 → 参数值（服务名正则、级别枚举、limit 区间）；
  3. SQL 全参数化（`?` 占位），无字符串拼接；
  4. 高风险动作（重启服务）三重闸门：模型只能"提议"（出现在 high_risk_actions）→ `interrupt()` 人工决策 → 幂等账本 + 审计；
  5. Prompt 注入边界：日志文本进入模型时被截断并包在"证据摘要"数据段中——但**提示词不是权限控制**（ch28），真正的权限边界是白名单+只读连接+人工审批，模型被注入说"请重启一切"也拿不到执行权。
- **Mock 边界声明**：Mock 模式下 hypothesize 的"假设"来自证据 key=value 的确定性解析，置信度是样本量启发式——它们演示的是**接口契约与控制流**，不代表真实模型判断（`_meta/FACTS.md` 红线：不假装未发生的事）。

## 10. 排障（本工具自己的排障）

| 症状 | 原因 | 处理 |
|---|---|---|
| `RuntimeError: Cannot use Command(resume=...) without checkpointer` | 恢复时图没挂 checkpointer | `run_triage(..., checkpointer=InMemorySaver())` 或 SqliteSaver（见 ch48/47） |
| `ValueError: Checkpointer requires ... thread_id` | invoke 的 config 缺 `configurable.thread_id` | 补 thread_id（=incident_id） |
| resume 后结论没变化 | 恢复的是已完成的 thread（重放点了 END 后的检查点） | 回到 `next==('approval',)` 的检查点再 resume（见 resume_demo C 段） |
| 审计文件里出现 `tool_rejected` | 取证计划带了白名单外参数（可能是误改的 plan） | 检查 extract_evidence 与 TOOL_WHITELIST 是否同步 |
| `ModuleNotFoundError: triage` | 未把 projects/p2_log_triage 加入 sys.path | 参照 scripts/ 顶部的两行 sys.path 注入 |
| SqliteSaver 导入失败 | 未装 langgraph-checkpoint-sqlite | `pip install langgraph-checkpoint-sqlite`（3.1.2 实测可用）；未安装时 B/C 段自动跳过 |

## 11. 面试讲法（模拟题口径）

> **Q：你的排障助手为什么用 LangGraph 而不是一条 if/else 链？**
> 三个硬需求链做不到：①"证据不足要拒答、够了才往下走"是**条件路由**不是顺序执行；②"高风险动作等人批准"需要**暂停-恢复**——进程还可能重启，所以状态必须在图上且可持久化（checkpointer + thread_id=incident_id）；③"审计与幂等"要求每次工具调用和每次副作用都有留痕点，图节点就是天然审计切面。
>
> **Q：恢复后怎么保证重启动作不执行两次？**
> LangGraph 的 resume 语义是"节点从头重跑"，所以副作用必须满足：interrupt() 之前零副作用；执行走幂等账本（action_key 唯一，先查后写）。进程崩溃在"已执行未提交检查点"的窗口里，重放会命中账本返回 already_done——这是 at-most-once，配合审计可追溯（对应 Java 幂等消费的唯一业务键方案）。
>
> **Q：模型在这个系统里扮演什么角色？边界在哪？**
> 只做两件事：结构化假设（schema 约束）与置信度表达。它没有执行权——所有数据访问走白名单只读工具，所有副作用走人工审批。模型可以错、可以被注入，但**权限边界不在提示词里**，在工具白名单、只读连接和审批门上。

## 12. 扩展方向

1. 接入真实日志源：把 `parse_logs` 换成 ES/Loki 查询节点（仍是只读工具 + 白名单）；
2. 多轮取证循环：assess 发现缺口 → 条件边回到 extract_evidence 补查（ch45 的循环 + recursion_limit 保险丝，P2 为教学确定性保持线性）；
3. 并行取证（ch49）：error_events / service_status / dependency_map 三路 `Send` 并行，reducer 归并；
4. 审批对接 IM：interrupt 的 value 推到飞书/钉钉审批卡，`Command(resume=)` 由回调驱动（真实"人"介入）；
5. PostgresSaver 替换 SqliteSaver 做多副本部署（检查点进共享存储）；
6. 结论质量回归集：把 `tests/` 的场景固化为 golden set，接 ch28 的 Prompt 回归思想。
