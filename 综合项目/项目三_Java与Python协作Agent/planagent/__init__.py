# 综合项目/项目三_Java与Python协作Agent/planagent/__init__.py
"""项目三：Java + Python 协作的业务 Agent（生产计划查询与异常分析）。

包结构：
    audit.py       审计 JSONL（who/when/what/outcome，与 ch54 同形状）
    tools_layer.py Java 客户端 + 工具层（参数校验/权限/幂等键/业务规则）
    agent_core.py  规则模型 + create_agent（含 HITL 审批中间件）
    task_store.py  异步任务状态机（202 + task_id + 轮询 + 取消）
    main.py        FastAPI 入口（create_app 工厂，便于测试注入）
"""
