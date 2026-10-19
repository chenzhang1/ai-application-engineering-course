# 综合项目/项目二_日志排障助手/triage/config.py
"""运行配置：路径全部显式可注入，测试用 tmp_path 隔离。"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]   # 综合项目/项目二_日志排障助手


@dataclass
class TriageConfig:
    """排障助手运行配置。

    data_dir    ：日志/快照/SQLite 所在目录（只读使用）
    audit_path  ：审计日志 JSONL（每次工具调用一行）
    ledger_path ：副作用账本 JSONL（restart 等高风险动作的幂等去重）
    operator    ：审计里的 who（真实系统应来自登录态）
    """

    data_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "data")
    audit_path: Path = field(default_factory=lambda: PROJECT_ROOT / "audit" / "audit.jsonl")
    ledger_path: Path = field(default_factory=lambda: PROJECT_ROOT / "audit" / "actions_ledger.jsonl")
    operator: str = "triage-bot"

    def ensure_dirs(self) -> None:
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
