# EX-12-04 | argparse：把脚本变成正规 CLI（对照 Java 的 args4j/picocli）
# 运行（三种都试）：
#   python3 examples/ch12_stdlib_project/ex_12_04_argparse_basics.py SO-123 --rate 0.13 --verbose
#   python3 examples/ch12_stdlib_project/ex_12_04_argparse_basics.py SO-123 --rate abc
#   python3 examples/ch12_stdlib_project/ex_12_04_argparse_basics.py --help
"""完整可运行：位置参数 + 选项 + 类型校验 + 自动 help。"""
from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="order-fee",
        description="计算订单含税费用（教学演示：argparse 基本面）",
    )
    # 位置参数（必填）：类似 picocli 的 @Parameters(index = "0")
    parser.add_argument("order_id", help="订单编号，如 SO-123")
    # 选项（可选）：--rate 0.13；type=float 由 argparse 自动做类型校验
    parser.add_argument("-r", "--rate", type=float, default=0.0,
                        help="税率（默认 0，如 0.13 表示 13%%）")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="输出详细过程")
    return parser


def main(argv: list[str] | None = None) -> int:
    # argv=None 时 argparse 自动读 sys.argv[1:]；显式传参是为了测试方便
    args = build_parser().parse_args(argv)
    if args.verbose:
        print(f"[verbose] order_id={args.order_id!r} rate={args.rate!r}")
    if args.rate < 0:
        # argparse 只做"类型"校验，业务规则要自己把关
        print("错误：税率不能为负", flush=True)
        return 2
    total = round(100.0 * (1 + args.rate), 2)
    print(f"订单 {args.order_id} 含税金额: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
