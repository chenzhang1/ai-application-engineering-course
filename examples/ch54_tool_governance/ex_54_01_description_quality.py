# EX-54-01 | 描述质量对工具选择的影响：同一批请求，只改描述做对照实验
# 运行: python3 examples/ch54_tool_governance/ex_54_01_description_quality.py
"""完整可运行（纯标准库，无模型调用，确定性）：

工具描述（description）是模型选择工具的唯一依据（ch39 讲过 schema 三件套，
本章从"治理"角度量化它）。本例做一组对照实验：
    同一批 8 个业务请求 + 同一组 6 个工具，
    A 组用"敷衍描述"（动词含糊、职责重叠、不写参数格式），
    B 组用"结构化描述"（职责一句话 + 参数格式 + 适用边界），
    比较确定性匹配器（模拟"模型按描述匹配请求"的教学替身）的误选率。

匹配器两条规则（真实模型选择依据的教学简化）：
    ① 中文语义 2-gram 重叠：请求与描述的中文词面重叠（ASCII 编号/日期剔除，
       避免"P-1002"这类编号造成的假相关）；
    ② 参数格式线索：请求里出现编号/日期（WO-2091、2026-03-18）时，描述里
       写明了对应格式（"WO-开头"、"YYYY-MM-DD"）的工具获得加成——
       真实模型同样依赖描述中的参数格式线索来对号入座。

结论预告：不改一行工具代码，只重写描述，误选率显著下降——
这是所有工具治理动作里性价比最高的一项（54.3 的治理清单把它排第一）。
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# ---- 工具集：同一组函数，两份描述 -------------------------------------------------
# A 组：敷衍描述——真实代码评审里最常见的样子（抄函数名 + 空话）
TOOLS_BAD: dict[str, str] = {
    "query_plan": "查询生产计划，处理计划相关业务",
    "query_workorder": "查询工单，处理工单相关业务",
    "submit_adjustment": "提交调整，处理调整相关业务",
    "query_material": "查询物料，处理物料相关业务",
    "export_report": "导出报表，处理报表业务",
    "search_history": "搜索历史，处理历史业务",
}
# B 组：结构化描述——职责 + 参数格式 + 边界（何时该用/不该用）
TOOLS_GOOD: dict[str, str] = {
    "query_plan": "按日期(YYYY-MM-DD)查询当日生产计划列表（计划号/产品/数量/状态）。"
                  "只读。查单个计划详情用 query_plan，不要用它查工单。",
    "query_workorder": "按工单号(WO-开头)查询单个工单的完成数量与状态。只读。"
                       "不知道工单号时先用 query_plan 找到计划再反查。",
    "submit_adjustment": "提交生产计划调整（写操作！）：把计划数量改成 new_qty。"
                         "参数 plan_id、new_qty(整数)、reason(必填)。仅低风险(≤计划量20%)可直接提交。",
    "query_material": "按物料编码(MAT-开头)查询库存与在途量。只读。",
    "export_report": "导出指定月份(YYYY-MM)的排产报表为 CSV。异步，返回下载链接。",
    "search_history": "按关键词搜索过去 90 天的计划调整记录（谁在什么时候改过什么）。只读。",
}

REQUESTS: list[tuple[str, str]] = [
    # (请求文本, 期望工具)
    ("帮我看看 2026-03-18 有哪些生产计划", "query_plan"),
    ("工单 WO-2091 完成了多少", "query_workorder"),
    ("P-1002 要改成 1500 件，原因是客户加急", "submit_adjustment"),
    ("MAT-309 的库存还剩多少", "query_material"),
    ("把 2 月的排产报表导出来", "export_report"),
    ("上个月有没有人改过 P-1002", "search_history"),
    ("WO-2091 的状态是什么", "query_workorder"),
    ("查一下今天的计划", "query_plan"),
]

# 剔除 ASCII（编号/日期）后的中文 2-gram；单字请求退化为单字
_CJK_RE = re.compile(r"[\u4e00-\u9fff]+")
_DATE_RE = re.compile(r"\d{4}-\d{2}(?:-\d{2})?")
_CODE_RE = re.compile(r"\b([A-Z]{1,6})-\d+\b")
_FMT_RE = re.compile(r"YYYY-MM(?:-DD)?|\b([A-Z]{1,6})-\b")


def _cjk_grams(text: str) -> set[str]:
    grams: set[str] = set()
    for seg in _CJK_RE.findall(text):
        if len(seg) == 1:
            grams.add(seg)
        else:
            grams.update(seg[i:i + 2] for i in range(len(seg) - 1))
    return grams


def _format_clues(text: str) -> set[str]:
    """请求/描述中的"格式线索"：日期（2026-03-18 或 YYYY-MM-DD）→ YYYY-MM；
    编号（WO-2091 或 WO-开头）→ 字母前缀 WO-。两种写法归一到同一个键。"""
    clues: set[str] = set()
    if _DATE_RE.search(text) or "YYYY-MM" in text:
        clues.add("YYYY-MM")
    for m in _CODE_RE.finditer(text):
        clues.add(m.group(1) + "-")
    for m in _FMT_RE.finditer(text):
        prefix = m.group(1)
        clues.add((prefix + "-") if prefix else "YYYY-MM")
    return clues


def pick_tool(tools: dict[str, str], request: str) -> str:
    """确定性工具选择器（教学替身）：
    得分 = 中文 2-gram 重叠数 + 格式线索命中数（每条 +2）；平分取先声明者。"""
    req_grams = _cjk_grams(request)
    req_clues = _format_clues(request)
    best, best_score = "", -1
    for name, desc in tools.items():
        score = len(req_grams & _cjk_grams(desc))
        if req_clues:
            desc_clues = _format_clues(desc)
            score += 2 * len(req_clues & desc_clues)
        if score > best_score:
            best, best_score = name, score
    return best


@dataclass
class MatchReport:
    """一次对照实验的结果。"""

    label: str
    correct: int
    wrong: int
    wrong_cases: list[str]


def run_experiment(label: str, tools: dict[str, str]) -> MatchReport:
    correct, wrong_cases = 0, []
    for req, expected in REQUESTS:
        got = pick_tool(tools, req)
        if got == expected:
            correct += 1
        else:
            wrong_cases.append(f"「{req}」→ 选了 {got}（期望 {expected}）")
    return MatchReport(label, correct, len(REQUESTS) - correct, wrong_cases)


def main() -> None:
    print("== 工具描述对照实验（同一组工具、同一批请求，只改描述）==")
    bad = run_experiment("A 敷衍描述", TOOLS_BAD)
    good = run_experiment("B 结构化描述", TOOLS_GOOD)
    for rep in (bad, good):
        print(f"\n[{rep.label}] 正确 {rep.correct}/8，误选 {rep.wrong}/8")
        for w in rep.wrong_cases:
            print(f"  ✗ {w}")
    print(f"\n结论：只重写描述（职责+参数格式+边界），误选 {bad.wrong}/8 → {good.wrong}/8。")
    print("治理含义：描述不是注释，是模型读的'接口文档'——评审工具代码时连描述一起评审。")
    print("注意边界：本实验用确定性匹配器代替模型（教学替身）；真实模型的错误模式不同，")
    print("但'描述含糊→选择漂移'的方向一致，生产以线上误选率回归为准（54.9 练习 2）。")


if __name__ == "__main__":
    main()
