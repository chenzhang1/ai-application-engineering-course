# 项目一：企业文档知识库（p1_doc_kb）

> 教材第六部分（ch30~ch36）的配套实战项目：入库 → 切分 → numpy 向量检索 → 引用问答 → 权限过滤 → FastAPI + SSE → 评估集 → pytest。
> 全流程在 `LLM_MODE=mock` 下离线可复现（同输入同输出）；`LLM_MODE=real` 需 `OPENAI_API_KEY`（生成路径已按 openai 3.35.1 签名编写，沙箱无 Key 未实调，见"未验证项"）。
> 版本基线：Python 3.14.7 验证（兼容 3.12+）；fastapi 0.146.0、langchain-text-splitters 1.1.3、numpy 2.5.4，全部来自教材仓库 `requirements.txt`。

## 1. 业务目标与非目标

**目标**：给"示例公司 Acme"做一个内部制度问答服务——员工提问（"年假会清零吗"），系统检索公司制度文档，**只依据检索到的证据**回答，并且：

1. 每个回答带引用（`[n]` 标记 + `[doc_id, chunk_id, score]` 明细），可溯源到原文片段；
2. 证据不足时**拒答**而不是编造（分数阈值 + 证据充分性判定双保险）；
3. 多租户 + 部门级权限：无权文档在**检索层**就被过滤，不参与打分、不进上下文、不出现在引用里；
4. 文档可整篇覆盖更新与删除（按 doc_id）；
5. 支持流式输出（SSE），先发引用元信息、再逐片发回答。

**非目标**（教学边界，诚实声明）：

- 不做真实 embedding 模型（MockEmbedder 是"概念词典+哈希词袋"的确定性教学替身）；
- 不做多轮对话（本项目只有单轮问答，历史管理见 ch27）；
- 不做文档解析全家桶（PDF/网页解析在教学示例 ch31 中讲，本项目的合成语料直接用 markdown）；
- 不追求检索性能指标——25 个 chunk 全量扫描足够快，性能讨论见第 9 节。

## 2. 架构与选型

```text
                        ┌────────────────────────────────────────────┐
 data/*.md (12 篇)      │            FastAPI (app/main.py)           │
   │ front-matter       │  POST /ingest   POST /ask   GET /ask/stream│
   ▼                    │  DELETE /docs    GET /health               │
 ingest/loaders.py ──► ingest/cleaner.py ──► ingest/pipeline.py          │
   （加载+校验）          （清洗）              （切分+入库）              │
   │                                                        ▲           │
   ▼                                                        │           │
 ┌──────────────────────── app/kb.py : KnowledgeBase ───────┴─────────┐ │
 │ 检索: ①权限过滤(can_read) → ②numpy 余弦全量打分 → ③词面重排 → top_k │ │
 │ 问答:  拒答双保险(gate1 分数阈值 → gate2 证据充分性判定) → 生成      │ │
 │ 生成:  Mock=抽取式回答 / Real=LLM(编号证据+引用指令)                 │ │
 │ 存储:  内存 dict + JSON 原子落盘(data/vector_store.json)            │ │
 └────────────────────────────────────────────────────────────────────┘ │
          依赖教材共享基座: 示例代码/公共/embeddings.py (get_embedder) │
                          示例代码/公共/llm_client.py (get_llm)       │
                                                          eval/run_eval.py
```

**关键选型与理由**：

| 决策点 | 选择 | 理由（与教材章节呼应） |
|---|---|---|
| 向量检索 | numpy 矩阵点积全量扫描 | 25 个 chunk 无需 ANN 索引；点积即余弦（向量已 L2 归一化）——先把原理写透（ch33） |
| 词面重排 | 2-gram 词面包含度，`fused = 0.5*cos + 0.5*lex` | MockEmbedder 哈希词袋在专业词表外区分度不足（ch33 实测），用词面特征补偿；真实 embedding 下可把权重调回向量主导 |
| 切分 | `RecursiveCharacterTextSplitter(chunk_size=200, chunk_overlap=30)` | langchain-text-splitters 1.1.3；按段落/句子边界递归切分，重叠保上下文（ch32 实测） |
| 权限 | 检索前过滤（can_read → 候选集） | 事后过滤会泄露"存在但不可见"的信息（ch34 红线） |
| 拒答 | gate1 阈值 0.16 + gate2 判定器 | 阈值挡"检索器不自信"，判定器挡"检索器自信但证据答不了"——实测两道闸各拦住过不同的坏例（见 run log） |
| 存储 | 内存 + JSON 原子落盘 | 简单可读、断点可查；生产迁移点见第 8 节 |
| 服务 | FastAPI + StreamingResponse（SSE） | ch17 同款技术栈；SSE 便于前端逐字渲染与引用先行的 UI |

**目录结构**：

```text
p1_doc_kb/
├── README.md            # 本文件
├── app/                 # FastAPI 服务层
│   ├── bootstrap.py     #   教材仓库根路径引导（示例代码.公共 依赖）
│   ├── schemas.py       #   Pydantic 请求/响应契约
│   ├── security.py      #   UserContext + can_read（多租户/部门权限）
│   ├── lexical.py       #   中文 2-gram 词面特征（重排与判定共用）
│   ├── judge.py         #   证据充分性判定（RuleJudge/LLMJudge 双模式）
│   ├── kb.py            #   KnowledgeBase 核心（存储/检索/问答/流式）
│   └── main.py          #   FastAPI 路由（应用工厂 create_app）
├── ingest/              # 入库管线
│   ├── loaders.py       #   markdown + front-matter 加载与校验
│   ├── cleaner.py       #   清洗（换行/HTML 注释/零宽字符/空行）
│   └── pipeline.py      #   批量入库 CLI（python3 -m ingest.pipeline）
├── eval/
│   ├── evalset.jsonl    #   16 条评估用例（14 应答 + 2 应拒答）
│   └── run_eval.py      #   评估脚本（hit@2/关键词/引用/拒答四指标）
├── data/                # 12 篇合成制度文档（acme 租户，含 1 篇 all 部门 FAQ）
└── （测试统一放在教材仓库 测试/test_p1.py，随全书 pytest 一起跑）
```

## 3. 合成数据说明

`data/` 下 12 篇 markdown 全部为**合成的虚构公司制度**（公司"示例公司 Acme"为教学虚构，人名、规则数值均不指向任何真实企业），覆盖 4 类：

- HR（hr 部门）：请假制度、入职清单；
- IT（it 部门）：VPN 指南、密码重置、设备申请；
- 财务（finance 部门）：报销、开票、差旅；
- 行政/安全/公共（admin、security、all）：会议室、办公用品、数据密级、综合 FAQ。

每篇头部 front-matter 是权限与溯源元数据（ch32 元数据设计的落地）：

```markdown
---
doc_id: hr_leave_policy
tenant_id: acme
department: hr
title: 员工请假制度
---
# 员工请假制度（V2.3，2026 年 1 月修订）
...
```

文档刻意写成"一条规则一句话"的密度（每篇 2~4 个小节），既接近真实制度文档，又让切分后每块语义完整、评估关键词可核对。另有 1 篇 `data/faq_common.md` 的 `department: all`（租户内公开），用于演示"公开文档"规则。

## 4. 启动与调用命令

```bash
# 0) 前置：教材仓库根目录（本项目的 embedder/llm_client 依赖 示例代码/公共）
cd /workspace/ai_application_course
pip install -r requirements.txt          # 版本已锁定并实际验证

# 1) 批量入库（合成数据 → 向量库 JSON 落盘）
cd 综合项目/项目一_文档知识库
python3 -m ingest.pipeline
#   换存储位置：P1_STORE_PATH=/tmp/p1_store.json python3 -m ingest.pipeline

# 2) 启动服务（Mock 模式，离线）
LLM_MODE=mock python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8765

# 3) 另开终端调用（完整请求/响应示例见第 5 节）
curl -s http://127.0.0.1:8765/health
curl -s -X POST http://127.0.0.1:8765/ask -H 'Content-Type: application/json' \
  -d '{"question":"年假年底会清零吗","tenant_id":"acme","user_id":"alice","departments":["hr"]}'
curl -s -N "http://127.0.0.1:8765/ask/stream?question=%E5%B9%B4%E5%81%87%E5%B9%B4%E5%BA%95%E4%BC%9A%E6%B8%85%E9%9B%B6%E5%90%97&tenant_id=acme&user_id=alice&departments=hr"

# 4) 评估（不需要起服务）
python3 eval/run_eval.py

# 5) 测试（教材仓库根目录）
cd /workspace/ai_application_course && python3 -m pytest 测试/test_p1.py -v
```

## 5. 请求响应示例

**POST /ask（正常回答 + 引用）**

```json
// 请求
{"question": "年假年底会清零吗", "tenant_id": "acme", "user_id": "alice",
 "departments": ["hr"], "top_k": 3}
// 响应（Mock 运行输出）
{"question": "年假年底会清零吗", "status": "answered",
 "answer": "（Mock·抽取式回答）年假原则上当年使用完毕，每年 12 月 31 日 24 点清零，不可结转到次年。… [1]",
 "refusal_reason": null,
 "citations": [
   {"index": 1, "doc_id": "hr_leave_policy", "chunk_id": "hr_leave_policy#001",
    "score": 0.194, "snippet": "## 年假 年假按工龄计算：工作满 1 年不满 10 年…"},
   {"index": 2, "doc_id": "hr_onboarding_checklist", "chunk_id": "hr_onboarding_checklist#000",
    "score": 0.0623, "snippet": "# 新员工入职清单（V1.4）…"}]}
```

**GET /ask/stream（SSE 事件序列）**

```text
event: meta
data: {"status": "answered", "refusal_reason": null, "citations": [ ...同上... ]}

event: delta
data: {"text": "（Mock·抽取"}

event: delta
data: {"text": "式回答）…"}      ← 共 N 片，拼接 = 完整回答

event: done
data: {"finish_reason": "stop"}
```

**失败路径（三类，均真实运行过，证据见 `验证报告/运行日志/part06.md`）**

| 路径 | 触发方式 | 响应 |
|---|---|---|
| 部门权限拒绝 | finance 用户问年假 | `{"status":"refused","refusal_reason":"below_score_threshold","citations":[]}` |
| 跨租户拒绝 | acme 用户问 beta 文档 | `{"status":"refused","refusal_reason":"evidence_insufficient_judge","citations":[]}` |
| 库里没有的知识 | "程序员节有什么福利" | `{"status":"refused","refusal_reason":"below_score_threshold","citations":[]}` |
| 删除不存在的文档 | `DELETE /docs/xxx` | HTTP 404 `{"detail":"文档 xxx 不存在"}` |

注意跨租户案例的细节：该查询在 acme 可见集里靠余弦分数越过了 gate1（0.16），却被 gate2 的词面判定拦下——**两道闸各司其职**的实证，这正是"双保险"设计的理由。

## 6. 测试与评估说明

**pytest（17 个，位于 `测试/test_p1.py`）**覆盖：入库→chunk 数→JSON 落盘重载一致性、同 doc_id 覆盖更新、删除、检索 top1 命中、租户隔离、部门 ACL、引用结构与编号有效性、无证据拒答、阈值拒答（gate1）、判定器拒答（gate2，降阈值绕过 gate1 验证）、SSE 事件序列（meta→delta*→done）、SSE HTTP 层、API 端点（TestClient）、评估脚本冒烟（四指标 100%）。运行：`python3 -m pytest 测试/test_p1.py -v`。

**评估集（16 条）与指标**：`eval/run_eval.py` 输出——

```text
检索命中率@2：100.00%（16 条用例）
关键词覆盖率：100.00%
引用有效率　：100.00%
拒答正确率　：100.00%
整体通过　　：100.00%
```

口径（ch35 的可计算定义）：hit@2 = expect_doc_id 出现在引用前 2 条；关键词覆盖率 = expect_keywords 全部出现在回答文本；引用有效性 = 回答中 `[n]` 标记 ⊆ 返回的引用编号；拒答正确率 = expect_refused 用例确实 refused 且无引用。**这些是词面级/结构级指标，只能做回归守门**；"答案是否真对"要人工抽检——Mock 抽取式回答直接取自原文句子，人工核对成本低，但真实 LLM 模式下必须保留人工抽检环节。

## 7. 性能 / 成本 / 安全讨论

**性能**：当前规模（25 chunk）检索是 numpy 全量点积，单次 <1ms；千级 chunk 仍可行（64 维 float64 矩阵 ≈ 0.5MB）；十万级必须换 ANN 索引（FAISS/HNSW，见第 8 节迁移点）。入库耗时主要在 embedding 调用（真实模型下是网络 IO，应批量与并发控制，ch13/ch15）。

**成本**：Mock 模式 0 成本。Real 模式单次问答成本 ≈ embedding 1 次（问题文本）+ LLM 1 次（编号证据 prompt，约 1~2k token 输入）。3 个检索块 × 200 字已能把 prompt 控制在预算内（ch27 预算表）；top_k 与 chunk_size 是成本杠杆。

**安全**：
1. 权限在检索层过滤，身份来自请求上下文（生产从 JWT/Session 解析）——**绝不来自问题文本或模型输出**（ch28 红线：提示词不是权限控制）；
2. 拒答优先：宁可"证据不足"也不编造；
3. 间接注入预警：本文档语料可信，若未来接入外部网页/工单（ch31），入库前要做来源白名单与内容审核，且检索内容进上下文时永远标记为"数据段"（ch28）；
4. 审计：每次问答的 citations + refusal_reason 落日志，可回放"模型当时看到了什么"；
5. 密钥：代码零硬编码密钥，real 模式密钥只从 `OPENAI_API_KEY` 环境变量读取。

## 8. 常见故障排查

| 现象 | 原因 | 处置 |
|---|---|---|
| `ModuleNotFoundError: No module named 'examples'` | 项目不在教材仓库内运行，找不到共享基座 | 确认目录位于教材仓库 `综合项目/` 下；`app/bootstrap.py` 会自动向上查找，报错说明目录结构被移动 |
| `real 模式需要 OPENAI_API_KEY` | LLM_MODE=real 但无 Key | 导出 Key，或保持默认 mock |
| 所有查询都拒答（below_score_threshold） | 存储为空 / 换了 embedding 模型没重建索引 | 先跑 `python3 -m ingest.pipeline`；换了模型必须全量重建（新旧向量不可混） |
| 命中错误的文档 | 阈值/权重是按本合成语料校准的，换了语料或真实模型需重新校准 | 用 evalset 重新标定 `ANSWER_SCORE_THRESHOLD` 与 W_VECTOR/W_LEXICAL（ch35：阈值必须用自家语料实测） |
| `GET /ask/stream` 一次性收到全部数据 | 中间层（nginx 等）缓冲了 SSE | 确认 `X-Accel-Buffering: no` 透传、代理关闭响应缓冲 |
| 422 校验错误 | 请求体缺字段 / departments 传了字符串而不是数组 | 对照第 5 节请求示例；GET /ask/stream 的 departments 是逗号分隔字符串 |
| 重启后数据丢了 | 没设 P1_STORE_PATH 时默认写 `data/vector_store.json`，删库重建即可 | 检查该文件是否存在与 mtime |

## 9. 生产迁移点（从教学实现到真实系统）

1. **向量存储**：本实现的存储面收敛在 `KnowledgeBase` 的 `_rebuild_matrix/ingest_doc/delete_doc/save/_load` 几个方法上。生产换 FAISS（单机内存级）或 Milvus/Qdrant/云托管向量库（多副本、过滤查询）时，实现同等接口即可，检索/问答业务层不动。选型维度：规模、过滤需求（权限过滤下推到库）、更新频率、运维成本。FAISS 在本书沙箱未安装（Python 3.14 轮子风险，见 FACTS），只在选型讨论中提及。
2. **Embedding**：MockEmbedder → 真实 embedding API（`RealEmbedder` 已按 openai 3.35.1 签名实现）。换模型 = 全量重建向量 + 重校准阈值；记录模型版本到 chunk 元数据。
3. **权限**：can_read 的部门清单来自 RBAC 系统；过滤条件（tenant_id/department）应下推到向量库的 metadata filter，避免拉全量再过滤。
4. **拒答判定**：RuleJudge → LLMJudge（已实现，real 模式生效），并监控判定器失败率；判定失败按拒答兜底（宁拒不编）。
5. **可观测**：logging → 结构化日志 + trace_id（ch60）；评估集接入 CI（每次改切分参数/阈值/模型都重跑 run_eval，指标回退即拦下）。

## 10. 面试讲法（90 秒版本）

"我做了一个企业制度知识库：入库侧是加载→清洗→RecursiveCharacterTextSplitter 切分（200/30），每块带 doc_id/租户/部门元数据；检索侧用 numpy 自实现余弦检索，因为 embedding 是 mock 的哈希词袋，我加了词面重排做补偿，融合分做 Top-k；问答侧有两个设计我实测验证过：一是拒答双保险——分数阈值拦'检索器不自信'，证据充分性判定拦'检索器自信但证据答不了'，压测时两道闸各拦住过不同的坏例；二是权限在检索前过滤而不是事后删——无权文档不进候选矩阵，不泄露存在性。评估是我自己建的 16 条评估集，算 hit@2、关键词覆盖、引用有效性和拒答正确率，接入 pytest 做回归。这个项目让我把'RAG 答错怎么定位'变成流程：先看 refusal_reason 分流，再看 top-k 分数分布判断是检索问题还是生成问题。"（对应 ch35 验收标准：解释"为什么我的 RAG 答错"并给出至少 3 类定位手段。）

## 11. 扩展方向

1. 多轮追问：把"上一轮引用的文档"带进下一轮检索做查询改写（ch33 概念）；
2. 重排序升级：交叉编码器 rerank（ch33 重排小节的概念落地）；
3. 增量同步：文档变更事件驱动重建，代替整篇覆盖；
4. 反馈闭环：前端"赞/踩"落库，badcase 回填 evalset（ch28/ch35）；
5. 与 Spring Boot 集成：本服务作为内部微服务，Java 侧经网关转发（ch57 的 Python AI 服务 ↔ Spring 模式）。

## 12. 未验证项（诚实清单）

1. `LLM_MODE=real` 的 LLM 生成路径（`_llm_messages` + `get_llm().chat/chat_stream`）与 LLMJudge 的真实模型行为：代码按 openai 3.35.1 已核实签名编写，沙箱无 Key 未实调；
2. 阈值 0.16 与融合权重 0.5/0.5 只对本合成语料 + MockEmbedder 有效，属"用自家语料实测校准"的示范值，不具普遍性；
3. SSE 在真实反向代理（nginx/网关）下的缓冲行为未实测（沙箱直连 uvicorn）；
4. 性能数字为量级推断（25 chunk 场景 <1ms），未做基准测试报告。
