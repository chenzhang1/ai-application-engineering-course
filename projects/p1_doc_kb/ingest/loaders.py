# P1 文档加载：markdown + 简易 front-matter（--- 包围的 key: value 头部）
"""教学取舍：不引入 python-frontmatter / PyYAML 等额外依赖（requirements 红线），
front-matter 只支持本项目用到的"字符串 key: value"子集，解析失败给出明确报错。

支持的字段：doc_id / tenant_id / department / title（缺一不可）。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_FRONT_MATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.S)
_REQUIRED = ("doc_id", "tenant_id", "department", "title")


@dataclass
class RawDoc:
    doc_id: str
    tenant_id: str
    department: str
    title: str
    text: str        # 已去掉 front-matter 的正文
    source: str      # 来源文件名（审计用）


def parse_front_matter(text: str) -> tuple[dict[str, str], str]:
    """拆 (元数据, 正文)。无 front-matter 时元数据为空 dict。"""
    m = _FRONT_MATTER_RE.match(text.strip())
    if not m:
        return {}, text
    meta: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if not line.strip():
            continue
        key, sep, value = line.partition(":")
        if not sep:
            raise ValueError(f"front-matter 行缺少冒号：{line!r}")
        meta[key.strip()] = value.strip()
    return meta, m.group(2)


def load_markdown_file(path: Path) -> RawDoc:
    """读一个 markdown 文档并校验必需元数据字段。"""
    raw = path.read_text(encoding="utf-8")
    meta, body = parse_front_matter(raw)
    missing = [k for k in _REQUIRED if k not in meta]
    if missing:
        raise ValueError(f"{path.name} 缺少 front-matter 字段：{missing}")
    return RawDoc(doc_id=meta["doc_id"], tenant_id=meta["tenant_id"],
                  department=meta["department"], title=meta["title"],
                  text=body, source=path.name)


def load_directory(data_dir: Path) -> list[RawDoc]:
    """加载目录下全部 .md（按文件名排序，保证可复现）。"""
    docs = [load_markdown_file(p) for p in sorted(data_dir.glob("*.md"))]
    ids = [d.doc_id for d in docs]
    dup = {x for x in ids if ids.count(x) > 1}
    if dup:
        raise ValueError(f"doc_id 重复：{sorted(dup)}")
    return docs
