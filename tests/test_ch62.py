# ch62 测试 | 选择树的确定性、三个案例走树合理性、非法输入校验
# 运行：cd /workspace/ai_application_course && python3 -m pytest tests/test_ch62.py -v
import pytest

from examples.ch62_finetuning_boundary.ex_62_01_route_selector import NeedFeatures, decide


def _f(**kw) -> NeedFeatures:
    base = dict(knowledge_private=False, knowledge_update_freq="static",
                needs_citations=False, style_format_strict=False,
                labeled_pairs=0, budget_small=True)
    base.update(kw)
    return NeedFeatures(**base)


def test_deterministic_same_input_same_output():
    """选择树是纯规则：同输入必同输出（可回归、可测试）。"""
    f = _f(knowledge_private=True, needs_citations=True)
    d1, d2 = decide(f), decide(f)
    assert d1.route == d2.route
    assert d1.tree_path == d2.tree_path and d1.reasons == d2.reasons


def test_case_citations_or_updates_lead_to_rag():
    """案例 2 型诉求：需引用 / 知识频繁更新 → RAG。"""
    assert decide(_f(needs_citations=True)).route == "rag"
    assert decide(_f(knowledge_private=True, knowledge_update_freq="daily")).route == "rag"


def test_case_style_with_enough_samples_leads_to_lora():
    """案例 3 型诉求：格式严格 + 样本 ≥1000 → LoRA 候选。"""
    d = decide(_f(style_format_strict=True, labeled_pairs=5000, budget_small=False))
    assert d.route == "sft_lora"


def test_case_small_samples_stay_with_prompt():
    """案例 1 型诉求：格式严格但样本少 → 先 Prompt+few-shot，不跳微调。"""
    d = decide(_f(style_format_strict=True, labeled_pairs=80))
    assert d.route == "prompt"
    assert any("Prompt+few-shot" in p or "补样本" in p for p in d.tree_path)


def test_hybrid_when_knowledge_and_style_both_hard():
    """知识侧与风格侧都硬 → 混合路线（RAG+LoRA），并带'先建评估集'告诫。"""
    d = decide(_f(knowledge_private=True, knowledge_update_freq="daily",
                  style_format_strict=True, labeled_pairs=2000))
    assert d.route == "hybrid_rag_lora"
    assert any("评估集" in c for c in d.caveats)


def test_private_static_knowledge_respects_budget():
    """私有但更新慢的知识：预算紧 → Prompt 直接带知识；预算足 → RAG。"""
    assert decide(_f(knowledge_private=True, budget_small=True)).route == "prompt"
    assert decide(_f(knowledge_private=True, budget_small=False)).route == "rag"


def test_invalid_inputs_raise():
    """非法输入：负样本量 / 非法更新频率必须报错，不许静默。"""
    with pytest.raises(ValueError):
        _f(labeled_pairs=-1)
    with pytest.raises(ValueError):
        _f(knowledge_update_freq="everyday")
