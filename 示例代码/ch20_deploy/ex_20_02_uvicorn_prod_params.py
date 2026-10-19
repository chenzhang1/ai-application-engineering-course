# EX-20-02 | uvicorn 生产参数核对：用 `uvicorn --help` 验证参数真实存在（不凭记忆写文档）
# 运行：python3 示例代码/ch20_deploy/ex_20_02_uvicorn_prod_params.py
import subprocess
import sys

import uvicorn

# 生产常用参数与一句话语义（具体默认值以 `uvicorn --help` 与官方文档为准）
PARAMS: list[tuple[str, str]] = [
    ("--workers", "进程数：绕过 GIL 的多进程并行；容器内常设 1~2×vCPU，交给编排器水平扩"),
    ("--host", "监听地址：容器内必须 0.0.0.0，否则端口映射不进来"),
    ("--port", "监听端口：与 EXPOSE/Service 对齐"),
    ("--timeout-keep-alive", "keep-alive 空闲超时（秒）：小于 LB 的空闲超时，避免半开连接堆积"),
    ("--limit-concurrency", "并发上限：超过即拒绝，保护下游（配合 ch19 限流思想）"),
    ("--timeout-graceful-shutdown", "优雅停机宽限期：给在途请求留出收尾时间"),
    ("--access-log", "访问日志：排障期开启，稳定后可关（高频日志的成本）"),
]


def main() -> None:
    help_text = subprocess.run(
        [sys.executable, "-m", "uvicorn", "--help"],
        capture_output=True, text=True, check=True).stdout

    print(f"uvicorn 版本：{uvicorn.__version__}\n")
    ok = 0
    for flag, meaning in PARAMS:
        present = flag in help_text
        ok += present
        print(f"  [{'✓' if present else '✗'}] {flag:<26} {meaning}")
    print(f"\n{ok}/{len(PARAMS)} 个参数在本机 uvicorn --help 中实际存在。")
    print("提示：--workers>1 时应用必须可多进程安全运行（无进程内共享可变状态，"
          "限流计数要放 Redis——这正是 ch17 收束演练用 Redis 而非内存字典的原因）。")


if __name__ == "__main__":
    main()
