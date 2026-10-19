# ch57 测试 | 契约演进兼容性、超时预算分解、异步任务状态机与幂等
# 运行：cd /workspace/ai_application_course && python3 -m pytest tests/test_ch57.py -v
import pytest
from pydantic import ValidationError

from examples.ch57_arch_boundary.ex_57_01_contract_evolution import AIReplyV1, AIReplyV2
from examples.ch57_arch_boundary.ex_57_02_timeout_budget import Budget
from examples.ch57_arch_boundary.ex_57_03_async_task_contract import JobStatus, TaskStore


def test_contract_add_field_with_default_is_compatible():
    """R1：新增字段带默认值 → 旧客户端解析新响应必须成功。"""
    v2_payload = {"answer": "ok", "refs": ["d1"], "confidence": 0.9}
    old_view = AIReplyV1.model_validate(v2_payload)
    assert old_view.answer == "ok"
    assert old_view.refs == ["d1"]


def test_contract_remove_required_field_breaks():
    """R2：删除必填字段 → 旧客户端解析必须报错（破坏契约要被发现，而不是静默）。"""
    with pytest.raises(ValidationError):
        AIReplyV1.model_validate({"answer": "ok"})


def test_contract_new_client_parses_v2():
    """新客户端（V2 模型）解析缺省新字段的旧响应 → 用默认值，不炸。"""
    v = AIReplyV2.model_validate({"answer": "ok", "refs": []})
    assert v.confidence == 0.0


def test_budget_children_must_be_less_than_total():
    """超时预算：子步骤之和 >= 总预算必须报错（配置期拦住事故）。"""
    with pytest.raises(ValueError):
        Budget("业务", 10.0).allocate(("AI", 10.0))
    # 正常分配：逐级递减
    children = Budget("网关", 30.0).allocate(("业务", 26.0))
    assert children[0].total_s == 26.0
    assert children[0].total_s < 30.0


def test_task_idempotent_submit_and_lifecycle():
    """异步任务：同一幂等键重复提交返回同一任务；生命周期单向推进。"""
    store = TaskStore()
    job, created = store.submit("batch", {"x": "1"}, "idem-1")
    assert created is True
    again, created2 = store.submit("batch", {"x": "1"}, "idem-1")
    assert created2 is False and again.job_id == job.job_id  # 不重复执行

    assert store.advance(job.job_id) is JobStatus.RUNNING
    assert store.advance(job.job_id) is JobStatus.SUCCEEDED


def test_task_terminal_state_rejects_transition():
    """终态拒绝一切转移：取消后再推进必须抛错；终态任务取消返回 False。"""
    store = TaskStore()
    job, _ = store.submit("batch", {}, "idem-2")
    store.advance(job.job_id)             # RUNNING
    assert store.cancel(job.job_id) is True
    with pytest.raises(ValueError):
        store.advance(job.job_id)         # CANCELLED 是终态，worker 拒绝推进
    done, _ = store.submit("batch2", {}, "idem-3")
    store.advance(done.job_id)
    store.advance(done.job_id)            # SUCCEEDED
    assert store.cancel(done.job_id) is False
