# ch63 测试 | 数据质量对照模拟（垃圾进垃圾出）、时效/权限边界演示、教学模拟诚实标注
# 运行：cd /workspace/ai_application_course && python3 -m pytest tests/test_ch63.py -v
import examples.ch63_boundary.ex_63_01_garbage_in_garbage_out as gigo
import examples.ch63_boundary.ex_63_02_what_finetune_cannot as cannot
from examples.ch63_boundary.ex_63_01_garbage_in_garbage_out import judge
from examples.ch63_boundary.ex_63_02_what_finetune_cannot import (
    QUESTION_NEW_POLICY,
    check_salary_permission,
    rag_answer,
    sft_model,
)


def _outputs(script: list[dict]) -> list[str]:
    from examples.common.llm_client import MockLLM

    llm = MockLLM(script=script)
    return [llm.chat([{"role": "user", "content": q}]).content for q in gigo.TEST_QS]


def test_clean_data_model_scores_full():
    """干净数据模拟：格式一致 + 训练外正确拒答 → 可用率 4/4。"""
    outs = _outputs(gigo.SCRIPT_CLEAN)
    verdicts = judge(outs)
    assert all(v.startswith("✓") for v in verdicts)
    assert outs[-1].startswith("（知识库中没有")            # 拒答而不是编造


def test_dirty_data_model_fails_all():
    """脏数据模拟：格式漂移/错别字/矛盾口径/训练外编造全部出现 → 可用率 0/4。"""
    outs = _outputs(gigo.SCRIPT_DIRTY)
    verdicts = judge(outs)
    assert not any(v == "✓" for v in verdicts)
    assert any("错别字" in v for v in verdicts)
    assert any("矛盾" in v for v in verdicts)
    assert any("编造" in v for v in verdicts)               # 幻觉被脏数据放大


def test_simulation_honestly_labeled_as_teaching_mock():
    """诚实红线：两个示例都必须显著标注'教学模拟/脚本预设，非真实训练'。"""
    import inspect

    for module in (gigo, cannot):
        text = (module.__doc__ or "") + inspect.getsource(module.main)
        assert ("教学模拟" in text and "不是真实训练" in text) or "脚本预设" in text


def test_knowledge_staleness_sft_old_rag_new():
    """时效边界：'微调模型'答旧口径；RAG 流程引用 2026 新文件答新口径。"""
    sft_out = sft_model.chat([{"role": "user", "content": QUESTION_NEW_POLICY}]).content
    assert "2025" in sft_out and "8 天" not in sft_out      # 权重冻在旧知识
    rag_out = rag_answer(QUESTION_NEW_POLICY)
    assert "2026" in rag_out or "HR-2026" in rag_out
    assert "8 天" in rag_out                                 # RAG 检索到新政策


def test_permission_never_lives_in_model():
    """权限边界：权限判定只认会话身份；本人可查、他人不可查（与消息内容无关）。"""
    assert check_salary_permission("zhangsan", "zhangsan") is True
    assert check_salary_permission("alice", "zhangsan") is False
