# 第十一部分（ch62~ch63）运行与验证记录

> 验证环境：教材沙箱，Python 3.14.7（pyenv），examples/common/llm_client.py（MockLLM script 模式）。
> 验证日期：2026-10-19。作者：part11 章节作者。
> 本部分的特殊诚实边界：**不提供训练实操**——没有真实训练、没有 GPU、没有训练框架调用；两个示例都是"规则/脚本模拟"，演示的是问题归属与因果方向，不代表任何真实训练结果。所有输出在教材中均已标注"教学模拟"。

## 1. 示例运行记录（全部真实执行，退出码 0）

| 示例 | 命令 | 退出码 | 输出摘要（已贴入教材） |
|---|---|---|---|
| EX-62-01 | `python3 examples/ch62_finetuning_boundary/ex_62_01_route_selector.py` | 0 | 案例 1（语气统一，样本 80）→ prompt；案例 2（制度问答，引用+weekly）→ rag；案例 3（结构化抽取，5000 对）→ sft_lora；每案例输出特征/路径/理由/边界；非法输入（负样本量、非法更新频率）两条 ValueError |
| EX-63-01 | `python3 examples/ch63_boundary/ex_63_01_garbage_in_garbage_out.py` | 0 | clean_model 可用率 4/4（含训练外正确拒答）；dirty_model 可用率 0/4（格式漂移/口径矛盾 15 天/错别字"发标电字开据"/训练外编造换货流程） |
| EX-63-02 | `python3 examples/ch63_boundary/ex_63_02_what_finetune_cannot.py` | 0 | 实验 A：'2026 新版年假政策'——"微调模型"答 2025 旧口径 5 天，RAG 引用 HR-2026-011 答 8 天；实验 B：alice 查张三薪资单 → 代码层 allowed=False；结论对照表（时效/幻觉/权限 × 能否解决 × 正确工具） |

说明：EX-63-01/02 的"模型回答"由 MockLLM script 预设——脚本内容是教学设计，非训练产物；该标注在示例 docstring、运行输出首行、教材正文三处重复出现。

## 2. pytest 记录

```text
命令：cd /workspace/ai_application_course && python3 -m pytest tests/test_ch62.py tests/test_ch63.py -v
退出码：0
结果：test_ch62=7, test_ch63=5
全量回归：python3 -m pytest tests/  →  424 passed（未破坏任何存量测试）
```

覆盖要点：ch62 选择树确定性（同输入同输出）/三案例路线合理性/混合路线/预算对路线的影响/非法输入报错；ch63 干净数据 4/4 与脏数据 0/4（含错别字/矛盾/编造三类断言）/教学模拟诚实标注存在性（两个模块的 docstring+main 源码必须含"教学模拟"+"不是真实训练"）/时效对照（SFT 旧口径无 8 天、RAG 新口径有 8 天）/权限只认会话身份。

## 3. 失败与修复过程（真实踩坑）

1. **EX-62-01 非法输入在 try 外构造**：初版 `for bad in (NeedFeatures(...), ...)` 的构造发生在 try 块外，第一个负样本量直接让脚本以 traceback 退出。修复：改为 dict 列表 + try 内 `NeedFeatures(**bad)` 构造。
2. **EX-62-01 样本 <100 分支缺失**：`elif f.style_format_strict and 100 <= f.labeled_pairs < 1000` 漏掉 80 样本的情形，走到"无风格硬约束"的 else，路径文案与事实矛盾。修复：合并为 `elif f.style_format_strict` 单条件，理由文案区分"几十条精选 > 几百条噪声"。
3. **EX-63-01 训练数据对照展示错位**：初版用 `for (qc, _), (qd, _) in zip(...)` 打印，`_` 变量遮蔽导致 clean 行显示的是 dirty 的答案。修复：clean/dirty 两段分别独立打印（TRAIN_CLEAN[:2] / TRAIN_DIRTY[:2]）。
4. **EX-63-01 judge 判定混淆**："15 天"关键字会同时命中"口径矛盾"与训练外的编造答案；判定说明的拼接逻辑产生空括号。修复：judge(outputs, unseen_idx=3) 显式区分——训练内索引才报"口径矛盾"，unseen 索引报"训练外编造"。
5. **测试 test_simulation_honestly_labeled 初版实现绕**：用 `__import__("inspect")` 内联取源码，可读性差且在 frozen dataclass 场景脆弱。修复：标准 `import inspect` + `inspect.getsource(module.main)`，断言 docstring+main 源码同时含"教学模拟"与"不是真实训练"。
6. **编号与交叉引用同步**：按全书 N.1~N.11 模板重排（新增 63.4 示例总览、63.6/62.6 安装三件套；数据质量并入 63.5.1、边界声明并入 63.5.2），示例文件与教材正文中的编号引用（ch63.4→ch63.5.1 等）同步更新并复跑。

## 4. 未验证项（诚实清单）

- **无真实训练**：本部分没有任何 GPU/训练框架/SFT 实操；"数据质量→输出质量"的方向性结论是数据工程共识+脚本演示，**量化差异必须由读者在自己的评估集上实测**（ch62.5 依据三、ch63.5.1）。
- **LoRA/全量微调效果对比未验证**：不给任何量化结论；"接近全量"在具体任务上需实测。
- **选择树为规则推导**：输出是路线候选与理由，未经过真实项目数据验证；三个案例为合成案例。
- **成本量级不给数字**：吞吐/单价/重训次数等均要求按厂商报价与实测获取（62.5 依据三的框架）。
- **"微调降低幻觉"的研究进展**：本文未引量化结论，采用前以最新论文与自测为准（63.11 待核实）。
