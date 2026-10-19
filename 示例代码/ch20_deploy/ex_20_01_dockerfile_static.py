# EX-20-01 | Dockerfile 静态检查器：逐条核对生产镜像的关键特征（沙箱无 Docker 的替代验证）
# 运行：python3 示例代码/ch20_deploy/ex_20_01_dockerfile_static.py
"""检查点即知识点：多阶段构建 / slim 基础镜像固定版本 / 依赖层先于代码层 /
非 root 用户 / HEALTHCHECK / 固定 uvicorn 生产参数。任何一条缺失都会在这里报错。"""
import re
import sys
from pathlib import Path

DOCKERFILE = Path(__file__).parent / "Dockerfile"

CHECKS: list[tuple[str, str]] = [
    ("多阶段构建（至少两个 FROM）", r"(?mi)^FROM\s+\S+\s+AS\s+\S+"),
    ("基础镜像用 slim 变体", r"(?mi)^FROM\s+python:3\.12-slim(\s+AS\s+\w+)?$"),
    ("构建阶段先 COPY requirements 再安装（层缓存）",
     r"(?s)COPY\s+requirements\.txt.*?pip install"),
    ("pip 安装带 --no-cache-dir（不留缓存层）", r"(?m)^\s*RUN pip install\s+--no-cache-dir"),
    ("从 builder 阶段拷贝安装产物（--from=builder）", r"(?m)^COPY\s+--from=builder\s"),
    ("存在非 root 用户切换", r"(?mi)^USER\s+appuser$"),
    ("存在 HEALTHCHECK", r"(?mi)^HEALTHCHECK\s+"),
    ("HEALTHCHECK 指向 /healthz", r"(?ims)^HEALTHCHECK.*?/healthz"),
    ("CMD 明确 --workers（多进程并行）", r"(?ims)^CMD.*?--workers"),
    ("CMD 明确 --timeout-keep-alive", r"(?ims)^CMD.*?--timeout-keep-alive"),
    ("CMD 绑定 0.0.0.0（容器外可访问）", r"(?ims)^CMD.*?--host.*?0\.0\.0\.0"),
]


def main() -> int:
    text = DOCKERFILE.read_text(encoding="utf-8")
    failures: list[str] = []
    print(f"静态检查目标：{DOCKERFILE}\n")
    for name, pattern in CHECKS:
        ok = re.search(pattern, text) is not None
        print(f"  [{'✓' if ok else '✗'}] {name}")
        if not ok:
            failures.append(name)
    print(f"\n结果：{len(CHECKS) - len(failures)}/{len(CHECKS)} 项通过")
    if failures:
        print("未通过项：" + "；".join(failures))
        return 1
    print("说明：本检查仅验证 Dockerfile 文本特征，不等价于镜像可构建（沙箱无 Docker，"
          "构建验证需读者在有 Docker 的环境执行，以官方构建输出为准）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
