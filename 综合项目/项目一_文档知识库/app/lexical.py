# P1 词面特征：中文 2-gram + ASCII 词元（检索重排与规则判定共用）
"""MockEmbedder 的哈希词袋在专业词表外区分度不足（教材 ch33 实测），
P1 用一个极简的词面重叠特征做重排补偿：查询切 2-gram 后统计在候选块中的命中率。

这是教学取舍：真实系统里这一步通常由 BM25 或交叉编码器重排承担（ch33/ch34），
此处 20 行实现换来"Mock 模式下可复现、可解释"的检索行为。
"""
from __future__ import annotations

import re

_ASCII_WORD_RE = re.compile(r"[a-z0-9]+")
_CJK_RUN_RE = re.compile(r"[\u4e00-\u9fff]+")


def tokenize(text: str) -> set[str]:
    """极简分词：ASCII 单词 + 中文 2-gram（单字 run 保留为 1-gram）。小写归一。"""
    lowered = text.lower()
    tokens: set[str] = set(_ASCII_WORD_RE.findall(lowered))
    for run in _CJK_RUN_RE.findall(lowered):
        if len(run) == 1:
            tokens.add(run)
        else:
            tokens.update(run[i:i + 2] for i in range(len(run) - 1))
    return tokens


def lexical_overlap(question: str, text: str) -> float:
    """词面包含度：|问题词元 ∩ 文本词元| / |问题词元|；问题为空按 0。"""
    q = tokenize(question)
    if not q:
        return 0.0
    return len(q & tokenize(text)) / len(q)
