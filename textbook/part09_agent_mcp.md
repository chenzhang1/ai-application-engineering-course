# 第九部分 Agent、MCP 与复杂应用（ch52~ch56）

> **本部分定位**：第七、八部分分别给了你 Agent 的"框架快捷方式"（create_agent）与"手写能力"（LangGraph）。本部分回答工程落地前的最后一组问题：**这个需求该用 Workflow 还是 Agent（ch52）？该用单 Agent 还是多 Agent（ch53）？工具多了怎么管住（ch54）？工具如何标准化地暴露给模型（ch55，MCP）？以及全书的主线问题——怎么和已有的 Java 系统协作（ch56，项目三把 ch52~ch56 全部串起来）**。
> **环境与核实基线**：langchain 1.4.6 / langgraph 1.2.16（沙箱实测）；MCP 规范版本 **2026-07-28**（编写日 2026-10-19 经官网 modelcontextprotocol.io 核实，核实方式与日期在 55.2 明确标注）；mcp（官方 Python SDK）1.30.0 与 langchain-mcp-adapters 0.3.2 已在沙箱安装并实测——**二者未入 requirements.txt 锁定文件**（原因与建议见 55.9"待核实"小节，由主编统一决定是否收编）。
> **如何读本部分**：赶项目的人按 ch52（决策表）→ ch56（集成模式）→ 项目三 → ch54（工具治理）的顺序读，两天可落地一个最小版本；ch53 与 ch55 是"要评审判你讲得出边界"的部分，放到第一遍做完项目后回读。每章的 N.7（排障）建议全部过一遍——本部分的错误形态在生产中出现率极高。全部 16 个 EX 可离线复现（LLM_MODE=mock），run log 见 verification/run_logs/part09.md。

---

# 第 52 章 Workflow vs Agent：把选型变成可执行的决策表

> **本章目标**：给一条业务需求，用三个硬问题判定它该用 Workflow（控制流写死）还是 Agent（模型决定控制流）；学会从**外部**观察一个 Agent loop（日志/事件流），而不是把它当黑盒；掌握任务拆解/规划/验证在工程上的最小闭环。
> **前置知识**：ch42（create_agent 与六步循环）、ch45（条件路由与循环）、ch48（人工介入）。
> **学完你能做什么**：在架构评审时拿出一张可运行的决策表而不是"我感觉"；给 Agent 加上事件追踪让排障有据可查；为模糊目标写出"拆解→执行→验证→重规划"的闭环。

## 52.1 真实问题引入：评审会上吵起来的"要不要上 Agent"

某电商平台的售后团队（合成案例）要做一个"发票信息提取后路由工单"的功能。方案评审会上，刚从短视频学完 Agent 的同学坚持"用 Agent，让模型自己决定下一步"；负责对账系统的老工程师反问："步骤就三步——抽取、校验、路由，每一步的输入输出都是定死的，为什么要让模型来决定流程？出了错谁负责？"两边谁也说服不了谁，因为**争论的双方都没有说出判断标准**。

这个争论的答案是：**不是"Agent 更先进所以更对"，而是"控制流由谁决定"**。路径能提前画死的，控制流就该写死（Workflow）；路径取决于运行时读到的数据和模型判断的，才需要 Agent。本章把这句话变成三个可回答的硬问题和一张可运行的决策表。

## 52.2 一句话解释 + 生活类比 + 类比边界

**一句话解释**：Workflow 是你写死的控制流调用模型（模型只做节点内的"脏活"），Agent 是模型决定控制流（你在旁边放工具和护栏）；选型的本质是回答"路径能不能提前画出来、失败了要不要换路、出错的代价多大"。

**生活类比**：Workflow 像**流水线**——工位顺序固定，每个工位操作标准化，质检点在固定位置；Agent 像**老师傅带徒弟修疑难杂症**——先看哪里响（查）、再猜原因（假设）、拆开验证、不对就换个思路再来。Java 对照：Workflow ≈ Spring Integration 的固定消息通道编排 / Camunda 的 BPMN 流程定义；Agent ≈ 一个"节点内部逻辑由 LLM 即时决定"的动态流程，LangGraph（ch44 起）就是你画这张动态流程图的引擎。

> 💡 类比边界：
> 1. 流水线的质检是**抽样**，Workflow 的验证节点可以全量且确定性（断言字段、格式、业务规则）——**能写进 if 的判据绝不要让模型猜**；
> 2. 老师傅也会用固定流程处理常见故障——真实系统几乎总是"Workflow 骨架 + 个别 Agent 节点"的混合体，不是二选一；
> 3. Agent 的"自主"只发生在**选工具与定参数**这一层；权限、预算、终止条件永远在你的代码里（ch54/ch42 护栏）。

## 52.3 正式原理与准确术语

**Workflow（工作流）**：控制流（control flow，即"下一步做什么"的决策序列）由开发者预先定义的应用形态。节点可以内部调用模型（抽取、分类、生成），但"走哪条边"是代码。英文术语 workflow / orchestrated pipeline。

**Agent（智能体）**：控制流由模型在运行时决定的应用形态——模型看到目标与工具清单，自己决定调用哪个工具、传什么参数、何时收口（ch24 的六步闭环、ch42 的框架托管版）。英文术语 agent / tool-using LLM loop。

**三条硬问题（决策表的行为准则）**：
- **Q1 路径能不能提前画出来？** 能 → Workflow。判据：把流程画在白板上后，每条边都能标注"由什么字段/规则决定"。
- **Q2 失败了要不要"换一条路再试"？** 要换路（换参数、换工具、换顺序）→ Agent 的本职；只需原样重试的，退避重试中间件就够（ch42 ToolRetryMiddleware），不需要 Agent。
- **Q3 出错时业务能接受多大代价？** 代价高 → 收敛自由度：要么降级为 Workflow，要么保留 Agent 但给高风险动作挂人工审批（ch48 的 interrupt——项目三的高风险调整正是这么做的）。

**Agent loop 的外部可观察执行方式**：Agent 从外面看是"输入一句话，输出一段话"的黑盒函数，但 loop 的每一步都可以发**结构化事件**：`loop_start / model_call（含 finish_reason 与点名的工具）/ tool_call / tool_result / final_answer / loop_end`，字段统一（round、tool、args、duration_ms）。这些事件就是 ch54 审计日志与 ch60 可观测性的数据源——**事件模型先定好，落盘只是换个 handler**。

**任务拆解/规划/验证的工程形态**：不让模型"一口气做完"，而是三段闭环——
- **拆解（decompose）**：用结构化输出（ch26/ch38 的 schema 约束）把模糊目标变成子任务清单，**每个子任务必须自带"完成判据"（done_when）**，否则验证无从谈起；
- **执行（execute）**：逐个子任务调工具，异常转成失败记录而不是炸掉循环（"错误即数据"）；
- **验证（verify）**：对照判据检查每个子任务——能用确定性规则验证的用规则（返回非空、字段齐、数值范围），必须语义判断的用模型判分；不合格的**带着失败原因**重新规划；重规划次数有上限（max_attempts），到顶就带已有结论收口并转人工——这是防失控的第一道保险丝。

**规划（planning）的三种工程形态**（按"计划由谁、何时产生"划分，选型的依据是任务的确定性比例）：

| 形态 | 计划产生方式 | 适用 | 风险 |
|---|---|---|---|
| 一次性计划（plan-then-execute） | 开始时模型产出完整 Plan，之后纯执行 | 步骤间依赖稳定、中途信息不变 | 执行中发现计划错了要整盘重规划 |
| 增量规划（interleaved） | 每步执行后模型决定下一步（ReAct 风格） | 下一步强依赖上一步结果 | 无全局视野，可能绕远/循环——靠事件流+上限护栏兜底 |
| 固定骨架+LLM 节点 | 人画流程图，LLM 只做节点内的判断 | 大部分业务系统（推荐默认） | 不是真"规划"，但可控可测 |

EX-52-03 是一次性计划的最小形态；ch42 的 create_agent 是增量规划（模型每轮决定点不点工具）；项目三是"固定骨架+LLM 节点"（分析主链 Agent 化、提交链路写死）。**历史注记**：ReAct（Reasoning+Acting 交替）是增量规划的学术起源名词，面试常考——答出"它是一种增量规划模式，对应今天的工具循环"即可，不必展开论文。

**护栏（guardrail）**：约束 Agent 行为的代码机制总称——步数上限、工具白名单、参数校验、权限分级、审批门、预算上限。记忆句：**护栏回答"不许做什么"，prompt 回答"建议做什么"**——两者的可靠性相差一个数量级，所以护栏必须代码化（ch28 的红线在 Agent 层的重述）。

**Java 对照**：决策表三问 ≈ 技术选型评审清单；事件流 ≈ Micrometer/Logback MDC 里的 trace 日志；拆解-执行-验证 ≈ 测试驱动开发的"红-绿-重构"在 Agent 世界的对应物。

## 52.4 最小完整示例：决策表、事件流、计划-验证闭环

**EX-52-01 | examples/ch52_workflow_agent/ex_52_01_workflow_vs_agent_decision.py（完整可运行）**

```python
# EX-52-01 | Workflow 还是 Agent：把选型变成可执行的决策表 | 运行: python3 examples/ch52_workflow_agent/ex_52_01_workflow_vs_agent_decision.py
"""确定性演示（纯标准库，无模型调用）：给 5 个真实业务需求逐条打分，
输出"该用 Workflow 还是 Agent"的判断与理由（三条硬问题的组合逻辑）。"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal

@dataclass
class Requirement:
    name: str
    steps_known_in_advance: bool    # Q1: 路径可提前画死吗
    needs_reroute_on_failure: bool  # Q2: 失败要换路吗
    blast_radius: Literal["low", "high"]  # Q3: 出错代价

def decide(req: Requirement):
    reasons = []
    choice = "workflow" if req.steps_known_in_advance else "agent"
    reasons.append("Q1=能：路径可提前画出，控制流写死反而可测试、可审计" if req.steps_known_in_advance
                   else "Q1=否：路径取决于运行时读到的数据/模型判断，需要动态路由")
    if req.needs_reroute_on_failure:
        reasons.append("Q2=要：失败后要换一条路（换参数/换工具/换顺序），这是 Agent loop 的本职")
        choice = "agent"
    if req.blast_radius == "high":
        if choice == "agent":
            reasons.append("Q3=代价高：Agent 自由度高 + 副作用大 → 保留 Agent 规划，但高风险动作挂人工审批")
            choice = "workflow+审批"
        else:
            reasons.append("Q3=代价高：Workflow 路径固定即可控，副作用节点前加人审门（ch48 interrupt）")
            choice = "workflow+审批"
    return choice, reasons
# main() 对 5 个需求逐一判定并打印（完整源码见示例文件）
```

```text
# 真实运行输出（纯标准库，Python 3.14.7）
== Workflow vs Agent 决策表（运行结果）==

需求：发票抬头抽取后按类别路由工单
  - Q1=能：路径可提前画出，控制流写死反而可测试、可审计
  ⇒ 结论：workflow

需求：按用户自然语言查订单+查物流+生成解释
  - Q1=否：路径取决于运行时读到的数据/模型判断，需要动态路由
  ⇒ 结论：agent

需求：排障助手：日志取证→假设→验证→（证据不足换证据再查）
  - Q1=否：… - Q2=要：失败后要换一条路（换参数/换工具/换顺序），这是 Agent loop 的本职
  ⇒ 结论：agent

需求：生产计划异常分析并自动提交延期报告
  - Q1=否：… - Q2=要：… - Q3=代价高：Agent 自由度高 + 副作用大 → 保留 Agent 规划，但高风险动作挂人工审批
  ⇒ 结论：workflow+审批

需求：月度报表：固定 SQL→固定模板→固定邮件
  - Q1=能：… ⇒ 结论：workflow
```

注意第 4 条：它同时命中 Q2（要换路）与 Q3（代价高）——这正是项目三的场景，最终形态是"Agent 做分析与建议 + 高风险提交挂审批"，而不是"全自动 Agent"或"纯 Workflow"。

**EX-52-02 | examples/ch52_workflow_agent/ex_52_02_agent_loop_observable.py（完整可运行，LLM_MODE=mock）**

```python
# EX-52-02 | Agent loop 的外部可观察行为：用日志事件流看清一轮完整循环 | 运行: python3 examples/ch52_workflow_agent/ex_52_02_agent_loop_observable.py
"""MockLLM script 驱动一轮完整工具循环，在 loop 每个环节打结构化事件
（event/round/tool/args/duration_ms）——生产上这就是审计与可观测的数据源。"""
def run_agent(question: str, *, tracer: EventTracer, max_rounds: int = 5) -> str:
    tracer.emit("loop_start", question=question)
    llm = get_llm(script=[  # 第 1 轮发起工具调用，第 2 轮整合作答（Mock 脚本见源码）
        {"tool_calls": [{"name": "query_plan", "arguments": {"plan_id": "P-1002"}}]},
        {"content": "P-1002（转向节，1200 件）当前延期，建议先查供应商交付记录。"},
    ])
    messages = [system, user]           # 省略：与 ch24 六步一致
    for round_no in range(1, max_rounds + 1):
        result = llm.chat(messages)
        tracer.emit("model_call", round=round_no, finish_reason=result.finish_reason,
                    tool_calls=[c.name for c in result.tool_calls] or None,
                    duration_ms=...)
        messages.append(assistant_msg_with_tool_calls)
        if not result.has_tool_calls:           # finish_reason=stop → 收口
            tracer.emit("final_answer", round=round_no, chars=len(result.content))
            tracer.emit("loop_end", rounds=round_no)
            return result.content
        for tc in result.tool_calls:            # 执行模型点名的每个工具
            tracer.emit("tool_call", round=round_no, tool=tc.name, args=...)
            output = TOOLS[tc.name](**tc.arguments)
            tracer.emit("tool_result", round=round_no, tool=tc.name, summary=...)
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": ...})
    raise RuntimeError(f"超过 max_rounds={max_rounds}，模型一直在点名工具（防线见 52.7③）")
```

```text
# Mock 运行输出（控制流真实运行；LLM 为 MockLLM script 驱动，离线确定性）
== Agent loop 事件流（外部观察者视角）==
  loop_start     question=P-1002 这单什么情况？
  model_call     round=1 finish_reason=tool_calls tool_calls=['query_plan'] duration_ms=173.9
  tool_call      round=1 tool=query_plan args={"plan_id": "P-1002"}
  tool_result    round=1 tool=query_plan summary={"plan_id": "P-1002", "product": "转向节",
  model_call     round=2 finish_reason=stop tool_calls=None duration_ms=0.1
  final_answer   round=2 chars=35
  loop_end       rounds=2

最终回答：P-1002（转向节，1200 件）当前延期，建议先查供应商交付记录。

事件总数=7，事件类型序列=
loop_start → model_call → tool_call → tool_result → model_call → final_answer → loop_end
```

第 1 次 model_call 的 173.9ms 是 tiktoken 首次加载编码器的开销，不是模型延迟——**这正是事件流的价值：没有 duration 字段，你连"慢在哪"都问不出来**。

**EX-52-03 | examples/ch52_workflow_agent/ex_52_03_plan_verify_loop.py（完整可运行，Mock 结构化输出）**

```python
# EX-52-03 | 任务拆解/规划/验证：一个带"验收员"的最小计划-执行循环 | 运行: python3 examples/ch52_workflow_agent/ex_52_03_plan_verify_loop.py
"""拆解（带完成判据的 Plan schema）→ 执行（错误即数据）→ 验证（确定性判据）
→ 不合格带原因重规划；max_attempts=2 是防失控保险丝。教学剧本第一轮
故意含一个坏工具名，逼出"验证→重规划"闭环（完整源码见示例文件）。"""
class Step(BaseModel):
    step_id: str
    action: str                      # 做什么（人能读懂）
    tool: str
    argument: str = ""
    done_when: str = Field(default="工具返回非空结果")   # 完成判据：验证器的依据

def verify(step: Step, result: dict) -> tuple[bool, str]:
    if not result["ok"]:
        return False, f"执行失败：{result['output']}"
    if step.tool == "query_plan" and "不存在" in result["output"]:
        return False, "判据不满足：计划号不存在，需要先确认计划号"
    if "缺口" in result["output"] and step.tool == "check_material":
        return True, "完成：缺口已量化（后续动作：采购/改排产）"
    return True, "完成：工具返回非空结果"
```

```text
# Mock 运行输出（控制流真实运行）
== 计划-执行-验证循环（Mock 驱动，确定性）==
  [attempt 1] 1 个子任务未过验证 → 带原因重规划：执行失败：未知工具 destroy_plan

第 1 轮：
  S1 query_plan         ✓ 完成：工具返回非空结果
  S2 check_material     ✓ 完成：缺口已量化（后续动作：采购/改排产）
  S3 destroy_plan       ✗ 执行失败：未知工具 destroy_plan

第 2 轮：
  S1 query_plan         ✓ 完成：工具返回非空结果
  S2 check_material     ✓ 完成：缺口已量化（后续动作：采购/改排产）
  S3 estimate_recovery  ✓ 完成：工具返回非空结果

最终：全部子任务通过验证
```

## 52.5 逐段解释

1. **决策表为什么是代码不是散文**（EX-52-01）：`decide()` 是纯函数，输入需求特征、输出结论与理由——架构评审时可以直接跑给所有人看，理由列表就是评审记录。把它抄进你的团队 wiki，下次"要不要上 Agent"的讨论就从吵架变成填表。
2. **事件流的字段设计**（EX-52-02）：`event` 类型 + `round` + `tool` + `duration_ms` 是最小可用集。`finish_reason` 必须记录——它是"模型为什么停"的唯一线索（`tool_calls` = 还要干活，`stop` = 收口，`length` = 被截断，ch21）。真实模型下同一字段还承担成本归因（每轮的 usage 串起来就是这次任务的 token 账单）。
3. **max_rounds / max_attempts 是保险丝不是功能**（EX-52-02/03）：模型抽风循环点工具、验证永不收敛，都是低概率高代价事故。保险丝触发后的正确行为是**带已有信息收口 + 转人工**，而不是静默失败（EX-52-03 的"验证两轮未收敛，带已有结论收口"分支）。
4. **完成判据必须显式**（EX-52-03）：`done_when` 写在计划里而不是验证器脑子里——这让"验证"可以被测试（test_ch52 直接对 verify() 断言），也让模型重新规划时有明确靶子。验证器本身优先用确定性规则；语义判分（"这个总结是否忠实"）交给模型时，判分 prompt 也要进版本管理（ch28）。
5. **混合架构的判定流程**（真实系统的推荐路径）：第一步跑三问决策表，把需求切成"确定段"与"动态段"；第二步把确定段画成固定骨架（Workflow 节点/普通代码）；第三步只对动态段问"这个判断能不能写成规则"——能写的继续下沉为代码，写不出的才留给模型；第四步给剩下的 Agent 段配置护栏（步数/权限/审批）。用这个流程切出来的系统，模型调用通常只占节点数的 10%~30%，而这正是它可维护的原因。反着来（先上 Agent 框架再找地方塞规则）是大多数失控项目的起点。
6. **事件流到审计的演进路径**：EX-52-02 的 EventTracer（内存+打印）→ 换 handler 写 JSONL（EX-54-03，加 who/outcome 字段）→ 采集管道聚合告警（ch60）。三个阶段用的是**同一套事件字段**——所以字段设计（52.2）要在第一天就按终态设计，升级只换"往哪儿写"，不改"写什么"。这条经验对 Java 工程师很亲切：它就是"先定日志 schema 再接 ELK"的老规矩。

## 52.6 安装 / 文件位置 / 运行命令

```bash
# 安装：本章示例只用全书 requirements.txt 已锁定的包（langchain/langgraph/pydantic 等），无新增
cd /workspace/ai_application_course
python3 examples/ch52_workflow_agent/ex_52_01_workflow_vs_agent_decision.py   # 纯标准库
python3 examples/ch52_workflow_agent/ex_52_02_agent_loop_observable.py       # LLM_MODE=mock 默认
python3 examples/ch52_workflow_agent/ex_52_03_plan_verify_loop.py
python3 -m pytest tests/test_ch52.py -q                                      # 6 个测试
```

## 52.7 常见错误与排查

**① `RuntimeError: MockLLM 的 script 已耗尽（共 2 条，已消费 2 条）`**：脚本驱动的 Mock 模型被多消费了一次——通常是 loop 没有在 `finish_reason=stop` 时退出，多请求了一轮。修复：检查终止条件（`has_tool_calls` 为假必须 return），或者给 script 补条目。这个报错在真实模式下的对应物是"账单异常增长"——护栏（run_limit，ch42）永远要有。

**② Agent 每轮回答都不一样，没法写断言**：用了真实模型又想测控制流。修复：控制流测试用 Mock/脚本模型（EX-52-02 的做法），模型质量评估走独立评估集（ch35）——两类测试别混在一层。

**③ 模型循环点工具到 recursion/步数上限才停**：没有外层保险丝时的典型事故（ch45 的 GraphRecursionError 或 ch42 的 ModelCallLimitExceededError）。修复：create_agent 挂 `ModelCallLimitMiddleware(run_limit=N, exit_behavior="end")`；手写 loop 用 max_rounds。触发后**必须留事件痕迹**（52.2 的事件流），否则复盘时只剩"它自己停了"。

**④ 验证器永远通过（摆设验证）**：`done_when` 写成"完成任务"这种不可判定的判据，verify 只能返回 True。修复：判据必须可计算（字段存在/数值范围/正则匹配/工具返回非空），写不出的判据说明这个子任务不可验收——重新拆解。

## 52.8 企业场景中的使用方式（Spring Boot 集成视角）

- **混合架构是常态**：Java 侧 Spring Integration/Camel 管确定性的消息流转，把"需要理解自然语言/需要动态换路"的节点以 HTTP/gRPC 调 Python AI 服务（ch57 展开部署形态）；Python 侧该 Workflow 的用 LangGraph 写死边，该 Agent 的用 create_agent。
- **决策表进评审**：把 EX-52-01 的 `decide()` 挂在团队的 ADR（架构决策记录）模板里，每条"用了 Agent"的需求都要有三问的答案——这是对"为了先进堆 Agent"最便宜的组织防线。
- **事件流对接现有观测**：52.2 的事件字段与 Java 侧日志的 trace_id/span 对齐后，一次用户请求可以横跨 Java 与 Python 追踪（ch60）。
- **向架构师汇报的一句话版本**："我们用决策表决定哪里用 Agent（只有动态路由的环节），用治理清单管住它的每一步（校验/权限/幂等/审计），用标准模式接进现有系统（封装/长任务/超时重试）"——三句话分别对应 ch52、ch54、ch56，也是本部分的三块里程碑。

## 52.9 练习（基础 2 + 代码 2 + 调试题 1）

**基础 1**：三条硬问题分别把需求推向哪种形态？**基础 2**：为什么"失败原样重试"不需要 Agent？
**代码 1**：给 `decide()` 增加第四问"是否需要多轮人机澄清"，需要时返回 `agent+会话`。**代码 2**：给 EX-52-03 的 `verify()` 增加"数值越界"判据（new_qty > 100_000 → 不通过），并写一个 pytest。
**调试题**：某 Agent 上线后偶发"同一查询调用 20+ 次工具"，费用告警。给出至少两条定位手段与对应修复。

### 参考答案

基础 1：Q1 能→Workflow；Q1 否且 Q2 要→Agent；Q3 代价高→收敛（Workflow+审批 或 Agent+审批）。基础 2：原样重试是固定策略（退避+上限），控制流没有"分叉"，ch42 的 ToolRetryMiddleware 即可。代码 1：`if req.needs_clarification: choice="agent+会话"`（放在 Q1 判定后）。代码 2：`if step.tool=="submit_adjustment" and result.get("new_qty",0)>100_000: return False,"判据不满足：数量越界"`。调试题：先查事件流里 tool_call 的 args 是否逐轮漂移（漂移→模型在换路，是 prompt/工具描述问题）；再查是否同 args 重复（重复→死循环，加 ToolRetryMiddleware 的 on_failure 与步数护栏；若工具本身偶发超时，修工具超时而不是加大重试）。

## 52.10 自测检查表

- [ ] 我能对一条新需求跑完三问并给出结论与理由；
- [ ] 我能给 Agent loop 设计最小事件字段集，并说清 finish_reason 的四种取值含义；
- [ ] 我能写出"拆解（带判据）→执行（错误即数据）→验证→带原因重规划"的闭环并给重试设上限；
- [ ] 我知道保险丝触发后该"带结论收口+转人工"而不是静默失败；
- [ ] 我能把这套决策与事件模型讲给 Java 团队（对应 Spring Integration/BPMN/trace 日志）。

## 52.11 面试追问

1. **[模拟题] 你的项目里哪些部分是 Workflow、哪些是 Agent，为什么？** 答：以项目三为例——分析主链是 Agent（读什么证据、要不要提交调整取决于运行时数据），但"提交前校验、幂等键生成、审计"是写死的工具层逻辑，高风险提交固定走审批节点（interrupt）。理由：控制流中只有"查什么、改不改"是数据相关的，其余全部可以也应该写死。
2. **[模拟题] Agent 的"自主性"边界在哪里？** 答：只在选工具与定参数；终止条件（步数上限）、权限（工具分级）、副作用（审批+幂等）都在代码里——模型没有也不该有"权限"。
3. **[模拟题] 怎么向没有 AI 经验的架构师解释 Agent loop 的可观察性？** 答：把它类比成一次跨服务的分布式调用：每一步发结构化事件（类似 span），事件串起来就是 trace；排障不看"模型说了什么"的玄学，看事件序列断在哪一环。

---

# 第 53 章 单 Agent vs 多 Agent：先给"不拆"的理由

> **本章目标**：给出单/多 Agent 的取舍表与判断标准，学会用三个可测量的信号判断单 Agent 是否真的到顶了；掌握多 Agent 通信（结构化消息）、共享状态（最小化）与失败处理（retry→degrade→escalate）的工程形态。
> **前置知识**：ch52（决策表）、ch49（并行与子图——多 Agent 的机械基础）。
> **学完你能做什么**：在评审时挡住"为了先进上多 Agent"的方案；真要拆时，画出角色间的通信契约与失败升级路径。

## 53.1 真实问题引入：一个"全能客服 Agent"的三次事故

某平台的客服助手（合成案例）起步时是一个 Agent：查订单、查物流、开发票、改地址、取消订单，6 个工具一把梭。三个月里出了三次事故：①大促期间响应越来越慢——每轮请求都背着全部工具描述和全部历史；②"开一张发票"被理解成"查发票"——工具描述长得太像，模型选错；③发票模块改一个字段校验，回归测试要把 6 个工具全跑一遍。团队决议"拆成多 Agent"，拆完又发现：主 Agent 把任务派给子 Agent 后，子 Agent 挂了主 Agent 不知道，用户拿到一半答案。

事故①②是"单 Agent 到顶"的真信号，事故③的修复却不是多 Agent 而是**领域隔离 + 工具治理**。本章的立场：**多 Agent 是组织复杂度的手段，不是性能手段**——先给"不拆"的理由，再给拆的规矩。

## 53.2 一句话解释 + 生活类比 + 类比边界

**一句话解释**：单 Agent 是"一个大脑配一串工具"，多 Agent 是"多个各自带工具的小脑 + 一个协调者"；拆分的收益是上下文隔离与独立演进，代价是通信、失败升级与一致性复杂度。

**生活类比**：单 Agent ≈ 一个全栈工程师什么都干——小团队效率最高；多 Agent ≈ 按领域拆成前后端小组 + 项目经理协调——只有当"所有事都进一个人的脑子"成为瓶颈时才值得。Java 对照：单体应用 → 微服务拆分的全部判断经验在这里直接复用（按领域拆、契约先行、失败要降级），**包括"不要为了简历拆微服务"这条**。

> 💡 类比边界：
> 1. 微服务拆的是**部署与数据所有权**，多 Agent 拆的是**上下文与工具可见性**——后者即使不拆进程也能做（一个进程内两个子图，ch49）；"多 Agent"≠"多服务"；
> 2. 子 Agent 之间没有"心灵感应"：它们只通过结构化消息（SubTask/SubResult）交换信息——和微服务之间只通过 API 契约通信是一个道理；
> 3. 多 Agent 不提高单次推理质量：模型还是那些模型。它改善的是"每个决策看到的上下文更相关"。

## 53.3 正式原理与准确术语

**取舍表**：

| 维度 | 单 Agent | 多 Agent |
|---|---|---|
| 上下文 | 全部历史+全部工具说明随每轮增长 | 各自独立、只装本领域内容 |
| 工具选择 | 工具多/描述近 → 误选上升 | 每个只见自己的 2~5 个 |
| 失败影响 | 一个工具炸可能污染整个会话 | 领域内失败可隔离、可降级 |
| 独立演进 | 一个改动全量回归 | 各自开发/测试/上线 |
| 通信成本 | 无 | 派工单/回执的契约设计 + 序列化 |
| 一致性 | 天然一致 | 跨 Agent 状态要显式对账 |
| 适用规模 | 工具 ≤ ~10、单领域 | 多领域、大工具集、需并行 |

**单 Agent 到顶的三个可测量信号**（EX-53-01 演示前两个）：①**上下文膨胀**——系统段+历史+工具说明的 token 数逐轮显著增长（ch27 的预算表开始报警）；②**工具误选率上升**——工具数增多或描述相近后，线上选错工具的回归样例变多；③**职责混杂**——无法独立测试/独立上线，权限模型无法按领域收敛（这一条是组织信号，不是性能信号）。

**判断标准（先给不拆的理由）**：同时满足"①或②有一个真实发生"且"领域边界清晰（能画出子域与契约）"才拆。**三个应该坚持单 Agent 的真实场景**：
- **场景 A（工具少而正交）**：项目三的 Agent——查计划、查工单、提交调整、提交紧急调整 4 个工具，描述彼此差异大，单 Agent + 好描述 + 工具治理完全够用；拆了只会多出通信故障点。
- **场景 B（流程本身是线性的）**：ch52 决策表判成 Workflow 的需求即使工具多也不需要多 Agent——多 Agent 解决不了"路径该写死"的问题。
- **场景 C（状态强共享）**：一次对话内反复交叉引用多个领域的数据（"我上次改的地址对应的订单发票开了吗"）——拆开后跨 Agent 的状态对账成本会超过隔离收益；先靠共享状态（图 state/数据库）+ 单 Agent 扛。
- **一个合理的多 Agent 场景**：跨域并行取证——排障助手同时要查日志、查工单、查变更记录，三个域各有 3~5 个工具且互不依赖，用主 Agent 拆解 + 三个子 Agent 并行（LangGraph Send 扇出，ch45/ch49），失败按域降级。收益（并行加速 + 域内隔离）明确大于通信成本。

**通信**：结构化消息（Pydantic/TypedDict 契约）——派工单 SubTask（subtask_id/domain/instruction/must_include）与回执 SubResult（status ∈ ok/degraded/failed、summary、attempts、gaps）。禁止把主 Agent 的对话历史整段塞给子 Agent（上下文污染 + token 翻倍），只传"做完这件事需要的信息"。

**多 Agent 的四种拓扑**（选择拓扑=选择信息流向，先于选择实现）：

| 拓扑 | 信息流向 | 适用 | 主要风险 |
|---|---|---|---|
| 编排者-工人（orchestrator-workers，EX-53-02） | 中心拆解→并行→汇总 | 可独立并行的取证/检索类任务 | 中心是瓶颈与单点，协议要清晰 |
| 流水线（pipeline） | 顺序交接，上游产物是下游输入 | 阶段明确的加工链（提取→清洗→生成） | 上游错误放大；每级要带校验 |
| 辩论/评审（debate） | 两个以上 Agent 互看产出并批评 | 高价值结论的交叉验证（成本高） | token 成本×角色数；防"礼貌性一致" |
| 黑板（blackboard） | 各 Agent 读写共享状态，事件驱动 | 松耦合协作、参与方不确定 | 状态一致性要自己管；难测试 |

本书示例与项目用的是第一种；LangGraph 的对应物分别是"主图+子图/Send 扇出（ch49）"、"线性边"、"循环图+共享 state"。**没有第五种"自由市场"**——让 Agent 自由对话协商在当前模型能力下不可控，工程上不做（教学上不教）。

**通信字段设计的四个要点**：①派工单要**自包含**（子 Agent 不需要追问就能干活）；②回执要有**覆盖度自检**（must_include 逐项核对，见 EX-53-02）；③所有消息带 **trace_id**（跨 Agent 串联 ch52 的事件流）；④契约进版本管理——SubTask 加字段是兼容变更，改语义是破坏变更（要走双写过渡，和 API 版本管理同规矩）。

**共享状态**：最小化——子 Agent 互不可见，协调者只消费回执；跨 Agent 需要的数据放外部存储（图 state/DB），不靠"传话"。三种实现对比：

| 实现 | 机制 | 适用 | 注意 |
|---|---|---|---|
| 图 state（LangGraph） | 共享 state + reducer 合并 | 单进程内多节点/子图 | 大对象别进 state（检查点膨胀，ch47） |
| 外部 DB/缓存 | 落库，消息里只传主键 | 跨进程/持久需要 | 记得读写权限与脱敏（ch58） |
| 黑板对象（内存） | 进程内共享 dict+锁 | 原型/教学 | 不耐并发部署，生产换前两种 |

**失败处理三级收口**：retry（同参数原样重试一次，对瞬态故障有效）→ degrade（换退路工具/降级口径，给部分结果）→ escalate（如实上报 failed + gaps，由主 Agent 决定升级或放弃）。**子 Agent 不擅自编造**——缺口如实进 gaps 字段，这是项目二"证据不足拒答"在多 Agent 下的对应纪律。

**Java 对照**：SubTask/SubResult ≈ 微服务间的 DTO 契约；must_include ≈ 验收条件；retry→degrade→escalate ≈ 重试/降级/熔断三级（Resilience4j 的语义）；主 Agent ≈ Saga 编排器，gaps ≈ 补偿事务里的待办。

## 53.4 最小完整示例：疲劳信号测量与最小两角色协作

**EX-53-01 | examples/ch53_single_vs_multi/ex_53_01_single_agent_limits.py（完整可运行）**

```python
# EX-53-01 | 单 Agent 的三个疲劳信号：上下文膨胀、工具误选、职责混杂 | 运行: python3 examples/ch53_single_vs_multi/ex_53_01_single_agent_limits.py
"""tiktoken 真实计数 + 确定性匹配器：把 3 个领域 6 个工具塞给一个 Agent，
量化'大杂烩'的代价（完整源码见示例文件，核心是 pick_tool 匹配器与逐轮计数）。"""
def pick_tool(tools: dict[str, str], request: str) -> str:
    """确定性工具选择器（教学替身）：请求 2-gram 与工具描述求重叠得分。"""
    grams = {request[i:i+2] for i in range(len(request)-1)} - _STOP
    best, best_score = "", -1
    for name, desc in tools.items():
        score = sum(1 for g in grams if g in desc)
        if score > best_score:
            best, best_score = name, score
    return best
```

```text
# 真实运行输出（tiktoken cl100k_base 真实计数，匹配器确定性）
== 信号①：上下文膨胀（tiktoken cl100k_base 真实计数）==
  第1轮请求 prompt ≈  130 tokens（tiktoken:cl100k_base）
  第2轮请求 prompt ≈  139 tokens（tiktoken:cl100k_base）
  第3轮请求 prompt ≈  150 tokens（tiktoken:cl100k_base）
  第4轮请求 prompt ≈  157 tokens（tiktoken:cl100k_base）
  第5轮请求 prompt ≈  163 tokens（tiktoken:cl100k_base）

== 信号②：工具误选（确定性匹配器，模拟选择依据）==
  ✓ 「帮我查一下订单 A1001 的信息」→ query_order（期望 query_order）
  ✗ 「这个包裹到哪了」→ query_order（期望 query_logistics）
  ✓ 「开一张发票」→ query_invoice（期望 query_invoice）
  ✓ 「改地址」→ change_address（期望 change_address）
  大杂烩 6 工具：误选 1/4
  领域隔离后（订单子 Agent 只见 2 个工具）：查询类误选 0 次，且 prompt 系统段从 113 tokens 缩到 54 tokens

== 信号③：职责混杂（无法独立测试/独立上线）==
  - 发票工具改一个字段校验 → 全能 Agent 的 6 个工具一起回归测试
  - 权限模型：查/写/撤销混在同一个上下文，工具级权限（ch54）无法按领域收敛
  - 结论预告：这不是'必须拆多 Agent'，而是'拆了之后每个部件可独立演进'——53.2 给判断标准
```

**EX-53-02 | examples/ch53_single_vs_multi/ex_53_02_two_role_collaboration.py（完整可运行，Mock 驱动）**

```python
# EX-53-02 | 最小两角色协作：主 Agent 拆解派工，子 Agent 各自闭环，失败按策略处理 | 运行: python3 examples/ch53_single_vs_multi/ex_53_02_two_role_collaboration.py
"""主 Agent（orchestrator）拆解派工（SubTask 契约）→ 子 Agent 独立上下文执行
→ 回执 SubResult；失败三级收口 retry→degrade→escalate（完整源码见示例文件）。"""
def run_sub_agent(task: SubTask) -> SubResult:
    tools = DOMAINS[task.domain]          # 每个 domain 只有自己的工具，互相不可见
    attempts = 0
    while attempts < 2:                   # 最多两次尝试
        attempts += 1
        try:
            out = str(tools["query"](tools["arg"]))
            covered = [k for k in task.must_include if k in out]
            status = "ok" if len(covered) == len(task.must_include) else "degraded"
            gaps = [k for k in task.must_include if k not in out]
            return SubResult(task.subtask_id, status, out, attempts, gaps)
        except Exception as exc:          # 第 1 次失败→retry；第 2 次失败→出循环 escalate
            last_err = f"{type(exc).__name__}: {exc}"
    return SubResult(task.subtask_id, "failed", f"两次尝试均失败（{last_err}）",
                     attempts, gaps=["物流轨迹不可得"])   # 如实上报，不编造
```

```text
# Mock 运行输出（控制流真实运行；logistics 域教学剧本恒定抛错）
== 主 Agent + 子任务 Agent 最小协作（Mock 驱动）==
  T1: 尝试 1 次
  T2: 尝试 2 次
  T3: 尝试 1 次

汇总：2 成功 / 0 降级 / 1 失败
报告可用部分：
  - 订单 A1001：已发货，物流单号 SF-8899
  - 发票已开具：电子票，金额 12,800 元
缺口（如实上报，不编造）：['物流轨迹不可得']

通信=结构化 SubTask/SubResult；共享状态=无（子 Agent 互不可见）；失败=retry→degrade→escalate 三级收口
```

## 53.5 逐段解释

1. **SubTask 的 must_include 字段**：它把"验收条件"从协调者的脑子里搬进契约——子 Agent 自检覆盖度并给出 degraded/failed 判定，协调者不需要理解领域细节就能汇总。这就是"契约先行"在 Agent 协作里的样子。
2. **degraded 是一等状态**：EX-53-02 里若物流工具返回了轨迹但没有预计送达时间，status=degraded、gaps=["预计送达"]——报告照样能用部分结果。全部推翻重来（failed）是最后手段，不是默认。
3. **gaps 的纪律**：失败域**不进 report_parts**（不编造），只进 gaps（如实上报）。测试 test_ch53 锁定了这一行为——`out["summary"] == "2 成功 / 0 降级 / 1 失败"` 且 `len(out["report_parts"]) == 2`。
4. **为什么子 Agent 互不可见**：信息隔离不是教条，是防"一个域的噪声污染另一个域的选择"（53.1 事故②的机制根因）。需要跨域数据时，由主 Agent 把 A 的结论摘要放进派给 B 的 SubTask——数据流向是显式的、可审计的。
5. **拆分粒度：按领域，不按步骤**：把"查计划/查工单/提交调整"拆成三个串行子 Agent 是常见错误——那是**步骤**不是**领域**，串行交接只增加延迟与故障点（流水线拓扑才适合阶段明确的加工链）。判据：两个子 Agent 之间传递的若是"中间结果"（查到的数据），考虑合并；传递的若是"独立职责的结论"（订单域结论 vs 物流域结论），保持拆分。项目三选择单 Agent 的根本原因正在于此：它的三步是同一领域（生产计划）的连贯动作。
6. **多 Agent 测试的分层**：单层测（每个子 Agent 独立喂 SubTask 断言 SubResult——test_ch53 的做法）、协议测（契约字段完整性）、整链测（orchestrate 汇总口径）。整链测试用**脚本化子 Agent**（注入确定性行为）而不是真模型——否则链路测试会随模型漂移而闪断，那不是 bug 是噪声。

## 53.6 安装 / 文件位置 / 运行命令

```bash
cd /workspace/ai_application_course
python3 examples/ch53_single_vs_multi/ex_53_01_single_agent_limits.py   # tiktoken 首次联网下载词表，之后离线
python3 examples/ch53_single_vs_multi/ex_53_02_two_role_collaboration.py
python3 -m pytest tests/test_ch53.py -q     # 5 个测试
```

## 53.7 常见错误与排查

**① `StructuredOutputError: Mock 输出无法通过 schema SubTask 校验：1 个错误`**：本书编写时真实踩到的错——示例的用户消息里没有给必填字段 `subtask_id` 的 key=value，Mock 的结构化解析填不出必填项。修复：在输入里补 `subtask_id=T1`（或给字段默认值）。教训：**结构化输出失败先看 schema 的必填字段**（errors 列表里的 loc 会指名道姓，ch26 的校验回退循环）。

**② 子 Agent 拿到了主 Agent 的整段历史**：上下文爆炸 + 跨域噪声。修复：派工单只放 instruction 与必要字段；"为什么派这个活"最多一句话。

**③ 一个子 Agent 失败导致整体没有产出**：协调者把子 Agent 异常直接上抛。修复：异常在子 Agent 内部收口成 SubResult(failed+gaps)，协调者聚合后决定升级——"错误即数据"在 Agent 间的形态。

**④ 拆了之后 token 更贵了**：每个子 Agent 都带一份 system prompt 与工具说明，串行调用叠加成本。修复：确认拆分收益（隔离/并行）大于成本；能合并的子任务合并；子 Agent 的 system prompt 压到最小。

## 53.8 企业场景中的使用方式（Spring Boot 集成视角）

- **用微服务的经验讲给架构师**：多 Agent 拆分提案 = 一次"服务拆分评审"——要画领域边界、契约（SubTask/SubResult）、失败升级（retry/degrade/escalate）、可观测（每个子 Agent 独立 trace，ch52 事件流 + trace_id 串联）。
- **落地形态渐进**：先"逻辑拆分"（一个进程内两个 LangGraph 子图，ch49），验证边界清晰后再考虑"物理拆分"（独立服务+消息队列）——与单体→微服务的演进路径同构。
- **权限按域收敛**：领域拆分后每个子 Agent 的工具集天然收敛，ch54 的权限矩阵按域配置——这是 53.1 事故③的组织解。
- **给管理层的两个指标**：①单任务 token 成本（拆分前后对比——隔离的收益要用钱来验算）；②缺陷定位时长（多 Agent 的 trace 串联后，"哪个域出的错"应该一次查询可答）。两个指标都不改善，拆分就是组织学表演而不是工程改进。

## 53.9 练习（基础 2 + 代码 2 + 调试题 1）

**基础 1**：三个"该用单 Agent"的场景是哪三个？各自挡住的诱惑是什么？**基础 2**：degraded 和 failed 的区别是什么？gaps 字段存在的意义？
**代码 1**：给 SubResult 增加 `duration_ms` 字段并在 orchestrate 的汇总里输出最慢子任务。**代码 2**：把 run_sub_agent 的重试上限改成参数化（max_attempts），并写测试断言 attempts 永不超过它。
**调试题**：多 Agent 系统上线后，用户抱怨"答案经常缺一块"，但单测全绿。最可能的原因与修复？

### 参考答案

基础 1：A 工具少而正交（挡"工具多就要拆"）；B 流程线性（挡"多 Agent 能解决路径问题"）；C 状态强共享（挡"按组织架构拆"）。基础 2：degraded=部分完成且缺口已知（可用），failed=无法交付（如实上报）；gaps 让"缺什么"成为结构化数据，下游才能决定补查或披露。代码 1：回执记耗时，汇总 `max(results, key=lambda r: r.duration_ms)`。代码 2：`while attempts < max_attempts`，测试用恒抛工具断言 `result.attempts == max_attempts`。调试题：子 Agent 的 gaps 没进最终答复（协调者只拼 report_parts）——修复：汇总时把 gaps 渲染成"以下信息暂缺"段落；同时补一条端到端断言（含失败域的场景必须有缺口披露）。

## 53.10 自测检查表

- [ ] 我能说出三个疲劳信号并各给一个测量方法；
- [ ] 我能背出"该用单 Agent"的三个场景与一个合理多 Agent 场景；
- [ ] 我能设计 SubTask/SubResult 契约并解释 must_include 与 gaps；
- [ ] 我能讲清 retry→degrade→escalate 与 Resilience4j 的对应；
- [ ] 我知道"多 Agent 不提高单次推理质量"，它改善的是上下文相关性。

## 53.11 面试追问

1. **[模拟题] 什么时候必须上多 Agent？** 答：两个条件同时满足——单 Agent 出现真实疲劳信号（上下文膨胀/误选率），且领域能画出清晰契约边界。缺一先做工具治理与领域隔离。
2. **[模拟题] 多 Agent 的"共享状态"怎么做才不会乱？** 答：原则是最小化+外部化——子 Agent 互不可见，跨 Agent 数据放图 state 或 DB 由协调者按需下发；绝不通过"子 Agent 互相聊天"同步状态。
3. **[模拟题] 子 Agent 超时怎么处理？** 答：派工时带 deadline（超时算一次失败尝试），失败走 escalate；协调者对超时域降级（partial result + gaps），绝不为等一个域阻塞整体——与微服务的超时预算（deadline propagation）同构。

---

# 第 54 章 工具治理：描述、校验、权限、审计

> **本章目标**：把"工具"当作需要治理的生产资产：量化描述质量对工具选择的影响；用 Pydantic 给工具参数上第一道校验；用权限分级与高风险闸门落实"最小权限"；用 JSONL 审计让每次调用（包括被拒的）可追溯。
> **前置知识**：ch39（@tool 与 args_schema）、ch52（事件流）、ch48（审批与幂等账本）。
> **学完你能做什么**：为团队制定一份一页纸的工具治理清单；给任意工具补上校验/权限/审计三层防线；在审计调查中回答"谁、何时、用什么参数、做了什么"。

## 54.1 真实问题引入：同一批工具，两个团队的两番命运

两个团队（合成案例）几乎同时上线了"AI 助手调内部 API"。A 团队的工具描述是代码注释风格（"查询订单，处理订单相关业务"），三个月后用户投诉率居高不下，复盘发现大量"选错工具"（想查物流却查了订单）。B 团队上线前做了一次"工具评审会"：描述统一按"职责一句话+参数格式+适用边界"重写；参数全过 Pydantic；权限按只读/低风险/高风险分级；每次调用写审计。同期的工具误选投诉为零，且一次越权尝试（实习生的账号调了撤销接口）在审计里抓得清清楚楚。

差别不在模型，在治理。本章给出一套最小可落地的治理动作，按性价比排序：**描述质量 → 参数校验 → 权限分级 → 审计日志**。

## 54.2 一句话解释 + 生活类比 + 类比边界

**一句话解释**：工具是模型的手——描述是模型选择用哪只手的唯一依据，校验与权限保证"手不会乱伸"，审计保证"伸过就留痕"。

**生活类比**：Java 工程师最熟悉的映射——**描述 ≈ 对外 API 文档**（文档差，调用方（模型）乱猜）；**参数校验 ≈ Bean Validation**（@NotNull/@Max）；**权限分级 ≈ 方法级 @PreAuthorize + RBAC**；**审计 ≈ 访问日志 + 审计切面**。唯一的新认知是：调用方从"人类开发者"换成了"概率模型"——它会忠实利用你描述里的每一个线索，也会忠实放大你的每一个含糊。

> 💡 类比边界：
> 1. API 文档写得差，开发者还能看源码；模型只看描述——**描述就是模型的源码**；
> 2. @PreAuthorize 拒绝时返回 403 给"人"，工具权限拒绝要返回**可读的错误信息给模型**——模型可以据此换路（比如改走审批），不是简单报错（54.4 的"改道"设计）；
> 3. 审计日志≠调试日志：审计回答"谁做了什么"（合规），调试回答"为什么坏了"（工程）——两者字段不同，别混在一个文件里。

## 54.3 正式原理与准确术语

**工具治理清单（按性价比排序）**：

1. **描述质量（description hygiene）**：三要素=职责一句话+参数格式（含编号前缀/日期格式）+适用边界（"不要用它查工单"）。评审工具代码时连描述一起评审；描述变更进版本管理与回归（ch28 的 golden set 思路）。
2. **参数校验（input validation）**：@tool 自动生成的 schema 只保证类型，业务约束（格式正则、范围、必填理由）用 Pydantic args schema 显式声明（ch39 的 args_schema），**模型给的参数不可信**——校验失败把 ValidationError 的 loc/msg 翻译成模型可读的错误，模型往往能自我纠正。
3. **权限分级（least privilege）**：工具声明风险级别（READ / LOW_RISK_WRITE / HIGH_RISK_WRITE），角色声明可用级别（viewer/operator/…），**统一执行入口做检查**（deny by default）；高风险工具任何角色不可直调——唯一合法入口是审批流恢复（ch48 的 interrupt/Command(resume)），实现上用"审批凭证"（approved_tools 集合）放行。风险级别×角色的矩阵是**数据不是代码**——加角色/加工具只改表：

| 工具（示例） | 风险级别 | viewer | operator | admin |
|---|---|---|---|---|
| query_plans / query_workorder | READ | ✓ | ✓ | ✓ |
| submit_adjustment（≤20% 幅度） | LOW_RISK_WRITE | ✗ | ✓ | ✓ |
| submit_emergency_adjustment / restart_line | HIGH_RISK_WRITE | ✗ | ✗ | ✗（仅审批凭证放行） |

注意最后一行：**admin 列也是 ✗**——高风险不是"更高的角色"而是"另一条通道"（审批），角色管不够格的人，审批管够格的人这一次行不行。把这两个概念合并（"给 admin 开后门"）是最常见的权限设计事故。
4. **业务规则与改道**：合法但超限的请求（调整幅度>20%）返回结构化业务错误，引导模型改走高风险审批路径——权限管"谁够格"，审批管"这一次行不行"，两者不重复。
5. **审计日志（audit trail）**：JSONL 追加写，每条五要素——who（actor+role）/when（ts）/what（tool+args）/outcome（ok/denied/error）/context（trace_id）。**被拒的调用也要留痕**（denied 是最有价值的审计事件）；统一在执行入口写，不散落在工具内。

**幂等键（idempotency key）**：写操作的安全重试前提——同一逻辑操作生成同一 key（ch15），服务端按 key 去重（ch56 的 Java 账本）。它是"审计（事后追溯）"与"账本（事前去重）"这对组合里的账本侧。生成策略三种，按场景选：

| 策略 | 形态 | 优点 | 缺点/边界 |
|---|---|---|---|
| 内容哈希（本书项目三） | sha1(plan_id\|new_qty\|reason\|trace_id) | 确定性：同任务重试同 key，无需额外状态 | 同内容的不同业务意图会撞 key（reason 参与哈希缓解但不根除） |
| 一次性 UUID | uuid4，任务开始时生成、全程复用 | 不撞 key，实现最简 | 依赖"开始时生成并保存"的纪律；进程崩溃丢失后重放会换 key |
| 业务序号 | 服务端发的单号（如 Java 的 adjustment_id） | 与业务对账天然对齐 | 首次请求之前没有号——只防"重放"不防"首次重复提交" |

工程默认：**内容哈希 + trace_id 揉进盐**（项目三形态）；要求严格不撞时用"UUID+账本保存"。

**Java 对照**：这张清单 ≈ 一次接口安全评审的 checklist（文档/校验/鉴权/审计），只是"调用方"换成模型后，"描述"从次要文档升级为第一等资产。

## 54.4 最小完整示例：对照实验、双层防线、审计轨迹

**EX-54-01 | examples/ch54_tool_governance/ex_54_01_description_quality.py（完整可运行）**

```python
# EX-54-01 | 描述质量对工具选择的影响：同一批请求，只改描述做对照实验 | 运行: python3 examples/ch54_tool_governance/ex_54_01_description_quality.py
"""同一组 6 个工具、同一批 8 个请求：A 敷衍描述 vs B 结构化描述，
用确定性匹配器（教学替身）量化误选率（完整源码见示例文件）。匹配器两条规则：
① 中文语义 2-gram 重叠（剔除 ASCII 编号防假相关）；
② 参数格式线索：请求里出现 WO-2091/2026-03-18 时，描述里写明对应格式的工具加分。"""
```

```text
# 真实运行输出（纯标准库，确定性）
== 工具描述对照实验（同一组工具、同一批请求，只改描述）==

[A 敷衍描述] 正确 4/8，误选 4/8
  ✗ 「P-1002 要改成 1500 件，原因是客户加急」→ 选了 query_plan（期望 submit_adjustment）
  ✗ 「MAT-309 的库存还剩多少」→ 选了 query_plan（期望 query_material）
  ✗ 「上个月有没有人改过 P-1002」→ 选了 query_plan（期望 search_history）
  ✗ 「WO-2091 的状态是什么」→ 选了 query_plan（期望 query_workorder）

[B 结构化描述] 正确 7/8，误选 1/8
  ✗ 「查一下今天的计划」→ 选了 search_history（期望 query_plan）

结论：只重写描述（职责+参数格式+边界），误选 4/8 → 1/8。
```

两件事值得注意：B 组仍剩 1 个误选（"查一下今天的计划"被 search_history 的"计划调整记录"抢走）——**好描述显著降低但不消灭误选**，剩余部分要靠参数校验兜底与线上回归监控；误选清单本身就是最有价值的回归样例（53.9 调试题的素材）。

**EX-54-02 | examples/ch54_tool_governance/ex_54_02_param_validation_permission.py（完整可运行）**

```python
# EX-54-02 | 参数校验与权限分级：把"模型不能信任"写进代码 | 运行: python3 examples/ch54_tool_governance/ex_54_02_param_validation_permission.py
"""第一层 Pydantic 校验（格式/类型/必填），第二层权限分级（deny by default），
第三层业务规则（幅度≤20% 否则改道审批）。完整源码见示例文件——核心结构："""
class AdjustmentArgs(BaseModel):
    plan_id: str = Field(pattern=r"^P-\d{4}$", description="计划号，形如 P-1002")
    new_qty: int = Field(ge=0, le=100_000, description="调整后的数量")
    reason: str = Field(min_length=5, max_length=200, description="调整原因，必填")

def execute_tool(registry, name, role, raw_args, *, plan_qty=1000, approved=False):
    entry = registry.get(name)
    if entry is None:
        raise KeyError(f"未知工具 {name}")
    if entry.risk == Risk.HIGH_RISK_WRITE and not approved:
        raise PermissionDenied(f"{name} 是高风险工具，必须走人工审批入口")
    if entry.risk not in ROLE_MATRIX[role]:
        raise PermissionDenied(f"角色 {role.value} 无权调用 {name}（需要 {entry.risk.value} 级）")
    args = entry.args_schema.model_validate(raw_args) if entry.args_schema else raw_args
    ...  # 业务规则与实现（源码见示例文件）
```

```text
# 真实运行输出（pydantic 2.14.1，确定性）
== 第一层：参数校验（Pydantic 拦在工具实现之前）==
  ✓ 拦截 {"plan_id": "P1002", "new_qty": 1200, "reason": "客户加急订单"}
      理由：ValidationError → plan_id: String should match pattern '^P-\d{4}$'
  ✓ 拦截 {"plan_id": "P-1002", "new_qty": "abc", "reason": "客户加急订单"}
      理由：ValidationError → new_qty: Input should be a valid integer, unable to parse string as an integer
  ✓ 拦截 {"plan_id": "P-1002", "new_qty": 1200}
      理由：ValidationError → reason: Field required

== 第二层：权限分级（deny by default）==
  ✓ viewer 提交调整被拒：角色 viewer 无权调用 submit_adjustment（需要 low_risk 级）
  ✓ admin 直调 restart_line 也被拒（高风险工具任何角色不可直调）：restart_line 是高风险工具，必须走人工审批入口（审批恢复后 approved=True 才能执行）
  ✓ 审批流恢复后（approved=True）admin 执行：{'restarted': 'L-3'}

== 业务规则：低风险放行、高风险改道审批 ==
  ✓ 幅度 15% 低风险放行：{"accepted": true, "plan_id": "P-1002", "new_qty": 1150, "idempotency_key": "adj:P-1002:1150:1662"}
  ✓ 幅度 100% 超限改道：调整幅度 100% 超过 20%，属高风险调整，须走人工审批
     → 工程动作：返回结构化错误给模型，Agent 生成'建议+审批单'而非硬提交（ch48）
```

**EX-54-03 | examples/ch54_tool_governance/ex_54_03_audit_log.py（完整可运行）**

```python
# EX-54-03 | 审计日志：每次工具调用回答"谁、何时、用什么参数、做了什么、结果如何" | 运行: python3 examples/ch54_tool_governance/ex_54_03_audit_log.py
"""AuditLog 追加 JSONL：五要素（who/when/what/outcome/trace_id），
denied 也留痕；governed_execute 演示统一执行入口的审计接线（源码见示例文件）。"""
```

```text
# 真实运行输出（ts 时间随运行时刻变化，其余确定性）
== 一次会话的审计轨迹（trace_id=trace-d69910a7）==

共 3 条记录（含被拒绝的调用——denied 也必须留痕）：
  2026-10-19T05:25:59.419 agent-p3   operator query_plan         ok                 5.1ms  {"plan_id": "P-1002", "status": "延期"}
  2026-10-19T05:25:59.420 agent-p3   viewer   submit_adjustment  denied             0.0ms  角色 viewer 无权调用 submit_adjustment
  2026-10-19T05:25:59.425 agent-p3   operator submit_adjustment  ok                 5.1ms  {"submitted": true, "plan_id": "P-1002"}

合规三问（都能从 JSONL 回答）：
  ① 有没有人试过越权？→ 1 次 denied（viewer 提交调整）
  ② 提交调整用的什么参数？→ {'plan_id': 'P-1002', 'new_qty': 1150, 'reason': '客户加急订单5%内'}
  ③ 这次会话按时间线是什么？→ 3 条按 ts 排序即完整时间线
```

## 54.5 逐段解释

1. **为什么校验错误要翻译而不是原样抛**：模型收到 `plan_id: String should match pattern '^P-\d{4}$'` 这类信息时，下一轮往往能自己改对参数——错误信息是给模型的**纠错提示**，不是给人看的报错。工具层把 ValidationError 的 loc/msg 拼成一句话返回即可。
2. **审批凭证（approved_tools）的设计**（EX-54-02 的 approved 参数、项目三的同名集合）：高风险工具的执行需要"凭证"，而凭证只由审批恢复路径发放——这把"绕过 Agent 直调工具"的口子也堵上了（测试 test_ch54 与 test_p3 都锁定此行为）。凭证是**进程内瞬态的**，不落盘——重放执行必须重新走审批。
3. **denied 记录的 detail 要可检索**：写"角色 viewer 无权调用 submit_adjustment"而不是"权限错误"——合规调查时 grep denied 就能还原越权尝试的完整画像（谁、什么角色、想调什么、什么参数）。
4. **args 字段全量入审计的隐私边界**：参数里可能含敏感信息（客户理由、手机号）。生产要做脱敏（ch58：字段级脱敏规则），教学版记录原值但文件权限收紧——两条路都要在治理清单里写明。

## 54.6 安装 / 文件位置 / 运行命令

```bash
cd /workspace/ai_application_course
python3 examples/ch54_tool_governance/ex_54_01_description_quality.py
python3 examples/ch54_tool_governance/ex_54_02_param_validation_permission.py
python3 examples/ch54_tool_governance/ex_54_03_audit_log.py
python3 -m pytest tests/test_ch54.py -q     # 9 个测试
```

## 54.7 常见错误与排查

**① `pydantic_core._pydantic_core.ValidationError: 1 validation error for AdjustmentArgs`（线上偶发）**：模型给的参数没过校验。修复：把 e.errors()[0] 的 loc/msg 翻译成模型可读文本回传（54.5①），同时把高频失败的参数模式补进描述的"参数格式"段——校验报错统计是最好的描述改进依据。

**② 权限检查形同虚设（agent 角色永远是 admin）**：把角色写死在系统提示词里（"你是 admin"）。提示词不是权限控制（ch28 红线）。修复：角色来自**调用链身份**（API 网关注入的用户上下文），执行入口按角色查矩阵；提示词里只描述能力，不描述权限。

**③ 审计文件暴涨拖垮磁盘**：每条工具调用全量 JSON + 高频轮询。修复：审计按天滚动文件 + 采集管道（Filebeat→ES）；args 截断（AuditLog 的 detail[:300]）；轮询类只读调用可采样审计（但要保留全部写与全部 denied）。

**④ 同一写操作重复提交**：没有幂等键时的重试事故。修复：写操作在工具层生成确定性幂等键（内容+trace 哈希），服务端按 key 去重——ch56 项目三完整实现，此处不再展开。

## 54.8 企业场景中的使用方式（Spring Boot 集成视角）

- **权限矩阵的归属**：Java 侧已有 RBAC（角色-权限表）时，Python 工具层的权限矩阵应与它同源——工具风险级别作为新列加进现有权限表，Java 网关把"该用户在 AI 功能下的角色"随请求传给 Python 服务（ch57），避免两套权限各自漂移。
- **审计对账**：Python 的 JSONL 审计与 Java 侧的业务流水用同一把对账键（幂等键/trace_id），合规检查可以跨系统还原一次 AI 操作的完整链路。
- **描述评审进 CR 流程**：工具=一种对外接口，描述变更与接口变更同级——CR 模板加一条"工具描述是否更新、回归样例是否补充"。
- **AI 网关要不要建**：当 AI 应用超过 3 个，考虑统一入口——鉴权（校验用户→角色映射）、配额（每应用每工具的 QPS）、审计汇聚（各应用的 JSONL 汇进同一检索）、模型路由（廉价模型跑分类、贵模型跑分析，ch60 成本表）。注意网关只做横切，**工具治理（校验/权限/幂等）仍在各工具层**——把治理上收到网关的"统一管"是最常见的过度设计，因为业务规则（比如"幅度≤20%"）天然属于工具，不属于通道。

## 54.9 练习（基础 2 + 代码 2 + 调试题 1）

**基础 1**：工具描述三要素是什么？**基础 2**：为什么被拒绝的调用也要进审计？
**代码 1**：给 AdjustmentArgs 增加"调整只能在 06:00-22:00 提交"的 field_validator（用注入的当前时间，方便测试）。**代码 2**：给 AuditLog 增加 `stats()` 方法，返回 {tool: {ok, denied, error}} 计数，并写测试。
**调试题**：线上误选率突然升高，但工具代码没有任何变更。给出至少三条排查方向。

### 参考答案

基础 1：职责一句话、参数格式、适用边界。基础 2：denied 是最有价值的审计事件（越权尝试/权限配置错误的第一信号），不留痕就失去"事前防住之外"的全部追溯能力。代码 1：validator 内比较注入时钟（`info.context` 或类变量），夜间抛 ValueError；测试用 monkeypatch 时间。代码 2：读文件逐行 json.loads 累计，测试造 3 条不同 outcome 断言计数。调试题：①上游改了业务口径导致描述过时（对拍真实数据与描述）；②新上线工具与旧工具语义撞车（对比误选清单与近期发布）；③请求分布变化（新话术，样例不在描述语料里）——三条都指向"描述与回归样例要随业务演进"。

## 54.10 自测检查表

- [ ] 我能给任意工具按三要素重写描述并说清依据；
- [ ] 我能把业务约束翻译成 Pydantic args schema 并设计"错误回传模型"的文案；
- [ ] 我能画出风险级别×角色矩阵，并解释高风险工具的审批凭证机制；
- [ ] 我能设计审计五要素字段并解释 denied 事件的特殊价值；
- [ ] 我能把这套清单映射到 Java 的 Bean Validation/@PreAuthorize/审计切面。

## 54.11 面试追问

1. **[模拟题] 描述写得再好也会误选，最终兜底是什么？** 答：参数校验（选对了工具但参数不对会暴露）+ 业务规则（校验过了但超限会改道）+ 审计与线上回归（误选模式进样例库）。治理是纵深防御，不是单点保证。
2. **[模拟题] 工具权限和 Agent 自主性矛盾吗？** 答：不矛盾——自主性发生在"选哪个工具"（可选集内自由），权限决定"可选集是什么"。权限在代码里，模型感知到的是"工具清单少了哪些"。
3. **[模拟题] 审计日志被删了怎么办？** 答：追加写+远端采集（写本地只是缓冲）；审计文件的完整性（哈希链/只追加存储）在高合规场景要有方案——诚实地说教学版没做完整性保护，属于"待生产化"项。

---

# 第 55 章 MCP：把工具暴露给模型的标准化协议

> **本章目标**：讲清 MCP（Model Context Protocol）的定位——**它是协议不是框架**；掌握 host/client/server 角色分工与 tools/resources/prompts 三原语；按官方规范（2026-07-28 版）讲传输方式与安全边界；动手跑通"最小 MCP server → 官方 SDK 客户端 → langchain-mcp-adapters → create_agent"的完整闭环。
> **前置知识**：ch39（工具三件套：name/description/inputSchema）、ch42（create_agent 的工具契约）。
> **学完你能做什么**：判断团队该不该引入 MCP；自己写一个 stdio MCP server 并接到 LangChain Agent；把"MCP 与 REST API 的关系"讲清楚。

## 55.1 真实问题引入：接第五个 AI 应用时的重复劳动

某公司（合成案例）先做了排障 AI 助手，Python 工具直连内部 API；半年后知识库问答、报表助手、运维 Agent 相继立项——每个应用都把"查工单、查计划"的工具代码抄一遍，工具实现改一处要同步四处。更麻烦的是权限：每个应用自己实现一遍"谁能调什么"。

MCP 的目标就是消灭这种重复：**工具的实现方（server）只写一次，任何支持 MCP 的应用（host）都能发现并调用它**。类比 Java 世界：每个应用各自手写 JDBC 连接池 vs 统一的 JDBC 驱动标准——数据库只实现一次驱动，所有应用受益。

## 55.2 一句话解释 + 生活类比 + 类比边界

**一句话解释**：MCP 是一个开放协议，用 JSON-RPC 2.0 标准化"AI 应用（host，内嵌 client）"与"工具/数据提供方（server）"之间的消息——发现工具（tools/list）、调用工具（tools/call）、读资源（resources）、取提示模板（prompts）。

**规范核实声明**：本节以下事实**于 2026-10-19 通过 WebFetch 访问 modelcontextprotocol.io/specification/latest 核实**，当次解析到的版本化页面为 **2026-07-28**（规范正文自述"The specification ... based on the TypeScript schema in schema.ts（2026-07-28）"）。要点：①通信三角色 **Hosts**（发起连接的 LLM 应用）、**Clients**（host 内的连接器）、**Servers**（提供上下文与能力的服务）；②Server 提供三原语 **Resources**（上下文与数据）、**Prompts**（模板化消息）、**Tools**（供模型执行的函数）；③Client 可向 server 提供 **Elicitation**（服务端向用户索要额外信息的能力）；④传输绑定两种：**stdio**（客户端拉起子进程，标准流上传 newline 分隔消息）与 **Streamable HTTP**（每条消息 POST 到单一 MCP 端点，响应为 JSON 或 request-scoped SSE 流）；⑤安全原则：用户同意与控制（调用任何工具前须用户同意）、数据隐私、工具安全（**工具描述等元数据视为不可信内容**，除非来自可信 server）。另一要点与直觉相反：2026-07-28 版规范明确 "**servers do not initiate JSON-RPC requests**"（服务端不发 Request 只回 Response），需要模型/用户输入时通过结果语义表达；早期版本（含 initialize 握手与 server 主动请求）按"向后兼容"章节由实现方协商兼容。**规范演进快，读者落地前请以当日官网为准**——本节给出的版本号与日期即为本书的可追溯锚点。

**生活类比**：MCP ≈ JDBC（统一接口标准），MCP server ≈ 数据库驱动，host ≈ 使用驱动的应用（IDE/DataGrip），tools/resources/prompts ≈ 驱动暴露的执行/元数据/预编译语句能力。**类比边界**：①JDBC 只管"连接与执行"，权限模型在数据库侧；MCP 把"用户同意"列为协议级原则——**但同样只是原则**，规范明说"MCP itself cannot enforce these security principles at the protocol level"，强制力仍在实现方（你的 host 代码）；②JDBC 面向 SQL 语义，MCP 面向"模型可用的能力"——inputSchema 是给模型读的，不是给编译器读的。

## 55.3 正式原理与准确术语

**定位：协议不是框架**。MCP 不决定你怎么写工具逻辑、怎么做鉴权、怎么部署——它只标准化**消息**（JSON-RPC 2.0：请求有 id、通知无 id、响应带 result|error）与**能力发现**（initialize 握手中的能力协商）。你的业务逻辑一行不改地留在 server 里。

**三种角色**（2026-07-28 规范术语）：Host（LLM 应用本体，如 IDE/聊天客户端/你的 Agent 服务）内嵌一个或多个 Client；每个 Client 与一个 Server 维持一条逻辑连接。**对你（Java 工程师）最实际的认知**：LangChain/你的 Agent 代码扮演 host+client；你写的 MCP server 就是"把工具实现搬出应用"的那一端。

**三原语**：
- **Tools**（模型控制）：函数能力，`tools/list` 返回 name/description/inputSchema 三件套（与 ch39 的 @tool 自动生成物同构——这正是 langchain-mcp-adapters 能无缝翻译的原因），`tools/call` 执行。工具内部异常**不产生 JSON-RPC error**，而是返回 `isError: true` 的正常响应（错误即数据，协议层的明确设计）；
- **Resources**（应用控制）：上下文数据（文件/记录/快照），URI 标识，给"人或应用"消费，可订阅变更；
- **Prompts**（用户控制）：模板化提问骨架，给人选用。

**传输方式（2026-07-28 规范原文归纳）**：协议语义与传输无关（binding 只管帧与投递）。标准绑定两种——**stdio**：newline 分隔的 JSON-RPC 消息走子进程标准流，stdout 只承载协议（任何 print 到 stdout 都会污染协议帧——55.7 的真实翻车点）；**Streamable HTTP**：消息 POST 到单一端点，响应为 JSON 或 SSE 流，适合远程/托管 server。取消语义：stdio 发 `notifications/cancelled`，Streamable HTTP 直接关闭响应流。选择依据：

| 维度 | stdio | Streamable HTTP |
|---|---|---|
| server 生命周期 | client 拉起子进程，同生共死 | 独立部署，多 client 共享 |
| 鉴权 | 无（本地信任） | 标准 HTTP 鉴权机制（细节以当日规范为准） |
| 适用 | 本地工具（IDE/个人机/CLI） | 公司级共享工具、远程/托管服务 |
| 部署形态 | 随 host 分发（pip 装个包） | 独立服务+网关+注册（你的 Java 经验全适用） |
| 排障 | 看 stderr + 抓 stdin/stdout 帧 | 看访问日志 + HTTP 状态码 |

**initialize 握手时序**（排障时按此顺序核对）：①client 发 `initialize` 请求（protocolVersion 期望值 + client 能力 + clientInfo）；②server 回响应（**协商后的版本** + server 能力清单 + serverInfo）；③client 发 `notifications/initialized` 通知（无 id，不期待回复）——此后才能发业务请求。**版本协商规则**：server 返回它支持的版本，若 client 不支持则 client 断开重连降级——EX-55-03 输出里 SDK 协商出 2025-11-25 而规范最新是 2026-07-28，就是这个机制的实录（SDK 版本决定了它声明的版本集，待 SDK 升级后协商值会前移）。

**MCP 与 REST API / 普通工具调用的关系**（考试重点，也是最常见误解）：
- MCP **不是**你后端 API 的替代品——你的业务 API 该怎么设计还怎么设计；
- MCP 是"**把工具暴露给模型的标准化方式**"：解决的是"多个 AI 应用 × 多套工具"的 M×N 重复问题（55.1 的痛点），把它变成 M+N；
- 普通工具调用（ch24/ch39）中，工具 schema 与实现都在应用进程内；MCP 把它们搬到进程外，代价是多一跳协议（stdio 管道/HTTP），收益是复用与解耦。
- **对接已有 Java 服务（ch56 主线）的两条路**：①直接把 Java API 包成 Python 工具（项目三的做法——治理在工具层，见 55.8 的选择依据）；②把 Java 服务包一层 MCP server（本章做法）。两者的协议成本与治理归属不同，**先做②还是①取决于工具会被几个 AI 应用复用**。

**安全机制与边界**：规范级三原则（用户同意/数据隐私/工具安全）与一条坦诚声明（协议层无法强制）；实现层义务——host 调用工具前获得用户同意、server 的元数据不可信、鉴权（Streamable HTTP 场景）用标准 HTTP 鉴权机制（细节以规范 basic 与 security 章节当日版本为准）。**落到你的代码**：ch54 的权限/审批/审计防线一个都不能少——MCP 不是免检通道。

## 55.4 最小完整示例：帧结构 → stdio server → 客户端 → 接入 create_agent

**EX-55-01 | examples/ch55_mcp/ex_55_01_mcp_messages.py（完整可运行）**

```python
# EX-55-01 | MCP 的协议消息长什么样：手写 JSON-RPC 2.0 帧结构 | 运行: python3 examples/ch55_mcp/ex_55_01_mcp_messages.py
"""确定性演示：把 MCP 规范（2026-07-28 版，2026-10-19 核实）最常见的四类消息
按 JSON-RPC 2.0 形状手工构造——看 SDK 黑盒之前先看清线上字节（完整源码见示例文件）。"""
initialize_request = {
    "jsonrpc": "2.0", "id": 1, "method": "initialize",
    "params": {"protocolVersion": "2025-11-25",           # 客户端希望的规范版本（SDK 实测协商值）
               "capabilities": {"roots": {"listChanged": True}, "sampling": {}},
               "clientInfo": {"name": "textbook-client", "version": "1.0.0"}}}
# initialize 响应（服务端版本+能力清单）→ notifications/initialized 通知（无 id）
# → tools/list 响应（name/description/inputSchema）→ tools/call（成功 isError:false / 业务异常 isError:true）
```

```text
# 真实运行输出（节选；完整输出含全部帧）
── ① initialize 请求（JSON-RPC Request）──
{"jsonrpc": "2.0", "id": 1, "method": "initialize",
 "params": {"protocolVersion": "2025-11-25", ...}}
── ④ tools/list 响应（工具 = name + description + inputSchema）──
{"jsonrpc": "2.0", "id": 2, "result": {"tools": [
    {"name": "get_plan",
     "description": "按计划号查询生产计划详情（产品/数量/状态）。",
     "inputSchema": {"type": "object",
                     "properties": {"plan_id": {"type": "string"}},
                     "required": ["plan_id"]}}]}}
── 帧类型速查 ──
Request    (有 id, 有 method) → 期待 Response
Notification(无 id, 有 method) → 不期待回复（单向）
Response   (有 id, 有 result|error) → 只能由'收到 Request 的一方'发出
MCP 规范约束：服务端不发 Request 只回 Response（2026-07-28 版核实）；
需要模型/用户输入时通过 result 内的 InputRequiredResult 语义表达（EX 演示范围外）
```

**EX-55-02 | examples/ch55_mcp/ex_55_02_mcp_stdio_server.py（完整可运行——作为子进程被拉起）**

```python
# EX-55-02 | 最小 MCP stdio server：用官方 python-sdk（mcp 1.30.0）的 FastMCP 编写 | 运行（作为服务端进程被客户端拉起）: python3 examples/ch55_mcp/ex_55_02_mcp_stdio_server.py
"""教学版最小 MCP 服务器：暴露 2 个工具 + 1 个资源 + 1 个提示模板。
关键纪律：stdio 传输下 stdout 只能承载 JSON-RPC 消息，任何 print/logging 都必须走 stderr。"""
from mcp.server.fastmcp import FastMCP

mcp: FastMCP = FastMCP(
    name="plan-tools",
    instructions="生产计划查询工具集：查询计划详情、按产能过滤。数据为教学用内存数据。")

_PLANS = {"P-1001": {"plan_id": "P-1001", "product": "减速器壳体", "qty": 500, "status": "正常"},
          "P-1002": {"plan_id": "P-1002", "product": "转向节", "qty": 1200, "status": "延期"}}

@mcp.tool()
def get_plan(plan_id: str) -> dict:
    """按计划号查询生产计划详情（产品/数量/状态）。"""
    plan = _PLANS.get(plan_id)
    if plan is None:
        raise ValueError(f"计划 {plan_id} 不存在")  # MCP 会把它转成 isError=true 的工具级错误
    return plan

@mcp.tool()
def list_delayed_plans() -> list[dict]:
    """列出所有处于延期状态的生产计划。"""
    return [p for p in _PLANS.values() if p["status"] == "延期"]

@mcp.resource("plan://{plan_id}")
def plan_resource(plan_id: str) -> str:
    """把计划详情暴露为可订阅的资源（resources 能力演示）。"""
    return str(_PLANS.get(plan_id, {}))

@mcp.prompt()
def delay_analysis(plan_id: str) -> str:
    """生成"延期分析"提示模板（prompts 能力演示）。"""
    return f"请分析生产计划 {plan_id} 的延期原因，并给出恢复建议。"

if __name__ == "__main__":
    mcp.run(transport="stdio")   # stdout 从此只许走协议帧
```

**EX-55-03 | examples/ch55_mcp/ex_55_03_mcp_stdio_client.py（完整可运行——端到端实测）**

```python
# EX-55-03 | 真实 MCP 客户端：拉起 stdio server 子进程，完成握手→发现→调用 | 运行: python3 examples/ch55_mcp/ex_55_03_mcp_stdio_client.py
"""全书第一个端到端 MCP 实测（mcp 1.30.0，Python 3.14.7，2026-10-19 真实运行）：
StdioServerParameters 描述"怎么拉起服务端"→ stdio_client 建管道 →
ClientSession.initialize() 完成 JSON-RPC 握手 → list_tools()/call_tool()。"""
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

params = StdioServerParameters(command="python3",
                               args=["examples/ch55_mcp/ex_55_02_mcp_stdio_server.py"], env=None)
async def main() -> None:
    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            init = await session.initialize()          # 握手：协议版本+能力协商
            tools = await session.list_tools()          # tools/list
            ok = await session.call_tool("get_plan", {"plan_id": "P-1002"})   # tools/call
            bad = await session.call_tool("get_plan", {"plan_id": "P-9999"})  # 业务错误
            print(f"isError={ok.isError} | {ok.content[0].text}")
            print(f"isError={bad.isError} | {bad.content[0].text[:40]}")
anyio.run(main)
```

```text
# 真实运行输出（mcp 1.30.0；前几行是 server 子进程的 stderr 日志，属正常现象）
Processing request of type ListToolsRequest
Processing request of type CallToolRequest
── initialize 握手结果 ──
协议版本（SDK 侧协商）: 2025-11-25
服务端名称           : plan-tools
服务端能力           : ['experimental', 'prompts', 'resources', 'tools']
── tools/list 返回 ──
- get_plan: 按计划号查询生产计划详情（产品/数量/状态）。
  inputSchema 必填参数: ['plan_id']
- list_delayed_plans: 列出所有处于延期状态的生产计划。
  inputSchema 必填参数: []
── tools/call get_plan(P-1002) ──
isError=False | content={ "plan_id": "P-1002", ... "status": "延期" }
── tools/call get_plan(P-9999)（工具内部抛 ValueError）──
isError=True | content=Error executing tool get_plan: 计划 P-9999 不存在
```

**EX-55-04 | examples/ch55_mcp/ex_55_04_mcp_langchain_adapter.py（完整可运行）**

```python
# EX-55-04 | langchain-mcp-adapters：把 MCP 工具转成 LangChain BaseTool 并接入 create_agent | 运行: python3 examples/ch55_mcp/ex_55_04_mcp_langchain_adapter.py
"""实测（langchain-mcp-adapters 0.3.2 + mcp 1.30.0，2026-10-19 真实运行）：
load_mcp_tools(session) 把 tools/list 的结果翻译成 BaseTool——
name/description 原样保留，inputSchema 变成参数 schema；转换后的工具
本地直调走协议，交给 create_agent 后与 @tool 写的完全同构（源码见示例文件）。"""
tools: list[BaseTool] = await load_mcp_tools(session)     # MCP → LangChain 的协议翻译层
agent = create_agent(model=model, tools=tools, system_prompt="...")   # 与 EX-42-01 同一接线
result = await agent.ainvoke({"messages": [HumanMessage(content="查一下 P-1002 的状态")]})
# 注意：MCP 工具是 async-only，同步 invoke 会抛 NotImplementedError——必须用 ainvoke
```

```text
# 真实运行输出（节选；前两行是 server 子进程 stderr）
── load_mcp_tools 转换结果 ──
- name=get_plan | args_schema 必填字段=['plan_id']
  description=按计划号查询生产计划详情（产品/数量/状态）。
── BaseTool 直调 get_plan ──
[{'type': 'text', 'text': '{ "plan_id": "P-1001", "product": "减速器壳体", ... }}']
── create_agent + MCP 工具的完整闭环（Mock 驱动）──
  HumanMessage 查一下 P-1002 的状态
  AIMessage     tool_calls=['get_plan']
  ToolMessage  [{'type': 'text', 'text': '{ "plan_id": "P-1002", ... tool_call_id=call_001
  AIMessage    P-1002（转向节）处于延期状态，数量 1200，建议分析延期原因。
```

## 55.5 逐段解释

1. **FastMCP 的 @mcp.tool() 与 @tool 的对照**：装饰器同样从函数签名+docstring 生成 schema——你在 ch39 学的"描述三要素"纪律在 MCP server 里一字不改地适用。区别在执行位置：工具体运行在 **server 进程**，host 拿到的只是协议翻译后的 BaseTool 代理。
2. **stdio 的 stdout 纪律**（EX-55-02 的注释）：stdio 模式下 `mcp.run()` 会把 stdout 作为协议通道。示例里任何 `print()` 到 stdout 都会把非 JSON 字节混进帧流，客户端解析直接失败——**这就是 MCP 版的"日志要打 stderr"**，比 Java 的 stdout/stderr 约定更硬（协议 vs 习惯）。
3. **isError 的双层错误语义**（EX-55-03 输出）：P-9999 的业务异常走的是**正常 JSON-RPC 响应**（isError=true + 错误文本），而不是协议级 error 帧——前者是"工具的数据"，模型可以读到并改路；后者是"协议/传输事故"（如方法不存在、JSON 解析失败）。给你的启发：工具内部的失败尽量转成"工具结果"，把协议 error 留给真正的协议事故——这与 ch56 的"业务 404 是数据，5xx 是事故"完全同构。
4. **为什么 host 能力里有 experimental**（握手输出）：能力协商是逐字段的，SDK 版本会带实验性能力字段——读握手输出的能力清单是排障第一步（"我配置的能力 server 为什么没响应"先看这里）。
5. **async-only 的坑**（EX-55-04 注释）：MCP 协议调用本质异步（stdio 管道/HTTP），adapters 转换出的 BaseTool 只实现了异步路径，同步 `.invoke()` 会抛 NotImplementedError——**真实报错形态见 55.7②**。

## 55.6 安装 / 文件位置 / 运行命令

```bash
# 安装（选修，未入全书锁定文件——见 55.9"待核实"）：2026-10-19 沙箱实测版本
pip install mcp==1.30.0 langchain-mcp-adapters==0.3.2
# 运行
cd /workspace/ai_application_course
python3 examples/ch55_mcp/ex_55_01_mcp_messages.py          # 纯讲解，无网络
python3 examples/ch55_mcp/ex_55_02_mcp_stdio_server.py      # 单独跑=阻塞等协议输入，正常现象（Ctrl-C 退出）
python3 examples/ch55_mcp/ex_55_03_mcp_stdio_client.py      # 端到端：拉起 server 子进程
python3 examples/ch55_mcp/ex_55_04_mcp_langchain_adapter.py # 接入 create_agent
python3 -m pytest tests/test_ch55.py -q                     # 4 个测试（真实 stdio 协议闭环）
```

## 55.7 常见错误与排查

**① `ModuleNotFoundError: No module named 'mcp'`**：未安装官方 SDK。修复：`pip install mcp`（版本以 pip 实测为准，本书 1.30.0）；教材代码对 SDK API（FastMCP/ClientSession/StdioServerParameters）依赖较强，**升级后先跑 tests/test_ch55.py 回归**。

**② `NotImplementedError`（对 MCP 工具调 `.invoke()`）**：adapters 转换的工具是 async-only。修复：用 `await tool.ainvoke(...)`，Agent 用 `await agent.ainvoke(...)`（EX-55-04 的写法）。这个报错消息为空（基类只声明契约），看到空 NotImplementedError 先想到"同步/异步用错"。

**③ 客户端解析协议失败 / 卡在 initialize**：server 往 stdout 打了日志（print/logging 默认走 stdout）。修复：server 内一切输出走 stderr（logging.basicConfig(stream=sys.stderr)）；检查依赖库是否有"print 调试"残留。**排障技巧：先直接跑 server 脚本，凡 stdout 出现非 JSON 行都是嫌疑人。**

**④ `KeyError: 'plan_id'` / 工具参数缺失**：client 传参与 inputSchema 不符。修复：对照 tools/list 返回的 inputSchema（required 字段）；在 host 侧用 Pydantic 再校验一次（ch54 纪律不因 MCP 而豁免）。

## 55.8 企业场景中的使用方式（Spring Boot 集成视角）

- **什么时候把 Java 服务包成 MCP server**：同一批工具将被 ≥2 个 AI 应用复用，或工具方（Java 团队）想自治维护工具版本——在 Java 侧用 MCP Java SDK（版本待核实，落地前查官方 GitHub）或侧车进程（Python/Node stdio server 包 Java REST）暴露 MCP；只服务一个应用时，直接 HTTP 工具（ch56）更简单。
- **与 Spring 的类比要讲边界**：MCP client/server ≈ 服务消费方/提供方，但**它替换的不是 Spring Cloud 的服务调用，而是"工具元数据与调用的标准协议"**——注册中心/熔断/负载均衡该用什么还用什么（Streamable HTTP 场景前面就是普通网关）。
- **权限与审计不豁免**：MCP server 收到的调用同样要过 ch54 四道关卡；host 传来的用户身份（如 JWT）经 MCP 的请求元数据（_meta / HTTP header）透传——具体字段以当日规范为准（待核实项：企业级身份透传的推荐 schema 仍在演进）。
- **治理建议**：把"MCP server 清单"当作与"内部 API 清单"同级的资产登记——name/instructions/工具列表/owner/风险级别；AI 应用接入新 server 走评审（55.2 的"工具描述不可信"原则决定了**不可自动信任新 server**）。
- **什么时候不需要 MCP**（与 ch37"什么时候不需要 LangChain"同款的边界意识）：①只有一个 AI 应用消费（M+N 没有收益，直接 HTTP 工具更简单）；②工具变更频率极低且与应用同生命周期（拆出去只有部署成本）；③对延迟极度敏感且工具在本地（stdio 子进程每次冷启动拉 Python 解释器约几百毫秒——高频调用场景要么常驻要么别拆）。MCP 的价值公式：**复用方数量 × 工具自治需求 − 协议与治理成本 > 0**。

## 55.9 练习与"待核实"小节

**练习（基础 2 + 代码 2 + 调试题 1）**：
**基础 1**：MCP 的三种角色与三原语分别是什么？谁是"模型"谁是"人"的控制对象？**基础 2**：isError=true 的响应与 JSON-RPC error 帧的区别，各自应该在什么场景出现？
**代码 1**：给 EX-55-02 增加 `query_workorder` 工具（参数 workorder_id 校验 `^WO-\d+$`，不匹配抛 ValueError），并用 tests/test_ch55 的模式补一个测试。**代码 2**：写一个"权限包装器"——host 侧在 call_tool 前检查本地权限表，拒绝时根本不发协议请求，并写测试。
**调试题**：客户端 initialize 卡住 30 秒后超时，server 单独运行正常。最可能原因？

### 参考答案

基础 1：Hosts（LLM 应用）/Clients（host 内连接器）/Servers（能力提供方）；Tools（模型控制）/Resources（应用控制）/Prompts（用户控制）。基础 2：isError=true 是 tools/call 的正常响应（工具业务失败，模型可读可改路）；error 帧是协议级事故（未知方法/解析失败等），模型一般不可恢复。代码 1：装饰器照抄 get_plan 形状，schema 校验放函数体内或用 Pydantic；测试用 stdio_client 拉起后 call_tool 断言 isError=True。代码 2：包装函数查 `PERMS[role] & {tool_name}`，未授权直接 raise——测试断言 respx/server 收不到请求。调试题：server 的 stdout 被某依赖打印污染（进度条/横幅），协议帧解析失败——把依赖输出重定向 stderr，或用 `-W` / 环境变量关横幅。

### 待核实（本书诚实声明）

| 事项 | 状态 |
|---|---|
| MCP 规范版本号与传输细节 | 2026-07-28 版于 2026-10-19 经官网核实；规范演进快，**落地前以当日官网为准** |
| mcp 1.30.0 / langchain-mcp-adapters 0.3.2 | 沙箱 pip 实测可用（EX-55-03/04 与 test_ch55 真实运行）；**未写入 requirements.txt**：这两个包在本书成稿时是"选修演示"依赖，是否收编锁定文件由主编统一决定（55.6 的安装命令即当前实测版本）；若收编，需补一轮版本锁定与全量回归 |
| MCP Java SDK 的当前版本与成熟度 | 未在本书核实（沙箱未运行 Java 版 MCP server）——标注**待核实**，建议读者查 modelcontextprotocol.io 或官方 GitHub 组织当日 release |
| Streamable HTTP 的鉴权细节 | 规范指向标准 HTTP 鉴权机制，具体 header/流程以当日版本为准，本书未实测 |
| 企业级身份透传（_meta 字段）的推荐 schema | 规范演进中，**待核实** |

## 55.10 自测检查表

- [ ] 我能说清 MCP 是协议不是框架，以及它替换与不替换的东西；
- [ ] 我能手画 initialize/tools/list/tools/call 的 JSON-RPC 帧；
- [ ] 我能解释 stdio 下 stdout 纪律与 isError 双层错误语义；
- [ ] 我能在"包 MCP server vs 直接 HTTP 工具"之间给出选择依据；
- [ ] 我知道 MCP 不豁免任何一条 ch54 治理防线，并知道五条"待核实"边界。

## 55.11 面试追问

1. **[模拟题] MCP 和 Function Calling 什么关系？** 答：Function Calling 是"模型如何请求调用函数"的模型层约定（ch24 的 tool_calls）；MCP 是"应用如何发现与调用外部工具"的应用层协议。MCP 的工具最终仍以 Function Calling 的形式呈现给模型——两者互补不在一个层。
2. **[模拟题] 为什么说 MCP 把 M×N 变成 M+N？代价是什么？** 答：M 个应用各自实现 N 套工具 → M 个 host 各实现一次 client + N 个 server；代价是多一跳协议（进程边界/网络）、协议版本管理、工具元数据治理。
3. **[模拟题] host 如何防"恶意 server"？** 答：规范三原则——新 server 接入需用户同意；工具描述视为不可信（防描述注入诱导）；高危工具调用前逐次确认；再加实现层：server 白名单、工具级权限、审计。协议不强制，责任在实现。

---

# 第 56 章 对接已有 Java 服务：封装、长任务与超时重试

> **本章目标**：把"AI 应用对接已有 Java 系统"做成一套可复用的工程模式：HTTP 工具封装四件套；长任务模式（202 Accepted + task_id + 轮询/取消）；超时与重试的语义层（重试哪些、怎么重、何时停）。本章末尾给"Java 工程师最关心的 10 个集成问答"，并把全部知识收拢到项目三。
> **前置知识**：ch15（httpx 超时三件套与重试）、ch17（FastAPI）、ch54（工具治理）、ch48（审批与幂等）。
> **学完你能做什么**：为任意 REST API 写出"干净的工具层"；为慢接口设计异步任务契约；给集成方案配上正确的超时/重试/幂等参数。

## 56.1 真实问题引入：AI 助手上线的第四天，MES 团队找上门

项目三的背景场景（合成案例）：AI 助手要查生产计划、查工单、提交调整。MES 团队（Java）说："接口都有，你们直连就行。"第四天出了三件事：①AI 助手超时把 MES 的连接池占满——Python 侧没设超时；②网络抖动后重试，MES 里出现了两条相同的调整记录——重试没带幂等键；③运营抱怨"提交调整一直转圈"——分析要跑两分钟，HTTP 同步等死。

三个问题对应本章三节：**封装（怎么调干净）、幂等（怎么重试安全）、长任务（怎么不转圈）**。这些不是 AI 问题，是把 AI 的"不可靠性放大器"接到已有系统前的标准工程动作——Java 工程师在服务治理上的全部经验，这里是它们的主场。

## 56.2 一句话解释 + 生活类比 + 类比边界

**一句话解释**：封装=把 HTTP 调用包成"契约明确、错误分层、描述干净"的 Agent 工具；长任务=把"慢操作"改成"提交受理（202）→ 凭 task_id 轮询/取消"；超时重试=给每次上游调用定"最坏情况预算"（有限次数×幂等安全×退避抖动×错误白名单）。

**生活类比**：对接 MES ≈ 在两条马路之间修一个收费站 + 调度台——封装是收费站（标准化进出），长任务是调度台（急活给回执慢活给单据），超时重试是调度台的白板（每单写上"最晚几点放弃"）。Java 对照：这就是把 Feign/RestTemplate 的超时重试配置、幂等消费、异步任务表（Spring 的 @Async + 任务状态表）在 Python 侧重写一遍——**经验完全迁移**，只是"调用方是模型"多了一条：它不会看监控告警，超时预算必须由你的代码替它扛住。

> 💡 类比边界：
> 1. 微服务间的重试要防"重试风暴"（上游刚恢复被二次打死），AI 工具的重试还要防"模型学习错误样本"——重试耗尽后返回给模型的信息必须是"结构化失败"，不是堆栈；
> 2. 长任务的"取消"永远是协作式的：DELETE 只是请求停止（202），真正的停止要任务自身在每个检查点看标志位——与线程中断/协程取消同理；
> 3. 202 ≠ 快：它只是诚实地承认"这活儿还没干完"。把同步接口伪装成 200 立即返回空结果，比慢更糟。

## 56.3 正式原理与准确术语

**HTTP 工具封装四件套**（EX-56-01）：
1. **专用 httpx.Client**：连接池复用 + 超时三件套（connect/read/pool，ch15），绝不每调用新建；
2. **契约模型**：响应字段用 Pydantic 模型固定（契约即代码，与 data/*.json 对拍——项目三的契约测试）；
3. **错误翻译三层**：404 → 业务数据（"不存在"返回给模型）；5xx/超时/连接失败 → JavaServiceError（事故，交给上层重试/熔断）；4xx 其他 → 原样上抛（调用方的 bug）。**关键判断：哪些错误是"数据"，哪些是"事故"**；
4. **描述纪律**：docstring 写"何时用/何时不用"（ch54 三要素）。

**长任务模式**（EX-56-02）状态机：`pending → running → succeeded | failed | cancelled`。契约：POST → **202** `{task_id, poll}`；GET → 状态+result；DELETE → 202（协作式取消请求）或 409（已终态）。客户端三纪律：提交后只拿 task_id；轮询带间隔与上限；取消是"请求+确认"两步。项目三把同一模式反过来用：Python FastAPI 对外当服务方（POST /analysis），Java 的慢操作依然同步——**角色对调，契约不变**。

**超时与重试语义**（EX-56-03 的四条）：
- **有限次数**：max_attempts 封顶（本书 3 次）——最坏情况耗时 = Σ(每次超时)+Σ(退避)，可预算可告警。**算例**（项目三默认参数）：read 超时 5s、max_attempts=3、退避 0.05s/0.1s（含抖动 ±0.05s）→ 最坏 ≈ 5+0.05+5+0.1+5 ≈ **15.2s**。把这个数写进任务状态机的超时与前端提示——"分析最多等 15 秒"是可承诺的 SLA，"再等等"不是。若上游 SLA 是 P99=800ms，把 read 收到 2s → 最坏 ≈ 6.2s；
- **幂等才自动重试**：GET 天然幂等；POST 必须携带 Idempotency-Key（服务端按 key 去重）——项目三的幂等键由 trace_id+内容哈希确定性生成，同一次分析内重试同 key；
- **退避+抖动**：base×2^n + 随机抖动，防恢复瞬间的重试风暴；
- **可重试白名单**：超时/连接错误/5xx 重试；422/404 等业务错误绝不重试（重试一个"参数错了"的请求只会得到同样的错误，纯属烧钱）。

**结果获取的三种方式**（长任务的"怎么拿到结果"）：

| 方式 | 机制 | 适用 | 代价 |
|---|---|---|---|
| 轮询（本书主线） | 定时 GET 任务状态 | 实现最简、所有后端都支持 | 空轮询浪费；间隔与上限要调 |
| SSE/流式推送 | 服务端主动推状态事件 | 有长连接基建（ch17 SSE、ch42 astream） | 需要断线重连与事件补发 |
| 消息队列回调 | 完成后发 MQ 消息 | 已有 MQ 的公司（Java 团队常态） | 消费端幂等又要做一遍 |

三者的服务端状态机完全相同，差别只在"状态变化怎么通知客户端"——**先把状态机做对，通知方式可以逐步升级**（项目三轮询起步，README 扩展方向 4 给了 SSE 升级路径）。

**契约表（项目三 Java 端点，与 data/*.json 对拍）**：

| 端点 | 方法 | 幂等性 | 成功 | 错误 |
|---|---|---|---|---|
| /plans?date= | GET | 天然幂等 | 200 计划列表 | 400 bad_date |
| /workorders/{id} | GET | 天然幂等 | 200 工单详情 | 404 not_found |
| /adjustments | POST | **Idempotency-Key 必填** | 首次 201 / 重放 200+replay | 400 缺 key / 422 校验 |
| /slow?ms= | GET/POST | 只读演示 | 200（延迟后） | — |

**Java 对照**：四件套 ≈ Feign Client 配置（连接池/超时/解码器/错误解码器）；长任务 ≈ Spring @Async + 任务状态表 + 提交接口返回 taskId；幂等键 ≈ 消息消费的去重表；可重试白名单 ≈ RetryableException 分类。

## 56.4 最小完整示例：封装、长任务、超时重试

**EX-56-00（基础设施）| examples/ch56_java_bridge/stub_java_service.py**：线程内"Java 服务替身"，端点形状与项目三 PlanServer.java 逐字段一致（/plans、/workorders/{id}、/adjustments 幂等、/slow、/tasks 长任务）——EX 必须离线确定性可跑（STYLE_GUIDE D），替换成真 Java 服务只需改 base_url（项目三已验证两种指向行为一致）。

**EX-56-01 | examples/ch56_java_bridge/ex_56_01_http_tool_wrapper.py（完整可运行）**

```python
# EX-56-01 | 把已有 Java HTTP API 封装成 Agent 工具：@tool + httpx + Pydantic + 错误翻译 | 运行: python3 examples/ch56_java_bridge/ex_56_01_http_tool_wrapper.py
"""四件套：专用 Client（超时三件套）/ 契约模型 / 错误翻译三层 / 描述纪律。
完整源码见示例文件——核心形状："""
class ToolHTTPClient:
    def __init__(self, base_url: str) -> None:
        self._client = httpx.Client(base_url=base_url,
            timeout=httpx.Timeout(connect=2.0, read=5.0, write=2.0, pool=2.0))

    def get_json(self, path, *, params=None) -> dict:
        try:
            r = self._client.get(path, params=params)
        except httpx.TimeoutException as e:
            raise JavaServiceError(f"上游超时（read=5s）") from e
        except httpx.HTTPError as e:
            raise JavaServiceError(f"上游连接失败：{type(e).__name__}") from e
        if r.status_code >= 500:
            raise JavaServiceError(f"上游 5xx：{r.status_code}")
        if r.status_code == 404:
            return {"_not_found": True}      # 业务性"不存在"是数据 → 返回给模型
        r.raise_for_status()
        return r.json()

@tool 装饰的 tool_query_plans/tool_query_workorder 把响应过 Pydantic 契约模型再返回。
```

```text
# 真实运行输出（目标服务为线程内替身，端口随机）
== HTTP → Agent 工具（目标服务 http://127.0.0.1:39439）==
[1] 正常路径：query_plans('2026-03-18')
    count=2，第一条：{'plan_id': 'P-1001', 'product': '减速器壳体', 'qty': 500, 'status': '正常'}
[2] 正常路径：query_workorder('WO-2091')
    {'workorder_id': 'WO-2091', 'plan_id': 'P-1002', 'status': '生产中', 'produced_qty': 900, 'target_qty': 1200, 'exists': True}
[3] 业务性 404（数据，不是事故）：query_workorder('WO-9999')
    {'exists': False, 'workorder_id': 'WO-9999', 'hint': '工单不存在，请核对工单号（可用 tool_query_plans 反查）'}
[4] 基础设施错误（事故，交给上层重试/熔断）：关停服务后调用
    JavaServiceError: 上游连接失败：ConnectError
```

**EX-56-02 | examples/ch56_java_bridge/ex_56_02_long_task_pattern.py（完整可运行）**

```python
# EX-56-02 | 长任务模式：202 Accepted + task_id + 轮询 + 取消 | 运行: python3 examples/ch56_java_bridge/ex_56_02_long_task_pattern.py
"""对替身服务的 /tasks 端点演示完整生命周期。客户端三纪律：
提交只拿 task_id；轮询带上限（0.1s × 50 次）；取消是"请求+确认"两步。"""
def wait(self, *, interval_s=0.1, max_polls=50) -> dict:
    for i in range(max_polls):
        snap = self.poll()
        if snap["status"] in {"succeeded", "failed", "cancelled"}:
            return snap
        if i == max_polls - 1:
            raise TimeoutError(f"任务 {self.task_id} 轮询 {max_polls} 次仍未终态")
        time.sleep(interval_s)

def cancel(self) -> dict:
    r = self._client.delete(f"/tasks/{self.task_id}")
    if r.status_code == 409:
        return {"cancelled": False, "reason": "task_already_finished"}
    r.raise_for_status()
    return {"cancelled": True, **r.json()}
```

```text
# 真实运行输出（端口随机）
== 长任务模式（目标服务 http://127.0.0.1:41809）==
[1] 正常路径：提交 → 轮询到 succeeded
    ← 202 Accepted，task_id=TASK-943846a2（立即返回，不阻塞）
    终态：succeeded，result={'summary': '分析完成：P-1002 延期风险中'}（等待 0.4s）
[2] 取消路径：提交 → DELETE → 状态变 cancelled
    cancel → {'cancelled': True, 'task_id': 'TASK-3effe9bc', 'status': 'cancelled'}
    poll   → cancelled（协作式取消：任务线程每 0.05s 查一次标志位）
[3] 取消已结束的任务 → 409 Conflict（终态不可撤销）
    cancel → {'cancelled': False, 'reason': 'task_already_finished'}
[4] 查询不存在的任务 → 404
    GET /tasks/TASK-nope → 404 {'error': 'task_not_found', 'task_id': 'TASK-nope'}
```

**EX-56-03 | examples/ch56_java_bridge/ex_56_03_timeout_retry_semantics.py（完整可运行）**

```python
# EX-56-03 | 超时与重试语义：重试哪些、怎么重、何时停 | 运行: python3 examples/ch56_java_bridge/ex_56_03_timeout_retry_semantics.py
"""对 /slow 与 /adjustments 演示语义四条：有限次数/幂等才重试/退避加抖动/白名单。
完整源码见示例文件——call_with_retry 的骨架："""
RETRYABLE = (httpx.TimeoutException, httpx.TransportError)   # 可重试白名单

def call_with_retry(client, method, path, *, headers=None, json_body=None,
                    max_attempts=3, base_backoff_s=0.1):
    for attempt in range(1, max_attempts + 1):
        try:
            r = client.request(method, path, headers=headers, json=json_body)
            if r.status_code >= 500:
                last_exc = ...     # 5xx 可重试
            else:
                return r.json()    # 2xx/4xx 直接返回：4xx 是业务错误，重试无意义
        except RETRYABLE as e:
            last_exc = e
        if attempt < max_attempts:
            time.sleep(base_backoff_s * (2 ** (attempt - 1)) + random.uniform(0, 0.05))
    raise last_exc
```

```text
# 真实运行输出（端口随机；退避含抖动故毫秒数逐次不同）
== 超时与重试语义（目标服务 http://127.0.0.1:37507）==
[1] 快端点：/slow?ms=50，read 超时 1s → 一次成功，零重试
    → {'ok': True, 'delayed_ms': 50}
[2] 慢端点：/slow?ms=1200，read 超时 0.3s → 3 次全超时后放弃（止损上界）
    尝试1：ReadTimeout（0.30s 内失败，可重试）
    退避 0.13s 后重试
    尝试2：ReadTimeout（0.30s 内失败，可重试）
    退避 0.24s 后重试
    尝试3：ReadTimeout（0.30s 内失败，可重试）
    重试耗尽：ReadTimeout，总耗时 1.27s
    → 最坏情况 = Σ(每次超时) + Σ(退避)，可预算、可告警，不是'无限等'
[3] 幂等重试：POST /adjustments 同一 Idempotency-Key 重发两次
    首次：已受理，adjustment_id=ADJ-4e2e7712
    重放：HTTP 200 + 同 adjustment_id=ADJ-4e2e7712，idempotent_replay=True
[4] 业务错误不重试：404 直接返回给调用方（数据，不是事故）
    GET /workorders/WO-9999 → 404（call_with_retry 对 4xx 零重试）
```

## 56.5 逐段解释

1. **"数据 vs 事故"是错误翻译的脊柱**（EX-56-01 [3][4]）：404 返回 `{"exists": False, "hint": ...}`——模型读到后会说"请核对工单号"而不是把异常当结论；连接失败抛 JavaServiceError——上层（重试器/任务状态机）决定重试或失败，**模型永远不参与基础设施决策**。这条分界线写进团队规范，能省掉一半的"AI 助手抽风"工单。
2. **轮询上限不是可选项**（EX-56-02 的 max_polls）：上游卡死时，无上限轮询把调用方一起拖死——这与 ch15"超时是止损"同源。生产可升级为指数间隔（0.1→0.2→0.4…）+ 最大等待时间 + 回调/SSE 通知（省掉轮询本身）。
3. **重试耗尽要抛"最后一次的异常"**（EX-56-03）：吞掉异常返回空值是事故放大器。项目三的 JavaClient 统一包装为 JavaServiceError，任务状态机把它变成 task failed——失败对用户可见、对审计可见。
4. **202 的语义诚实**：EX-56-02 [1] 的"立即返回"与 [2] 的"等待 0.4s"对比就是长任务的价值——用户侧延迟与任务时长解耦。项目三的真实数据：低风险分析任务后台数百毫秒完成，但 HTTP 层 202 在 <10ms 内返回。
5. **幂等键的归属**：客户端生成（本项目）、服务端生成（返回给客户端重试用）都可以，但**必须同一次逻辑操作同一个 key**——项目三把 trace_id 揉进哈希，天然做到"任务内稳定、任务间不同"。
6. **一次高风险分析的完整时序走读**（把 ch42/ch48/ch56 的知识串成一条线，项目三真实运行实录）：`POST /analysis（紧急）` → FastAPI 202 返回 task_id → 后台线程建任务专属 Agent（工具闭包绑定该任务的审计/取消/权限上下文）→ 第 1 轮模型发起点 `query_plans` → 工具四道关卡 → Java GET /plans → ToolMessage 回传 → 第 2 轮模型点名 `submit_emergency_adjustment`（new_qty=现量×2）→ **HITL 中间件拦截：不执行工具，invoke 返回 `__interrupt__`** → 任务转 `waiting_approval`，审批单（工具名+参数+说明）入任务记录与审计 → 人 `POST /approval {"decision":"approve"}` → `Command(resume={"decisions":[{"type":"approve"}]})` 恢复（同一 checkpointer、同一 thread_id）→ 审批凭证集合加入高风险工具名 → 工具体执行：幂等键生成 → Java POST /adjustments → 201 → 模型第 3 轮整合作答 → 任务 succeeded。**全链每一跳都有审计事件**；reject 分支唯一的差别是中间件把工具调用替换为拒绝消息，Java 侧零写请求。把这段时序对着项目三 §6 的 curl 记录读一遍，第九部分就没有秘密了。

## 56.6 安装 / 文件位置 / 运行命令

```bash
cd /workspace/ai_application_course
python3 examples/ch56_java_bridge/stub_java_service.py            # 替身自测
python3 examples/ch56_java_bridge/ex_56_01_http_tool_wrapper.py
python3 examples/ch56_java_bridge/ex_56_02_long_task_pattern.py
python3 examples/ch56_java_bridge/ex_56_03_timeout_retry_semantics.py
python3 -m pytest tests/test_ch56.py -q      # 9 个测试（契约/幂等/长任务/错误翻译/超时预算）
# 完整工程化（Java 真服务 + FastAPI + Agent + 审批 + 取消）：
cd projects/p3_java_python_agent && cat README.md   # 启动命令与全链路验证记录
```

## 56.7 常见错误与排查

**① `ValueError: httpx.Timeout must either include a default, or set all four parameters explicitly.`**（本书真实踩到）：只传 connect/read 不传 write/pool。修复：四个参数显式给全，或 `httpx.Timeout(5.0, connect=2.0)` 给默认+覆盖。

**② 客户端超时后 Java 侧 BrokenPipeError**：客户端 read 超时断连，服务端睡够后写响应才发现管道已断。这是超时的固有代价（双方各付一次），替身示例已把该噪音静音并注释；生产 Java 侧无需处理（容器日志可忽略），要治的是**为什么慢**（超时预算 → 限流 → 降级）。

**③ 重试后 MES 出现两条调整记录**：POST 重试没带幂等键（或每次重试生成新 key）。修复：幂等键在**任务/trace 级**生成并随重试复用；服务端按 key 去重返回首次结果（项目三 PlanServer 的 ADJUST_SEEN 账本 + 测试锁定）。

**④ 轮询把上游打挂**：固定 0.05s 间隔 × 大量任务。修复：指数退避轮询、任务多时改回调/消息队列、客户端轮询加全局并发上限。

## 56.8 企业场景中的使用方式（Spring Boot 集成视角）

- **Java 侧要为"AI 调用方"做的三件事**：①给 AI 服务单独的限流配额（它可能比你的人类用户并发高得多）；②写接口强制 Idempotency-Key（对 AI 调用方=安全重试的前提）；③慢操作提供异步契约（202+task_id）——这三件事即使不做 AI 也值得做，AI 只是让它们的优先级提前了。
- **Python 侧对等义务**：超时三件套全配、重试白名单、退避抖动、错误翻译——把本节四件套写进团队的"AI 工具接入 checklist"。
- **审批与写操作**：写接口在 Java 侧再加一层业务校验（防 Python 侧治理被绕过）；高风险动作两端都要能"拒绝"（Python 的审批 + Java 的业务规则），纵深防御。

## 56.9 项目三落点 + Java 工程师最关心的 10 个集成问答

**项目三（projects/p3_java_python_agent）把 ch52~ch56 全部串起来**：Java 25 内置 HttpServer 模拟生产计划系统（四个端点含幂等写与慢端点）；Python FastAPI + create_agent（checkpointer + HITL 审批）+ 四道治理关卡的工具层 + 异步任务状态机 + 超时重试；data/ 契约对拍测试；Dockerfile（静态检查）。18 个测试全绿，Java 编译/启动/全链路 curl 验证记录在 verification/run_logs/part09.md。**先读项目 README 的架构图与契约表，再跑 §5 的启动命令**。

**Java 工程师最关心的 10 个集成问答**：

1. **Q：AI 服务会打挂我的 MES 吗？** A：会，如果你们不设防。Python 侧已配超时三件套+有限重试+退避抖动（56.3）；Java 侧请给 AI 服务单独配额与限流——双侧防线，缺一不可。
2. **Q：为什么写接口必须支持 Idempotency-Key？** A：重试是常态（网络抖动、审批恢复重跑、Agent 重新规划）。同 key 去重后，重试从"制造脏数据"变成"安全动作"。项目三实测：同 key 重放返回 200 + 同 adjustment_id + `idempotent_replay=true`。
3. **Q：AI 的"分析"要跑两分钟，我的接口怎么办？** A：两条路——Java 提供异步契约（202+task_id，EX-56-02 模式）；或 Java 保持同步、由 Python 侧包成异步任务对外（项目三 POST /analysis 模式）。选哪条取决于"慢"发生在谁那边。
4. **Q：AI 能直接写我的数据库吗？** A：永远不能。写操作只通过你的服务接口（带鉴权、校验、审计）；Python 工具层再加权限分级与审批（ch54）。数据库直连只读且只给最小权限账号——即使这样也要审计。
5. **Q：模型选错工具调了我的接口怎么办？** A：接口侧按参数完整性校验会自然拒绝（422）；Python 侧把错误翻译回模型可自纠。治理重点在预防：描述三要素 + 线上误选回归（ch54）。
6. **Q：怎么审计 AI 到底对我的系统做了什么？** A：Python 审计 JSONL（五要素）与 Java 业务流水用幂等键/trace_id 对账——能回答"哪次分析、谁批的、提交了什么调整"（项目三 §7 审计样例）。
7. **Q：应该把 Java 服务包成 MCP server 吗？** A：被 ≥2 个 AI 应用复用、且工具方想自治维护时值得（ch55.8）；单一消费方用直接 HTTP 工具更简单。两者治理动作相同。
8. **Q：超时设多少合适？** A：从你现有 SLA 倒推：Java 接口 P99 是 800ms → Python read 超时 2s（留余量）+ max_attempts=3 + 退避——最坏 8s 左右，这就是这个工具的预算；把预算写进任务状态机的超时（项目三 read_s 可配）。
9. **Q：AI 服务挂了会不会影响我的正常业务？** A：不该影响——AI 工具调用与人类流量走同一接口但不同配额；熔断在 Python 侧做（连续失败后快速失败，任务转 failed 并提示"上游暂不可用"），Java 侧限流兜底。
10. **Q：这套东西怎么向管理层要资源/解释价值？** A：一句话——"把工程师从重复的查数与报表里解放出来，同时用审批+幂等+审计保证它比人手误更可控"；项目三的可复现验证（一条命令起两端、18 个测试、全链路 curl 记录）就是可信度的证据。

## 56.10 练习（基础 2 + 代码 2 + 调试题 1）与自测

**基础 1**：HTTP 工具封装四件套是什么？**基础 2**：202 与 200 在长任务契约里的语义差别？
**代码 1**：给 stub_java_service 的 /tasks 增加 `GET /tasks`（列出全部任务），并为 TaskHandle 写对应方法。**代码 2**：把 EX-56-03 的 call_with_retry 改成类（RetryPolicy 可配置 max_attempts/backoff/jitter），配三个参数化测试。
**调试题**：Python 侧日志显示大量 `JavaServiceError: 上游 5xx：503`，Java 同学说"我们没问题"。给出至少三条定位手段。

### 参考答案

基础 1：专用 Client/契约模型/错误翻译三层/描述纪律。基础 2：202=已受理未完成（凭 task_id 续查），200=本次请求已完结（长任务里 200 用于查询/重放）。代码 1：`_TASKS.values()` 快照返回列表；TaskHandle.list_tasks(client)。代码 2：把循环参数搬进 dataclass RetryPolicy，`@pytest.mark.parametrize` 覆盖 5xx 重试/4xx 不重试/耗尽抛最后异常。调试题：①看 503 的时序是否与 Java 发布/重启对齐；②对比 Java 侧访问日志与 Python 审计的 request_id 对账（是否真打到 Java）；③压测复现（并发×参数），检查连接池/线程池上限——三条都指向"以对账日志代替口头互甩"。

**自测检查表**：
- [ ] 我能给任意 REST API 写出四件套封装并说明错误翻译的分界；
- [ ] 我能设计 202+task_id+轮询+取消的完整契约并给轮询加上限；
- [ ] 我能讲清重试语义四条并算出最坏耗时预算；
- [ ] 我能解释幂等键的生成与归属，并知道它在审批重放里的作用；
- [ ] 我能回答上面 10 个集成问答中的至少 6 个。

## 56.11 面试追问

1. **[模拟题] AI Agent 调用传统微服务和普通服务间调用，最大的差别是什么？** 答：调用方从"可通知、可值班"变成"概率性且无人值守"——所以超时预算、幂等、权限、审计必须全部代码化，错误信息要设计成"模型可读可自纠"的格式。
2. **[模拟题] 长任务的取消语义为什么是协作式的？强杀不行吗？** 答：强杀（杀线程/进程）会让副作用停在未知状态（写了半条/锁未释放）；协作式取消让任务在检查点自己退出并落终态。与数据库事务、线程 interrupt 的设计动机一致。
3. **[模拟题] 如果 Java 团队不接受任何改造，你还能接吗？** 答：能——只读工具直连；写操作降级为"生成建议+人工执行"（AI 不碰写接口），审批流把"执行"动作留给人。这是治理的底线形态，也是很多生产系统的现实起点。

---

# 第九部分收束：从知识到项目

五条主线在项目三汇合：ch52 的决策表解释了"为什么分析主链是 Agent、而校验/幂等/审计是写死的工具层"；ch53 的判断标准解释了"为什么它就该是单 Agent"；ch54 的治理清单是工具层四道关卡的出处；ch55 的 MCP 给出了工具复用的下一站（扩展方向 5）；ch56 的三个模式（封装/长任务/超时重试）是全部集成代码的模板。**验收标准（syllabus）**：为一个业务系统设计"哪些环节用 Workflow、哪些用 Agent"并说明理由——用 EX-52-01 的决策表跑一遍你自己的业务，就是最诚实的验收。

**向后衔接**：第十部分（ch57 起）把本部分的"单点正确"升级为"系统正确"——AI 服务与业务服务的架构边界（ch57）、纵深安全（ch58）、稳定性参数（ch59）、成本与可观测（ch60）、上线清单（ch61）。项目三里所有"教学从简"的地方（进程内任务表、内存 checkpointer、无熔断）都将在那里找到生产答案。
