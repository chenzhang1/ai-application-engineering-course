# ch58 测试 | 只读沙箱拒绝越界路径与放行合法路径、脱敏正则、工具权限矩阵与审计
# 运行：cd /workspace/ai_application_course && python3 -m pytest tests/test_ch58.py -v
import json

import pytest

from examples.ch58_security.ex_58_01_readonly_sandbox import (
    ReadOnlyFileTool,
    SandboxViolation,
)
from examples.ch58_security.ex_58_02_masking_boundary import mask_with_regex
from examples.ch58_security.ex_58_03_tool_rbac_audit import SessionUser, check_permission, invoke_tool


@pytest.fixture()
def sandbox(tmp_path):
    """白名单根目录：docs/policy.md 在内，secret.txt 在外。"""
    root = tmp_path / "workspace"
    (root / "docs").mkdir(parents=True)
    (root / "docs" / "policy.md").write_text("年假政策：5 天。", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("秘密", encoding="utf-8")
    return ReadOnlyFileTool(root)


def test_sandbox_allows_read_within_root(sandbox):
    assert "年假政策" in sandbox.read("docs/policy.md")


@pytest.mark.parametrize("evil", ["../secret.txt", "../../secret.txt", "/etc/passwd", "docs/../../secret.txt"])
def test_sandbox_rejects_path_traversal(sandbox, evil):
    """越界路径（../ 穿越 / 绝对路径）必须全部拒绝。"""
    with pytest.raises(SandboxViolation):
        sandbox.read(evil)


def test_sandbox_rejects_symlink_escape(sandbox, tmp_path):
    """符号链接逃逸：白名单内的软链指向外部 → resolve 后必须被拒。"""
    import os

    os.symlink(tmp_path / "secret.txt", sandbox.root / "innocent.md")
    with pytest.raises(SandboxViolation):
        sandbox.read("innocent.md")


def test_sandbox_has_no_write_or_execute_surface(sandbox):
    """最小工具面：包装器不存在 write/execute/run 方法（接口上消灭，而非运行时拦截）。"""
    assert not hasattr(sandbox, "write")
    assert not hasattr(sandbox, "execute")
    assert not hasattr(sandbox, "run")


def test_mask_regex_hits_standard_phone_and_email():
    masked, kinds = mask_with_regex("手机 13812345678 邮箱 a@b.com")
    assert "13812345678" not in masked and "[手机号]" in masked
    assert "a@b.com" not in masked and "[邮箱]" in masked
    assert set(kinds) == {"手机号", "邮箱"}


def test_mask_regex_documented_misses():
    r"""边界（有意记录的漏报）：全角数字与分段格式不被 \d 模式命中——漏报要可枚举。"""
    _, kinds1 = mask_with_regex("１３８１２３４５６７８")     # 全角
    _, kinds2 = mask_with_regex("138-1234-5678")              # 分段
    assert kinds1 == [] and kinds2 == []


def test_tool_rbac_denies_and_audits(tmp_path):
    """RBAC：越权拒绝 + 未注册拒绝；放行与拒绝都写审计（JSONL 可逐行解析）。"""
    audit = tmp_path / "audit.jsonl"
    admin = SessionUser("alice", "admin")
    viewer = SessionUser("carol", "viewer")

    assert invoke_tool(admin, "query_order", {"order_id": "ORD-1"}, audit, "t-1").startswith("[执行成功]")
    assert invoke_tool(viewer, "restart_svc", {}, audit, "t-2").startswith("[拒绝]")
    assert invoke_tool(admin, "drop_database", {}, audit, "t-3").startswith("[拒绝]")

    records = [json.loads(line) for line in audit.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 3                                   # 拒绝也要留痕
    assert [r["allowed"] for r in records] == [True, False, False]
    assert all("trace_id" in r for r in records)
    allowed, _ = check_permission(viewer, "read_log")          # operator 工具对 viewer 关闭
    assert allowed is False
