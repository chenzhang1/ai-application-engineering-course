# 运行记录：第九部分（Agent、MCP 与复杂应用，ch52~ch56）+ 项目三（p3_java_python_agent）

> 环境与工具链：Python 3.14.7（pyenv）、langchain 1.4.6、langchain-core 1.6.12、langgraph 1.2.16、pydantic 2.14.1、fastapi 0.146.0、httpx 0.28.1、respx 0.23.1、pytest 9.1.1；**Java 25.0.2（OpenJDK build 25.0.2+10-69）**；tz Asia/Shanghai。核实日期 2026-10-19。全部 LLM 相关输出为 Mock 模式（`LLM_MODE=mock` 默认，离线确定性）。

## 1. MCP 规范与依赖核实

| 事项 | 结果 |
|---|---|
| MCP 规范版本 | **2026-07-28**（WebFetch 访问 modelcontextprotocol.io/specification/latest → 版本化页面 2026-07-28，**2026-10-19 核实**）；关键事实：Hosts/Clients/Servers 三角色；Server 三原语 Tools/Resources/Prompts；Client 提供 Elicitation；传输绑定 stdio + Streamable HTTP；**servers do not initiate JSON-RPC requests**（服务端不发 Request）；安全三原则（用户同意/数据隐私/工具安全，描述视为不可信）且"协议层无法强制" |
| mcp（官方 Python SDK） | **1.30.0**（pip 实测安装可用）；stdio 握手实测协商 protocolVersion=**2025-11-25**（EX-55-03 输出为证） |
| langchain-mcp-adapters | **0.3.2**（pip 实测；`load_mcp_tools` 转换 MCP 工具为 BaseTool 实测通过） |
| **未入 requirements.txt 声明** | mcp 与 langchain-mcp-adapters 为本部分"选修演示"依赖，成稿时未写入锁定文件（requirements.txt 由全书统一管理，第九部分作者不改动）；实测版本与安装命令已写入教材 55.6/55.9，是否收编由主编统一决定；若收编需补版本锁定并回归 tests/test_ch55.py |
| HumanInTheLoopMiddleware | `interrupt_on: dict[str, bool \| InterruptOnConfig]`；`InterruptOnConfig` 为 TypedDict（allowed_decisions/description）；interrupt 载荷实测 `{"action_requests":[{name,args,description}],"review_configs":[...]}`；恢复 `Command(resume={"decisions":[{"type":"approve|reject"}]})`（probe 脚本实测 approve 执行 / reject 产生 "User rejected..." ToolMessage） |
| 其他 API 事实 | `BaseChatModel` 可直接子类化（_generate/bind_tools 覆盖，项目三 RuleChatModel 依据）；`ToolMessage.name` 由 ToolNode 正确填充（规则模型依赖其路由剧本，全链路验证）；`httpx.Timeout` 必须四参数全给或给 default（真实 ValueError，见 §5） |

## 2. 教学示例运行（全部真实运行，exit=0）

| 示例 | 命令 | 退出码 | 输出摘要 |
|---|---|---|---|
| EX-52-01 | `python3 examples/ch52_workflow_agent/ex_52_01_workflow_vs_agent_decision.py` | 0 | 5 需求判定：workflow ×2 / agent ×2 / workflow+审批 ×1 |
| EX-52-02 | `…ex_52_02_agent_loop_observable.py` | 0 | 7 事件序列 loop_start→…→loop_end；首 model_call 173.9ms 为 tiktoken 加载 |
| EX-52-03 | `…ex_52_03_plan_verify_loop.py` | 0 | 第 1 轮 S3 坏工具失败→带原因重规划→第 2 轮全过 |
| EX-53-01 | `python3 examples/ch53_single_vs_multi/ex_53_01_single_agent_limits.py` | 0 | 逐轮 130→163 tokens；误选 1/4；隔离后系统段 113→54 tokens |
| EX-53-02 | `…ex_53_02_two_role_collaboration.py` | 0 | 2 成功/1 失败；T2 重试 2 次；gaps 如实上报 |
| EX-54-01 | `python3 examples/ch54_tool_governance/ex_54_01_description_quality.py` | 0 | 误选 4/8 → 1/8（匹配器=中文 2-gram+参数格式线索；B 残留 1 例诚实展示） |
| EX-54-02 | `…ex_54_02_param_validation_permission.py` | 0 | 3 类 ValidationError 精确拦截；viewer 拒绝；admin 直调高风险拒绝+凭证放行；>20% 改道 |
| EX-54-03 | `…ex_54_03_audit_log.py` | 0 | 3 条审计（含 denied）；trace 检索与合规三问 |
| EX-55-01 | `python3 examples/ch55_mcp/ex_55_01_mcp_messages.py` | 0 | JSON-RPC 帧结构 + 帧类型速查 |
| EX-55-02 | `…ex_55_02_mcp_stdio_server.py` | 0 | stdio 模式启动即阻塞等待协议输入（预期行为，无 stdout 污染） |
| EX-55-03 | `…ex_55_03_mcp_stdio_client.py` | 0 | 握手（协商 2025-11-25/能力 experimental+prompts+resources+tools）→tools/list→tools/call 成功与 isError=True |
| EX-55-04 | `…ex_55_04_mcp_langchain_adapter.py` | 0 | load_mcp_tools 转换→BaseTool 直调→create_agent(Mock) 闭环 |
| EX-56-00 | `python3 examples/ch56_java_bridge/stub_java_service.py` | 0 | 替身自测两请求 |
| EX-56-01 | `…ex_56_01_http_tool_wrapper.py` | 0 | 正常×2 / 业务 404=数据 / 连接失败=JavaServiceError |
| EX-56-02 | `…ex_56_02_long_task_pattern.py` | 0 | 202→轮询 succeeded；取消 cancelled；终态 409；未知 404 |
| EX-56-03 | `…ex_56_03_timeout_retry_semantics.py` | 0 | 3×ReadTimeout 耗尽总耗时 1.27s；幂等重放同 adjustment_id；404 零重试 |

## 3. 项目三验证（真实执行，证据完整）

### 3.1 Java 编译与启动

```text
$ cd projects/p3_java_python_agent
$ rm -rf java/out && javac -d java/out java/PlanServer.java   → javac exit=0 OK
$ java -cp java/out PlanServer                                 → LISTENING port=8080
```

### 3.2 Java 四端点 curl（摘自 /tmp/p3_e2e_full.txt 全程记录）

```text
GET /health               → 200 {"service":"plan-server","status":"UP"}
GET /plans?date=2026-03-18 → 200 {"date":"2026-03-18","count":3,"plans":[P-1001/P-1002/P-1003]}
GET /workorders/WO-2091    → 200 {"produced_qty":900,"workorder_id":"WO-2091","status":"生产中","target_qty":1200,"plan_id":"P-1002"}
GET /workorders/WO-9999    → 404
POST /adjustments 首次（Idempotency-Key: e2e-001）→ 201 {"adjustment_id":"ADJ-0001",...}
POST /adjustments 同 key 重放 → 200 同 adjustment_id="ADJ-0001" + "idempotent_replay":true   ← 幂等证据
POST /adjustments 无幂等键 → 400
GET /slow?ms=100           → 200 {"delayed_ms":100,"ok":true}
```

### 3.3 Python 服务全链路（uvicorn planagent.main:app，真连 Java）

```text
[低风险] POST /analysis → 202 {"task_id":"task-209dcbc4c480","status":"running","poll":"..."}
         poll#1 → succeeded
         final: "分析结论：延期计划 P-1002 的调整已提交（调整单 ADJ-0002，幂等键 adj-P-1002-1260-db10649f43）..."
[高风险 approve] interrupt → waiting_approval（审批单含 submit_emergency_adjustment + args new_qty=2400）
         POST /approval {"decision":"approve","operator":"张工"} → succeeded（调整单 ADJ-0003）
         再审批 → 409
[高风险 reject] waiting_approval → {"decision":"reject","operator":"李工"} → succeeded
         final: "…建议的高风险调整被人拒绝，未执行…"（Java 侧无写请求）
[取消] waiting_approval → DELETE → 202 {"status":"cancelled"}；再 DELETE → 409；GET 未知任务 → 404
[审计] audit/audit.jsonl 尾部 8 行：query_plans/human_approval(waiting/approved/rejected)/
       submit_emergency_adjustment(ok)/cancel_task(cancelled) 全留痕
```

全程记录：`/tmp/p3_e2e_full.txt`（本次验证 2026-10-19）；关键输出已摘录进教材 56.9 与项目 README §6。

### 3.4 Dockerfile 静态检查（沙箱无 Docker，未实际构建）

```text
PASS FROM 存在 / 基础镜像为官方 slim / 顶层单条 CMD / 最后一条指令为 CMD /
     EXPOSE 8000 / HEALTHCHECK 存在 / 无硬编码密钥 / ENV 含 LLM_MODE=mock / --workers=1
→ Dockerfile 静态检查全部通过（仅静态检查）
```

## 4. pytest（全书回归）

| 范围 | 命令 | 结果 |
|---|---|---|
| ch52~ch56 新增 | `python3 -m pytest tests/test_ch52.py tests/test_ch53.py tests/test_ch54.py tests/test_ch55.py tests/test_ch56.py -q` | **33 passed**（ch52=6 / ch53=5 / ch54=9 / ch55=4 / ch56=9） |
| 项目三 | `python3 -m pytest tests/test_p3.py -q` | **18 passed**（单侧 respx 10 + 集成真 Java 8，集成 fixture 自动 javac+启动+回收） |
| 全书回归 | `python3 -m pytest tests/ -q` | **424 passed in 30.66s**（2026-10-19，无失败无错误；既有测试零破坏） |

test_ch55 的 4 个测试为**真实 stdio 协议闭环**（每测拉起 ex_55_02 子进程走 JSON-RPC）；test_p3 的集成测试真实编译并启动 `java/PlanServer.java`（PLAN_PORT=0 随机端口）。

## 5. 编写过程中的失败与修复（诚实记录）

| 现象 | 原因 | 修复 |
|---|---|---|
| ex_53_02 首跑 `StructuredOutputError: … SubTask 校验：1 个错误` | Mock 结构化解析缺必填 subtask_id（用户消息没给 key=value） | 输入补 `subtask_id=T1`；教训已写入教材 53.7① |
| ex_54_01 初版结论行硬编码"4/8→1/8"与实际 3/8 不符 | 匹配器过弱+结论未由数据计算 | 重写匹配器（中文 2-gram+格式线索）并让结论由实验数据计算，B 残留误选诚实保留 |
| ch56 示例 `ValueError: httpx.Timeout must either include a default…` | 只传 connect/read | 四参数显式给全；真实报错收进教材 56.7① |
| ex_56_03 [1] 返回 404 not_found | 替身服务只在 do_POST 实现了 /slow | do_GET 补 /slow；真 Java PlanServer 同样双方法支持 |
| 取消后重复 DELETE 返回 202 而非 409 | 替身终态集合漏了 cancelled | 补全 {"succeeded","failed","cancelled"} |
| test_p3 直调 `.invoke()` 报 `'function' object has no attribute 'name'` | build_tools 忘加 @tool 装饰 | 补装饰器 |
| test_p3 reject/approve 分支 final 为空 | resume 用了新建的 InMemorySaver（ch48 铁律） | run/resume 共享同一 checkpointer |
| 集成 fixture `FileNotFoundError: 'java'` | env 白名单丢了 mise 的 java 路径 | `{**os.environ, "PLAN_PORT": "0"}` + shutil.which("java") |
| JavaClient 重试耗尽裸抛 httpx.ReadTimeout | 未统一包装 | `_raise_exhausted` 统一包 JavaServiceError（教材 56.5③） |
| 替身服务在超时演示时刷 BrokenPipeError 堆栈 | 客户端超时断连后服务端写响应 | handle_one_request 捕获 BrokenPipe 并注释说明（教材 56.7②） |
| 高风险工具可被绕过 Agent 直调 | 工具体缺第二道闸门 | ToolContext.approved_tools 凭证机制 + resume 时发放（教材 54.5②） |

## 6. 未验证项 / 待核实（汇总）

1. **Docker 构建**：沙箱无 Docker，Dockerfile 仅静态检查（README/教材均已标注）；
2. **Spring Boot 对照实现**：README §11 为形状对照示意，未在沙箱运行 Spring 版本；
3. **真实模型路径**：`LLM_MODE=real` 分支代码存在（build_model），沙箱无 OPENAI_API_KEY 未实测——全部 Agent 行为验证基于规则模型（Mock）；
4. **MCP Java SDK / Streamable HTTP 鉴权细节 / 身份透传 schema**：教材 55.9 已标"待核实"；
5. **mcp 1.30.0 / langchain-mcp-adapters 0.3.2 锁定**：未入 requirements.txt（见 §1 声明），收编与否待主编决策；
6. **项目三进程内任务表/内存 checkpointer**：教学实现，生产替换路径见 README §13（第十部分展开）。
