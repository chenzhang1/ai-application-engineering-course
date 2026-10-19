# EX-55-02 | 最小 MCP stdio server：用官方 python-sdk（mcp 1.30.0）的 FastMCP 编写
# 运行（作为服务端进程被客户端拉起，通常不单独跑）:
#   python3 示例代码/ch55_mcp/ex_55_02_mcp_stdio_server.py
# 单独验证它能启动（stdio 模式下不打印任何东西到 stdout——stdout 是协议通道！）
"""教学版最小 MCP 服务器：暴露 2 个工具 + 1 个资源 + 1 个提示模板。

关键纪律（55.5 逐段解释）：stdio 传输下 stdout 只能承载 JSON-RPC 消息，
任何 print/logging 都必须走 stderr，否则协议帧被污染、客户端解析直接失败。
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

# 创建 MCP 服务器实例（name 会出现在 initialize 握手的 serverInfo 里）
mcp: FastMCP = FastMCP(
    name="plan-tools",
    instructions="生产计划查询工具集：查询计划详情、按产能过滤。数据为教学用内存数据。",
)

# 模拟业务数据（真实场景这里会调 Java/数据库 API）
_PLANS: dict[str, dict] = {
    "P-1001": {"plan_id": "P-1001", "product": "减速器壳体", "qty": 500, "status": "正常"},
    "P-1002": {"plan_id": "P-1002", "product": "转向节", "qty": 1200, "status": "延期"},
}


@mcp.tool()
def get_plan(plan_id: str) -> dict:
    """按计划号查询生产计划详情（产品/数量/状态）。"""
    plan = _PLANS.get(plan_id)
    if plan is None:
        raise ValueError(f"计划 {plan_id} 不存在")  # MCP 会把异常转成协议级错误响应
    return plan


@mcp.tool()
def list_delayed_plans() -> list[dict]:
    """列出所有处于延期状态的生产计划。"""
    return [p for p in _PLANS.values() if p["status"] == "延期"]


@mcp.resource("plan://{plan_id}")
def plan_resource(plan_id: str) -> str:
    """把计划详情暴露为可订阅的资源（resources 能力演示）。"""
    return str(_PLANS.get(plan_id, {}))


@mcp.prompt()
def delay_analysis(plan_id: str) -> str:
    """生成"延期分析"提示模板（prompts 能力演示：给人/给模型复用的提问骨架）。"""
    return f"请分析生产计划 {plan_id} 的延期原因，并给出恢复建议。"


if __name__ == "__main__":
    # stdio 传输：从 stdin 读 JSON-RPC，往 stdout 写 JSON-RPC（errlog 已被 SDK 重定向到 stderr）
    mcp.run(transport="stdio")
