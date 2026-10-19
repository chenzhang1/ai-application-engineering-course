# 综合项目/项目二_日志排障助手/triage/__init__.py
"""P2 生产日志与接口故障排障助手（LangGraph 编排）。

模块结构：
    config.py          运行配置（数据目录/审计文件/操作者）
    state.py           图状态 TriageState
    audit.py           JSONL 审计日志
    tools_readonly.py  受限只读工具（SQLite 只读连接 / JSON 快照 / 白名单校验 / 幂等副作用）
    nodes.py           图节点（解析→预筛→证据→查询→假设→评估→审批→结论）
    graph.py           组图与运行入口
    synth_data.py      合成数据生成（日志/快照/SQLite，确定性）
"""
from triage.config import TriageConfig
from triage.graph import build_triage_graph, run_triage

__all__ = ["TriageConfig", "build_triage_graph", "run_triage"]
