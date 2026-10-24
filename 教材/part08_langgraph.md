# 第八部分 LangGraph（ch43~ch51）★全书重点

> 资料核实日期：2026-10-19。本部分全部示例在本教材约定的沙箱环境（Python 3.14.7，langgraph 1.2.16，langchain-core 1.6.12，见 `requirements.txt`）实际运行；模型相关节点统一使用第四部分创建的 `示例代码/公共/llm_client.py`（`LLM_MODE=mock` 默认离线 / `LLM_MODE=real` 需 Key），输出标注 `# Mock 运行输出`。所有 API 形态（签名、报错文案、恢复语义）均以 `python3 -c "import inspect; ..."` 在 1.2.16 上实测为准，核实过程见各章与 `验证报告/运行日志/part08.md`。
> 前置知识：ch08（异常体系）、ch11（TypedDict/类型注解）、ch24（工具调用闭环——ch46 的前身）、ch18（pytest——ch51 的载体）；项目二（p2_log_triage）是本部分的综合落地，建议学完 ch48 后开始读。
> 学完你能做什么：
> 1. 把"链式写死"的 AI 流程重构为 LangGraph 图：State/Node/Edge/条件路由/循环/Send 并行/子图，并说清每个构件与 Java 状态机、工作流引擎的对应与**不等价**之处；
> 2. 用 checkpointer + thread_id + interrupt/Command 实现生产级的持久化、恢复与人工审批，讲透"恢复后从哪继续"与副作用幂等——这是 LangGraph 面试与生产事故的共同焦点；
> 3. 为整图建立测试体系：单节点直调、整图断言、快照校验、Mock LLM 注入，并把这套方法直接套用到项目二的排障助手上。

---

# 第 43 章 为什么需要图：链、状态机与图的边界

> **本章目标**：建立"控制流与业务分离"的编排直觉，知道什么时候链不够用、什么时候该上图。
> **前置知识**：ch24（工具调用闭环）、ch40（LCEL 链）。
> **学完你能做什么**：用一个具体需求变更案例，解释为什么把控制流搬进"图"；画出链/状态机/图三者的能力边界表；说出 LangGraph 与 Spring StateMachine 的四个不等价点。

## 43.1 真实问题引入：三次需求变更压垮一条链

某电商平台（合成案例）的 Java 团队给客服系统接了第一个大模型功能：工单自动分类。v1 是一条教科书式的链：清洗 → 分类 → 按类别分发，代码 30 行，上线一周很稳。然后需求来了——

- 第一次变更：命中敏感词的工单先走人工审核。小王在链的入口前加了一个 `if`。
- 第二次变更：VIP 工单跳过排队。又加一个 `if`，这次要穿透中间层，小王把方法签名改了。
- 第三次变更：账务工单夜间只受理不执行，还要把"这单为什么走了这条路"记进审计日志供客服主管查。小王的链里已经分不清哪段是业务、哪段是控制流，审计日志要横穿三层方法才能凑齐。

三次变更之后，这段"管线"变成谁都不敢动的面条代码。问题不在业务函数——清洗、分类、分发各自都好好的——而在**控制流长在了业务代码里**：每一次流转规则变化，都要改管线本体。EX-43-01 用最朴素的 Python 复现了这条命运曲线。

## 43.2 一句话解释 + 生活类比 + 类比边界

**一句话解释**：图编排把"下一步去哪"从业务代码里抽出来，变成**声明式的节点与连线**——节点只做业务（函数），连线只管流转（拓扑），状态在节点之间显式流动。

**生活类比**：把链式调用想成"传纸条"——每个人处理完把纸条递给固定的下一个人，路线焊死在每个人手里；把图编排想成"机场中转系统"——你只负责完成本段的值机（节点），去哪个登机口由航班动态看板（图拓扑 + 状态）决定，改航线不用通知每个柜台。

> 💡 类比边界：
> 1. 图不是"更高级的链"：两节点顺序流程用链更简单，LangGraph 官方也不建议把所有场景都上图——**控制流需要运行时决策、需要暂停恢复、需要多分支汇合**时，图才开始回本；
> 2. 图 ≠ 状态机：状态机是图的特例（状态数有限、迁移条件显式），但 LangGraph 的"状态"是任意结构的共享数据（dict），不是有限状态集合——这是与 Spring StateMachine 最重要的心智差异；
> 3. "声明式"不等于"零代码"：连线本身也是代码（`add_edge`/`add_conditional_edges`），只是它从业务函数里被剥离出来集中管理；
> 4. "图"不是 D3 那种可视化的图：LangGraph 的图是**执行拓扑**（可以打印成 mermaid/ASCII 便于 review），不是前端图表——别把它和 BI 图表工具混为一谈。

顺带把 43.1 的故事说完整：三次变更之后，这个团队最终没有立刻引入 LangGraph——他们先做了一次"控制流搬家"重构，把所有 `if` 挪进一个 `RouteRules` 配置类。重构之后确实好改了，但两次线上事故（一次是敏感词规则漏了"护照"，一次是审计日志没记全路径）暴露了纯配置方案的另外两个短板：**规则之间的组合没有测试**、**流程走到哪一步没有记录**。图的答案是：路由规则不只是配置，还是**可执行、可断言、可回放的拓扑**——这是他们后来迁移的直接动因。

## 43.3 正式原理与准确术语

**编排（orchestration）**：把多个处理步骤（节点）按显式声明的控制流（边）组织起来，并管理它们之间共享状态的机制。

**链（chain）**：步骤按固定顺序串联，控制流在编译期（写代码时）确定。对应 LangChain 的 LCEL 管道（ch40）。

**状态机（state machine）**：状态数有限、迁移规则显式的自动机。Spring 的 `StateMachine`（spring-statemachine-core）是其 Java 代表。

**图（graph）**：节点（计算单元）+ 边（流转关系，含条件边）+ 共享状态。LangGraph 在此之上叠加三个关键能力——**状态在图上**（state 是一等公民，每个节点读写同一个状态）、**可持久化**（每步之后状态快照可存盘）、**可恢复/可回放**（从快照继续执行，甚至从历史快照重新出发）。

**Java 对照**：LangGraph ↔ Spring StateMachine / Flowable 这类工作流引擎。相似的是"节点 + 迁移 + 条件分支"的拓扑思维；**不等价的是四件事**：

| 维度 | Spring StateMachine / 工作流引擎 | LangGraph |
|---|---|---|
| 状态载体 | 有限状态枚举，迁移即状态切换 | 任意 TypedDict/Pydantic 结构，节点返回"部分更新"由 reducer 归并 |
| 并发写入 | 单状态变量，迁移互斥 | 多节点同一超步写同一字段 → 必须声明 reducer 归并 |
| 持久化恢复 | 引擎各自的持久化 API（常需额外集成） | checkpointer 内建，每步自动快照，`thread_id` 标识流程实例 |
| 人在环路 | 需要自己实现等待节点/任务表 | `interrupt()` / `Command(resume=)` 内建（ch48） |

> 📌 生产提示：从 Java 过来的读者最容易犯的错是把 LangGraph 当"更好的流程引擎"，把状态当"流程变量"少量使用。恰恰相反——**LangGraph 的核心是让状态成为图的中心**，节点只是状态的变换器。状态设计做不好，图一定乱。

**选型决策表**（把 43.2 的类比边界落成可执行的判断）：

| 你面对的流程 | 建议 | 理由 |
|---|---|---|
| 固定顺序 1~2 步，无恢复需求 | 链（ch40）或裸 SDK | 图的样板成本换不来收益 |
| 分支固定、状态是有限枚举、纯规则 | Java 侧状态机 | 留在你的技术栈里最便宜 |
| 分支由**模型输出**决定 | LangGraph | 模型输出不可枚举，需要运行时路由 + 校验兜底（ch45） |
| 需要"中途等人批准" | LangGraph（interrupt） | 人工任务 + 恢复语义内建 |
| 进程可能重启/会话可能换人接手 | LangGraph（checkpointer） | 状态在图上 + thread_id 续跑 |
| 长周期跨天/跨部门的审批链 | 工作流引擎，LangGraph 做子流程 | 可视化、催办、组织权限是工作流引擎的主场 |

一句话口径：**"控制流里有模型、有等待、有恢复"三者占其一，图开始回本；占其三，不用图是自虐。**

**Java 经验迁移地图**（全书第八部分的对照索引，各章展开）：

| 你在 Java 里的老朋友 | LangGraph 里的对应物 | 去哪章看 |
|---|---|---|
| Spring StateMachine 的 state/transition/guard | 节点 / 边 / 条件边路由函数 | ch43~45 |
| `@Retryable`（指数退避） | `RetryPolicy`（`add_node` 参数） | ch50 |
| Saga / 事务日志 | checkpointer 的检查点链 | ch47 |
| 流程实例 ID（processInstanceId） | `configurable.thread_id` | ch47 |
| BPMN 人工任务 / 审批流 | `interrupt()` + `Command(resume=)` | ch48 |
| 幂等消费（唯一业务键 + 去重表） | 副作用幂等账本（action_key） | ch48 |
| `CompletableFuture.allOf` + 结果合并 | 静态并行 + reducer / Send 扇出 | ch49 |
| Spring Retry 的 include 异常清单 | `retry_on` 参数 | ch50 |
| BPMN 子流程 | 子图（schema 对齐 / 桥接映射） | ch49 |

用法建议：学每一章前先看一眼对应行，把新 API 挂到已有心智模型上；面试时这张表就是"Java 转 AI"的话术骨架（part12 展开）。

## 43.4 最小完整示例

**EX-43-01 | 示例代码/ch43_graph_intro/ex_43_01_chain_vs_graph.py（完整可运行）**

```python
# EX-43-01 | 链式硬编码 vs 图编排：需求变更下的两种命运 | 运行: python3 示例代码/ch43_graph_intro/ex_43_01_chain_vs_graph.py
# （完整源码见示例目录，此处展示核心骨架）
def pipeline_v1(text: str) -> str:
    """一条直线：normalize → classify → 按类别分发（控制流焊死在代码里）。"""
    cleaned = normalize(text)
    category = classify(cleaned)
    handler = {"billing": handle_billing, "tech": handle_tech, "general": handle_general}
    return handler[category](cleaned)

def pipeline_v2(text: str, *, is_vip: bool = False) -> str:
    cleaned = normalize(text)
    if "身份证" in cleaned or "银行卡" in cleaned:      # 新规则 1：敏感工单先审
        return f"[人工审核] 拦截：{text}"
    if is_vip:                                          # 新规则 2：VIP 加急
        return pipeline_v1(cleaned) + "（VIP 加急）"
    return pipeline_v1(cleaned)                         # 新规则 3 要再加 if……
```

```text
# 真实运行输出（Python 3.14.7，纯标准库）
== v1：硬编码链 ==
             '我的 发票 抬头开错了' -> [账务通道] 处理：我的 发票 抬头开错了
            'App 一直 报错 闪退' -> [技术通道] 处理：app 一直 报错 闪退
         '请查一下我的 银行卡 绑定信息' -> [通用通道] 处理：请查一下我的 银行卡 绑定信息
== v2：规则长进代码里 ==
            敏感工单 -> [人工审核] 拦截：请查一下我的 银行卡 绑定信息
      VIP 报错工单 -> [技术通道] 处理：app 一直 报错 闪退（VIP 加急）
结论：v2 里'业务函数'没变，变的是控制流——但控制流改一次，就要动一次管线代码。
把控制流抽出来变成'图'，节点只管业务，连线只管流转，这就是 LangGraph 的出发点。
```

**EX-43-02 | 示例代码/ch43_graph_intro/ex_43_02_first_graph_preview.py（完整可运行）**

同一套规则搬进 LangGraph：`sensitive_gate` 一个节点做闸门，条件边按闸门结果分流。核心三行：

```python
g.add_edge(START, "sensitive_gate")
g.add_conditional_edges("sensitive_gate", route_by_gate,
                        {"manual": "manual_review", "auto": "auto_pipeline"})
g.add_edge("manual_review", END); g.add_edge("auto_pipeline", END)
```

```text
# 真实运行输出（langgraph 1.2.16）
   '发票抬头开错了' -> route=auto   trace=['gate:放行', 'auto:发票抬头开错了…']
   '请查我的银行卡' -> route=manual trace=['gate:敏感拦截', 'manual_review:请查我的银行卡…']
图结构节点： ['__start__', 'sensitive_gate', 'manual_review', 'auto_pipeline', '__end__']
```

注意 `trace` 字段：它是一个带"追加合并"reducer 的状态字段（ch44 展开），每经过一个节点就自动记录一笔——**审计日志不再需要横穿三层方法**，因为它就是图状态的一部分。

## 43.5 逐段解释

1. **`StateGraph(TicketState)`**：图的构造参数就是状态 schema（TypedDict）。这一行决定了"所有节点共享的那块看板长什么样"，是整张图最重要的设计决策。
2. **`add_node("名字", 函数)`**：节点是"输入状态 → 部分更新"的纯函数。注意返回的是 `dict`（只写自己关心的字段），不是新状态全量。
3. **`add_conditional_edges`**：条件边 = 路由函数 + 路由映射。路由函数读状态返回"路由值"，`path_map` 把路由值翻译成节点名——流转规则集中在这一处，业务函数里没有 `if`。
4. **`START`/`END`**：特殊的出入口哨兵节点，编译后真实存在于节点表里（输出里的 `__start__`/`__end__`），测试时可以用它们断言"图还没跑完/已经跑完"。

## 43.6 安装 / 文件位置 / 运行命令

```bash
# 安装（仓库 requirements.txt 已锁定，无需重复安装）
pip install langgraph==1.2.16        # 本教材实测版本
# 文件位置
示例代码/ch43_graph_intro/ex_43_01_chain_vs_graph.py
示例代码/ch43_graph_intro/ex_43_02_first_graph_preview.py
# 运行
python3 示例代码/ch43_graph_intro/ex_43_01_chain_vs_graph.py
python3 示例代码/ch43_graph_intro/ex_43_02_first_graph_preview.py
```

## 43.7 常见错误与排查

**① `InvalidUpdateError: Expected dict, got [Send(...)]`**：在**节点函数**里返回了 `Send` 列表。`Send` 只能从条件边函数返回，或包在 `Command(goto=[...])` 里由节点返回（ch45 实测）。修复：把扇出逻辑挪到条件边，或改返回 `Command(goto=...)`。

**② 图跑了但状态里没有输入的字段（KeyError）**：`StateGraph(dict)` 这种"无 schema"用法合法，但输入的键不会被建立为通道——节点拿到的是空状态。修复：永远给图定义显式 TypedDict schema（EX-43-02 的 `TicketState`）。

**③ `ValueError: Checkpointer requires one or more of the following 'configurable' keys: thread_id, ...`**：编译时传了 checkpointer，invoke 时却没给 `configurable.thread_id`（ch47 实测报错全文）。持久化与 thread_id 成对出现，ch47 展开。

## 43.8 企业场景中的使用方式

Spring 团队落地 LangGraph 的典型组合：**Spring Boot 业务服务保持不动，Python 图服务通过 REST/SSE 对接**（ch57 的架构边界）。工单分类这类"分支固定的流程"，用 Spring 的规则引擎也行；但当流程里出现"模型判断 + 工具取证 + 人工审批 + 可恢复"的组合时，LangGraph 的 checkpointer/interrupt 是自研状态机几周都未必踩平的坑。项目二（p2_log_triage）就是这样一个完整微缩案例：排障图由 Python 编排，未来通过 HTTP 供 Java 值班台调用。

**三条集成纪律**（第一部分就立好，后面所有章受益）：①**边界用数据不用对象**——Java 侧传 JSON，Python 侧的图状态在入口处从 JSON 构造、出口处序列化回 JSON，Pydantic 模型做边界校验（ch16），不把 Python 对象泄漏进接口；②**故障域隔离**——Python 图服务挂了，Java 侧降级为"人工排障流程"，图服务重启后凭 thread_id 续跑（ch47），SLO 分开算；③**一次编排一个 thread**——Java 发起的每次业务请求带唯一工单号，Python 侧禁止"跨请求复用 thread"，否则 ch47 的历史串台会在业务层表现为"张冠李戴的回答"。

## 43.9 练习与参考答案

**基础 1**：用一句话说出"链"和"图"的本质区别。**基础 2**：EX-43-01 的 v2 里，哪些代码属于业务函数、哪些属于控制流？各举两例。
**代码 1**：给 EX-43-02 再加一条规则："账务工单夜间只受理不执行"，只允许改条件边和路由函数，不许动 `sensitive_gate`/`auto_pipeline`。
**代码 2**：把 `trace` 字段的 reducer 去掉会发生什么？写出你的预测，再运行验证。
**调试题**：同事把 `Send('worker', x)` 直接从节点函数 return 了，报 `InvalidUpdateError`。给出两种修法。

### 参考答案

基础 1：链的控制流在写代码时焊死且不可持久化；图的控制流是声明式拓扑，状态在图上、可持久化、可恢复。基础 2：业务函数如 `normalize`/`classify`；控制流如 `pipeline_v2` 的两个 `if` 与调用顺序。代码 1：路由函数改为读状态里的 `is_night` 与 `category`，`path_map` 增加 `"billing_night": "billing_readonly"` 分支即可，业务函数零改动。代码 2：`trace` 变成普通字段（覆盖语义），最终只剩最后一个节点写入的一条记录，审计历史丢失——这正是 ch44 要展开的"覆盖 vs 追加"。调试题：修法一，改由条件边函数返回 `[Send('worker', x) for x in items]`；修法二，节点返回 `Command(goto=[Send('worker', x) ...])`（1.2.16 实测两者均可）。

## 43.10 自测检查表

- [ ] 我能用一个需求变更故事解释"控制流写死"的代价；
- [ ] 我能说出 LangGraph 与 Spring StateMachine 的四个不等价点（状态载体/并发写入/持久化/人在环路）；
- [ ] 我知道节点函数返回的是"部分更新"而不是全量状态；
- [ ] 我知道条件边 = 路由函数 + 路由映射，且它能替代业务代码里的 if/elif；
- [ ] 我能判断一个需求"该用链还是该用图"并给出理由。

## 43.11 面试追问

1. **[模拟题] 你们项目为什么选 LangGraph 而不是 Spring StateMachine/Flowable？** 答：先说共性（拓扑思维一致），再说决定性差异——AI 流程的状态是任意结构（消息列表、证据列表）而非有限状态枚举；需要每步自动快照恢复（checkpointer 内建）与人工审批（interrupt 内建）；最后补充：纯规则分支、无恢复需求的流程，留在 Java 侧用状态机更合适。
2. **[模拟题] 图让架构变复杂了，你怎么说服团队？** 答：用"三次需求变更"的成本曲线说话——控制流变更的 diff 从"横穿业务层"缩小到"只改连线"；再给出演示：EX-43-01 v2 的第 4 条规则改动行数 vs EX-43-02 加一条 path_map 的行数。
3. **[模拟题] LangGraph 和工作流引擎（Flowable）会互相取代吗？** 答：不会。Flowable 擅长长周期、多人工任务、需要 BPMN 可视化的业务流程；LangGraph 擅长"单次会话内"的 AI 编排。两者在企业里通常是父子关系：工作流引擎发起一个 AI 子流程。

---

# 第 44 章 最小两节点图：State、Node、Edge 与 reducer

> **本章目标**：手写并跑通最小两节点图，彻底搞懂"状态字段被谁、以什么规则更新"。
> **前置知识**：ch11（TypedDict/Annotated）、ch43。
> **学完你能做什么**：独立写出含 reducer 的状态 schema；精确说出 `add_messages` 的"覆盖 vs 追加 vs 同 id 替换"三态语义；预判并行写入冲突。

## 44.1 真实问题引入：一个字段，两个节点，谁说了算

承接 43.1 的工单系统：`detect` 节点检测风险词，`act` 节点根据检测结果处理。Java 工程师老张写下两个节点函数，各自往 `findings` 字段里写东西，然后发现：`act` 里有时读得到 `detect` 的结果，有时读不到；两个节点同时写的字段，有时剩下 A 有时剩下 B。他抱怨"框架有 bug"。其实 LangGraph 的更新规则完全确定——只是它的规则（**每步之后按字段的 reducer 归并部分更新**）和他默认想象的（"变量赋值"）不一样。本章把这套规则一次讲透。

## 44.2 一句话解释 + 生活类比 + 类比边界

**一句话解释**：LangGraph 的每个状态字段都是一个"通道（channel）"——不带 reducer 的通道是**覆盖语义**（后写顶掉先写），带 reducer 的通道按你声明的合并函数归并（最常见的是追加）。

**生活类比**：覆盖通道像一块**白板**——谁最后擦了写，板上就是谁的；reducer 通道像一张**签到表**——每人来了添一行，表只会变长（合并规则由表的设计决定，你甚至可以设计成"去重签到"）。

> 💡 类比边界：
> 1. reducer 不是"并发锁"：它解决的是"同一超步内多份更新如何归并"的**数据**问题；并发**执行**的互斥是另一回事（LangGraph 按 Pregel 超步模型推进，见 ch49）；
> 2. `add_messages` 的追加不是简单的 `list.append`：它还负责类型包装（tuple/str → 对应 Message 类型）和**按消息 id 的 upsert**（同 id 替换，不产生重复）——这是它比手写 reducer 值钱的地方；
> 3. "部分更新"是返回值层面的概念：节点返回 `{"findings": [...]}` 只表达"我要更新这个字段"，不表达"整个新状态"；
> 4. 白板与签到表是**字段级**的：同一个状态里可以白板字段和签到表字段并存（EX-44-01 的 `text` 覆盖、`findings` 追加）——别把整个状态想象成同一种语义。

## 44.3 正式原理与准确术语

**State（状态）**：图级共享数据，schema 用 `TypedDict`（也可用 dataclass/Pydantic 模型）定义；每个字段是一个**通道（channel）**。

**Node（节点）**：函数 `(state) -> dict`（或返回 `Command`，见 ch48），返回值为**部分更新（partial update）**。1.2.16 的 `StateGraph.add_node` 签名（实测）：`add_node(node, action=None, *, defer=False, metadata=None, input_schema=None, retry_policy=None, cache_policy=None, error_handler=None, destinations=None, timeout=None, ...)`——其中 `retry_policy` 在 ch50 展开。

**Edge（边）**：`add_edge(A, B)` 无条件流转；`START`/`END` 来自 `langgraph.graph`，是特殊哨兵节点。

**Reducer（归并器）**：字段的合并函数 `(旧值, 新值) -> 合并值`，通过 `Annotated[类型, reducer]` 声明。**不声明 reducer = 覆盖语义**。

**`add_messages`**：`langgraph.graph` 提供的消息通道 reducer，三态语义（1.2.16 实测）：新 id → 追加（自动把 tuple/str 包装成对应 Message 类型）；已有 id → **按 id 替换**（消息级 upsert）；配合 RemoveMessage 还可删除（本书不展开，需要时查官方文档）。

**`MessagesState`**：`langgraph.graph` 内置的对话状态类，等价于自己写 `messages: Annotated[list[AnyMessage], add_messages]`——对话场景直接用它，少一行声明。

**Java 对照**：reducer 之于通道，就像 `ConcurrentLinkedQueue.addAll` 之于并发追加——把"多写者合并"从调用方挪到数据结构本身；区别是 LangGraph 的归并发生在**超步边界**，且合并策略完全由你声明（求和、去重、取最大都是合法 reducer）。

**状态设计六条军规**（44.8 展开背景，这里给清单）：

1. **每个字段先问三件事**：谁写它（哪些节点）、何时被读（哪个节点/条件边/路由函数）、生命周期（单次运行还是跨 invoke 持久）——答不出的字段删掉；
2. **追加型字段（日志/证据/轨迹）一律显式 reducer**：`Annotated[list, merge_lists]`，绝不裸 list——裸 list 的覆盖语义迟早吃掉你的审计记录；
3. **"当前值"字段（如 category/route）保持覆盖语义**：它们本来就表达"最新判断"，追加反而制造歧义；
4. **可序列化优先**：状态要被 checkpointer 序列化（ch47），config/audit 这类**对象引用放闭包**（ch51 的工厂注入），状态里只放数据；
5. **大对象不进状态**：全量日志进状态会让每个检查点都背一份拷贝——状态里放"解析后的记录列表"而非文件内容本身，原始数据用路径/ID 引用；
6. **给"结论"和"过程"分字段**：`conclusion` 是给人看的最终产出，`records/evidence` 是过程留痕——混在一起会让下游（和未来的你）分不清哪个是承诺。

**`add_messages` 内部做了什么**（比"追加"多干的三件事，1.2.16 实测行为）：①**类型包装**——`("user", "你好")` 变 `HumanMessage`，裸字符串按 user 处理；②**id 生成**——新消息没有 id 时自动补 UUID（这就是为什么 EX-44-02 B 实验"恰好"追加而不覆盖）；③**按 id upsert**——传入消息的 id 已存在时原位替换，位置不变、长度不变。三件事合起来解释了一个高频面试题："为什么模型重答后消息列表不翻倍？"——因为适配层复用了原消息的 id（ch46 的 `to_ai_message` 若透传 id 就有此效果）。

## 44.4 最小完整示例

**EX-44-01 | 示例代码/ch44_minimal_graph/ex_44_01_minimal_two_nodes.py（完整可运行）【主线示例 1：两节点】**

```python
# EX-44-01 | 最小两节点图（节选，完整源码见示例文件）
def merge_list(left: list[str] | None, right: list[str] | None) -> list[str]:
    """列表 reducer：(旧值, 新值) -> 合并值。"""
    return (left or []) + (right or [])

class RiskState(TypedDict):
    text: str                                    # 无 reducer：整体覆盖
    findings: Annotated[list[str], merge_list]   # 有 reducer：追加合并

def detect(state: RiskState) -> dict:
    findings = [w for w in ("身份证", "银行卡", "密码") if w in state["text"]]
    return {"findings": findings}                # 部分更新：只写 findings

def act(state: RiskState) -> dict:
    if state["findings"]:                        # 能读到 detect 已归并的结果
        return {"text": "已打码", "findings": ["act:转人工"]}
    return {"findings": ["act:正常放行"]}

g = StateGraph(RiskState)
g.add_node("detect", detect); g.add_node("act", act)
g.add_edge(START, "detect"); g.add_edge("detect", "act"); g.add_edge("act", END)
app = g.compile()
```

```text
# 真实运行输出（langgraph 1.2.16）
命中风险： {'text': '已打码', 'findings': ['身份证', 'act:转人工']}
无风险　： {'text': '今天天气不错', 'findings': ['act:正常放行']}

图结构节点： ['__start__', 'detect', 'act', '__end__']
```

**EX-44-02 | 示例代码/ch44_minimal_graph/ex_44_02_reducer_semantics.py（完整可运行）**

```text
# 真实运行输出（langgraph 1.2.16）
A 无 reducer　： ['a2'] ← a2 覆盖了 a1，'init' 和 'a1' 都丢了
B add_messages： [('m-1', '第一版回答'), ('m-2', '第二版回答')] ← 自动包装成 AIMessage 并追加
B' 同 id 更新　： [('m-1', '同 id 替换版')] ← 仍 1 条：id 相同即替换
C 去重 reducer： ['tool_call'] ← 合并策略由你定义
```

**EX-44-03 | 示例代码/ch44_minimal_graph/ex_44_03_messages_state.py（完整可运行）**

```text
# 真实运行输出（langgraph 1.2.16）
第一轮消息序列：
  HumanMessage 查一下订单
  AIMessage    收到：查一下订单
  AIMessage    （质检：当前 1 轮提问）
第二轮消息序列（注意：每次 invoke 都从输入重新开始，历史要靠 ch47 的 checkpointer）：
  HumanMessage 再查一个订单
  AIMessage    收到：再查一个订单
  AIMessage    （质检：当前 1 轮提问）
```

EX-44-03 的第二轮输出还揭示一个常见误解：**没有 checkpointer 时，第二次 invoke 不会记得第一次**——图状态只活在一次 invoke 里，"对话记忆"是 ch47 的 checkpointer 给的，不是 MessagesState 给的。

## 44.5 逐段解释

1. **`Annotated[list[str], merge_list]`**：`Annotated` 的第二个参数就是 reducer 函数对象。注意一个 Python 3.12+ 的坑（教材在 3.14.7 实测）：`from __future__ import annotations` 会让注解变成字符串，LangGraph 求值时按**模块全局名**解析 reducer——**在函数内定义的局部 reducer 名会 `NameError`**。原则：reducer 定义在模块顶层。
2. **覆盖语义的用途**：`text` 这类"当前值"字段就该覆盖；把所有字段都加追加 reducer 是新手常见过度设计。
3. **`invoke({"text": ..., "findings": []})`**：输入也走同一 schema——没给的字段用通道默认值（空列表/None），给了的字段作为初始值。
4. **节点间"通信"的唯一媒介是状态**：`act` 能知道 `detect` 的结论，是因为 `detect` 的更新已经归并进状态。两个节点之间没有函数调用关系——这就是"状态在图上"。

## 44.6 安装 / 文件位置 / 运行命令

```bash
pip install langgraph==1.2.16 langchain-core==1.6.12   # MessagesState 演示需要 langchain-core
python3 示例代码/ch44_minimal_graph/ex_44_01_minimal_two_nodes.py
python3 示例代码/ch44_minimal_graph/ex_44_02_reducer_semantics.py
python3 示例代码/ch44_minimal_graph/ex_44_03_messages_state.py
```

## 44.7 常见错误与排查

**① `InvalidUpdateError: At key 'out': Can receive only one value per step. Use an Annotated key to handle multiple values.`**（1.2.16 实测全文）：同一超步两个节点写了同一个**无 reducer** 字段。修复：给字段加 reducer（EX-49-01），或把写入挪到不同超步。

**② `ValueError: Channel 'findings' already exists with a different type`**：同一进程里两个图用了**同名字段但不同 reducer**。LangGraph 按字段名+归并类型注册通道。修复：复用同一个 reducer 对象（测试/test_ch47.py 的 `_tt_app` 就是这么写的），或改字段名。

**③ `NameError: name 'merge' is not defined`（无任何明显笔误时）**：reducer 定义在函数内部 + `from __future__ import annotations` 的组合（见 44.5 第 1 条）。修复：reducer 提到模块顶层。

**④ 想让模型节点"更新"某条历史消息，结果消息列表翻倍**：`add_messages` 按 **id** 判重——不传 id 的新 AIMessage 永远是追加。修复：复用要替换的那条消息的 `id`（EX-44-02 B' 实验）。

## 44.8 企业场景中的使用方式

Spring 侧对照：状态 schema 相当于流程上下文对象（`ProcessContext`），reducer 相当于多分支写同一上下文字段时的**归并策略**（`BeanUtils` 合并、Map merge function）。落地建议：AI 服务的图状态字段只放"流程必要"的数据（消息、证据、结论），别把整个请求 DTO 塞进去——状态每次都要快照（ch47），字段越肥，持久化与恢复越贵。

**schema 的演进纪律**（状态结构迟早要改，提前立规矩）：①新字段可加、旧字段慎删——检查点里存着旧 schema 的快照，删字段会让老 thread 恢复时报键缺失；②字段语义只许"追加式变更"（列表加新元素类型），不许"原地改义"——否则老快照恢复出来的是另一种含义；③大改 schema 时同步作废旧 thread（迁移脚本把旧状态转换成新结构或显式归档），不要指望新旧混跑；④schema 版本写进 `metadata`（invoke 时可通过 config 传入 metadata）或独立字段 `schema_version: int`，排障时一眼判断"这个 thread 是哪个版本的数据"。这四条对应 Java 侧"流程变量版本化"的全部老经验——事件溯源里改事件结构的坑，这里一个不少。

## 44.9 练习与参考答案

**基础 1**：不查资料写出"覆盖语义"与"追加语义"的字段声明各一行。**基础 2**：`add_messages` 收到 `("user", "你好")` 会发生什么（两件事）？
**代码 1**：给 EX-44-01 加第三个节点 `report`，向新字段 `report: str` 写入摘要，并让它只在 `findings` 非空时执行（提示：下一章的条件边；本章可以先无条件跑通）。
**代码 2**：写一个 `sum_int` reducer（求和），用两个并行节点分别写 2 和 3，断言最终为 5。
**调试题**：`act` 节点里读 `state["findings"]` 抛 KeyError。列出两个可能原因。

### 参考答案

基础 1：`x: str`（覆盖）；`xs: Annotated[list[str], lambda a, b: (a or []) + (b or [])]`（追加）。基础 2：包装成 `HumanMessage` 并追加进消息列表。代码 1：`report` 节点返回 `{"report": "...摘要..."}`；条件写法在 ch45 学完后回填。代码 2：

```python
def sum_int(a: int | None, b: int | None) -> int:
    return (a or 0) + (b or 0)

class S(TypedDict):
    v: Annotated[int, sum_int]
# 两个节点分别返回 {"v": 2} / {"v": 3}，invoke 后 state["v"] == 5
```

调试题：①输入没给该字段且无默认值（通道初始为空）；②字段名拼写不一致（schema 里 `findings`、节点返回 `finding`）。

## 44.10 自测检查表

- [ ] 我能默写最小两节点图的六个构件（State/Node×2/Edge×3）；
- [ ] 我能说出 reducer 的函数签名与调用时机（超步边界归并）；
- [ ] 我能解释 add_messages 的三态语义并预判一段代码的消息列表长度；
- [ ] 我知道没有 checkpointer 就没有跨 invoke 的记忆；
- [ ] 我见过 "Can receive only one value per step" 并知道三种修法。

## 44.11 面试追问

1. **[模拟题] LangGraph 的状态更新为什么设计成"部分更新 + reducer"，而不是直接赋值整个状态？** 答：三个理由——节点解耦（只声明自己关心的字段）、并行安全（同一超步多节点写入必须有确定的归并规则）、恢复友好（快照 + 部分更新天然支持重放）。对照 Java：这就是把"并发写共享变量的合并策略"从调用方约定挪到数据结构声明。
2. **[模拟题] `add_messages` 按 id 替换语义在生产里有什么用？** 答：消息级修订（模型重答同一轮）、流式场景的 chunk 合并、以及人工修正历史（配合 ch47 时间旅行）时精确替换某一条而不动其他消息。
3. **[模拟题] 什么时候不该用 LangGraph？** 答：一次请求内固定顺序的一两步（用 ch40 的 LCEL 甚至裸 SDK）；控制流完全由代码决定的批处理（直接写 Python）。图的收益从"需要恢复/人工介入/动态分支"开始出现。

---

# 第 45 章 条件路由与循环：让图"会拐弯、能打转"

> **本章目标**：掌握条件边、循环、终止条件与 recursion_limit，以及 Send 动态扇出。
> **前置知识**：ch44。
> **学完你能做什么**：写出带 path_map 的多路分支；实现"评审不通过就打回"的循环并保证它必然终止；解释 GraphRecursionError 的计数口径；用 Send 做运行时才确定份数的 Map-Reduce。

## 45.1 真实问题引入：会拐弯之后，图才真正替代 if/else

43 章的工单系统顺利上线后，运营提了个"小需求"：加急工单要走独立通道，而且**分账单类型**。原有的"闸门 + 两条路"图变成了"一个分类节点 + 四条业务路"。团队里开始出现两种写法：小王在 `sensitive_gate` 节点里又写起了 `if/elif`（控制流又长回业务里了）；小李用条件边把路由表集中到一处。更麻烦的需求在后面——"模型对分类没把握的工单，自动改写一遍再分类一次，最多三轮"。这是**循环**，而且必须有一个"最多三轮"的保险丝，否则一次模型抽风就是一次线上挂死。本章就把"拐弯"与"打转"一次讲清。

## 45.2 一句话解释 + 生活类比 + 类比边界

**一句话解释**：条件边是在某个节点跑完后，**读当前状态决定下一跳**的机制；循环就是一条指回上游的边，它是否继续完全由你的终止条件（也是一个条件边）决定。

**生活类比**：条件边像机场的**中转柜台**——你把登机牌（状态）递过去，柜员看一眼系统告诉你去 A8 还是 B2；循环像**体检流程里的"复检"**——报告不合格就回到上一科室，合格就走"结束"通道，但体检中心有硬性闭馆时间（recursion_limit），防止你在两个科室之间转一整天。

> 💡 类比边界：
> 1. `recursion_limit` 数的不是"循环次数"，是**超步（superstep）数**——一轮"执行所有就绪节点"记一步（45.3），所以自环图 `recursion_limit=5` 大约等于 5 次节点执行；
> 2. 条件边的路由函数应该**只读状态、快速返回**——在里面写副作用（调接口、写库）会让"路由"变得不可测试、不可重放；
> 3. 循环没有"while"语法：`draft → review`，`review` 后面的条件边返回 `"continue"` 映射回 `draft` 就是循环——图论上它只是普通的边；
> 4. Send 不是"异步 fire-and-forget"：扇出的每份任务都在超步屏障处汇合归并，发送方所在超步要**等所有份完成**才结束——它是"动态的静态并行"，不是消息队列。

## 45.3 正式原理与准确术语

**条件边（conditional edge）**：`add_conditional_edges(source, path, path_map=None)`（1.2.16 实测签名）。`path` 是路由函数：返回单个路由值（配合 `path_map` 映射）或直接返回节点名/节点名列表/`Send` 列表；`path_map` 缺失时路由值必须就是节点名。**路由值不在 path_map 里 → `KeyError`**（1.2.16 实测，`KeyError: 'general'`）——fail fast，测试里应该锁住这个行为。

**循环（loop）**：拓扑上指向祖先节点的边。**终止条件**是一个返回 `END`（或不再回到环上的节点）的条件边。

**递归限制（recursion_limit）**：invoke 配置项，默认 25，按超步计数。超限抛 `langgraph.errors.GraphRecursionError`，1.2.16 实测报错全文：

```text
Recursion limit of 5 reached without hitting a stop condition. You can increase the limit
by setting the `recursion_limit` config key.
For troubleshooting, visit: https://docs.langchain.com/oss/python/langgraph/errors/GRAPH_RECURSION_LIMIT
```

**Send API（动态扇出）**：条件边函数返回 `[Send("节点名", 每份的输入), ...]`，运行时把任意份数的任务推给目标节点，每份输入可以不同——份数由数据决定，这是它与 ch49"静态并行"的本质区别。1.2.16 实测 `Send(node, arg, *, timeout=None)`；也支持节点返回 `Command(goto=[Send(...)])`。**Map 节点收到的输入是 Send 的 `arg`，不是整张图状态**。

**Java 对照**：条件边 ↔ Spring StateMachine 的 `transition` guard + choice 伪状态；循环 ↔ "回退迁移"；recursion_limit ↔ 工作流引擎的死循环防护（Flowable 的流程实例超时）；Send ↔ `ExecutorService` 的动态任务提交——但 Send 的任务是图节点且结果自动归并回状态。

**Pregel 超步模型图解**（理解并行/循环/汇聚行为的钥匙，EX-45-03 实测验证）：

```text
超步 1            超步 2              超步 3
┌─────────┐      ┌─────────┐
│   hub   │ ───▶ │ score×N │ ───▶ （Send 扇出：N 份同超步并行）
└─────────┘      └────┬────┘
     │ 条件边返回       │ 全部完成后归并（reducer）→ 写快照
     │ [Send...]       ▼
     └────────▶  ┌──────────┐
                 │ combine  │   ← 超步屏障：等本超步所有任务完成才进入
                 └──────────┘
```

三条推论，每条都对应一个常见 bug：①同一超步的节点**看不到彼此的写入**（归并发生在超步末尾）——想"先写后读"必须连成两个超步；②循环的每一圈至少消耗一个超步——recursion_limit 数的就是这个；③汇聚节点必须有**且仅有**从分支来的入边，早到的直连边会让它和分支同超步执行、读到空结果（45.7③）。

## 45.4 最小完整示例

**EX-45-01 | 示例代码/ch45_conditional_routing/ex_45_01_conditional_route.py（完整可运行）【主线示例 2：条件分支】**

```python
# EX-45-01 | 条件路由（节选）：分类节点用 get_llm().chat_structured（Mock/Real 双模式）
g.add_edge(START, "classify")
g.add_conditional_edges("classify", route_by_category,
                        {"billing": "billing", "tech": "tech", "general": "general"})  # path_map
for leaf in ("billing", "tech", "general"):
    g.add_edge(leaf, END)
```

```text
# Mock 运行输出（控制流真实运行；分类值由 Mock 规则从输入 key=value 解析）
发票抬头开错了    -> trace=['classify:billing', 'billing:账务处理'] urgent=True
App        -> trace=['classify:tech', 'tech:技术排查'] urgent=False
你们几点上班     -> trace=['classify:general', 'general:通用应答'] urgent=False
```

**EX-45-02 | 示例代码/ch45_conditional_routing/ex_45_02_loop_and_recursion.py（完整可运行）**

```text
# 真实运行输出（langgraph 1.2.16）
A 循环轨迹： draft:v1 -> review:打回 -> draft:v2 -> review:打回 -> draft:v3 -> review:通过
B 熔断　　　： GraphRecursionError — Recursion limit of 5 reached without hitting a s …
（recursion_limit 按'超步 superstep'计数：本图 5 个超步 ≈ 5 次节点执行）
```

**EX-45-03 | 示例代码/ch45_conditional_routing/ex_45_03_send_fanout.py（完整可运行）**

```text
# 真实运行输出（langgraph 1.2.16）
scores = [2, 16, 7]
best   = 最高分 16（共 3 份）
第二次 ： [4] / 最高分 4（共 1 份）
```

第二次输入只有 1 篇文档，扇出份数自动变成 1——**拓扑不变，行为随数据伸缩**，这就是 Send 与"画死两条并行边"的区别。

## 45.5 逐段解释

1. **路由函数读什么**：只读已经归并进状态的字段（EX-45-01 里是 `state["category"]`）。分类字段由 `classify` 节点写入——**"判断"放节点里（可测），"分流"放条件边里（可改）**。
2. **循环的终止条件写在评审节点后面的条件边里**（EX-45-02 的 `should_continue`）：`passed` → `END`，否则 → `"draft"`。让"何时停"成为一个独立可测试的纯函数，是循环图可维护的关键。
3. **recursion_limit 是保险丝不是设计**：正经的循环必须有业务终止条件；recursion_limit 只在"终止条件写错了"时把事故降级为异常。生产上把它留在默认 25 即可，别靠调大它来"支持更多轮"。
4. **Send 的输入契约**：`score(inputs)` 收到的是 `{"doc": ...}`——所以 Map 节点的参数注解不要写整图 State 类型，写"单份任务"的类型（EX-45-03 的 `inputs: dict`），否则读字段时一头雾水。

**路由表设计规范**（把"会拐弯"变成可维护的资产）：

1. **路由值用业务词汇**（`"billing"`/`"approval"`），不用节点名做路由值再碰巧映射同名节点——前者改节点名不破坏路由表；
2. **path_map 与节点名单同步测试**：写一个元测试，遍历 path_map 的 values 断言都是已注册节点——重命名节点时立刻红；
3. **路由函数零副作用、零 IO**：只读状态、纯计算返回；需要"查库再决定"的逻辑放进上游节点（把决策结果写进状态），路由只消费决策；
4. **每个路由值至少一条测试路径**：45.9 的 `pytest.raises(KeyError)` 锁"未定义取值"，正常用例锁"每个取值都走到"——条件边的覆盖率和代码分支覆盖率同等重要。

**终止条件设计清单**（循环图上线前的最后一道检查）：

1. **业务上限**：轮次/步数字段有明确上限，且达到上限的**行为**是显式定义的（返回部分结果 + 打标 `hit_limit=true`，而不是抛异常）；
2. **进展可度量**：每轮循环都要朝终止条件前进（分数上升、候选减少），出现"零进展轮"时提前退出；
3. **边界输入**：第一轮就满足终止条件（0 次循环）与永远不满足（打满上限）都有测试；
4. **副作用审查**：循环体内每次执行的动作是否幂等？循环 × 重试 × 恢复重跑三者相乘，是副作用重复执行的三重放大器（ch48 的账本在此不可省）。

**四种常见路由模式**（把 45.5 的纪律套成可抄的形状）：

```python
# ① 分类路由：一进多出，path_map 全覆盖（EX-45-01）
def route_by_category(s): return s["category"]

# ② 闸门路由：不通过就出图（或去人工），通过才放行（项目二 assess 之后）
def route_after_assess(s):
    return "approval" if (s["assessment"]["can_conclude"]
                          and s["assessment"]["high_risk_actions"]) else "conclude"

# ③ 升级路由：按严重程度逐级分流，低级先走便宜通道
def route_by_severity(s):
    if s["risk_score"] >= 8: return "pager"
    if s["risk_score"] >= 4: return "ticket"
    return "log_only"

# ④ 扇出路由：返回 Send 列表，份数由数据决定（EX-45-03）
def fan_out(s): return [Send("score", {"doc": d}) for d in s["docs"]]
```

识别方法：需求里出现"根据 X 走不同流程"是①；"不满足就不准往下"是②；"越严重越要快/越要贵的人"是③；"每个元素都要处理一遍"是④。同一个图里这四种模式可以共存——项目二就同时有②和④的候选位（取证扇出）。

## 45.6 安装 / 文件位置 / 运行命令

```bash
python3 示例代码/ch45_conditional_routing/ex_45_01_conditional_route.py   # LLM_MODE=mock 默认
python3 示例代码/ch45_conditional_routing/ex_45_02_loop_and_recursion.py
python3 示例代码/ch45_conditional_routing/ex_45_03_send_fanout.py
```

## 45.7 常见错误与排查

**① `KeyError: 'general'`**（路由值不在 path_map）：分类节点输出了 path_map 没覆盖的取值。修复：path_map 补全枚举 + 给分类节点加默认值兜底；测试里锁住 `pytest.raises(KeyError)`。

**② `GraphRecursionError` 在"看起来没循环"的图里出现**：两个节点互相指（`a → b → a`）或条件边在两个分支间震荡。修复：给震荡路径加"尝试次数"状态字段并设上限（EX-45-02 的 `rounds` 思路），而不是调大 recursion_limit。

**③ Send 扇出后 `combine` 拿到空列表**：`combine` 与 Map 节点在**同一个超步**被调度（比如都从 START 出发）。修复：让 combine 只从 Map 节点有入边（EX-45-03 的 `g.add_edge("score", "combine")`），Pregel 超步屏障保证它等所有份到齐。

**④ `InvalidUpdateError: Expected dict, got [Send(...)]`**：见 43.7①——Send 只能从条件边或 `Command(goto=)` 出来。

## 45.8 企业场景中的使用方式

Spring 落地视角：条件路由表（path_map）建议做成**配置常量 + 单元测试断言全覆盖**（每个路由值都有测试走到），因为它是图里最常被需求改动的地方。循环图的"尝试上限"必须进监控埋点——`rounds` 字段（或 metadata）写入结构化日志，`rounds` 打满却没终止的 thread_id 就是 prompt 有问题的名单。项目二里，条件边只有一条（assess 之后要不要人工审批），这是刻意为之：**生产编排里每一条条件边都该有测试，边越少越稳**。

**模型分类 + 路由的校验回退**（EX-45-01 的真实模式补完）：真实模型可能输出 path_map 之外的分类值（幻觉或措辞漂移），此时 45.7① 的 `KeyError` 会把问题暴露出来——但生产不能靠崩。标准三段式：①schema 兜底——`chat_structured` 的枚举约束（`Literal["billing","tech","general"]`）让非法值在 Pydantic 层先报错；②校验失败重试一次——把 Pydantic 的 errors 拼回消息再请求（ch26/ch24 的回退循环）；③仍失败走 `general` 通道并打标 `classification_fallback=true`——错分的代价是"走了通用通道"，可控且可统计。这套兜底对 ch51 的测试地图意味着三类用例：合法值路由正确、非法值触发回退、回退有埋点可查。

## 45.9 练习与参考答案

**基础 1**：path_map 缺失时路由函数的返回值被当作什么？**基础 2**：recursion_limit=25 时，一个 `a→b→a` 的双节点环大约会执行多少次节点？
**代码 1**：把 EX-45-02 的终止条件从"第 3 轮通过"改成"分数 >= 80 通过"，`review` 节点给确定性分数（`60 + 15 * rounds`）。
**代码 2**：用 Send 实现"把 5 个 URL 各发一个 fetch 节点、结果合并成列表"的 Map-Reduce（fetch 用假函数返回 `f"内容 of {url}"`）。
**调试题**：同事报告"偶发 GraphRecursionError"，日志显示路由函数根据 `state["retry_count"]` 分流，但 `retry_count` 从不增长。说出根因。

### 参考答案

基础 1：直接当节点名使用（缺失即 KeyError）。基础 2：约 25 次（每超步 1~2 次，取决于环长）。代码 1：`review` 返回 `{"score": 60 + 15 * state["rounds"], "passed": 60 + 15 * state["rounds"] >= 80}`，第 2 轮 90 分通过。代码 2：

```python
def fan(s): return [Send("fetch", {"url": u}) for u in s["urls"]]
def fetch(x): return {"pages": [f"内容 of {x['url']}"]}   # pages 为追加 reducer
# START -> hub -> (conditional fan) -> fetch -> combine
```

调试题：路由函数读的 `retry_count` 没有任何节点去更新它（或更新写进了另一个字段名/被覆盖语义顶掉）——循环图的"计数器"必须是带追加或自增语义的字段，且确实有节点在环上写它。

## 45.10 自测检查表

- [ ] 我能不查资料写出 `add_conditional_edges` 三种 path 用法（返回值+映射 / 直接节点名 / Send 列表）；
- [ ] 我能把"打回重做"需求翻译成一条回边 + 一个终止条件函数；
- [ ] 我能说出 recursion_limit 的计数口径，并知道正道是业务终止条件；
- [ ] 我知道 Send 的份数与输入都在运行时决定，且 Map 节点收到的是单份 arg；
- [ ] 我能给"路由值不在映射里"写出 fail-fast 测试。

## 45.11 面试追问

1. **[模拟题] 循环 + 大模型，最常见的生产事故是什么？** 答：终止条件依赖模型"自我声明完成"（模型说好了才算好）——模型抽风就死循环。对策：轮次上限（业务字段，非 recursion_limit）+ 每轮产出落状态可回放 + 对"打满上限"的 thread 告警。
2. **[模拟题] Send 和"画多条并行边"怎么选？** 答：份数/目标编译期已知 → 静态并行（ch49，代码更少）；份数由数据决定（每个文件、每个 service）→ Send。两者都要求目标字段有 reducer。
3. **[模拟题] recursion_limit 应该设多大？** 答：默认 25 覆盖绝大多数编排；按"最长合法路径的节点数 × 2"心算校验即可。调大它来容纳失控循环是把 bug 配置化。

---

# 第 46 章 工具调用循环：模型节点与工具节点分离

> **本章目标**：在图里实现完整的"模型要调工具 → 程序执行 → 结果回传 → 模型总结"循环。
> **前置知识**：ch24（工具调用闭环）、ch44（MessagesState）。
> **学完你能做什么**：写出 agent/tools 双节点 + 条件边的标准结构；把全书统一的 ChatResult 适配成 AIMessage；解释消息状态每轮如何演进；知道 ToolNode 替你做了什么。

## 46.1 真实问题引入：为什么"再问一次模型"不是一个 if

ch24 已经手写过一次工具循环：`while result.has_tool_calls` 的 while 循环。放进真实系统，老张的 while 循环遇到了三件事：循环跑到第 9 轮模型还在要工具（没有保险丝）；想给"每次工具执行"记审计日志，得在循环体里再加代码；进程重启后循环从第 1 轮重来。**把循环画成图**（agent ↔ tools 两个节点来回连边），这三件事分别变成 recursion_limit（ch45）、tools 节点一个切面（本章）、checkpointer（ch47）——控制流的横切需求全部有落点。这就是"工具调用循环要上图"的完整理由。

## 46.2 一句话解释 + 生活类比 + 类比边界

**一句话解释**：工具循环图 = `agent` 节点（问模型"下一步调什么工具"）+ `tools` 节点（真的执行）+ 一条 `tools → agent` 的回边 + 一条"没有工具调用了就去 END"的条件边。

**生活类比**：医生（模型）开检查单（tool_calls）→ 护士站（ToolNode）执行检查把报告放回病历（消息状态）→ 医生看报告决定再开单还是出诊断。**病历是共享状态**：医生不直接跟护士站喊话，一切凭病历上的记录说话。

> 💡 类比边界：
> 1. ToolNode 不是模型：它是"执行者"，拿真函数跑，与 Mock/Real 无关——所以整图在 Mock 下确定可复现（本书红线）；
> 2. `bind_tools` 在本教材 Mock 模式下不存在"真绑定"：MockLLM 不看 tools 参数（它由脚本/规则决定调什么）——我们演示的是**接口契约**（AIMessage.tool_calls 的形态），真实模式下 `ChatOpenAI.bind_tools(tools)` 生成同样的消息形态（ch24 已实测）；
> 3. 循环的终点不是"模型说完了"这么简单：脚本耗尽/递归上限/工具异常都是合法出口，生产必须每一个都有处理；
> 4. "模型决定调什么工具"不等于"模型有权执行"：决策权（选工具）与执行权（真的跑）在架构上分离——执行权在 tools 节点，而 tools 节点受白名单与审批约束（项目二把这一层做成了独立节点）。

## 46.3 正式原理与准确术语

**agent 节点**：调用 LLM 的节点。输入消息状态，输出 `{"messages": [AIMessage(...)]}`——若模型要调工具，AIMessage 带 `tool_calls=[{name, args, id, type}]`（langchain-core 1.x 的 dict 形态，实测可用）。

**tools 节点**：`langgraph.prebuilt.ToolNode(tools)`，1.2.16 实测签名 `ToolNode(tools, *, name='tools', tags=None, handle_tool_errors=..., messages_key='messages', ...)`。它读消息状态里最后一条 AIMessage 的 tool_calls，逐个执行同名工具，为每个调用产出一条 `ToolMessage(content=结果, tool_call_id=...)`。工具就是普通 Python 函数（配 `@tool` 得到 schema 校验，见 ch39）。

**条件边 `route_after_agent`**：最后一条消息有 `tool_calls` → `"tools"`；否则 → `END`。

**消息状态演进（Mock 实测序列）**：`Human → AIMessage(tool_calls) → ToolMessage → AIMessage(tool_calls) → ToolMessage → AIMessage(最终回答)`——EX-46-01 输出逐条可见。

图解这轮循环（谁写哪条消息、控制流在哪拐弯）：

```text
            ┌────────────────────────────────────────────┐
            │              MessagesState（消息通道，add_messages 追加）       │
            └────────────────────────────────────────────┘
   invoke 输入        agent 节点写          ToolNode 写         agent 节点写
      │                  │                    │                   │
      ▼                  ▼                    ▼                   ▼
 [HumanMessage] → [AIMessage(tool_calls)] → [ToolMessage] → [AIMessage(最终)]
                          │                    ▲                 │
                  有 tool_calls                │            无 tool_calls
                          ▼                    │                 ▼
                     ┌─条件边─┐          tools→agent 回边         END
                     ▼        ▼
                  "tools"    END
```

**agent 节点的系统提示词设计**（真实模式下决定循环质量的第三根杠杆，前两根是工具描述与 schema）：①写清"你只能用下列工具收集证据，收集够了再回答"——工具选择策略显式化；②写明"禁止编造查询结果"——配合 ToolMessage 的真实回传，幻觉无处落笔；③限制轮次预期（"通常 1~3 次调用足够"）——与业务保险丝（46.9 代码 2）双保险。Mock 模式下这些提示词不生效（Mock 不读语义），但**保留它们**：LLM_MODE=real 时同一张图、同一份 prompt 直接升级，这是双模式架构的核心收益。

**状态字段的扩展**：真实系统的 agent 状态不止 `messages`——`tool_rounds`（轮次保险丝，46.9）、`evidence`（结构化证据，供审批与审计）、`budget`（token/成本预算，ch27 的方法）。扩展方式是继承：`class AgentState(MessagesState, total=False):` 加字段——`total=False` 让新字段可不提供初始值（`MessagesState` 自身只有 messages 一个字段）。

**Mock 驱动工具循环的两种模式**（`示例代码/公共/llm_client.py` 的既有能力，EX-46-01 用了前者）：

1. **脚本模式**（`get_llm(script=[...])`）：第 1 次调用返回条目 1、第 2 次返回条目 2……游标耗尽抛 `RuntimeError`。适合精确编排"模型第几轮要什么"，测试断言可以数调用次数（`len(llm.calls) == 3`）。注意：llm 实例必须跨节点复用（工厂闭包持有），每次 `get_llm()` 都是新实例、游标会归零——EX-46-01 把 llm 放进 `make_agent_node` 的闭包正是为此。
2. **规则触发模式**（脚本留空）：最后一条 user 消息含 `USE_TOOL:工具名 key=value ...` 时，Mock 解析出对应的工具调用请求；工具结果回传后（最后一条是 tool 消息），Mock 输出"整合工具结果"的确定性回答并结束循环。适合演示**单轮**工具循环的接口契约——不用写剧本，输入即剧本。

**工具结果的格式纪律**（决定模型下一轮质量的隐藏变量）：①返回 JSON 字符串而不是 Python 对象的 `str()`——真实 API 里工具结果就是文本（ch24），JSON 对模型最友好；②控制长度——EX-46-01 的 Mock 会把工具结果截到 60 字符整合，真实工具查询也应 LIMIT + 字段裁剪（项目二的 `limit=10`）；③失败要"可读地失败"——`{"error": "超时"}` 优于抛裸异常，模型能基于失败信息决定换工具还是放弃。

**Java 对照**：agent 节点 ↔ 领域服务里的"决策端点"（调外部模型 API），tools 节点 ↔ `@ReadOperation` 的运维查询端点，回边 ↔ 决策-执行循环。不同之处：这里的"执行结果回传给决策者"是**消息层**的（ToolMessage 拼回消息列表），不是方法返回值——这让每一步都可快照、可恢复。

## 46.4 最小完整示例

**EX-46-01 | 示例代码/ch46_tool_loop/ex_46_01_tool_loop.py（完整可运行）【主线示例 3：工具循环】**

```python
# EX-46-01 | 工具循环（节选）：适配层 + 组图
def to_ai_message(result: ChatResult) -> AIMessage:
    """全书统一的 ChatResult → LangChain 消息（bind_tools 在真实模型上的产物同构）。"""
    return AIMessage(content=result.content,
                     tool_calls=[{"name": tc.name, "args": tc.arguments,
                                  "id": tc.id, "type": "tool_call"} for tc in result.tool_calls])

def make_agent_node(llm):
    def agent(state: MessagesState) -> dict:
        r = llm.chat(to_openai_style(state["messages"]))   # Mock/Real 统一入口
        return {"messages": [to_ai_message(r)]}
    return agent

g = StateGraph(MessagesState)
g.add_node("agent", make_agent_node(llm))
g.add_node("tools", ToolNode(TOOLS))          # 工具节点：执行真函数
g.add_edge(START, "agent")
g.add_conditional_edges("agent", route_after_agent, {"tools": "tools", END: END})
g.add_edge("tools", "agent")                  # 工具结果回给模型 → 循环
```

```text
# Mock 运行输出（脚本驱动 2 轮工具调用；控制流真实运行）
消息状态演进（6 条）：
  1. HumanMessage ORD-1001 想退款，能退吗？
  2. AIMessage    <空，发起工具调用>
     └─ 请求工具 query_order_status args={'order_id': 'ORD-1001'}
  3. ToolMessage  {"order_id": "ORD-1001", "status": "paid", "
     └─ 工具结果回传（tool_call_id=call_001）
  4. AIMessage    <空，发起工具调用>
     └─ 请求工具 query_refund_policy args={'order_type': 'physical'}
  5. ToolMessage  {"order_type": "physical", "policy": "7 天无理由
     └─ 工具结果回传（tool_call_id=call_002）
  6. AIMessage    订单 ORD-1001 已支付；按政策支持 7 天无理由退款，可直接申请。
```

两个工具函数 `query_order_status`/`query_refund_policy` 是真函数（离线确定），`ToolNode` 拿到模型请求后真实执行——**"模型决定"与"程序执行"两条线在 Mock 下同样成立**。

## 46.5 逐段解释

1. **适配层 `to_openai_style`/`to_ai_message`**：LangChain 消息 ↔ 全书统一消息格式的双向翻译。没有真实 API Key 不影响学控制流——真实模式下只需把 `make_agent_node` 里的 `llm.chat` 换成 `ChatOpenAI(...).bind_tools(TOOLS)` 的调用，消息形态一致。
2. **`make_agent_node(llm)` 依赖注入**：llm 从外面传进来（脚本 Mock 或 `get_llm()`），测试时注入脚本化 Mock（ch51），这正是项目二 hypothesize 节点的同一套路。
3. **条件边返回 `"tools"`/`END` 直接当节点名**：`route_after_agent` 返回值与节点名重合，无需 path_map——两种写法都实测可用，选一种团队统一的。
4. **回边 `tools → agent` 就是循环**：ch45 的全部纪律（终止条件、保险丝）在这里继续生效——recursion_limit 默认 25 就是"模型最多连续要 25 轮工具"的硬上限。
5. **调试这个循环的最短路径**：把 `invoke` 换成 `stream(stream_mode="updates")` 跑一遍——每一帧的键就是 agent/tools 的交替节奏，"模型第几轮要了什么工具、工具回了什么"一目了然；再配合 `llm.calls`（MockLLM 记录每次收到的完整消息快照，test_ch46 用它断言 `len(llm.calls) == 3`），模型视角与图视角的执行史就齐了。两个视角合起来，能回答工具循环排障的三大问题：模型没调对工具？工具没返回对结果？还是循环没按预期收敛？

## 46.6 安装 / 文件位置 / 运行命令

```bash
pip install langgraph==1.2.16 langchain-core==1.6.12
python3 示例代码/ch46_tool_loop/ex_46_01_tool_loop.py     # LLM_MODE=mock 默认离线
```

## 46.7 常见错误与排查

**① `langgraph.errors.InvalidUpdateError`：ToolMessage 的 tool_call_id 与 AIMessage 对不上**：手工构造消息时复制错了 id。修复：`to_ai_message` 里保留 `tc.id` 原样透传，ToolNode 按 id 配对回传。

**② 脚本耗尽 `RuntimeError: ... script 已耗尽 ...`**（Mock）：脚本条数少于循环轮数。这是 MockLLM 的**设计行为**（绝不硬编造第 N+1 轮回答）。修复：按预期轮数补脚本条目——这也逼你想清楚"模型到底该调几轮工具"。

**③ 模型每轮都重复要同一个工具**：ToolMessage 的 content 写成了非文本对象或丢了结果，模型"没看见"结果。修复：工具返回 JSON 字符串（EX-46-01 的做法），并确认 `ToolMessage(tool_call_id=...)` 挂对 id。

**④ 工具抛异常直接炸图**：ToolNode 的 `handle_tool_errors` 参数（1.2.16 实测存在）可配置把异常转成文本回传给模型；或学 ch50 的"错误即数据"。生产推荐后者：异常也是证据。

## 46.8 企业场景中的使用方式

Spring 集成视角：tools 通常就是**对 Java 服务的只读查询**（HTTP 工具封装，ch56 展开）。纪律：①工具只给"查"，不给"改"——改操作必须离开这个循环走 ch48 的审批节点；②每个工具的耗时/失败率打点（tools 节点天然是埋点位置）；③ToolNode 执行工具与模型决策分离后，"模型一次都没调对工具"和"工具本身故障"可以分开归因——EX-46-01 的消息序列就是归因的时间线。项目二的 `query_tools` 节点没有用 ToolNode 而是手工白名单执行，因为取证计划需要**先审查后执行**（先落 plan 再跑），这个变体在项目二 README 有完整对照。

**agent 图的三种部署形态**（决定"循环"活在哪里）：

1. **请求内循环（本书全部示例）**：一次 HTTP 请求里跑完整张图，循环在单次 invoke 内完成——实现简单，但循环期间占着连接，循环长会撞超时（ch15 三件套）；
2. **异步任务化**：请求只做"受理"（返回 thread_id + 任务号），图跑在后台 worker（FastAPI BackgroundTasks 或任务队列），前端轮询 `get_state` 或订阅 SSE——工具循环长（多轮取数）时的标配；
3. **分步推进**：每次请求推进一步（利用检查点续跑语义），前端像翻页一样驱动——特殊交互（逐步审批的向导）用，常规不用。

选型判断：循环轮数 ≤3 且总时长 <10s 用形态 1；轮数不可控或涉及慢工具用形态 2；需要"人看着每一步"的强交互才用形态 3。形态 2 是 ch17 后台任务 + ch47 检查点的组合拳，也是项目二 CLI 之外的服务化路线。

## 46.9 练习与参考答案

**基础 1**：说出工具循环图的四个构件与两条关键边。**基础 2**：消息状态演进序列里，第 3 条消息为什么是 ToolMessage 而不是 AIMessage？
**代码 1**：给 EX-46-01 增加第三个工具 `query_order_logistics(order_id)`，并让脚本模式多走一轮。
**代码 2**：实现"最多 3 轮工具调用"的业务保险丝：状态里加 `tool_rounds`（自增 reducer），route 函数在 `tool_rounds >= 3` 时强制去 `END`。
**调试题**：模型第二轮的请求里 `tool_calls` 为空、content 也是空——查消息序列发现问题出在第一轮。说出两个可能根因。

### 参考答案

基础 1：agent 节点、tools 节点、`agent →(条件)→ tools/END` 条件边、`tools → agent` 回边。基础 2：它由 ToolNode 生成，是"工具执行结果"的载体，与发起调用的 AIMessage 通过 tool_call_id 配对。代码 1：脚本追加 `{"tool_calls": [{"id": "call_003", "name": "query_order_logistics", "arguments": {"order_id": "ORD-1001"}}]}`，最终总结条目前移。代码 2：

```python
class AgentState(MessagesState, total=False):
    tool_rounds: Annotated[int, lambda a, b: (a or 0) + (b or 0)]
# tools 节点返回 {"tool_rounds": 1}；route 改为：
def route(s):
    if s.get("tool_rounds", 0) >= 3: return END
    return "tools" if getattr(s["messages"][-1], "tool_calls", None) else END
```

调试题：①第一轮工具返回的 ToolMessage content 为空（工具函数没返回值/返回 None 被 str 化），模型无信息可总结；②第一轮 AIMessage 的 tool_call_id 与 ToolMessage 不匹配，模型上下文里"工具还没回话"。

## 46.10 自测检查表

- [ ] 我能默写 agent/tools 双节点组图并解释每条边；
- [ ] 我能把 ChatResult 适配成带 tool_calls 的 AIMessage，说清四个键；
- [ ] 我能逐条读出 2 轮工具循环的消息序列并解释每条是谁写的；
- [ ] 我知道 ToolNode 的三个关键参数（name/messages_key/handle_tool_errors）；
- [ ] 我知道"模型决定"与"程序执行"分离对测试和审计的价值。

## 46.11 面试追问

1. **[模拟题] create_agent（ch42）一步就建好了 agent，为什么还要手写工具循环图？** 答：create_agent 适合"标准 agent loop"；手写图的价值在于**控制流可定制**——比如在 tools 前插审批节点、在 agent 后加证据评估、给不同工具不同的重试策略。企业里常见路径：先 create_agent，出现定制控制流需求时展开成图（两者状态结构兼容，迁移平滑）。
2. **[模拟题] 工具循环怎么防"模型刷工具"？** 答：三层——recursion_limit 硬保险丝；业务层轮次计数（`tool_rounds` 字段）触发提前收尾并返回"已查到的部分结果"；工具侧限流（ch15 的幂等与退避思想同样适用于工具执行）。
3. **[模拟题] ToolMessage 为什么必须带 tool_call_id？** 答：一轮请求可以并行发多个工具调用（parallel tool calls），id 是模型把"结果"对回"请求"的唯一依据；错配会让模型读到错位的上下文——这是 agent 输出错乱的经典来源。

---

# 第 47 章 持久化：checkpointer、thread_id 与时间旅行

> **本章目标**：让图"记得"每个会话，并能跨进程恢复、回到历史任意一步。
> **前置知识**：ch44（reducer）、ch46（工具循环）。
> **学完你能做什么**：用 InMemorySaver 实现多轮记忆与 thread 隔离；用 SqliteSaver 做到"进程重启会话不丢"；用 `get_state`/`get_state_history` 排查执行轨迹；用时间旅行重放/分叉历史。

## 47.1 真实问题引入：客服会话为什么换个人也能接

44.4 的最后留了个钩子：第二次 invoke 不记得第一次。老张的客服系统因此出了事故——用户说"我刚才说过的那个订单"，AI 答"您还没说过任何订单"。修复方案不是把历史拼进输入（那是 ch27 的上下文管理，治标），而是给图配**检查点（checkpoint）**：每跑一步，把整个状态快照存下来，用 `thread_id`（= 流程实例 ID）索引。下一次 invoke 带着同一个 thread_id 来，图从上次的快照继续。更进一步：把检查点放到 SQLite/Postgres 里，进程重启、甚至换一台机器，会话照样无缝接上——这正是值班系统"换人接手工单"的基础设施。

## 47.2 一句话解释 + 生活类比 + 类比边界

**一句话解释**：checkpointer 让图在**每个超步之后**自动保存状态快照；`thread_id` 是会话主键；`get_state`/`get_state_history` 是查询接口，历史快照还能拿来重放（时间旅行）。

**生活类比**：电子游戏的**存档系统**——thread_id 是存档槽位，每过一关自动存档；`get_state` 读当前进度，`get_state_history` 翻存档列表，时间旅行就是"读旧档接着玩"（甚至可以读旧档换个打法，产生新分支）。

> 💡 类比边界：
> 1. 检查点存的是**图状态**，不是模型侧的对话：模型服务本身无状态（ch27），"记忆"完全由你的应用层（这里就是 checkpointer）负责；
> 2. InMemorySaver 的"持久"只到进程退出为止——它是**会话内存**不是存储；生产要跨进程/跨副本，用 SqliteSaver/PostgresSaver；
> 3. 时间旅行不修改历史：旧检查点是不可变的，"分叉"产生的是新分支，`get_state` 的"现在"指向新分支——像 git checkout 新分支，旧 commit 还在；
> 4. checkpointer 保存的是"执行到某超步时的**全部**状态"，不是 diff——恢复是整体读档，不是逐条重放事件；所以状态越大恢复越慢（呼应 44.8 的字段瘦身）。

一句话总结持久化的心智模型：**把图当成一个带自动存档的游戏引擎——compile 是装载引擎，checkpointer 是存档卡，thread_id 是存档槽，get_state 是读档，时间旅行是读旧档，interrupt 是剧情分支处的强制存档。** 后面两章的审批与恢复，全部建立在这句话上。

**持久化方案速查**（本书环境实测范围 + 生产常识）：

| 方案 | 跨进程 | 多副本并发写 | 本书验证 | 适用 |
|---|---|---|---|---|
| InMemorySaver | ✗（进程退出即丢） | ✗（单进程内即可） | ✅ 全书示例 | 教学单测、进程内审批 |
| SqliteSaver（3.1.2 实测） | ✅ 同机文件 | ✗（SQLite 单写者） | ✅ EX-47-02、resume_demo | 单实例服务、本地开发 |
| PostgresSaver | ✅ | ✅（共享库） | ✗ 无 PG 环境（待核实） | 生产多副本 |

## 47.3 正式原理与准确术语

**Checkpointer（检查点器）**：`compile(checkpointer=...)` 注入。本书实测可用：`InMemorySaver`（`from langgraph.checkpoint.memory import`）与 `SqliteSaver`（`from langgraph.checkpoint.sqlite import`，需 `pip install langgraph-checkpoint-sqlite`，实测版本 3.1.2，`SqliteSaver.from_conn_string(path)` 是上下文管理器）。生产可选 PostgresSaver（官方包，本书沙箱无 PG 未实测）。

**thread_id**：`config={"configurable": {"thread_id": ...}}`。**thread_id ↔ 流程实例 ID**（Java 工作流的 processInstanceId）。1.2.16 实测：带 checkpointer 的图 invoke 时缺 thread_id 直接报错——`ValueError: Checkpointer requires one or more of the following 'configurable' keys: thread_id, checkpoint_ns, checkpoint_id`。

**StateSnapshot（状态快照）**：`app.get_state(config)` 返回的命名元组，1.2.16 实测字段：`config / created_at / metadata / next / parent_config / tasks / values / interrupts / index / count`。最常用四个：`values`（状态全量）、`next`（即将执行的节点元组，空元组=已到 END）、`metadata`（含 step 步数）、`interrupts`（停在哪些人工中断，ch48）。

**get_state_history**：返回该 thread 的检查点列表（**从新到旧**），每个元素也是 StateSnapshot，其 `next` 显示"该检查点之后本来要跑什么"。

**时间旅行（time travel）**：把历史检查点的 `checkpoint_id` 塞回 config——`invoke(None, 旧config)` 从该点**原路重放**；`invoke(新输入, 旧config)` 从该点**换路分叉**。两条路径 1.2.16 均实测通过（EX-47-03）。

**恢复语义总表（ch47~ch48 的地基）**：新 invoke + 同 thread → 从最后快照继续；`Command(resume=...)` → 从 interrupt 处继续（ch48）；`invoke(None, 旧config)` → 从旧检查点重放。

**一个检查点里有什么**（解剖 EX-47-01 的快照链）：

```text
thread: user-A
  cp#0  __start__ 前   values=输入态            next=('support',)   parent=None
  cp#1  support 前     values=输入态            next=('support',)   parent=cp#0
  cp#2  support 后     values=+AIMessage        next=()             parent=cp#1
  （第二轮 invoke 再续 cp#3~cp#5；每个 cp 记录 parent 指针 → 链式可回溯）
```

三个要点：①**parent 指针成链**——`get_state_history` 能从新到旧遍历就靠它，时间旅行的"不可变历史"也是它（旧检查点永不改写，分叉只新增）；②**每步一份**——默认每超步结束都落快照，因此恢复可以精确到任意两节点之间；③**checkpoint_id 是新 config 的钥匙**——EX-47-03 把历史检查点的 `checkpoint_id` 塞回 `configurable` 即完成"读档"。1.2.16 还提供 `durability` 运行参数（`invoke/stream` 的关键字参数，实测取值 `'sync' | 'async' | 'exit'`，即同步落盘/异步落盘/退出时落盘）——高频写入场景可用它换吞吐，默认行为与持久化保证以官方文档为准，本书未逐项实测，标注**待核实**。

**Java 对照**：checkpointer ↔ Saga/事务日志——每步之后落一条可恢复的记录；thread_id ↔ 流程实例 ID；`get_state_history` ↔ 审计流水；时间旅行 ↔ 从备份点重放（event sourcing 的 replay）。不同之处：LangGraph 的快照由框架自动管理，Java 里这些通常散落在 Saga 日志表 + 编排代码里。

## 47.4 最小完整示例

**EX-47-01 | 示例代码/ch47_persistence/ex_47_01_persistence_memory.py（完整可运行）【主线示例 4：持久化】**

```python
# EX-47-01 | InMemorySaver + thread_id（节选）
def build_app():
    g = StateGraph(MessagesState)
    g.add_node("support", support_node)
    g.add_edge(START, "support"); g.add_edge("support", END)
    return g.compile(checkpointer=InMemorySaver())     # ← 唯一新增的一行

cfg_a = {"configurable": {"thread_id": "user-A"}}
app.invoke({"messages": [HumanMessage(content="第一次提问")]}, cfg_a)
r2 = app.invoke({"messages": [HumanMessage(content="第二次提问")]}, cfg_a)
```

```text
# 真实运行输出（langgraph 1.2.16）
thread user-A 第 2 次后消息数： 4 ← 第一次的历史还在（InMemorySaver 记住了）
thread user-B 消息数　　　： 2 ← 与 user-A 互不干扰
get_state(user-A).next = () （空元组=已到 END） | messages 数 = 4
get_state_history(user-A)：共 6 个检查点，next 序列（新→旧）：
 [(), ('support',), ('__start__',), (), ('support',), ('__start__',)]
每个检查点含：config / values / next / metadata(step) / created_at —— 可回到任意一步
```

读历史的三件事：两轮对话共 6 个检查点（每轮 3 个：start 前 / support 前 / 结束）；`next` 序列从新到旧回放出了整条执行轨迹；不同 thread 的检查点彼此独立。

**EX-47-02 | 示例代码/ch47_persistence/ex_47_02_persistence_sqlite.py（完整可运行）**

```python
# EX-47-02 | SqliteSaver（节选）：两个"进程"接力同一个会话
with SqliteSaver.from_conn_string(str(db_path)) as saver1:   # 进程 1
    app1 = build_graph().compile(checkpointer=saver1)
    app1.invoke({...}, cfg); app1.invoke({...}, cfg)
# —— 进程 1 退出 ——
with SqliteSaver.from_conn_string(str(db_path)) as saver2:   # 进程 2：新编译 + 同一个库
    app2 = build_graph().compile(checkpointer=saver2)
    snap = app2.get_state(cfg)      # 读到进程 1 的全部历史
    r = app2.invoke({"messages": [HumanMessage(content="继续跟进这个单子")]}, cfg)
```

```text
# 真实运行输出（langgraph 1.2.16 + langgraph-checkpoint-sqlite 3.1.2）
进程 1 完成 2 轮对话，检查点已写入 checkpoints.db
进程 2 get_state 读到 messages 数： 4
进程 2 继续对话后 messages 数： 6 ← 历史从 SQLite 恢复，会话无缝接续
对照：InMemorySaver 停在内存（进程重启即丢）；SqliteSaver/PostgresSaver 落盘可恢复。
```

**EX-47-03 | 示例代码/ch47_persistence/ex_47_03_time_travel.py（完整可运行，○ 进阶选修）**

```text
# 真实运行输出（langgraph 1.2.16）
正常跑完： ['step_one', 'step_two']
回退点：next = ('step_two',) （即将执行 step_two）
A 重放结果： ['step_one', 'step_two'] ；回放后 get_state().next = ()
B 分叉结果： ['step_one', '手工修正', 'step_one', 'step_two'] ；thread 的'现在'已切到新分支
检查点历史仍是完整的——时间旅行 = 在不可变检查点链上自由检出新分支
```

B 段值得逐条读：分叉输入 `{"steps": ["手工修正"]}` 先与该检查点的状态（`['step_one']`）合并，然后从 `step_one` 继续跑——所以结果里 `step_one` 出现了两次。**分叉不是"改写历史"，是"在旧档位上开新档"**。

## 47.5 逐段解释

1. **`compile(checkpointer=...)` 是唯一改动**（EX-47-01）：图定义零变化——持久化是编译期注入的能力，这正是"状态在图上"的红利：框架知道每一步之后状态长什么样，才能替你快照。
2. **`config` 是 invoke 的"寻址参数"**：`{"configurable": {"thread_id": ...}}` 定位会话；`recursion_limit` 等**运行时选项**与 configurable 平级（EX-45-02）。把它类比成 Java 里 `ProcessInstanceQuery(processInstanceId)` 的调用形态。
3. **`get_state().next == ()`**：可断言的"流程已完成"信号（ch51 的快照测试用它）；`next == ('approval',)` 则是"停在人工审批"（ch48）。
4. **SqliteSaver 的连接管理**：`from_conn_string` 返回**上下文管理器**——库文件在 with 块内持有。"模拟两个进程"的诚实写法就是两个独立的 with 块（EX-47-02），而不是同一个连接里装两个 app。

## 47.6 安装 / 文件位置 / 运行命令

```bash
pip install langgraph==1.2.16                       # InMemorySaver 随主包
pip install langgraph-checkpoint-sqlite             # SqliteSaver；本书实测 3.1.2
python3 示例代码/ch47_persistence/ex_47_01_persistence_memory.py
python3 示例代码/ch47_persistence/ex_47_02_persistence_sqlite.py
python3 示例代码/ch47_persistence/ex_47_03_time_travel.py
```

## 47.7 常见错误与排查

**① `ValueError: Checkpointer requires one or more of the following 'configurable' keys: thread_id, checkpoint_ns, checkpoint_id`**：挂了 checkpointer 但没给 thread_id。修复：config 永远带上 `{"configurable": {"thread_id": ...}}`；生产里 thread_id 用业务 ID（工单号/会话号），不要用随机 UUID——否则出事时对不上业务。

**② `RuntimeError: Cannot use Command(resume=...) without checkpointer`**（1.2.16 实测全文）：图没挂 checkpointer 就想恢复 interrupt。这两个能力是绑定的，见 ch48。

**③ 同一个进程里两个图报 `Channel ... already exists with a different type`**：见 44.7②。thread 隔离救不了 schema 冲突——通道在图编译时注册。

**④ 恢复后"还是旧答案"**：用了新 thread_id（等于新会话），或 SqliteSaver 的库文件路径指错了。排查口诀：**先 `get_state` 看快照是不是你以为的那个，再谈恢复**。

## 47.8 企业场景中的使用方式

- **会话亲和与多副本**：Python 图服务多副本部署时，InMemorySaver 不可用（副本间不共享）；SqliteSaver 适合单机/演示，生产用 PostgresSaver——所有副本连同一个检查点库，任何副本都能接手任意 thread（对应 Java 侧"分布式流程实例存储"）。
- **thread_id 命名规范**（建议三选一并写进团队约定）：①业务单据号（项目二的 `incident-<工单>`）——运维对得上账；②`<user_id>:<session_id>`——客服场景，天然带隔离维度；③UUID——仅在"流程与业务实体无对应关系"时用。反模式：把**用户级** ID 当 thread_id 让多轮业务共享一个 thread——历史会串台（44.4 第二轮的教训放大版）。
- **检查点保留策略**：历史快照会膨胀，生产要配 TTL/清理任务（官方 saver 支持按 thread 删除）；审计需求另由业务审计表承担（项目二的 JSONL 审计），**不要拿检查点当审计日志**——它是执行机制不是合规记录。
- **SqliteSaver 的适用边界**：SQLite 是单写者模型，多进程同时写同一检查点库会互锁/报错——它适合"单实例服务/本地开发/演示"，**不是**多副本方案（EX-47-02 的"两个进程"是串行接力，不是并发写入）。多副本请上 PostgresSaver（待核实项 1）。
- **恢复前的健康检查**：接手一个 thread 前先 `get_state` 三看——`next`（跑完了没/停在谁）、`values`（事实是否完整）、`metadata`（step 与时间戳判断新鲜度）——项目二 resume_demo 的进程 2 就是标准动作。
- **检查点安全**：快照里是完整业务状态（可能含敏感日志内容），存储权限要按"敏感数据"级别管理——PostgresSaver 的库账号、SQLite 文件的磁盘权限，与业务主库同级对待；这是 ch58 密钥与数据分级清单在编排层的落点。

## 47.9 练习与参考答案

**基础 1**：`get_state(cfg).next` 为空元组、为 `('approval',)` 分别意味着什么？**基础 2**：两轮对话为什么产生 6 个检查点？
**代码 1**：在 EX-47-01 基础上写测试：thread A 与 thread B 各自独立计数，互不污染（测试/test_ch47.py 已示范）。
**代码 2**：用时间旅行实现"从第 1 轮结束的检查点重放，但换一句用户输入"。
**调试题**：同事说"SqliteSaver 恢复后消息重复了两遍"。查他的代码：两个 with 块用了**同一个 thread_id** 且第二次 invoke 传了完整历史输入。说出根因与修法。

### 参考答案

基础 1：流程已结束；流程停在 approval 节点等人工决策。基础 2：每轮 invoke 产生 start 前/support 前/结束共 3 个检查点（EX-47-01 输出的 next 序列可数）。代码 2：取 `next == ('第二步节点',)` 的历史检查点，`invoke({"messages": [HumanMessage("新输入")]}, 旧config)`。调试题：恢复 invoke 的输入应该是**增量**（只放新增消息）——恢复时图会从快照里的旧历史继续，再把输入的"完整历史"追加了一遍，消息翻倍。修法：恢复调用只传新消息。注意 `invoke(None, cfg)` 不是恢复手段——那是 ch47 的时间旅行语义（从历史检查点**原路重放**）；若是 interrupt 后的人工恢复，必须用 `Command(resume=...)`（ch48）。

## 47.10 自测检查表

- [ ] 我能说出 checkpointer / thread_id / StateSnapshot 三者的关系；
- [ ] 我能默写 StateSnapshot 里最常用的四个字段；
- [ ] 我能演示"两个进程接力同一会话"并解释为什么不许复用同一个连接对象；
- [ ] 我能区分重放（None 输入）与分叉（新输入）两种时间旅行；
- [ ] 我知道检查点不是审计日志，生产要分开设计。

## 47.11 面试追问

1. **[模拟题] checkpointer 和"把对话历史存数据库"有什么区别？** 答：存历史只管"消息列表"；checkpointer 保存**图的完整执行状态**（含中间字段、下一步是谁、人工中断信息），因此能精确恢复到任意超步。历史存库是它的一种退化用法。
2. **[模拟题] 每步都写快照，性能账怎么算？** 答：InMemorySaver 是内存对象拷贝，微秒级；Sqlite/Postgres 是一次本地写。成本大头是状态体积——控制状态字段（46.8/44.8 的建议）比关快照更有效；官方 saver 的序列化也可自定义。
3. **[模拟题] 时间旅行在生产有什么正经用途？** 答：三种——修复类（模型答错的那轮换输入重跑）；排障类（从事故现场检查点重放定位）；测试类（ch51 从 interrupt 检查点重放验证幂等，项目二 test_p2 就用它）。

---

# 第 48 章 人工介入：interrupt、Command(resume) 与副作用幂等性

> **本章目标**：实现"高风险动作等人批准"，并彻底讲清恢复语义与幂等风险。
> **前置知识**：ch47（checkpointer 是恢复的前提）。
> **学完你能做什么**：用 `interrupt()`/`Command(resume=)` 实现审批流；画出"恢复后从哪继续"的完整图景；识别"副作用执行两次"的窗口并给出工程防线。

## 48.1 真实问题引入：AI 说"我帮你重启了"，运维连夜回滚

项目二的排障助手上线内测后出了险情：一次误报里，AI 判断"payment-service 需要重启"，而集成代码"贴心地"直接调了运维接口。重启瞬间把正在写的批处理任务打断了。复盘结论一句话：**高风险动作必须有人点头，而且点头这个动作要能跨进程、能审计、能重试而不重复**。这不是在 agent 提示词里写"请先询问用户"能解决的——提示词不是权限控制（ch28）。LangGraph 的答案是把"等人"做成图的一等公民：`interrupt()` 把图**暂停在检查点上**，人做完决定，`Command(resume=...)` 让图**从暂停点继续**——决策本身成为可持久化、可审计、可重放的数据。

## 48.2 一句话解释 + 生活类比 + 类比边界

**一句话解释**：节点里调用 `interrupt(payload)` 时，本次 invoke 立即返回（结果带 `__interrupt__`），图停在检查点上；人工把决策用 `Command(resume=value)` 传回来，该节点**从头重跑**，跑到 `interrupt()` 那一行时它"返回" resume 的值，图继续往下走。

**生活类比**：签证窗口（审批节点）叫号叫到你（interrupt），你回家等通知；材料补齐后你**重新取号排队**（节点从头重跑），但这次窗口直接办结（interrupt 处拿到结果继续往下）。重要细节：**重新排队时你会再走一遍大厅**——interrupt 之前的代码会再执行一遍。

> 💡 类比边界：
> 1. interrupt 不是异常处理：虽然实现上像一个特殊异常，但语义是"流程级暂停"，返回值带 `__interrupt__` 结构而不是抛到调用方；
> 2. "节点从头重跑"是**恢复语义的内核**，不是实现瑕疵——它保证恢复路径与正常路径共享同一段代码；代价是 interrupt 之前的代码必须幂等/只读（48.3 的铁律）；
> 3. resume 的值是**一次性**的：被消费后再次 invoke `Command(resume=...)` 于已完成的 thread 不会重放节点（EX-48-02 实测，重复恢复要靠时间旅行回到中断检查点）；
> 4. interrupt ≠ 提问：向模型追问"这样可以吗"是**对话**，interrupt 是**流程控制**——后者改变的是图的执行轨迹（停在检查点、等外部输入才能继续），前者只改变下一条消息的内容。判断标准：如果"没人回应流程就永远走不下去"，那就是 interrupt。

## 48.3 正式原理与准确术语

**interrupt()**：`from langgraph.types import interrupt`；1.2.16 实测签名 `interrupt(value, *, response_schema=None)`。`value` 是给"人"看的暂停载荷（审批单、问题、选项）；调用后当前 invoke 结束，返回 dict 里出现 `__interrupt__` 键，元素是 `Interrupt` 数据类（实测字段：`value / id / interrupt_id / response_schema`）。

**Command(resume=...)**：`from langgraph.types import Command`；数据类字段（实测）：`graph / update / resume / goto`。恢复调用：`app.invoke(Command(resume=决定), 同一config)`。`Command` 还能做节点内跳转（`goto`，含 Send）与状态更新（`update`），本书在 ch45（goto+Send）与本章（resume）各用一角。

**恢复语义三要点（全部实测）**：
1. 暂停点可查：`app.get_state(cfg).next == ('审批节点名',)`，快照的 `interrupts` 字段带载荷（EX-47-02 进程 2 的输出演示了跨进程读取）；
2. 恢复后节点**从顶部重跑**：interrupt 之前的代码再执行一遍；
3. 没有检查点就没有恢复：两者绑定，`RuntimeError: Cannot use Command(resume=...) without checkpointer`。
另有一个容易被忽略的运维要点：**interrupt 挂起后图不会自己等也不会自己醒**——催办/超时升级必须由外部机制扫描 `get_state().interrupts` 实现（见 48.8），把"人不在场"显式建模。

**副作用幂等性（idempotency）**：同一操作执行多次与一次效果相同。恢复场景的重复窗口：副作用执行成功 → 进程在写检查点前崩溃 → 恢复重跑节点 → 副作用再次执行。**图检查点不保证跨系统副作用恰好一次**，防线有三层（EX-48-02 实测前两层，项目二 test_p2 全部验证）：
- **纪律层**：interrupt() 之前零副作用（只读准备）；
- **账本层**：副作用走幂等账本（action_key 先查后写，等价于数据库唯一索引）；
- **审计层**：每次决策与执行留痕（项目二的 JSONL 审计）。

**"恢复后从哪继续"完整图解**（本章最重要的图，EX-48-01/48-02 的运行序列对照着读）：

```text
时间轴 ──────────────────────────────────────────────────────────▶
进程 1（服务实例）
  invoke(input, cfg)
      │
      ▼
  ┌────────┐   ┌───────────┐   ┌──────────────┐
  │ propose │ → │  approve   │ →│   interrupt!  │ ←在此打检查点：next=('approve',)
  └────────┘   └───────────┘   └──────┬───────┘    interrupt 载荷已入快照
   正常执行       正常执行            │
                                     │ 本次 invoke 返回 {__interrupt__: [...]}
                                     ▼
                          控制权回到调用方（HTTP 200 返回"待审批"）
  ═════════════════ 进程可以重启/换实例，检查点在存储里 ═════════════════
进程 2（可能是重启后的同一服务，也可能是审批回调服务）
  审批系统回调 → invoke(Command(resume=True), 同一 cfg)
      │
      ▼
  从 cp(next='approve') 恢复：
  ┌───────────┐   ┌──────────────────────────────┐   ┌─────────┐
  │  approve   │ →│ interrupt() 处直接"返回" resume 值 │ →│ execute  │ → END
  │ 从头重跑！  │   └──────────────────────────────┘   └─────────┘
  └───────────┘
   ↑ 只读段（重拼审批单）                    ↑ 副作用区：账本幂等 + 审计
```

三句话记忆：**暂停=在 interrupt 处打快照并返回调用方；恢复=从该快照把该节点重跑一遍、interrupt 处取 resume 值；继续=沿图走到 END。** 重跑段只读、副作用只在恢复后 + 账本，就是这个图对代码结构的全部要求。

**生产接入模式**（谁持有 config、谁来 resume）：审批回调服务需要三样东西——图定义（同一份 `build_graph()`）、checkpointer（指向同一个存储）、`config={"configurable": {"thread_id": 工单号}}`。流程：AI 服务 invoke → 返回体携带 `thread_id` 与审批单 → 审批单入审批系统（飞书/工单）→ 审批回调服务拿 `thread_id + 决定` 构造 `Command(resume=...)` → invoke 恢复。**没有任何一方需要"记住"内存状态**——这是 interrupt 与 sleep 方案的分水岭。项目二 `resume_demo.py` 的 B 段就是这个模式的两进程最小复现。

**Java 对照**：interrupt ↔ BPMN 的人工任务节点/审批流（但 pause 点内建、无需自建任务表）；`Command(resume)` ↔ 审批回调驱动流程继续；幂等账本 ↔ 幂等消费的唯一业务键 + 去重表（ch15/19 的思想在编排层的复用）；恢复重跑 ↔ 消息重投递——**正因为重跑是常态，副作用才必须幂等**。

## 48.4 最小完整示例

**EX-48-01 | 示例代码/ch48_human_in_loop/ex_48_01_human_approval.py（完整可运行）【主线示例 5：人工审批】**

```python
# EX-48-01 | 审批节点（节选）：interrupt 之前只读，副作用在恢复之后
def approve(state: DeployState) -> dict:
    ticket = f"申请人=AI助手 action={state['action']}"   # 只读：拼审批单
    decision = interrupt({"ticket": ticket, "question": "是否批准该高风险操作？"})
    return {"approved": bool(decision), "trace": [f"approve:{decision}"]}

def execute(state: DeployState) -> dict:
    if state["approved"]:
        return {"trace": [f"execute:{state['action']}（真实副作用放这里）"]}
    return {"trace": ["rejected:已拒绝，不执行"]}
```

```text
# 真实运行输出（langgraph 1.2.16，关键事件序列）
── 第 1 次 invoke：跑到 interrupt 暂停 ──
暂停点 next = ('approve',) | 审批单 = 申请人=AI助手 action=restart:order-service
── 第 2 次 invoke：Command(resume=True) 放行 ──
轨迹： ['propose:restart:order-service', 'approve:True', 'execute:restart:order-service（真实副作用放这里）'] | approved = True
── 新 thread：Command(resume=False) 拒绝 ──
轨迹： ['propose:restart:order-service', 'approve:False', 'rejected:已拒绝，不执行'] | approved = False

事件序列：invoke(暂停/含 __interrupt__) → 人工决定 → invoke(Command(resume=...)) → 从暂停节点继续
```

**EX-48-02 | 示例代码/ch48_human_in_loop/ex_48_02_side_effect_idempotency.py（完整可运行）**

```text
# 真实运行输出（langgraph 1.2.16，关键事件序列）
── 实验 A：副作用写在 interrupt 之前 ──
第一次 invoke： 等待审批 | 已执行副作用： ['副作用:send-sms-1']
恢复之后　　：副作用执行了 2 次 ← 通知/扣款发两遍的事故就这么来的
── 实验 B：interrupt 放最前 + 幂等账本 ──
第一次恢复　：副作用执行了 1 次
从中断点重放：副作用仍是 1 次，新轨迹： ['idempotent-skip:send-sms-2'] ← 节点重跑了，但账本命中，副作用没有重复
```

实验 B 的"从中断点重放"用了 ch47 的时间旅行（回到 `next=('node',)` 的检查点再 resume）——它精确模拟了"执行成功但检查点没写上就崩了，运维再恢复一次"的最坏情况。账本命中的那条 `idempotent-skip` 轨迹，就是幂等设计存在的意义。

## 48.5 逐段解释

1. **`interrupt()` 的载荷设计**：`value` 里放"人做决定需要的全部信息"（项目二放的是审批单列表：动作/服务/理由）。载荷会成为检查点的一部分——人两天后才批，上下文还在。
2. **恢复后的代码路径**：`approve` 第二次进入时，`interrupt()` 这一行直接返回 `Command(resume=...)` 的值——代码看起来"暂停又继续"，实际上是"重跑 + 在暂停点取值"，两者是同一个入口。
3. **拒绝也是一等结果**：`resume=False` 走到 `execute` 的拒绝分支，**结论照常产出**（项目二测试 `test_human_rejection_blocks_side_effect` 锁定：拒绝动作 ≠ 结论作废）。审批流的出口永远应该是"执行"或"记录在案地拒绝"，不能是"悬而未决"。
4. **`execute` 独立于 `approve` 节点**：副作用放在下一个节点，天然落在"恢复之后"；即使审批节点重跑一百遍，它也只是重算了审批单。项目二把执行再包一层账本，防的是崩溃窗口，两层防线不重复。

**四种审批形态与实现**（同一个 interrupt 原语，组织方式不同）：

| 形态 | 实现 | 恢复方式 | 适用 |
|---|---|---|---|
| 单票单审 | 一个节点一次 `interrupt()` | `Command(resume=bool)` | 项目二的重启确认 |
| 会签（全员同意才过） | 单节点**顺序多次** `interrupt()`，每次停独立检查点 | 逐次 resume，任一拒绝即终止 | 删除生产数据 |
| 或签（任一人批即可） | interrupt 前查已有批复记录（外部审批系统为准） | 回调先到者触发 resume | 值班告急场景 |
| 升级审批 | 条件边按金额/风险分级，高级别进额外审批节点 | 分级各自 resume | 越危险越多人点头 |

会签的两次 interrupt 放同一节点是刻意设计：两个暂停点天然是两个检查点，"谁先批的、谁后批的"完整留在检查点链里（ch47 的历史即审批履历）；或签的"查已有批复"放在 interrupt 之前的只读段，正好符合"重跑安全"纪律。

## 48.6 安装 / 文件位置 / 运行命令

```bash
pip install langgraph==1.2.16
python3 示例代码/ch48_human_in_loop/ex_48_01_human_approval.py
python3 示例代码/ch48_human_in_loop/ex_48_02_side_effect_idempotency.py
# 项目二的完整工程化实现（只读工具 + 审批 + 幂等账本 + 审计）：
cd 综合项目/项目二_日志排障助手 && python3 scripts/run_triage.py --scenario payment-outage   # 观察 __interrupt__
python3 scripts/resume_demo.py                                                          # 进程内/跨进程/幂等三段演示
```

## 48.7 常见错误与排查

**① `RuntimeError: Cannot use Command(resume=...) without checkpointer`**：恢复的前提是检查点。修复见 47.7①；CLI 场景同一个进程内用 InMemorySaver 即可（项目二 run_triage.py），跨进程用 SqliteSaver（resume_demo.py B 段）。

**② 恢复时报"没有匹配的 interrupt"**：resume 的 thread 已经消费过那次中断（或 thread_id 写错）。先 `get_state`：`next` 为空说明流程已完，`interrupts` 为空说明没有待决中断。

**③ interrupt 之前的副作用执行了两次**：EX-48-02 实验 A 的翻版。修复顺序：把副作用挪到 interrupt 之后 → 再加账本（无法挪动的遗留副作用至少要有 action_key 去重）。

**④ `ValueError: No checkpointer set` / 恢复后状态"回退"**：恢复用了**新的 checkpointer 实例**（内存检查点没共享）。内存检查点要跨 invoke 复用同一实例；跨进程必须落盘（SqliteSaver）。

## 48.8 企业场景中的使用方式

- **审批对接**：interrupt 的载荷推到审批系统（飞书审批卡/工单系统），审批回调服务再 `invoke(Command(resume=结果), config)`——"人"不直接摸 Python，人只产生结构化决定。项目二 README 的"扩展方向"给了对接口。
- **超时升级**：interrupt 长时间无人处理，应由外部定时任务检查 `get_state().interrupts` 并升级（催办/自动拒绝），LangGraph 不替你做超时策略——它是"停"，不是"等到"。
- **与 Saga 的对照**：检查点链 ≈ Saga 的事务日志；interrupt ≈ 补偿等待点；幂等账本 ≈ Saga 参与者的去重表。Java 团队可以把"审批 + 恢复 + 幂等"三个词直接映射到已有中间件经验上向架构师解释。

**与 Java 审批系统的字段映射**（对接审批平台时的翻译表，项目二审计 JSONL 已含前四列）：

| LangGraph 侧 | 审批平台侧（Java） | 备注 |
|---|---|---|
| thread_id | businessKey / 流程实例号 | 平台用它回调定位会话 |
| interrupt 的 value（审批单） | 申请单 payload | 结构自定，建议含动作/目标/理由/风险等级 |
| `Command(resume=...)` 的值 | 审批结果（approve/reject + 操作者） | 回调服务负责翻译成 resume 值 |
| 审计 `approval.*` 事件 | 审批流水表 | 双边各存一份，对账字段：action_key |
| ActionLedger 的 action_key | 幂等键（唯一索引） | 平台侧重复回调时据此去重 |
| get_state().interrupts | 待办查询接口 | 供"我的待办"页面拉取挂起中的审批 |

对接纪律：**resume 值要带操作者身份**（48.9 代码 1），审计才能回答"谁批的"；审批平台侧的幂等键与图的 action_key 用同一个字符串，两边对账才有公共主键。

## 48.9 练习与参考答案

**基础 1**：resume 之后，审批节点里 interrupt **之前**的代码会怎样？**基础 2**：`get_state(cfg)` 的哪两个字段告诉你"图停在人工审批、审批单内容是什么"？
**代码 1**：给 EX-48-01 加"审批人"概念：resume 的值改为 `{"approve": True, "operator": "zhang"}`，`execute` 把操作者写进轨迹。
**代码 2**：实现"二级审批"：金额 > 1 万需两个审批人先后 interrupt 确认（一个节点里两次 interrupt 即可，想想为什么）。
**调试题**：运维报告"同一个重启动作执行了两次"，审计里只有一条人工批准记录。给出最可能的窗口与修复。

### 参考答案

基础 1：会再执行一遍——所以那里只能放只读操作。基础 2：`next`（停在审批节点）与 `interrupts`（载荷）。代码 1：`decision = interrupt(...)` 返回 dict，`{"approved": bool(d["approve"]), "trace": [f"operator={d['operator']}"]}`。代码 2：同一节点顺序两次 `interrupt()`，各自停在独立检查点（第二次 interrupt 之前仍无副作用）；一次恢复只消费一个中断。调试题：窗口=执行成功但检查点未落；修复=执行走幂等账本（action_key 唯一），并核对审计的 `approval.*` 与账本记录一一对应（项目二 test_p2 的重放幂等测试即此场景）。

## 48.10 自测检查表

- [ ] 我能画出"暂停 → 检查点 → 人工 → resume → 节点重跑 → interrupt 处取值"的完整序列；
- [ ] 我能解释为什么 interrupt 之前不能有副作用；
- [ ] 我能说出三层防线的适用场景（纪律/账本/审计）；
- [ ] 我知道拒绝是正常出口且要留痕；
- [ ] 我能把 interrupt/Command 映射到 Java 的人工任务与审批回调。

## 48.11 面试追问

1. **[模拟题] interrupt 和"在节点里 sleep 等审批"有什么区别？** 答：sleep 占着线程、进程死了全丢；interrupt 把控制权交还调用方，状态在检查点上，进程可以正常释放、重启、换机器——恢复时凭 thread_id 找回现场。
2. **[模拟题] 恢复语义是"节点重跑"，那我的节点里有 HTTP 调用怎么办？** 答：把"读"与"写"拆开——重跑段只读（拼上下文）；写动作放到 interrupt 之后并过幂等键。若写动作本身不可幂等（如发短信），账本层必须先行（先占 action_key 再发送）。
3. **[模拟题] 多个审批人（会签）怎么实现？怎么测试？** 答：单节点多次 interrupt（串行会签）或多节点（职责分离）；测试用 ch51 的模式：断言每次暂停点的 `interrupts` 载荷，逐次 `Command(resume=...)`——暂停序列完全可脚本化（项目二 14 个测试里审批相关占 4 个）。

---

# 第 49 章 并行与子图：分头做事，合总成文

> **本章目标**：掌握静态并行（多边同发）与结果归并、以及子图的两种封装方式。
> **前置知识**：ch44（reducer 是本章的先决条件）、ch45（Send 与静态并行的分工）。
> **学完你能做什么**：写出"多路检查 → 汇总"的并行图并避免归并冲突；把大图拆成可复用子图，处理好字段映射；理解超步屏障对"什么时候能汇总"的保证。

## 49.1 真实问题引入：一次排障为什么要等三次串行查询

项目二的取证阶段是串行的：查错误事件 → 查服务状态 → 查依赖表。这三个查询**彼此不依赖**——都只读数据源、都只依赖告警列表；假设每次查询几百毫秒（本地只读 Source 的真实量级），一次假设验证的等待就是三倍。值班场景下这类等待累积得很快。串行改并行的第一版代码直接报错：两个分支都往 `findings` 字段写——`InvalidUpdateError`。本章解决三件事：怎么并行、怎么归并、以及把反复出现的"取证子流程"抽成子图复用。

## 49.2 一句话解释 + 生活类比 + 类比边界

**一句话解释**：静态并行 = 同一个节点（或 START）后面挂多条边，这些节点在**同一个超步**里执行，各写各的部分更新，由字段 reducer 归并；子图 = 把一张编译好的图当节点用。

**生活类比**：并行 = 会诊——三位医生（节点）同时看同一份病历（状态），各自写会诊意见，病历管理员（reducer）把三份意见**都**贴上去；子图 = 科室——"呼吸科流程"对外是一个科室（节点），内部有自己的多个步骤和自己的小病历。

> 💡 类比边界：
> 1. LangGraph 的并行是**超步级**的不是线程级：同一超步的节点都执行完才进下一步（Pregel 模型）；节点内部要不要多线程是节点自己的事（ch14）；
> 2. 并行写入同一个**无 reducer** 字段必然报错——这不是缺陷而是设计：没有归并规则的并行是没有语义的；
> 3. 子图不是微服务：它是**同进程内**的复用与命名空间，没有网络边界；跨服务拆分要用 ch57 的架构手段；
> 4. "并行"改变的是**等待结构**不是正确性规则：并行前后，业务语义必须等价（串行跑 5 分、并行跑也 5 分）——如果归并顺序影响结果（比如 reducer 是"取最后写入"），说明这个字段不适合并行写。

## 49.3 正式原理与准确术语

**静态并行（fan-out/fan-in）**：`g.add_edge(START, "a")` + `g.add_edge(START, "b")`（或从同一节点出多条边），两节点同超步执行；汇聚点 `summarize` 同时有 `a → summarize` 与 `b → summarize` 两条入边，超步屏障保证它等两路都到齐。

**结果合并（reduce）**：被并行写的字段必须 `Annotated` reducer。EX-49-01 用两个 reducer：`findings`（列表追加）、`risk_score`（数值求和）——**reducer 可以是任何 `(旧, 新) -> 新` 的函数**。

**子图（subgraph）**：编译后的图也是节点。两种接法（1.2.16 实测）：
- **schema 对齐**：父状态包含子图输入/输出的同名字段 → `g.add_node("子图名", 子图.compile())` 直接嵌入，字段自动映射；
- **显式映射**：字段名不同 → 写一个"桥接节点"，函数体内 `子图.invoke({...})`，手工搬运字段（相当于 Java 两个服务之间的 DTO 转换器）。

**超步屏障（superstep barrier）**：一轮里所有被调度的任务（含 Send 扇出的多份）都完成后，归并写入、快照、进入下一轮——这是"汇总节点拿到的是完整结果"的依据。

**并行安全清单**（改并行前逐条打勾）：

1. 被并行写的**每个**字段都有 reducer，且 reducer 语义有单测（求和/追加别弄反）；
2. 分支节点之间**无先后依赖**——如果 B 要读 A 的结果，那不是并行，连成 A→B；
3. 分支读的输入字段在**进入本超步前**已经稳定（由上游节点或初始输入写入）；
4. 汇聚节点只从分支接入（无 START 直连之类的旁路）；
5. 分支里的模型调用各自有超时/重试（ch50），一路慢不拖死整超步——超步屏障等**所有**分支，最慢分支决定步长。

**子图状态映射图解**（EX-49-02 两种接法的对照）：

```text
用法 1（schema 对齐）                    用法 2（显式映射）
父状态 ParentDirect                     父状态 ParentMapped
  alert ──同名──▶ 子图.AlertState.alert    incident ─┐
  cause ◀─同名── 子图.AlertState.cause     cause ◀───┤ bridge 节点手工搬运
                                            trace    ─┘   sub_out → {"cause": ...}
add_node("sub", 子图.compile())          add_node("bridge", bridge_fn)
```

选型口诀：**原型期用同名（快），定稿期用桥接（稳）**——重命名安全与输入校验都落在桥接节点里，一处代码保护一个边界。

**Java 对照**：并行+归并 ↔ `CompletableFuture.allOf` 后合并结果（但归并策略在 schema 里声明，不在调用点）；子图 ↔ 把一段流程封装成独立 BPMN 子流程；超步屏障 ↔ `allOf` 的 join 语义。

## 49.4 最小完整示例

**EX-49-01 | 示例代码/ch49_parallel_subgraph/ex_49_01_parallel_merge.py（完整可运行）**

```python
# EX-49-01 | 并行分支与归并（节选）：同一起点两条边 = 并行
g.add_edge(START, "llm_check")       # 分支 1：模型视角（Mock 确定性输出）
g.add_edge(START, "metric_check")    # 分支 2：指标视角
g.add_edge("llm_check", "summarize") # 汇聚：两条入边 → 超步屏障保证都到齐
g.add_edge("metric_check", "summarize")

class CheckState(TypedDict):
    service: str
    findings: Annotated[list[str], merge_list]                    # 追加归并
    risk_score: Annotated[int, lambda a, b: (a or 0) + (b or 0)]  # 数值求和
```

```text
# 真实运行输出（langgraph 1.2.16）
 - 模型: order-service 日志含 timeout 关键词
 - 指标: order-service P99 上升 40%
 - 汇总: 综合 5 分 → P1
risk_score = 5 （2+3 由数值 reducer 求和）

若把 findings 字段的 reducer 去掉，两个分支的写入会抛 InvalidUpdateError —— 并行必有归并。
```

**EX-49-02 | 示例代码/ch49_parallel_subgraph/ex_49_02_subgraph.py（完整可运行）**

```text
# 真实运行输出（langgraph 1.2.16）
用法 1（schema 对齐）： ['direct-report:ALERT-7 的根因是连接池耗尽']
用法 2（显式映射）： ['mapped:子图结果已搬运', 'mapped-report:INC-9 的根因是连接池耗尽']
```

## 49.5 逐段解释

1. **"汇总节点"是普通节点**：它没有特殊性，只是恰好有两条入边——Pregel 调度器把"等所有上游完成"当成默认行为，不需要 `await all`。
2. **数值 reducer 的写法**：`lambda a, b: (a or 0) + (b or 0)`——注意 `or 0` 处理首写时旧值为 `None` 的情况；求和/取最大/集合去重都是合法策略，**选错的代价是语义错了但不报错**（比如把"求和"写成"追加"，分数变成 `[2, 3]` 而不是 5）。
3. **子图用法 1 的隐藏前提**：字段同名才自动映射——这既是便利也是脆弱点：父图重命名一个字段，子图静默拿到空值。团队约定：能显式就显式（用法 2 的桥接节点多三行，换来重命名安全）。
4. **子图与 checkpointer**：子图节点也可以有自己内部的检查点（compile 时传入）；本章不展开，需要"子流程独立恢复"时查官方文档。

## 49.6 安装 / 文件位置 / 运行命令

```bash
python3 示例代码/ch49_parallel_subgraph/ex_49_01_parallel_merge.py
python3 示例代码/ch49_parallel_subgraph/ex_49_02_subgraph.py
# 项目二的并行化改造建议见其 README 第 12 节（三路取证用 Send 并行）
```

## 49.7 常见错误与排查

**① `InvalidUpdateError: At key 'out': Can receive only one value per step. Use an Annotated key to handle multiple values.`**（1.2.16 实测全文）：并行写无 reducer 字段。修复：加 reducer，或让每路写不同字段（分字段也是一种"归并"）。

**② 汇总节点拿到部分结果**：汇总节点与分支在**同一超步**被调度（它也有从 START 出发的直连边之类）。修复：保证汇总节点**只有**从分支来的入边。

**③ 子图静默拿到空输入**：schema "同名映射"被父图重命名破坏。修复：桥接节点显式映射 + 对子图输入做必填校验。

**④ 想用 `asyncio.gather` 在节点内并行**：合法但那是 ch13/ch14 的工具；图级并行交给图——混用前先问"这个并行需要进快照吗"，需要就上图的并行（可恢复），不需要才在节点内做。

## 49.8 企业场景中的使用方式

Spring 视角：并行分支+归并 ↔ `@Async` + `CompletableFuture.allOf`（但这里归并策略声明在类型上，测试可以只测 reducer）；子图 ↔ 把"标准取证流程"沉淀为团队库里的可复用编排单元，跨项目 import 复用（同进程、同依赖版本，比抽微服务轻得多）。项目二的取证三连（错误事件/服务状态/依赖表）是教科书式的并行候选——README 扩展方向第 3 条给出了 Send 版改造路线，保持状态可恢复的同时砍掉 2/3 等待时间。

项目二并行化的改造草图（供学完本章后动手，状态字段全是追加 reducer，天然兼容）：

```python
# 现状：extract_evidence 产出 plan，query_tools 串行执行
# 改造：extract_evidence 里的路由函数按计划逐条 Send，每份一个只读查询
def fan_out_queries(state):
    return [Send("run_one_query", q) for q in state["queries"] if q["status"] == "planned"]

def run_one_query(q, *, cfg, audit):          # 单条查询：白名单校验 + 只读执行 + 审计
    ...  # 原 query_tools 的单条逻辑，返回 {"queries": [记录], "evidence": [证据]}
# extract_evidence →(fan_out_queries 条件边)→ run_one_query × N → hypothesize
# queries/evidence 两个字段都是 Annotated[list, merge_lists]，N 份结果自动归并
```

改造后审计语义不变（每个查询仍各写一条 JSONL），唯一要留意的是 fan_out 前先去重（原 `seen` 集合逻辑保留在 extract_evidence 里）。

## 49.9 练习与参考答案

**基础 1**：静态并行与 Send 扇出在"份数"上的区别？**基础 2**：超步屏障给了汇总节点什么保证？
**代码 1**：EX-49-01 加第三路 `log_check`（写 findings、risk_score=1），预测汇总分数并验证。
**代码 2**：把"解析 + 预筛"抽成子图，用显式映射接入主图（父字段叫 `raw_logs`，子图字段叫 `records`）。
**调试题**：并行改造后 `risk_score` 时而 5 时而 `23`——reducer 被谁改过？

### 参考答案

基础 1：静态并行份数在图定义时固定；Send 运行时按数据决定份数与每份输入。基础 2：它读到的状态已包含**所有**分支该轮的归并结果。代码 1：6（2+3+1）。代码 2：桥接节点 `{"records": state["raw_logs"]}` 调子图，返回 `{"alerts": sub_out["alerts"]}`。调试题：把"求和"改成了"列表追加"（或字段被两个 reducer 声明）——23 就是 `[2,3]` 被字符串化的痕迹；固定 reducer 并用 44.9 代码 2 式的单测锁死语义。

## 49.10 自测检查表

- [ ] 我能写出并行分支 + 汇聚的最小图并预判归并结果；
- [ ] 我能说出 "Can receive only one value per step" 的根因与三种修法；
- [ ] 我能实现子图两种接法并说明何时必须显式映射；
- [ ] 我知道并行写入的字段必须有 reducer，且 reducer 语义要被单测锁定；
- [ ] 我能判断"这个并行该上图还是在节点内做"。

## 49.11 面试追问

1. **[模拟题] LangGraph 的并行是真并行吗？** 答：默认在同一事件循环里按超步调度（IO 密集型节点天然并发，CPU 密集型节点间是并发调度）；需要多进程/多线程压榨 CPU 时在节点内部做（ch14），图的职责是编排与归并。
2. **[模拟题] 子图和"把节点函数抽成模块"有什么区别？** 答：子图有自己的状态 schema、可独立测试/编译/加检查点，边界是**控制流级**的；抽函数只是代码组织。当"这段流程要被三张图复用且有自己的内部状态"时才值得子图化。
3. **[模拟题] 并行分支一路失败，整图怎么办？** 答：默认异常冒泡终止（配合 ch50 的重试/降级）。要"部分成功"语义，就在分支节点内捕获异常写错误标记（错误即数据），汇总节点按标记区分处理——项目二的 tool_error 证据就是这个模式。

---

# 第 50 章 流式与错误处理：看得见的执行，砸不烂的图

> **本章目标**：用 stream 的三种模式观察图执行；用 RetryPolicy 与"错误即数据"模式加固节点。
> **前置知识**：ch23（流式 chunk）、ch09（生成器）。
> **学完你能做什么**：为 UI 选对 stream 模式（values/updates/messages）；给抖动节点配置指数退避重试；区分"异常冒泡"与"错误即数据"两条错误处理路线并知道各自的使用场景。

## 50.1 真实问题引入：用户盯着白屏的 40 秒

客服图上线后，产品投诉"AI 回答要等 40 秒，中间一片空白"。40 秒里图其实在干活（模型节点、两个工具节点），只是 `invoke` 是"全部完成才返回"。解法是流式：`stream()` 返回生成器，图每推进一步就吐一个事件，前端实时渲染。与此同时，SRE 提了另一类需求：工具偶尔超时抖动，重试策略别散落在每个工具里；某个节点彻底失败时，别让整张图崩掉。本章把"看得见"（流式）与"砸不烂"（错误处理）拼成一章——它们共同的底层都是同一件事：**图把执行过程结构化了**，所以过程本身可订阅、每一步可加固。

## 50.2 一句话解释 + 生活类比 + 类比边界

**一句话解释**：`app.stream(输入, stream_mode=...)` 按**模式**吐出执行事件——`values` 每步给全量状态快照、`updates` 每节点给增量写入、`messages` 给图内部产生的 LLM 消息流；错误处理的两条正道是**节点级重试**（RetryPolicy）与**错误即数据**（节点捕获异常写进状态，用条件边走降级分支）。

**生活类比**：values 像**施工现场的全景直播**（每分钟拍一张全景照片）；updates 像**工单系统的事件流**（"3 号工位完成了什么"）；messages 像**对讲机里工人的实时语音**。错误处理上，RetryPolicy 是"干不好自动再试三次"，错误即数据是"干不了就填一张问题单流转到下一站"。

> 💡 类比边界：
> 1. `messages` 模式吐的是**图内部产生的消息**：节点直接返回 AIMessage 时它整条出现一次；只有节点内部是真实模型的流式调用时，才是逐 token 的 `AIMessageChunk`（本教材 Mock 不发 token 流，故 EX-50-01 展示的是整条消息形态——这是 Mock 边界的诚实声明）；
> 2. RetryPolicy 重试的是**节点**：重试期间节点整体重入，所以节点里的副作用同样要幂等（ch48 的账本在这里继续有效）；
> 3. "错误即数据"不是吞异常：只捕获**预期内**的异常类型，写进状态留痕，让路由显式处理；意外的 bug 依旧让它炸出来；
> 4. 流式输出的"实时"是**执行进度级**的：图保证"节点完成就可见"，不保证"节点内部实时"——想在节点执行中途看到进展（比如长工具的百分比），要么把工具拆成多节点，要么节点里调 `langgraph.config.get_stream_writer()` 写自定义事件（import 已实测存在；写入后的消费形态本书未演示，需时查官方文档）。

## 50.3 正式原理与准确术语

**stream 与 stream_mode**：`stream_mode="values"|"updates"|"messages"`（1.2.16 实测），也可传列表同时订阅多种。`values` 的每帧是"到当前超步为止的全量状态"；`updates` 的每帧是 `{节点名: 该节点的部分更新}`；`messages` 的每帧是 `(消息对象, 元数据)` 二元组，元数据含 `langgraph_node`（来源节点）。

**RetryPolicy**：`from langgraph.types import RetryPolicy`，加在 `add_node(..., retry_policy=RetryPolicy(...))` 上。1.2.16 实测字段与默认值：`initial_interval=0.5, backoff_factor=2.0, max_interval=128.0, max_attempts=3, jitter=True, retry_on=default_retry_on`——指数退避 + 抖动，`retry_on` 可传异常类型或谓词函数（默认只重试"值得重试"的瞬态错误；指定 `retry_on=ValueError` 即按你的清单来）。

**异常冒泡**：重试耗尽后异常从 `invoke` 冒出，任务名与错误信息随 traceback 可见（EX-50-02 B 段）。

**错误即数据（error as data）**：节点内 try/except 预期异常 → 写入 `errors` 字段 → 条件边路由到降级节点。这是 ch35"拒答策略"在编排层的同族思想：**失败是合法输出，不是意外**。

**Java 对照**：stream ↔ SSE 推送（ch17 的 StreamingResponse 正好做前端出口）；RetryPolicy ↔ Spring Retry 的 `@Retryable`（指数退避 + include 异常清单）；错误即数据 ↔ `Result<T>` 封装而不是抛异常穿透——AI 流程里"带着错误继续走"往往比"fail fast"更符合业务（排障场景：查不到数据本身就是证据）。

**stream 模式选型表**（50.8 的速查版）：

| 消费方 | 模式 | 每帧内容 | 前端动作 |
|---|---|---|---|
| 聊天窗口 | messages | (消息/chunk, 来源元数据) | 逐条/逐 token 渲染气泡 |
| 运维控制台 | updates | {节点名: 部分更新} | 进度条："取证中…评估中…" |
| 调试回放/状态同步 | values | 全量状态快照 | 整页刷新为最新态 |
| 审计管道 | updates | 同上 | 落事件表（项目二审计的编排层补充） |
| 全都要 | 列表混订 | (模式名, 帧) | 按模式名分发到不同处理器 |

两条纪律：①**一条流一个消费者**——同一帧别既做渲染又做审计（写两遍处理逻辑不如开两条订阅）；②**流式不改变检查点语义**——无论 stream 与否，超步末尾照常快照，所以前端断了不影响恢复（重连后用 values 补最新帧即可）。

## 50.4 最小完整示例

**EX-50-01 | 示例代码/ch50_streaming_errors/ex_50_01_stream_modes.py（完整可运行）**

```text
# 真实运行输出（langgraph 1.2.16）
── stream_mode='values'：全量快照 ──
  第1帧：[]
  第2帧：['A 节点的回答']
  第3帧：['A 节点的回答', 'B 节点的回答']
── stream_mode='updates'：增量写入 ──
  节点 A 写入：['A 节点的回答']
  节点 B 写入：['B 节点的回答']
── stream_mode='messages'：LLM 消息流 ──
  消息 AIMessage('A 节点的回答') 来自节点 A
  消息 AIMessage('B 节点的回答') 来自节点 B
```

三种模式三帧/两帧/两帧——粒度从"全景"到"工单"到"语音"，UI 选型见 50.8。

**混订两种模式**（`stream_mode` 传列表，实测输出）：每帧变成 `(模式名, 内容)` 元组，values 与 updates 交替出现——

```python
for mode, chunk in app.stream({"messages": []}, stream_mode=["updates", "values"]):
    print(mode, "→", str(chunk)[:60])
```

```text
# 真实运行输出（langgraph 1.2.16）
values  → {'messages': []}
updates → {'A': {'messages': [AIMessage(content='A 节点的回答', additional_
values  → {'messages': [AIMessage(content='A 节点的回答', additional_kwargs
updates → {'B': {'messages': [AIMessage(content='B 节点的回答', additional_
values  → {'messages': [AIMessage(content='A 节点的回答', additional_kwargs
```

可以看到节奏：每完成一个超步，先吐 `updates`（谁写了什么）再吐 `values`（合并后的最新态）——UI 可以同时做"进度提示 + 内容替换"。

**EX-50-02 | 示例代码/ch50_streaming_errors/ex_50_02_retry_and_errors.py（完整可运行）**

```text
# 真实运行输出（langgraph 1.2.16）
A 重试成功： flaky 成功（第 3 次尝试）
B 重试耗尽： hopeless 第 2 次调用失败（模拟下游抖动）
C 错误即数据：errors = ['resilient 捕获 TimeoutError: 下游 3 秒未响应'] | result = 降级：返回缓存的上次结果
```

A 段闭包计数证明重试真实发生了两次；B 段异常文本带着节点名冒出；C 段整图"带着错误走完了"并给出降级结果——三条路径都值得背下来。

## 50.5 逐段解释

1. **`values` 模式的第 1 帧是输入态**：`[]` 说明还没任何节点跑——前端可以拿它做"初始化渲染"。
2. **`updates` 的键是节点名**：审计日志直接订阅这个模式（EX-43-02 的 trace 思路的官方版），它天然回答了"哪个节点在什么时候写了什么"。
3. **RetryPolicy 的参数口径**（实测默认）：0.5s 起步、×2 退避、封顶 128s、共 3 次、带抖动。EX-50-02 把 `initial_interval` 调小、`jitter` 关掉是为了输出可复现——**生产保持默认抖动**，防止惊群。
4. **C 段的条件边**：`lambda s: "fallback" if s["errors"] else END`——降级路径显式画在图上，而不是藏在 try 块里。review 图的人一眼看到"失败会去哪"。

## 50.6 安装 / 文件位置 / 运行命令

```bash
python3 示例代码/ch50_streaming_errors/ex_50_01_stream_modes.py
python3 示例代码/ch50_streaming_errors/ex_50_02_retry_and_errors.py
```

## 50.7 常见错误与排查

**① `GraphRecursionError` 而不是预期的异常**：节点重试也是超步，`max_attempts` 大于 `recursion_limit` 的余量时先撞递归上限。修复：单节点重试次数计入"最长路径"预算（44.8 心算公式 × max_attempts）。

**② 重试没生效**：默认 `retry_on=default_retry_on` 不重试你的业务异常（它只认瞬态类错误）。修复：显式 `retry_on=你的异常类型或谓词`（EX-50-02 的 `retry_on=ValueError`）。

**③ stream 后丢输出**：生成器没消费完就丢弃/提前 return——流是惰性的。修复：消费完整迭代器，或用 `for chunk in app.stream(...)` 全程循环。

**④ 重试导致副作用重复**：节点里写了 HTTP POST。修复：副作用移出被重试节点，或过 ch48 的幂等账本；RetryPolicy 原则上只给只读节点（项目二的只读取证查询就是它的天然候选）。

## 50.8 企业场景中的使用方式

- **UI 出口选型**：聊天界面用 `messages`（逐条/逐 token 渲染）；运维控制台用 `updates`（节点级进度条）；调试回放用 `values`。三者可以同时订阅（`stream_mode=["updates","messages"]`）。
- **SSE 落地**：`stream()` 的生成器直接喂 ch17 的 `StreamingResponse`——图事件与 HTTP 事件一一对应，trace_id 贯穿（ch60）。最小草图（FastAPI 侧，完整版本见 ch17 的 SSE 语法）：

```python
@app.get("/triage/stream/{incident_id}")
async def stream_triage(incident_id: str):
    async def gen():
        for mode, chunk in app.stream(input_state, {"configurable": {"thread_id": incident_id}},
                                      stream_mode=["updates", "values"]):
            yield f"data: {json.dumps({'mode': mode, 'chunk': str(chunk)[:200]}, ensure_ascii=False)}\n\n"
        yield "event: done\ndata: {}\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream")
```

三个生产细节：①`str(chunk)[:200]` 是占位——真实实现要按模式序列化（updates 取节点名+摘要，values 取结论字段），别把整个状态推给前端；②生成器里**不要**再开新的事件循环调用同步阻塞的图——用 `astream` 或把同步图丢进线程池（ch13 的 sync 阻塞伤害同样适用于图）；③连接断开时图仍在按检查点推进，前端重连后用 `get_state` 补帧——流是视图，检查点才是事实。
- **重试治理**：RetryPolicy 集中在图定义处，review 图 = review 全部重试策略——比散落在每个工具里的 try/except 好治理得多；参数对齐 ch59 的稳定性清单（超时/重试/限流在 LLM 场景的具体值）。
- **项目二的对应物**：`query_tools` 捕获 `sqlite3.OperationalError/FileNotFoundError` 写 `tool_error` 证据（错误即数据），取证结果缺失直接转化为缺口清单——错误帮助"证据不足"结论的生成，这是错误即数据的最佳注脚。

## 50.9 练习与参考答案

**基础 1**：三种 stream 模式各自吐什么的"粒度"？**基础 2**：RetryPolicy 默认重试几次、退避基数多大？
**代码 1**：把 EX-50-02 的降级分支改成两级——先重试（RetryPolicy max_attempts=2），再降级。
**代码 2**：订阅 `["updates", "messages"]` 双模式，打印每帧的类型，验证元组结构。
**调试题**：`updates` 流里出现了 5 个节点的帧，但 `values` 只有 3 帧——可能吗？为什么？

### 参考答案

基础 1：全量快照 / 节点级增量 / 图内 LLM 消息。基础 2：3 次、0.5 秒起 ×2 指数退避（封顶 128s，带抖动）。代码 1：`add_node("resilient", ..., retry_policy=RetryPolicy(max_attempts=2, retry_on=TimeoutError))`，重试耗尽抛出的 TimeoutError 由外层节点的调用方捕获——或把重试节点包进内层图。代码 2：`for mode, chunk in app.stream(inp, stream_mode=["updates","messages"], ...)`，帧形如 `("updates", {...})` / `("messages", (msg, meta))`。调试题：可能——并行超步里 2 个节点同帧完成时，`values` 两帧合并为 1 帧，`updates` 仍按节点各吐一帧。

## 50.10 自测检查表

- [ ] 我能按 UI 场景选对 stream 模式并说清理由；
- [ ] 我能默写 RetryPolicy 的六个字段与默认值；
- [ ] 我能实现"重试 → 仍失败 → 降级"的完整链路；
- [ ] 我知道重试与副作用幂等的冲突并会规避；
- [ ] 我知道 Mock 模式下 messages 模式的边界（整条消息 vs token 流）。

## 50.11 面试追问

1. **[模拟题] values/updates/messages 怎么取舍？全都要行不行？** 答：按消费方定——行，`stream_mode` 传列表即可，每帧带模式标签；但订阅越多，前端处理越复杂，别把三种模式都推给同一个消费者。
2. **[模拟题] 哪些节点该配 RetryPolicy？** 答：只读、幂等、外部依赖的节点（模型调用、工具查询）；带副作用的节点用"账本 + 上层重放"而不是节点重试。重试是给"瞬态失败"的，不是给"业务拒绝"的。
3. **[模拟题] 图级错误处理和全局异常处理器（FastAPI exception_handler）怎么分工？** 答：图内处理"业务预期失败"（降级、拒答、错误即数据）；框架层兜底"意外故障"（统一 5xx、告警）。混用会导致"错误被两层各自吞一半"，排查时两边日志都要看。

---

# 第 51 章 测试 LangGraph：从单节点到整图的分层验证

> **本章目标**：建立图的四层测试体系：节点直调、整图断言、快照校验、Mock LLM 注入。
> **前置知识**：ch18（pytest）、ch44~ch50 全部。
> **学完你能做什么**：为每个节点写纯函数测试；用脚本化 Mock 驱动整图终点；断言 StateSnapshot 的 next/values/metadata；把 interrupt 流测试脚本化——并将这套体系直接复用到项目二。

## 51.1 真实问题引入："图没法测"是最大的误解

引入 LangGraph 后，团队最初的反应是"这东西没法测"——以前测一个方法给输入断输出，现在是一个动态执行的图。三个月后他们发现恰恰相反：**图把控制流变成了数据，测试断言的对象反而更多了**——不只断言最终输出，还能断言"走到过哪些节点"（快照 next）、"谁写了什么"（updates 流）、"停在哪等人"（interrupts）。老张给排障助手补测试时发现，最难的不是测图，而是测"模型的不确定性"——解法也简单：模型节点做成工厂注入 llm，测试注入脚本化 MockLLM（ch46 的 `make_agent_node(llm)` 本来就是为此设计的）。本章把这四层写成可复制的模板。

## 51.2 一句话解释 + 生活类比 + 类比边界

**一句话解释**：LangGraph 的测试分层 = **单节点测纯函数**（状态进、更新出）→ **整图测终点**（Mock 注入 + invoke 断言）→ **快照测过程**（next/values/metadata/interrupts）→ **失败路径测纪律**（recursion_limit、脚本耗尽、白名单拒绝）。

**生活类比**：验收一条地铁线——单节点测是"验收每个站台的设备"，整图测是"从起点坐到终点看准点率"，快照测是"调行车记录核对每一站的到发时刻"，失败路径测是"演练信号故障时列车怎么降级"。

> 💡 类比边界：
> 1. Mock 注入测的是**控制流**，不是模型质量：模型质量归评估集（ch35/golden set，ch28），两套测试别互相越位；
> 2. 快照测试有"锁死实现"的风险：断言 `next` 序列太细会让重构变痛苦——只锁**业务上有意义的**停点（比如"停在审批"），别锁每一步；
> 3. 测试里不要用真实 checkpointer 库做慢 IO：进程内场景 InMemorySaver 足够，SqliteSaver 测试只在"跨进程恢复"故事里出现（测试/test_ch47.py 用 `importorskip` + `tmp_path`）；
> 4. 测试的确定性来自**三层注入**：数据（tmp_path 重建合成数据）、模型（脚本 Mock）、检查点（每测试新 InMemorySaver）——三层里任何一层共享了实例，测试就会彼此污染，而且往往"偶尔红"，比稳定失败更难查。

## 51.3 正式原理与准确术语

**节点直调**：节点是 `(state) -> dict` 的函数，绕过图直接调用——最快的单测，覆盖业务分支（EX-51-01 姿势 1）。

**Mock LLM 注入**：模型节点由工厂闭包创建（`make_agent_node(llm)`/项目二 `make_nodes(cfg, audit)`），测试注入 `MockLLM(script=[...])`——脚本逐次返回预置回答，游标耗尽抛 `RuntimeError`（绝不静默编造），失败路径因此可测（test_ch46 的 `test_script_exhaustion_fails_loudly`）。

**整图测试**：`invoke` 后断言最终状态。含 interrupt 的图要**两段式**：第一段 invoke 断言 `__interrupt__`，第二段 `Command(resume=...)` 断言终点。

**快照测试**：`app.get_state(cfg)` 断言 `next`（停在/到达哪）、`values`（状态内容）、`metadata["step"]`（步数）、`interrupts`（载荷）。`get_state_history` 可断言完整轨迹。

**失败路径**：`pytest.raises(GraphRecursionError)`（配 `recursion_limit`）、`pytest.raises(KeyError)`（path_map 缺失）、`pytest.raises(RuntimeError)`（脚本耗尽）——1.2.16 实测的异常类型。

**测试文件布局（本书约定）**：`测试/test_chNN.py` 按章组织，从 `examples.chNN_*` 直接 import 模块级函数复用；项目级测试 `测试/test_p2.py` 用 `tmp_path` 注入独立数据/审计目录。

**两段可复制的测试模板**（项目二与各章测试里反复出现的形状）：

```python
# 模板 A：隔离式整图 fixture（test_p2 的 _make_cfg/_run 精简版）
@pytest.fixture()
def triage_env(tmp_path):
    cfg = TriageConfig(data_dir=tmp_path / "data", audit_path=tmp_path / "audit.jsonl",
                       ledger_path=tmp_path / "ledger.jsonl")
    cfg.ensure_dirs()
    build_all(cfg.data_dir)                    # 确定性合成数据
    return cfg, AuditLog(cfg.audit_path)

def test_something(triage_env):
    cfg, audit = triage_env
    run = _run("case-1", SOURCES, cfg, audit)  # 每测试独立 checkpointer + 独立目录

# 模板 B：中断前后快照对比（恢复语义测试的通用断言骨架）
snap_before = run.app.get_state(run.config)        # 暂停时
final = resume_triage(run, True)
snap_after = final.app.get_state(final.config)
assert snap_after.values["hypothesis"] == snap_before.values["hypothesis"]  # 事实不变
assert snap_before.next == ("approval",) and snap_after.next == ()          # 从停点到终点
```

**项目二测试地图**（四层 × 业务路径，14 个测试的分布）：

| 层 | 测试 | 锁定什么 |
|---|---|---|
| 单节点 | 白名单三道校验 ×2、SQLite 只读、工具级幂等 | 防线本身可靠 |
| 整图 | 正常路径、证据不足、空日志、文件缺失 | 业务结论正确 |
| 快照 | 恢复前后一致、thread 隔离 | 恢复不破坏事实 |
| 失败路径 | recursion_limit、人工拒绝、重放幂等、审计字段完备 | 保险丝与留痕 |

## 51.4 最小完整示例

**EX-51-01 | 示例代码/ch51_graph_testing/ex_51_01_graph_testing.py（完整可运行）**

```python
# EX-51-01 | 四种测试姿势（节选）：Mock 注入是核心
def classify_llm_node_factory(llm):
    """依赖注入：生产传 get_llm()，测试传脚本化 MockLLM——控制流测试不依赖真实模型。"""
    def node(state: RiskState) -> dict:
        r = llm.chat([{"role": "user", "content": f"风险等级? {state['text']}"}])
        return {"action": "block" if "block=true" in r.content else "allow"}
    return node

# 姿势 2 + 4：整图（含 interrupt）两段式
app = build_app(MockLLM(script=[{"content": "风险评估 block=true"}]))
paused = app.invoke({"text": "查我的银行卡", "findings": [], "action": ""}, cfg)
assert "__interrupt__" in paused
final = app.invoke(Command(resume=True), cfg)
assert final["action"] == "executed"
```

```text
# 真实运行输出（langgraph 1.2.16）
1) 单节点测试　　　：PASS —— 节点是纯函数，输入 dict 输出 dict
2) 整图测试　　　　：PASS —— 注入脚本 Mock + 恢复，终点状态确定
3) 快照测试　　　　：PASS —— next/values/metadata 全部可断言
4) interrupt 流测试：PASS —— 暂停/恢复都可脚本化断言
```

这四个断言在 `测试/test_ch51.py` 里以 pytest 形式（5 个测试）纳入全书回归；项目二 `测试/test_p2.py` 的 14 个测试是同一套方法的工程化放大（白名单拒绝、审计字段、幂等重放等）。

## 51.5 逐段解释

1. **为什么先测节点再测图**：节点测试失败 → 修函数；只有整图测试时，一次失败要在动态执行里找原因——分层让失败定位从"查案"变成"对号"。
2. **两段式 interrupt 测试是模板**：第一段断言暂停点（`next == ('gate',)`），第二段断言恢复结果——暂停点断言比终点断言更早失败、信息更准（项目二 `test_resume_state_consistent_with_prior_snapshot` 把中断前后的快照做**逐字段对比**，锁定"恢复不破坏事实"）。
3. **Mock 脚本即"模型行为剧本"**：测试读起来像剧本（第 1 轮模型要查订单 → 第 2 轮要查政策 → 第 3 轮总结），非模型同事也能 review 测试用例——这是团队协作层面的收益。
4. **失败路径是图的特有价值**：recursion_limit、脚本耗尽、白名单拒绝这些"保险丝"，在函数式代码里很难单独触发，在图测试里就是一行 `pytest.raises`。
5. **命名与断言风格约定**（本项目 测试/ 的既成事实，团队可直接抄）：测试名用"行为_结果"句式（`test_human_rejection_blocks_side_effect`），读测试列表如读需求清单；每个测试 docstring 第一行写"锁定什么"（正常路径/失败路径/契约）；断言先具体值后语义（先 `== "P1"` 再讲 reason）；一个测试只回答一个问题——"正常路径 + 审批 + 幂等"三件事分三个测试，失败时定位零歧义。

## 51.6 安装 / 文件位置 / 运行命令

```bash
cd /workspace/ai_application_course
python3 示例代码/ch51_graph_testing/ex_51_01_graph_testing.py
python3 -m pytest 测试/test_ch43.py 测试/test_ch44.py 测试/test_ch45.py 测试/test_ch46.py \
                  测试/test_ch47.py 测试/test_ch48.py 测试/test_ch49.py 测试/test_ch50.py \
                  测试/test_ch51.py 测试/test_p2.py -q      # 本部分回归
python3 -m pytest 测试/ -q                                        # 全书回归
```

## 51.7 常见错误与排查

**① `ValueError: Channel 'xxx' already exists with a different type`**：测试里重新声明了同名字段但不同 reducer。修复：从被测模块 import 同一个 reducer 对象（测试/test_ch47.py 的 `_tt_app` 示范）。

**② 测试里 reducer `NameError`**：reducer 定义在被测函数内部 + `from __future__ import annotations`（44.7③ 的同款坑在测试里最常复发）。修复：reducer 放模块顶层。

**③ 整图测试莫名停在半路**：图里有 interrupt，invoke 返回了 `__interrupt__` 而测试没恢复。修复：两段式模板；或断言 `snap.next` 把"停在哪"显式化。

**④ 测试之间互相污染**：共享了同一个 InMemorySaver/审计文件/数据目录。修复：fixture 里 `tmp_path` + 每测试新建 saver（test_p2 的 `_make_cfg` 模板）；MockLLM 的 `calls` 记录也是实例级的，别跨测试复用实例。

## 51.8 企业场景中的使用方式

- **CI 策略**：节点测试与整图测试全量跑（秒级）；含 SqliteSaver 的测试标记慢速层；Prompt 回归（golden set）与控制流回归分开两个 job——前者变异敏感，后者要求 100% 绿。
- **契约测试**：把"AIMessage.tool_calls 的 dict 形态"、"StateSnapshot 字段"这类**框架契约**写成断言（test_ch50 的 `test_retry_policy_defaults_documented` 锁 RetryPolicy 默认值），升级 langgraph 版本时先跑它——版本升级的破坏点一览无余。

```python
# 契约测试的两个样板（测试/ 里的实测形态）
def test_retry_policy_defaults_documented():
    """锁 1.2.16 的 RetryPolicy 默认值：升级版本时这里先红。"""
    p = RetryPolicy()
    assert p.max_attempts == 3 and p.initial_interval == 0.5
    assert p.backoff_factor == 2.0 and p.jitter is True

def test_error_messages_are_stable():
    """锁关键报错文案：ch47/ch48 的排障手册引用它们，改版即提示同步文档。"""
    with pytest.raises(ValueError, match="thread_id"):
        app.invoke(state, {})                      # 缺 thread_id
    # RuntimeError("Cannot use Command(resume=...) without checkpointer") 同理可锁
```

为什么值得：书里的报错排查表（各章 7 号小节）引用了这些文案——框架升级文案一变，契约测试先红，避免"手册教用户找一句已经不存在的报错"。

- **项目二的测试地图**（14 个测试 = 四层 × 业务路径）：单节点（工具白名单/只读连接）→ 整图（正常路径/证据不足/空日志/文件缺失）→ 快照（恢复一致性/thread 隔离）→ 失败路径（递归上限/人工拒绝/幂等重放）。接受任何新需求前先问：这个测试地图哪里要加一格。

## 51.9 练习与参考答案

**基础 1**：四层测试各自断言的对象是什么？**基础 2**：为什么 MockLLM 脚本耗尽要抛错而不是返回默认值？
**代码 1**：给 EX-51-01 的 `gate` 写会签测试：两次 interrupt，第一次批准第二次拒绝，断言最终 `rejected`。
**代码 2**：写一个"契约测试"：断言 `add_conditional_edges` 的 path_map 缺失路由值时抛 KeyError。
**调试题**：同事的整图测试"有时绿有时红"，日志显示工具调用次数偶发不同。说出最可能的根因与修法。

### 参考答案

基础 1：节点函数输出 / 图终点状态 / 执行过程（next/metadata/interrupts）/ 保险丝行为。基础 2：默认值会把"模型行为超出剧本"静默洗白成"测试通过"——抛错暴露剧本与现实的偏差。代码 1：

```python
r1 = app.invoke(state, cfg); assert "__interrupt__" in r1
r2 = app.invoke(Command(resume=True), cfg); assert "__interrupt__" in r2   # 第二道审批
r3 = app.invoke(Command(resume=False), cfg); assert r3["action"] == "rejected"
```

代码 2：仿 测试/test_ch45.py 的 `test_conditional_edges_mapping`。调试题：脚本 Mock 没注入（或注入了规则模式），模型行为受输入里 USE_TOOL 触发词影响导致轮数漂移；修法：显式注入脚本化 Mock，并把"预期轮数"断言加上（`len(llm.calls) == 3`，test_ch46 的做法）。

## 51.10 自测检查表

- [ ] 我能不查资料写出"节点直调 + 整图两段式"的最小测试；
- [ ] 我能断言 StateSnapshot 的四个关键字段并知道别锁太细；
- [ ] 我会用脚本化 MockLLM 驱动含工具循环/interrupt 的整图测试；
- [ ] 我能给 recursion_limit/path_map 缺失/脚本耗尽写失败路径测试；
- [ ] 我能把项目二的 14 个测试讲成一张四层测试地图。

## 51.11 面试追问

1. **[模拟题] LangGraph 应用的测试金字塔长什么样？** 答：底座是节点纯函数测试（快、多、稳）；中层是 Mock 注入的整图测试（控制流覆盖）；上层是少量真模型评估（golden set，跑评估集而非单测）；外加框架契约测试防版本升级。项目二 14 个测试全部离线秒级，就是这套金字塔的落地样本。
2. **[模拟题] 怎么测"模型乱来"（幻觉/编服务名）？** 答：控制流层用 Mock 模拟"乱来"的剧本，验证系统防线（白名单拒绝、证据不足拒答）真实生效；模型层用评估集量化发生率。两层合起来回答"乱来了会怎样+多常发生"。
3. **[模拟题] 恢复语义怎么测试才可信？** 答：三步——断言暂停点（next+interrupts）；恢复后对比中断前后快照的事实字段（假设/告警不变）；用时间旅行回到中断检查点重放，验证副作用账本命中不重复执行。这三步就是项目二 `test_resume_state_consistent_with_prior_snapshot` 与 `test_replayed_resume_does_not_repeat_side_effect`。

---

## 第八部分小结与验收

**验收标准（对应 syllabus）**：不查资料手写"带审批 + 恢复 + 持久化"的三节点图。自评清单：

1. 图能暂停在审批节点（interrupt），暂停点可从另一个进程观察到（SqliteSaver + get_state）；
2. 审批通过后副作用**恰好执行一次**（幂等账本 + 审计留痕）；
3. 拒绝时结论照常产出并留痕；
4. 全部行为有 pytest 锁定（测试/test_ch48.py + 测试/test_p2.py 可作参照答案）。

**五个循序渐进主线示例回顾**：EX-44-01 两节点 → EX-45-01 条件分支 → EX-46-01 工具循环 → EX-47-01/47-02 持久化恢复 → EX-48-01 人工审批，全部真实运行；第十步起请进入项目二 `综合项目/项目二_日志排障助手`（README 从架构到面试讲法完整走一遍），把本章方法落进生产形态的代码。

**本部分示例运行记录索引**（完整命令、退出码与输出摘要见 `验证报告/运行日志/part08.md`）：

| EX | 文件 | 教学角色 | 运行结果 |
|---|---|---|---|
| EX-43-01 | ex_43_01_chain_vs_graph.py | 链式硬编码之痛 | exit=0，v1/v2 对照输出 |
| EX-43-02 | ex_43_02_first_graph_preview.py | 首张图预览 | exit=0，双路由 + trace |
| EX-44-01 | ex_44_01_minimal_two_nodes.py | 主线①两节点 | exit=0，reducer 追加验证 |
| EX-44-02 | ex_44_02_reducer_semantics.py | 覆盖 vs 追加 vs upsert | exit=0，四组实验 |
| EX-44-03 | ex_44_03_messages_state.py | MessagesState | exit=0，两轮消息序列 |
| EX-45-01 | ex_45_01_conditional_route.py | 主线②条件分支 | exit=0，Mock 分类三路由 |
| EX-45-02 | ex_45_02_loop_and_recursion.py | 循环 + 熔断 | exit=0，第 3 轮通过/limit=5 熔断 |
| EX-45-03 | ex_45_03_send_fanout.py | Send 动态扇出 | exit=0，3 份/1 份自适应 |
| EX-46-01 | ex_46_01_tool_loop.py | 主线③工具循环 | exit=0，两轮 6 条消息演进 |
| EX-47-01 | ex_47_01_persistence_memory.py | 主线④持久化 | exit=0，6 检查点/双线程隔离 |
| EX-47-02 | ex_47_02_persistence_sqlite.py | 跨进程恢复 | exit=0，SQLite 3.1.2 实测 |
| EX-47-03 | ex_47_03_time_travel.py | 时间旅行 | exit=0，重放+分叉 |
| EX-48-01 | ex_48_01_human_approval.py | 主线⑤人工审批 | exit=0，暂停/放行/拒绝序列 |
| EX-48-02 | ex_48_02_side_effect_idempotency.py | 幂等实证 | exit=0，反面 2 次/正面 1 次 |
| EX-49-01 | ex_49_01_parallel_merge.py | 并行归并 | exit=0，2+3=5 |
| EX-49-02 | ex_49_02_subgraph.py | 子图两种接法 | exit=0 |
| EX-50-01 | ex_50_01_stream_modes.py | 三种 stream 模式 | exit=0，帧形对照 |
| EX-50-02 | ex_50_02_retry_and_errors.py | 重试/耗尽/降级 | exit=0，三实验 |
| EX-51-01 | ex_51_01_graph_testing.py | 四层测试演示 | exit=0，4 PASS |

**API 事实基线（1.2.16 实测汇总，供全书其他部分引用）**：`StateGraph/START/END/MessagesState/add_messages` 来自 `langgraph.graph`；`InMemorySaver` 来自 `langgraph.checkpoint.memory`；`Command/interrupt/Send/StateSnapshot/RetryPolicy` 来自 `langgraph.types`；`GraphRecursionError` 来自 `langgraph.errors`；`ToolNode` 来自 `langgraph.prebuilt`；`SqliteSaver` 来自 `langgraph.checkpoint.sqlite`（langgraph-checkpoint-sqlite 3.1.2）。

### 本部分待核实清单（作者声明，勿当已验证事实引用）

1. **PostgresSaver**：官方提供但沙箱无 PostgreSQL 服务，未实测——用法请对照官方文档（langchain-ai.github.io/langgraph）；
2. **`durability` 参数（`'sync'/'async'/'exit'`）**：取值已实测存在，但三种模式的持久化保证细节与默认值未逐项验证；
3. **RemoveMessage**（消息删除）：存在性未在本书环境验证，44.3 只给出方向；
4. **异步 API**（`ainvoke/astream/add_node` 传协程函数）：本书全部用同步 API 验证，异步版行为（含 interrupt 的异步恢复）未逐项测试；
5. **子图内嵌独立 checkpointer**：49.5 提到但未演示，需按官方文档核实；
6. **`interrupt(response_schema=...)` 参数**：1.2.16 签名里存在，用于约束 resume 值的结构，本书未使用、未验证语义；
7. **ToolNode 的 `handle_tool_errors` 自定义回调**：参数存在性已核实，回调协议细节未实测。

### 学完本部分，接下来去哪

- **项目二（综合项目/项目二_日志排障助手）**：把 ch44~ch51 全部构件组装成生产形态（只读工具白名单、审计 JSONL、幂等账本、跨进程恢复演示），并带 14 个 pytest；
- **第九部分（Agent、MCP）**：ch52 的 Workflow vs Agent 决策表会直接引用本章的"控制流三要素"（模型决策/等待/恢复）；ch54 工具治理是项目二白名单与审计的方法论化；
- **第十部分**：ch58 的安全清单（只读账户/白名单/审批沙箱）在项目二已各就各位，届时只需要"对号入座"。



