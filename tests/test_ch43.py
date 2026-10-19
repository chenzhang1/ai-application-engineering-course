# tests/test_ch43.py | ch43 为什么需要图
"""覆盖：链式管线的确定性与规则命中、图版预览的路由分流、非法输入。"""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from examples.ch43_graph_intro.ex_43_01_chain_vs_graph import (
    classify,
    normalize,
    pipeline_v1,
    pipeline_v2,
)
from examples.ch43_graph_intro.ex_43_02_first_graph_preview import (
    TicketState,
    auto_pipeline,
    manual_review,
    route_by_gate,
    sensitive_gate,
)


def test_chain_v1_routes_by_keyword() -> None:
    """正常路径：链式管线按关键词走三个通道。"""
    assert "账务通道" in pipeline_v1("发票 抬头 错了")
    assert "技术通道" in pipeline_v1("App 报错")
    assert "通用通道" in pipeline_v1("你们几点上班")


def test_chain_v2_new_rules_take_over() -> None:
    """需求变更路径：敏感词拦截优先于普通分类，VIP 只做加急标记。"""
    assert "人工审核" in pipeline_v2("请查我的银行卡")
    assert "VIP 加急" in pipeline_v2("App 报错", is_vip=True)
    # normalize 是纯函数：非法输入（None）应抛 AttributeError 而不是静默通过
    try:
        normalize(None)  # type: ignore[arg-type]
        raised = False
    except AttributeError:
        raised = True
    assert raised


def test_classify_boundaries() -> None:
    """边界：同时命中两类关键词时按规则顺序取第一类；无命中归 general。"""
    assert classify(normalize("发票报错")) == "billing"     # billing 规则在前
    assert classify(normalize("hello world")) == "general"


def _build_preview_graph():
    g = StateGraph(TicketState)   # 用示例模块里的状态 schema（reducer 在模块级，可解析）
    g.add_node("sensitive_gate", sensitive_gate)
    g.add_node("manual_review", manual_review)
    g.add_node("auto_pipeline", auto_pipeline)
    g.add_edge(START, "sensitive_gate")
    g.add_conditional_edges("sensitive_gate", route_by_gate,
                            {"manual": "manual_review", "auto": "auto_pipeline"})
    g.add_edge("manual_review", END)
    g.add_edge("auto_pipeline", END)
    return g.compile()


def test_graph_preview_same_rules_same_results() -> None:
    """等价性：同一批规则画成图后行为一致，且 trace 记录了完整路径。"""
    app = _build_preview_graph()
    r1 = app.invoke({"text": "发票抬头开错了", "route": "", "trace": []})
    assert r1["route"] == "auto" and r1["trace"][0] == "gate:放行"
    r2 = app.invoke({"text": "请查我的银行卡", "route": "", "trace": []})
    assert r2["route"] == "manual" and r2["trace"][0] == "gate:敏感拦截"
