# 事实库（所有作者必须遵守）

资料核实日期：2026-10-19（沙箱内实际安装并运行验证）。

## 1. 环境事实

- 沙箱 Python：3.14.7（pyenv）。本书代码全部在该解释器上实际运行验证。
- 教材基准：Python 3.12+，代码兼容 3.10+；语法特性如需更高版本必须标注。
- 沙箱可用：Java 25（mise 安装）、Maven 3.9.10、git 2.43.0、zip、poppler-utils（pdftotext/pdftoppm）。
- 沙箱 **没有** `OPENAI_API_KEY`：任何真实模型调用的"输出"一律写"示例输出（非真实记录）"，并在验证报告注明 Mock 验证。
- Redis：沙箱用 fakeredis 2.40.0（可尝试 apt 安装 redis-server，装上则用真实服务并记录）。
- 数据库：不依赖外部数据库服务；SQL 讲解用 sqlite3（标准库），PostgreSQL 只讲用法差异。
- Docker：沙箱内不可用（可写 Dockerfile，标注"仅静态检查"）。

## 2. 锁定版本（pip 实际安装，勿改勿猜）

openai==3.35.1, pydantic==2.14.1, pydantic-settings==2.16.0,
fastapi==0.146.0, uvicorn==0.54.0, httpx==0.28.1, tiktoken==0.14.0,
langchain==1.4.6, langchain-core==1.6.12, langchain-openai==1.7.2,
langchain-community==0.4.2, langchain-text-splitters==1.1.3,
langgraph==1.2.16, numpy==2.5.4,
pytest==9.1.1, pytest-asyncio==1.4.0, respx==0.23.1, fakeredis==2.40.0,
weasyprint==70.0（仅工具链）

## 3. 已核实的 API 形态（LangChain/LangGraph 1.x，禁止使用 0.x 老写法）

- `from langchain.agents import create_agent`，参数含：model, tools, system_prompt,
  middleware, response_format, state_schema, context_schema, checkpointer, store,
  interrupt_before, interrupt_after, debug, name, cache, transformers。
- `from langgraph.graph import StateGraph, START, END, MessagesState, add_messages`
- `from langgraph.checkpoint.memory import InMemorySaver`
- `from langgraph.types import Command, interrupt, Send, StateSnapshot`
- `from langgraph.prebuilt import ToolNode`
- `from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage, AIMessageChunk`
- `from langchain_core.tools import tool`；`from langchain_core.documents import Document`
- `from langchain_core.runnables import RunnableLambda, RunnablePassthrough`
- `from langchain_text_splitters import RecursiveCharacterTextSplitter`
- `langchain_openai.ChatOpenAI` 支持 `.bind_tools()` / `.with_structured_output()`
- 历史写法（如 `AgentExecutor`、`initialize_agent`、`langchain.chains`）只允许在"历史背景"小节出现并给出替代方式。

## 4. 写作红线

1. 版本号只能引用本文件或 `requirements.txt`，不得凭记忆写版本。
2. 任何 API 不确定时：先 `python3 -c "import inspect; print(inspect.signature(...))"` 核实，再写。
3. 禁止编造：就业承诺、性能指标、"大厂真题"自称为真题。模拟题必须标"模拟题"。
4. 禁止声称未执行过的代码"已运行"。真实输出、示例输出、Mock 输出三选一明确标注。
5. 不把 OpenAI 兼容接口说成功能完全一致；写明支持边界需读者对照厂商文档核实。
6. 官方来源链接优先：docs.openai.com、python.langchain.com、langchain-ai.github.io/langgraph、docs.fastapi.tiangolo.com、docs.pydantic.dev。
7. 作者不确定的点写在章节末"待核实"小节，不得假装确定。

## 5. 术语与对照基线（Java→Python）

- 类型注解 ≠ 编译期类型检查；Pydantic ≠ DTO（是运行时校验）；asyncio ≠ 线程池；
- GIL：CPython 实现细节，按版本说明（3.12 前/3.13 free-threading 实验选项——写时须核实当前状态，不确定就写"以官方发布说明为准"）；
- LangGraph ↔ Spring StateMachine/工作流引擎（对照但强调差异：状态在图上、可持久化、可恢复）；
- 向量检索 ↔ 相似度查询（非 B-tree 等值索引）。
