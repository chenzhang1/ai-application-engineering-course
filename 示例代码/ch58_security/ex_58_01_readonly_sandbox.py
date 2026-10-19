# EX-58-01 | 只读沙箱工具包装器：文件系统白名单 + 路径穿越防护 | 运行: python3 示例代码/ch58_security/ex_58_01_readonly_sandbox.py
"""完整可运行（纯标准库，离线）：把"允许 LLM 触碰的文件系统"收进一个白名单沙箱。

设计原则（本章正文展开）：
  1) 最小工具面：包装器只暴露 read()——不存在 write/execute 方法，从接口上消灭
     "写文件/执行命令"的可能，而不是"运行时拦截坏调用"；
  2) 路径规范化后校验：先 resolve()（展开 ..、符号链接、相对路径），再校验必须在
     白名单根目录内——同时挡住 ../ 穿越、绝对路径注入、符号链接逃逸三种手法；
  3) 拒绝理由可审计：每次拒绝抛 SandboxViolation，消息里带原始请求与原因，进审计日志。

边界：这是"进程内教学沙箱"，防的是模型/用户越界路径；生产上若要跑不可信代码，
需要操作系统级隔离（子进程 + 无网络 + 独立用户 → 容器 → 微 VM），见 58.5 沙箱等级表。
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path


class SandboxViolation(PermissionError):
    """请求越出白名单边界。继承 PermissionError：调用方按权限错误统一处理。"""


class ReadOnlyFileTool:
    """只读文件工具：LLM 能看到的全部接口就是 read(path) 一个方法。"""

    def __init__(self, allowed_root: Path) -> None:
        self.root = allowed_root.resolve()   # 根目录本身先规范化（防根路径自己带 ..）

    # -- 路径校验：全部拒绝理由都从这里产生 --------------------------------
    def _validate(self, requested: str) -> Path:
        if not requested.strip():
            raise SandboxViolation(f"拒绝：路径为空")
        p = (self.root / requested).resolve()     # resolve 展开 ../、symlink、相对段
        if not p.is_relative_to(self.root):       # 3.9+；不在白名单内一律拒绝
            raise SandboxViolation(f"拒绝：{requested!r} 解析后越出白名单根目录 {self.root}")
        return p

    # -- 唯一暴露给 LLM 的能力 --------------------------------------------
    def read(self, requested: str) -> str:
        p = self._validate(requested)
        if not p.is_file():
            raise FileNotFoundError(f"文件不存在：{requested}")
        return p.read_text(encoding="utf-8")

    def describe_for_llm(self) -> dict[str, str]:
        """注册给模型时的工具 schema：只有 read，参数只有 path（模型无从请求写/执行）。"""
        return {"tool": "read_file", "params": {"path": "相对白名单根目录的路径"},
                "description": "只读检索白名单目录内的文本文件"}


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "workspace"
        (root / "docs").mkdir(parents=True)
        (root / "docs" / "policy.md").write_text("年假政策：入职满一年 5 天。", encoding="utf-8")
        secret = Path(tmp) / "secret.txt"
        secret.write_text("数据库密码=不给你看", encoding="utf-8")

        tool = ReadOnlyFileTool(root)
        print(f"[沙箱] 白名单根目录：{root}")

        print("\n── 合法请求：读白名单内文件 ──")
        print(f"    read('docs/policy.md') → {tool.read('docs/policy.md')}")

        print("\n── 攻击 1：../ 穿越（经典路径遍历）──")
        try:
            tool.read("../../secret.txt")
        except SandboxViolation as exc:
            print(f"    SandboxViolation: {exc}")

        print("\n── 攻击 2：绝对路径注入 ──")
        try:
            tool.read(str(secret))            # /tmp/.../secret.txt
        except SandboxViolation as exc:
            print(f"    SandboxViolation: {exc}")

        print("\n── 攻击 3：符号链接逃逸（白名单内放一个指向外面的软链）──")
        link = root / "innocent.md"
        os.symlink(secret, link)              # 名字无害，指向白名单外
        try:
            tool.read("innocent.md")
        except SandboxViolation as exc:
            print(f"    SandboxViolation: {exc}（resolve() 展开了软链的真实目标）")

        print("\n── 攻击 4：想写文件 / 想执行命令？接口上就不存在 ──")
        print(f"    工具注册给模型的 schema：{tool.describe_for_llm()}")
        has_write = hasattr(tool, "write")
        has_exec = hasattr(tool, "execute") or hasattr(tool, "run")
        print(f"    包装器有 write 方法？{has_write}  有 execute/run 方法？{has_exec}")
        print("    结论：最小工具面（只暴露 read）+ 路径规范化校验（resolve + is_relative_to）")
        print("          + 拒绝可审计（SandboxViolation 消息进审计日志）= 只读沙箱三件套。")


if __name__ == "__main__":
    main()
