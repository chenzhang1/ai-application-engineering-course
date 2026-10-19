# EX-09-03 | 生成器表达式：惰性求值与一次性消费
# 运行：python3 示例代码/ch09_iterators/ex_09_03_genexpr_lazy.py
"""完整可运行：生成器表达式 vs 列表推导式的内存差异；两次消费陷阱。"""
from __future__ import annotations

import sys


def main() -> None:
    n = 1_000_000

    # 列表推导式：立刻把 100 万个数全部算出来放进内存
    list_comp = [x * x for x in range(n)]
    # 生成器表达式：只是"记住怎么算"，一个数都还没算（惰性求值）
    gen_expr = (x * x for x in range(n))

    print(f"列表推导式占用内存: {sys.getsizeof(list_comp):,} 字节")
    print(f"生成器表达式占用内存: {sys.getsizeof(gen_expr):,} 字节")
    print(f"创建 gen_expr 时算过任何数了吗？答案：没有——此刻才惰性地算第一个:")
    print("第一个值:", next(gen_expr))

    # 惰性求值：sum 边要边算，全程内存里只有一个中间值
    total = sum(x * x for x in range(100))  # 生成器表达式作为唯一参数可省外层括号
    print("sum(生成器表达式) 1..99 的平方和:", total)

    # ⚠️ 经典陷阱：生成器是一次性的
    squares = (x * x for x in range(5))
    print("第一次 sum:", sum(squares))   # 正常：30
    print("第二次 sum:", sum(squares))   # 已经耗尽：0（不是报错，更隐蔽！）

    # 处理大数据的惯用法：生成器管道（不产生中间大列表）
    words = ["Hello", "World", "Python", "Stream", "LLM"]
    pipeline = (w.strip().lower() for w in words)
    pipeline = (w for w in pipeline if len(w) > 4)
    lengths = (len(w) for w in pipeline)
    print("管道结果:", list(lengths))


if __name__ == "__main__":
    main()
