# Part05 运行日志（第五部分 ch26~ch29 Prompt 与上下文工程）

- 执行环境：沙箱 Linux，Python 3.14.7（pyenv），CI=true 非交互；LLM 演示统一使用第四部分交付的 `examples/common/llm_client.py`（LLM_MODE=mock 默认离线）。
- 核实日期：2026-10-19。沙箱无 OPENAI_API_KEY：涉及"模型行为差异"的对照（随口 prompt vs 模板、zero-shot vs few-shot、注入失守 vs 拒绝）由脚本化 MockLLM 驱动，教材逐处标注"Mock 运行输出/示例输出（非真实记录）"；确定性程序（token 计数、截断/摘要算术、白名单正则、签名核实、pytest 护栏）为真实执行。

## 1. 示例运行记录（12 个 EX 全部真实执行，退出码 0）

| EX | 文件 | 关键输出摘要 |
|---|---|---|
| EX-26-01 | examples/ch26_prompt/ex_26_01_template_parts.py | 随口 prompt 输出散文 vs 三段式输出固定 JSON（脚本模拟差异，已标注）；渲染后 system 消息含角色/约束/输入数据三段 |
| EX-26-02 | examples/ch26_prompt/ex_26_02_few_shot.py | zero-shot 68 字符输出"换货" vs few-shot 216 字符输出"退款"（脚本模拟）；成本提醒多 148 字符 |
| EX-26-03 | examples/ch26_prompt/ex_26_03_format_guard.py | 第 1 次缺 order_id → Pydantic missing 错误真实抛出 → 错误翻译回传 → 第 2 次通过；重试上限 3 |
| EX-27-01 | examples/ch27_history/ex_27_01_window_truncate.py | 10 条 209 token → 截断后 5 条 115 token（省 94）；"换货"恰好在被丢第 4 条（信息损失演示） |
| EX-27-02 | examples/ch27_history/ex_27_02_summary_compress.py | 纯截断 51 token（丢事实）vs 摘要压缩 159 token（摘要 91 token，事实保留）；策略对照表 |
| EX-27-03 | examples/ch27_history/ex_27_03_token_budget.py | demo-16k 预算表 10%/45%/30%/15%；当前占用 119/63/21 全 OK；输入侧合计 203 |
| EX-28-01 | examples/ch28_prompt_tests/ex_28_01_prompt_regression.py | golden set：v1 通过 4/5（口径漂移被抓）vs v2 通过 5/5；断言引擎含 JSON 合法性 + must_contain/must_not |
| EX-28-02 | examples/ch28_prompt_tests/ex_28_02_version_compare.py | v1 歧义"处理订单"→取消+退款（脚本模拟高危理解）vs v2 唯一动作"已改期"；版本管理四实践 |
| EX-28-03 | examples/ch28_prompt_tests/ex_28_03_injection_demo.py | 无防护版输出系统提示词（脚本模拟失守）vs 防护版输出被程序侧白名单放行；"提示词不是权限控制"四条边界 |
| EX-29-01 | examples/ch29_ai_collab/ex_29_01_explain_code.py | 裸问题泛泛一句 vs 三要素模板产出三段结构化解释（脚本模拟） |
| EX-29-02 | examples/ch29_ai_collab/ex_29_02_error_signals.py | 5 信号清单；信号 1 自动化核查真实执行：create 签名拒绝 ['api_version', 'max_retries'] |
| EX-29-03 | examples/ch29_ai_collab/ex_29_03_guard_generated.py | AI 第一版 dict 列表真实 TypeError（cannot use 'dict' as a dict key）；修复版 3/3 全绿 |

## 2. pytest 汇总

命令：`cd /workspace/ai_application_course && python3 -m pytest tests/ -q`

最终结果摘要行：

```
184 passed in 14.51s
```

本部分新增：tests/test_ch26.py 4 个、test_ch27.py 4 个、test_ch28.py 5 个、test_ch29.py 5 个（合计 18 个；与 part04 的 45 个 + 基座 17 个共同构成新增 63 个，既有 121 个测试未破坏）。

golden set 的 pytest 接入形态：`test_ch28.py` 直接复用 EX-28-01 的 `run_suite`，断言"v1 恰好 4/5（回归引擎能抓口径漂移）、v2 全过"——Mock 阶段测试的是测试设施本身；接真实模型后同一套断言即 CI 门槛。

## 3. 失败与修复过程（真实踩坑记录，与 part04 日志互补）

1. **EX-28-01 模板 KeyError: '"label"'**：PROMPTS 里 JSON 示例未双大括号。修复 `{{"label": ...}}`；与 EX-26-01 的 `KeyError: '"category"'` 同源，均写进 ch26.7 排错首位。
2. **EX-29-02 核查器断言修正**：预期只拒 `api_version`，实际连 `max_retries` 一起拒（它属于客户端构造参数）——修正断言并把"参数张冠李戴"升格为教学点。
3. **EX-29-03 修复版自身 AttributeError**：`x.items()` 对 str 崩；改为 try-hashable/except-unhashable 双路径；verdict 判定最初把"第一版故意失败"的结果算进修复版结论（显示"仍有失败"），改为只看修复版三条断言。
4. **tests/test_ch23 规则模式整合轮**：脚本模式与规则模式的第 2 轮行为不同（脚本=预设回答；规则=Mock 整合工具结果），拆成两个测试分别断言；整合轮断言 `not has_tool_calls`（不死循环）。
5. **ch26 few-shot 示例格式断言**：`FEW_SHOT.count("输出：") == 3` 锁定三个示例，防止后续改示例时数量漂移未被发现。

## 4. 未验证项（诚实清单）

1. 真实模型上三组对照的实际效果差（三段式提升幅度、few-shot 口径钉死效果、注入失守率）：全部为脚本模拟，教材已逐处标注；上线前用 golden set 在真实模型实测（CI 夜间任务）。
2. 摘要压缩的"小模型调用"路径：EX-27-02 用规则模板生成摘要（生产中为一次真实模型调用），该调用本身未验证。
3. ch28.5 的发布链路（配置中心/灰度/回滚）为工程规范描述，未在本书沙箱搭建真实配置中心。
4. ch29 信号 2 的 LangChain 1.x 替代写法详情：按 FACTS 留待第七部分按官方文档展开。
