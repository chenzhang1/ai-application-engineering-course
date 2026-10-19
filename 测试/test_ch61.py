# ch61 测试 | CI YAML 静态检查、就绪/存活分离语义、上线检查清单完整性
# 运行：cd /workspace/ai_application_course && python3 -m pytest 测试/test_ch61.py -v
from pathlib import Path

from fastapi.testclient import TestClient

from 示例代码.ch61_release.ex_61_01_ci_yaml_static_check import CHECKS, YAML_PATH, main
from 示例代码.ch61_release.ex_61_02_readiness_probe import create_app


def test_ci_yaml_static_checks_all_pass(capsys):
    """CI YAML：12 项静态特征全部通过（与 ex_61_01 的真实运行一致）。"""
    rc = main()
    out = capsys.readouterr().out
    assert rc == 0
    assert f"{len(CHECKS)}/{len(CHECKS)} 项通过" in out
    assert len(CHECKS) >= 12


def test_ci_yaml_mentions_mock_mode_and_secrets():
    """CI 红线：测试必须跑 Mock 模式；密钥只能来自 secrets 注入。"""
    text = YAML_PATH.read_text(encoding="utf-8")
    assert "LLM_MODE: mock" in text
    assert "${{ secrets." in text
    assert "sk-" not in text                              # 绝不硬编码密钥


def test_readiness_fails_with_503_liveness_stays_200():
    """就绪/存活分离：依赖挂掉 → /readyz 503 且列出故障依赖；/healthz 仍 200。"""
    def broken_redis() -> bool:
        raise ConnectionError("connection refused")

    client = TestClient(create_app({"redis": broken_redis, "llm_config": lambda: True}))
    r = client.get("/readyz")
    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "not_ready"
    assert any("redis" in item for item in body["failed"])   # 告诉运维是谁挂了
    assert client.get("/healthz").status_code == 200         # 进程本身活着，不该重启


def test_readiness_ok_when_all_deps_healthy():
    client = TestClient(create_app({"redis": lambda: True, "llm_config": lambda: True}))
    r = client.get("/readyz")
    assert r.status_code == 200 and r.json()["status"] == "ready"


def test_checklist_file_contains_15_items():
    """上线检查清单（教材 ch61.6）：正文表格必须 ≥15 项可勾选条目。"""
    md = (Path(__file__).resolve().parents[1] / "教材" / "part10_production.md").read_text(encoding="utf-8")
    n_checked = md.count("- [ ]") + md.count("- [x]")
    assert n_checked >= 15
