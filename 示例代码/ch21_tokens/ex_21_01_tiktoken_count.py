# EX-21-01 | tiktoken 计数实验：token ≠ 字符 ≠ 字 | 运行: python3 示例代码/ch21_tokens/ex_21_01_tiktoken_count.py
"""完整可运行：用 tiktoken 0.14.0（cl100k_base 词表）真实计数。

注意：tiktoken 首次使用需要联网下载 BPE 词表（本书沙箱经代理下载成功，约 27 秒，
缓存到 $TIKTOKEN_CACHE_DIR 或系统临时目录后离线可用）。下载失败时 llm_client 会
回退到 len//4 近似——本文件演示两种方式并对比误差，绝不静默混淆。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # 仓库根，便于 import 示例代码.公共

from 示例代码.公共.llm_client import count_tokens  # noqa: E402


def approx_tokens(text: str) -> int:
    """近似计数：len(text)//4（对英文粗略成立，对中文严重低估）。"""
    return max(1, len(text) // 4)


SAMPLES: list[tuple[str, str]] = [
    ("英文短句", "Hello, how may I help you today?"),
    ("中文短句", "您好，请问有什么可以帮您？"),
    ("混合文本", "订单 ORD-1001 已支付 129.5 元，请查收 invoice.pdf"),
    ("JSON 片段", '{"order_id": "ORD-1001", "status": "paid", "amount": 129.5}'),
    ("Java 代码", "public static void main(String[] args) { System.out.println(\"hi\"); }"),
]


def main() -> None:
    print(f"{'样本':<10} {'字符数':>6} {'近似(len//4)':>12} {'tiktoken 精确':>12} {'偏差':>8}")
    print("-" * 56)
    for label, text in SAMPLES:
        exact, method = count_tokens(text)
        approx = approx_tokens(text)
        bias = approx - exact
        print(f"{label:<10} {len(text):>6} {approx:>12} {exact:>12} {bias:>+8}")
        assert method == "tiktoken:cl100k_base", f"预期 tiktoken 精确计数，实际 {method}"

    # encode/decode 往返：token 是模型眼里的"字"
    from 示例代码.公共.llm_client import _get_encoding  # 教学演示用内部函数

    enc = _get_encoding()
    text = "订单查询"
    token_ids = enc.encode(text)
    print(f"\n[往返] {text!r} → token ids = {token_ids} → decode 还原 = {enc.decode(token_ids)!r}")
    print(f"[字符] {len(text)} 个汉字 vs {len(token_ids)} 个 token —— 中文常见 1 汉字≈0.5~1.5 token")
    for tid in token_ids:
        piece = enc.decode([tid])
        print(f"    token {tid:>6} → {piece!r}（单 token 解码可能显示异常：多字节序列被拆开）")


if __name__ == "__main__":
    main()
