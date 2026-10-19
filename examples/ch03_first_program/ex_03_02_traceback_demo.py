# EX-03-02 | 运行命令: python3 examples/ch03_first_program/ex_03_02_traceback_demo.py
#            （本脚本预期失败，退出码 1——它是用来练习读 traceback 的）
"""教学用：制造一个真实 traceback，学会逐行阅读。

运行结果取决于当前工作目录（CWD）下有没有 config.json：
- 没有 config.json          -> FileNotFoundError（ch03 正文逐行讲解的就是它）
- config.json 内容不是 JSON -> ConfigError（异常链：raise ... from 的真实样子）
- 一切正常                  -> 又会触发除零错误（另一类经典 traceback）

请在专门的练习目录里运行，不要在项目根目录放 config.json。
"""
from __future__ import annotations

import json
from pathlib import Path


class ConfigError(Exception):
    """配置文件不可用。"""


def load_config(path: str) -> dict[str, int]:
    text = Path(path).read_text(encoding="utf-8")  # 文件不存在在这里炸
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        # 异常链：原始原因挂在 __cause__ 上，traceback 会打印两段
        raise ConfigError(f"配置文件 {path} 不是合法 JSON") from exc
    return {"timeout": int(data["timeout"])}


def ratio(timeout: int, limit: int) -> float:
    return timeout / limit


def main() -> None:
    cfg = load_config("config.json")  # 相对 CWD 解析——ch03 讲它为什么重要
    print(ratio(cfg["timeout"], 0))  # 分母写死 0：第二颗雷


if __name__ == "__main__":
    main()
