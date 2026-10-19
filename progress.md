# 进度记录（progress.md）

> 每完成一章/一个部件更新本文件：完成内容、验证结果、未解决问题、下一步。
> 跨会话恢复时：先读本文件，再读 `_meta/`，再继续，不要重做目录。

## 2026-10-19 工程启动

- [x] 环境核查：Python 3.14.7 / pip 26.2.1 / git 2.43.0 / Java 25 + Maven 3.9.10 / 代理出网正常（pypi 200）
- [x] 依赖实际安装并锁定（requirements.txt / requirements-lock.txt），核心版本：
  openai 3.35.1、pydantic 2.14.1、fastapi 0.146.0、langchain 1.4.6、langchain-core 1.6.12、
  langchain-openai 1.7.2、langgraph 1.2.16、langchain-text-splitters 1.1.3、pytest 9.1.1、
  pytest-asyncio 1.4.0、respx 0.23.1、tiktoken 0.14.0、fakeredis 2.40.0、numpy 2.5.4、
  langgraph-checkpoint-sqlite 3.1.2、mcp 1.30.0、langchain-mcp-adapters 0.3.2
- [x] PDF 工具链：weasyprint 70.0 + Noto CJK 字体（中文渲染与文本提取验证通过）
- [x] GitHub 认证核查：PAT（MCP 提供）对已有仓库有 contents/admin 权限；**用户级建仓被拒**（Resource not accessible by personal access token）→ 需要用户手动建空仓库或授权后再推
- [x] 骨架与基座文件：README / syllabus / progress / sources / requirements / _meta(FACTS+STYLE_GUIDE)

## 逐章进度（2026-10-19 全部完成）

| 部件 | 内容 | 状态 | 验证 | 备注 |
|---|---|---|---|---|
| part00 | 前言与全书导读 | ✅ | 文本自检 | 资料核实日期 2026-10-19 |
| part01 | 整体认知与环境 ch01-03 | ✅ | 8 EX+shell 链 / 20 测试 | run_logs/part01.md |
| part02a | Python 基础（上）ch04-08 | ✅ | 28 EX / 33 测试 | 3.14 行为实测修正 |
| part02b | Python 基础（下）ch09-12 | ✅ | 20 EX / 28 测试 | ch12 在线+回退双路径实证 |
| part03 | 工程化与服务 ch13-20 | ✅ | 30 EX / 40 测试 | 真实 Redis/uvicorn/SSE/429 限流 |
| part04 | 模型 API ch21-25 | ✅ | 12 EX / 23 测试 | openai 3.35.1 签名全核实 |
| part05 | Prompt ch26-29 | ✅ | 12 EX / 23 测试 | golden set 回归 |
| part06 | RAG ch30-36 | ✅ | 19 EX / 40 测试 | BM25/RRF/引用/拒答/评估 |
| part07 | LangChain ch37-42 | ✅ | 17 EX / 29 测试 | 1.4.6 API 全实测+历史考古 |
| part08 | LangGraph ch43-51 | ✅ | 19 EX / 49 测试 | 五渐进示例+SqliteSaver+interrupt |
| part09 | Agent/MCP ch52-56 | ✅ | 16 EX / 47 测试 | MCP 规范 2026-07-28 实访核实 |
| part10 | 生产架构 ch57-61 | ✅ | 17 EX / 47 测试 | CI YAML 静态检查 12/12 |
| part11 | 微调边界 ch62-63 | ✅ | 4 EX / 12 测试 | 无真实训练（已声明） |
| part12 | 面试（62 题[模拟题]） | ✅ | 口径对账 | interview/ 8 分片一致 |
| P1 | 文档知识库（projects/p1_doc_kb） | ✅ | 17 测试 + 11 组 curl 证据 | 权限/租户/引用/SSE 全验 |
| P2 | 日志排障助手（projects/p2_log_triage） | ✅ | 14 测试 + 恢复三段证据 | 审批/幂等/审计全验 |
| P3 | Java+Python Agent（projects/p3_java_python_agent） | ✅ | 18 测试 + Java/Python 全链路 | 幂等 replay 实证 |
| 汇总 | 全量 pytest | ✅ | **424 passed**（2026-10-19 复跑） | verification/verification_report.md |
| PDF | exports/ai_application_engineering.pdf | ✅ | 599 页 / 书签 1039 / 文本提取正常 | verification/pdf_check.md |
| 导出 | ai_application_engineering.md / ai_application_code.zip | ✅ | 1.8MB / 650KB | exports/ |

## 未解决问题

1. GitHub 推送：PAT 无用户级建仓权限（内容已就绪，等仓库地址后直推）。
2. 沙箱无 OPENAI_API_KEY：全部 LLM 输出为 Mock/示例输出（全书诚实标注）。
3. Docker/K8s/CI/Postgres/真实模型：未验证项已全部汇总至 verification/verification_report.md 第 6 节。
