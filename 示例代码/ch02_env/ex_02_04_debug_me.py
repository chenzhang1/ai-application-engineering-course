# EX-02-04 | 运行命令: python3 示例代码/ch02_env/ex_02_04_debug_me.py
"""VSCode 断点练习：这个程序有一处边界逻辑 bug，先读代码猜一猜，
再在 moving_average 里打断点验证你的猜想（练习题见教材 ch02 N.9）。

文档声称：window 大于序列长度时，返回"全体数据的平均"这一项。
实际行为是否一致？窗口=10 的输出会给你答案。
"""
from __future__ import annotations


def moving_average(values: list[float], window: int) -> list[float]:
    """滑动平均。window<=0 抛 ValueError；window 大于序列长度时
    按文档应返回全体平均（一项）——请用断点验证真实行为。"""
    if window <= 0:
        raise ValueError(f"window 必须为正整数，收到 {window}")
    result: list[float] = []
    for i in range(len(values) - window + 1):
        chunk = values[i : i + window]
        result.append(sum(chunk) / len(chunk))
    return result


def main() -> None:
    data = [3.0, 5.0, 8.0, 13.0, 21.0, 34.0]
    print("数据     :", data)
    print("窗口=1   :", moving_average(data, 1))
    print("窗口=2   :", moving_average(data, 2))
    print("窗口=10  :", moving_average(data, 10))


if __name__ == "__main__":
    main()
