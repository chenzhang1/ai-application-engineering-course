# P1 文本清洗：入库前的最低限度规范化（ch31 思路的工程化落地）
"""清洗只做"无损或低损"操作，每条都可解释：
1) 统一换行 \r\n|\r → \n（Windows 老文档常见）；
2) 去掉 HTML 注释（协作过程遗留，检索无价值且可能误导）；
3) 去掉零宽字符（复制粘贴常见，会污染 token 与向量）；
4) 行尾空白 + 连续 3 空行压缩为 1 空行（切分器按空行分段的信号更干净）。

不做的事：不改写正文语义、不删 markdown 结构符号——标题符号是切分与
元数据的信号（ch32），去格式属于过度清洗。
"""
from __future__ import annotations

import re

_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
_ZERO_WIDTH_RE = re.compile(r"[\u200b\u200c\u200d\ufeff]")
_TRAILING_SPACE_RE = re.compile(r"[ \t]+$", re.M)
_BLANK_LINES_RE = re.compile(r"\n{3,}")


def clean_markdown(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _HTML_COMMENT_RE.sub("", text)
    text = _ZERO_WIDTH_RE.sub("", text)
    text = _TRAILING_SPACE_RE.sub("", text)
    text = _BLANK_LINES_RE.sub("\n\n", text)
    return text.strip() + "\n"
