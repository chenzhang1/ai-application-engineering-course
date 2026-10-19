# EX-23-04 | 多模态图片输入的消息结构（base64 data URL）| 运行: python3 示例代码/ch23_chat/ex_23_04_multimodal_structure.py
"""完整可运行（仅构造消息结构，不联网）：演示 OpenAI 风格的图片输入消息如何组装。

沙箱无 OPENAI_API_KEY，本示例只构造并打印消息结构；真实发送属于 LLM_MODE=real
路径，效果与模型能力以官方文档为准——教材已如实标注。
"""
from __future__ import annotations

import base64
import json
import sys
import zlib
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def tiny_png_b64() -> str:
    """手工构造 1×1 红色像素 PNG（最小合法文件），返回 base64。

    PNG = 固定签名 + IHDR/IDAT/IEND 块。这里用 zlib 压缩原始像素数据，
    不依赖任何图片库——顺便证明 base64 只是"字节换文本"的编码，不是加密。
    """
    import struct

    def chunk(tag: bytes, data: bytes) -> bytes:
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)      # 1x1, 8bit, RGB
    raw = zlib.compress(b"\x00\xff\x00\x00")                  # 1 行 filter0 + RGB(255,0,0)
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
           + chunk(b"IDAT", raw) + chunk(b"IEND", b""))
    return base64.b64encode(png).decode("ascii")


def build_vision_message(question: str, png_b64: str) -> list[dict[str, Any]]:
    """图文混合消息：content 是"分段数组"，text 与 image_url 交替（OpenAI 风格）。"""
    return [{
        "role": "user",
        "content": [
            {"type": "text", "text": question},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{png_b64}"}},
        ],
    }]


def main() -> None:
    png_b64 = tiny_png_b64()
    print(f"[1] 1×1 PNG 的 base64（{len(png_b64)} 字符）：{png_b64}")
    decoded = base64.b64decode(png_b64)
    is_png = decoded[:8] == b"\x89PNG\r\n\x1a\n"  # PNG 固定 8 字节魔数
    print(f"    解回字节后是合法 PNG：{is_png}，共 {len(decoded)} 字节")
    assert is_png

    messages = build_vision_message("这张图里是什么颜色？", png_b64)
    print("\n[2] 图文混合消息结构（content 为分段数组）：")
    print(json.dumps(messages, ensure_ascii=False, indent=2)[:600] + " …（截断显示）")

    print("\n[3] 双模式说明：")
    print("    - 本示例仅构造结构；LLM_MODE=mock 下即使调用 MockLLM 也只做文本演示；")
    print("    - LLM_MODE=real 时该结构原样发给 client.chat.completions.create(messages=...)；")
    print("    - 沙箱无 Key：真实多模态调用结果未验证，具体支持的图片格式/大小限制以厂商文档为准。")


if __name__ == "__main__":
    main()
