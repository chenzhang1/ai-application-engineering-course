# 第十部分（ch57~ch61）运行与验证记录

> 验证环境：教材沙箱，Python 3.14.7（pyenv），fastapi 0.146.0 / pydantic 2.14.1 / fakeredis 2.40.0 / numpy 2.5.4（均来自仓库 requirements.txt）。
> 验证日期：2026-10-19。作者：part10 章节作者。
> 诚实边界：沙箱无 OPENAI_API_KEY（全部 LLM 路径为 Mock）、无 Docker、无 GitHub 运行环境（CI YAML 仅静态检查）、无 Kubernetes 集群（探针/K8s 内容为概念+本地演示）、无真实生产流量（59.5.1 参数表数值为工程惯例起点，非压测结论）。

## 1. 示例运行记录（全部真实执行，退出码 0）

| 示例 | 命令 | 退出码 | 输出摘要（已贴入教材） |
|---|---|---|---|
| EX-57-01 | `python3 examples/ch57_arch_boundary/ex_57_01_contract_evolution.py` | 0 | 场景1 V2 响应→V1 客户端解析成功（confidence 被忽略）；场景2 删必填 refs → `missing loc=('refs',)`；场景3 改类型 → `string_type`；四条军规输出 |
| EX-57-02 | `python3 examples/ch57_arch_boundary/ex_57_02_timeout_budget.py` | 0 | 预算树 30→26→22→18 逐级递减；错误配置说明；校验器 ValueError 演示 |
| EX-57-03 | `python3 examples/ch57_arch_boundary/ex_57_03_async_task_contract.py` | 0 | queued→running→succeeded；幂等键二次提交 created=False 同一 job；终态拒绝推进 ValueError；终态取消返回 False |
| EX-58-01 | `python3 examples/ch58_security/ex_58_01_readonly_sandbox.py` | 0 | 合法读取成功；../ 穿越 / 绝对路径 / 符号链接逃逸三类 SandboxViolation；write/execute 方法不存在（False/False） |
| EX-58-02 | `python3 examples/ch58_security/ex_58_02_masking_boundary.py` | 0 | 标准 11 位手机号+邮箱命中；全角/分段两个变体漏报；Mock 模拟 LLM 脱敏误改工号（A1024→"9 开头"） |
| EX-58-03 | `python3 examples/ch58_security/ex_58_03_tool_rbac_audit.py` | 0 | admin 放行 / viewer 越权拒绝 / 未注册工具拒绝 / "我是管理员"话术失效（身份只认 SessionUser）；4 行 JSONL 审计 |
| EX-59-01 | `python3 examples/ch59_stability/ex_59_01_retry_double_billing.py` | 0 | 策略 A 计费 3 次只用 1 份；策略 B 幂等键计费 1 次三次同结果；读超时四行处置决策表 |
| EX-59-02 | `python3 examples/ch59_stability/ex_59_02_backpressure.py` | 0 | 并发 3+队列 2，10 请求 → 完成 5 / 快速拒绝 5；accepted=5 rejected=5 |
| EX-59-03 | `python3 examples/ch59_stability/ex_59_03_semantic_cache_mishit.py` | 0 | 阈值 0.8：'年假有几天'误命中'病假有几天'（相似度 0.866，MockEmbedder 实测）；阈值 0.9：miss |
| EX-59-04 | `python3 examples/ch59_stability/ex_59_04_circuit_breaker.py` | 0 | CLOSED→OPEN（6/10 失败）→HALF_OPEN（探测名额 2）→CLOSED；阶段 5 独立小窗口复现"探测失败重新 OPEN" |
| EX-60-01 | `python3 examples/ch60_observability/ex_60_01_cost_middleware.py` | 0 | 两条 JSONL：trace_id/latency_ms/prompt_tokens/completion_tokens/count_method=tiktoken:cl100k_base/cost_est_yuan（演示价目） |
| EX-60-02 | `python3 examples/ch60_observability/ex_60_02_eval_three_layers.py` | 0 | v1 total=0.60 / v2 total=1.00；在线满意率 0.69→0.86 方向一致；回归门槛通过；badcase 回填后 6 条 |
| EX-61-01 | `python3 examples/ch61_release/ex_61_01_ci_yaml_static_check.py` | 0 | 12/12 项静态特征通过（Mock 纪律/secrets 注入/needs 链等） |
| EX-61-02 | `python3 examples/ch61_release/ex_61_02_readiness_probe.py` | 0 | /healthz 恒 200；Redis 挂 → /readyz 503 且 failed 列出 `redis: ConnectionError: connection refused` |
| EX-61-03 | `examples/ch61_release/github_workflows_ci.yml` | ——（静态文件） | 仅通过 EX-61-01 静态检查；**未在 GitHub 真实触发**（沙箱无 GitHub 运行环境） |

说明：示例输出中的路径（如 `/tmp/tmpxohn5b9g/...`）、job_id（uuid）、时间戳/延迟为每次运行不同的易变值，教材粘贴的是当次真实输出。

## 2. pytest 记录

```text
命令：cd /workspace/ai_application_course && python3 -m pytest tests/test_ch57.py ... tests/test_ch63.py -v
退出码：0
结果（逐文件）：test_ch57=6, test_ch58=10, test_ch59=8, test_ch60=6, test_ch61=5
全量回归：python3 -m pytest tests/  →  424 passed（含其他部分与项目的既有测试，未破坏任何存量测试）
```

覆盖要点：ch57 契约兼容三场景/预算校验/任务幂等与终态；ch58 沙箱越界路径参数化（4 组 evil 输入）/软链逃逸/最小工具面/脱敏命中与已记录漏报/RBAC 拒绝+审计断言；ch59 重复计费 vs 幂等键/背压 5+5/语义缓存误命中与阈值收紧/熔断五次状态迁移；ch60 中间件字段与成本公式自洽/usage 缺失显式记账/评估分数与回归门槛；ch61 CI 静态 12 项+secrets 红线+无硬编码 sk-（!）/就绪与存活分离/清单 ≥15 项（读教材正文校验）。

## 3. 失败与修复过程（真实踩坑）

1. **EX-57-01 场景 2 "删除字段"未触发校验错误**：初版 `refs` 带默认值 `[]`，删除后解析不报错——演示失效。修复：把 refs 改为必填（对应"引用溯源是产品硬承诺"的现实），并在输出中补充"可选字段删除不炸但语义可能变"的边界说明。这本身成了一条教学点。
2. **EX-57-03 终态推进不报错**：`advance()` 的分支未覆盖终态，静默返回。修复：补 else 抛 `ValueError`，输出中出现预期的 "worker 拒绝推进"。
3. **EX-59-01 初版幂等键命不中**：第一版在超时路径上"先抛超时、后记账"，导致账本永远为空、策略 B 也计费 3 次——与真实时序（服务端已生成并计费、结果入账、响应丢失）不符。重写 `FakeLLMBackend.chat`：超时路径先把结果写入幂等账本再抛超时。修复后策略 B 计费 1 次，教学结论成立。
4. **EX-59-04 阶段 5 "探测失败重新 OPEN"不触发**：主熔断器在阶段 4 已恢复 CLOSED，直接 record(False) 只在窗口里记一笔。修复：阶段 5 改用独立的小窗口（window_size=4）熔断器快速复现 open→半开→探测失败→重新打开。
5. **EX-60-01 两处**：①`ModuleNotFoundError: No module named 'examples'`——补 `sys.path.insert` 引导（与全书其他示例一致）；②中间件与端点间 usage 传递初版用"共享 dict + 钩子"绕，重构为 `request.state`（scope 共享），并实测 BaseHTTPMiddleware 下端点写入、中间件可读。
6. **EX-61-02 `from fastapi.status import ...` 报 ModuleNotFoundError**：fastapi 0.146.0 无该导入路径。修复：直接用整数状态码 200/503。
7. **EX-60-02 评估分母硬编码**：`hit_rate` 分母写死 3，实际非拒答样本 4 条（v2 出现 1.33 的荒谬分数）。修复：动态计数 `n_resp`。修复后 v1=0.50 / v2=1.00。
8. **EX-62-01 两处**：①`__post_init__` 的 ValueError 在构造表达式处抛出、未被 try 捕获——改为在 try 内构造；②样本 80 的分支缺失（`100 <= x < 1000` 漏掉 <100）——合并为 `style_format_strict` 单条件分支并输出"几十条精选 > 几百条噪声"。
9. **EX-63-01 两处**：①训练数据对照展示的 zip 变量遮蔽导致 clean/dirty 错位——改为两段分别打印；②judge 判定文案混乱且"15 天"误伤训练外问题——重构 judge(outputs, unseen_idx) 并区分"口径矛盾"与"训练外编造"。
10. **编号与交叉引用**：初稿 ch58~ch63 缺"安装/文件位置/运行命令"小节且尾部编号超出 N.11 模板——按全书模板重排（内容段并入 58.5/59.5/63.5 子节），并全文修正过期引用（如 58.4 位置纪律→58.5.1、ch59.4 表→ch59.5.1）；示例文件内的编号引用同步更新并复跑（ex_59_01/03/04、ex_63_01）。

## 4. 未验证项（诚实清单）

- **CI YAML 未真实运行**：沙箱无 GitHub。EX-61-01 的 12 项检查只验证文本特征；Action 版本、workflow 语法、Environments 行为需读者在真实仓库触发验证。
- **K8s 探针/HPA/Deployment 未验证**：沙箱无集群；61.5 的探针参数（initialDelaySeconds 等）以所用集群版本文档为准。
- **参数表数值未经压测**：59.5.1 全部数值为工程惯例起点；容量公式（59.8）的每个输入需实测。
- **厂商接口差异未实测**：幂等键支持（EX-59-01 策略 B 的前提）、429 的 Retry-After 单位、usage 口径——均按 ch24.5 核实清单读者自查。
- **LLM 路径全部为 Mock**：EX-60-01 的 usage 由 MockLLM 的 tiktoken/近似回退生成；真实模型口径以服务端 usage 为准。
- **故障排查三案例为合成**：现象与排查路径参照真实故障形态构造，数字虚构，已标注。
