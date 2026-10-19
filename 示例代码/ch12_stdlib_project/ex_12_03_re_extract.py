# EX-12-03 | re 正则实战：命名组提取、版本号解析（Java 日志风格）
# 运行：python3 示例代码/ch12_stdlib_project/ex_12_03_re_extract.py
"""完整可运行：一次 compile，处处复用；命名组让正则可读可维护。"""
from __future__ import annotations

import re

# Java 工程师熟悉的日志行：
# 2026-10-19 09:30:01.123 ERROR [order-svc] 订单超时：下游 503
LOG_PATTERN = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})\s+"   # 时间戳
    r"(?P<level>[A-Z]+)\s+"                                     # 日志级别
    r"\[(?P<service>[\w-]+)\]\s+"                               # 服务名
    r"(?P<message>.*)$"                                         # 正文
)

# GitHub tag 名 → 语义化版本号（命名组）
TAG_PATTERN = re.compile(r"^v(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)$")


def parse_log_line(line: str) -> dict[str, str] | None:
    """单行日志 → 结构化 dict；不匹配返回 None（EAFP 调用方决定怎么办）。"""
    m = LOG_PATTERN.match(line)
    return m.groupdict() if m else None


def parse_tag(tag: str) -> tuple[int, int, int] | None:
    """'v1.2.16' → (1, 2, 16)；不合规返回 None。元组天然可排序。"""
    m = TAG_PATTERN.match(tag)
    if not m:
        return None
    return int(m["major"]), int(m["minor"]), int(m["patch"])


def main() -> None:
    print("[1] 命名组解析 Java 风格日志行:")
    line = "2026-10-19 09:30:01.123 ERROR [order-svc] 订单超时：下游 503"
    parsed = parse_log_line(line)
    for key, value in parsed.items():  # type: union-attr  # 教学示例确定能匹配
        print(f"    {key:8} = {value}")
    print("    无法解析的行 →", parse_log_line("free text not a log"))

    print("\n[2] findall / finditer / search 的区别:")
    text = "升级路径: v1.0.0 -> v1.2.16 -> v2.0.0-rc1"
    print("    findall 全部数字版本:", re.findall(r"\d+\.\d+\.\d+", text))
    first = re.search(r"\d+\.\d+\.\d+", text)
    print("    search 只找第一处  :", first.group(0) if first else None)

    print("\n[3] tag 名 → semver 元组（可排序）:")
    tags = ["v0.0.8", "v0.0.7", "v1.2.16", "nightly", "v0.10.2", "v0.9.1"]
    for tag in tags:
        print(f"    {tag:10} → {parse_tag(tag)}")

    print("\n[4] 字符串排序 vs semver 排序（'0.10.2' > '0.9.1' 但 '10'<'9' 字符串序会错）:")
    versions = [parse_tag(t) for t in tags]
    tuples = sorted(v for v in versions if v is not None)
    print("    semver 排序:", [f"v{a}.{b}.{c}" for a, b, c in tuples])
    print("    字符串排序:", sorted(t for t in tags if parse_tag(t)), "← 错误示范")

    print("\n[5] sub 替换：把日志级别打码（脱敏常见操作）")
    masked = LOG_PATTERN.sub(r"\g<ts> *** [\g<service>] ***", line)
    print("   ", masked)


if __name__ == "__main__":
    main()
