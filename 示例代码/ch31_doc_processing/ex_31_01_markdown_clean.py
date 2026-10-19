# EX-31-01 | markdown 文档加载与清洗：front-matter、注释与零宽字符 | 运行: python3 示例代码/ch31_doc_processing/ex_31_01_markdown_clean.py
"""完整可运行（确定性程序，真实运行输出）：入库前的第一步——把"人看的 markdown"
变成"机器可靠处理的文本"。演示三个真实世界最常见的脏：
1) front-matter 元数据（doc_id/租户/部门——ch32 元数据与 ch34 权限过滤的原料）；
2) HTML 注释（评审遗留，检索价值为零还可能带敏感内容）；
3) 零宽字符与不规则空行（复制粘贴常态，污染 token 计数与切分边界）。
"""
from __future__ import annotations

import re
from pathlib import Path

_FRONT_MATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.S)
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
_ZERO_WIDTH_RE = re.compile(r"[\u200b\u200c\u200d\ufeff]")
_TRAILING_RE = re.compile(r"[ \t]+$", re.M)
_BLANK_RE = re.compile(r"\n{3,}")

MESSY_DOC = """---
doc_id: hr_leave_policy
tenant_id: acme
department: hr
title: 员工请假制度
---
# 员工请假制度

<!-- 评审备注：年假规则法务还没确认，先按旧版发布 -->
## 年假

年假每年 12 月 31 日 24 点清零。​不可结转。（行尾有空格与零宽字符）


<!-- TODO: 补充婚假说明 -->


## 病假
病假超过 3 天需医院证明。
"""


def parse_front_matter(text: str) -> tuple[dict[str, str], str]:
    """拆 (元数据, 正文)。教学最小实现：仅支持 'key: value' 行。"""
    m = _FRONT_MATTER_RE.match(text.strip())
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).splitlines():
        key, sep, value = line.partition(":")
        if not sep:
            raise ValueError(f"front-matter 行缺少冒号：{line!r}")
        meta[key.strip()] = value.strip()
    return meta, m.group(2)


def clean_markdown(text: str) -> str:
    """清洗四连：换行归一 → 去 HTML 注释 → 去零宽字符 → 行尾空白与多余空行。"""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _HTML_COMMENT_RE.sub("", text)
    text = _ZERO_WIDTH_RE.sub("", text)
    text = _TRAILING_RE.sub("", text)
    text = _BLANK_RE.sub("\n\n", text)
    return text.strip() + "\n"


def main() -> None:
    meta, body = parse_front_matter(MESSY_DOC)
    print("[1] front-matter 解析（权限过滤与溯源的原料，ch32/ch34 会用到）：")
    for k, v in meta.items():
        print(f"    {k:<12} = {v}")

    cleaned = clean_markdown(body)
    print(f"\n[2] 清洗前后对比：")
    print(f"    字符数：{len(body)} → {len(cleaned)}；注释块：{body.count('<!--')} → {cleaned.count('<!--')}；"
          f"零宽字符：{len(_ZERO_WIDTH_RE.findall(body))} → {len(_ZERO_WIDTH_RE.findall(cleaned))}")
    print("\n[3] 清洗后的正文（注意：评审备注已消失、空行收敛、行尾干净）：")
    print("    " + cleaned.replace("\n", "\n    ").rstrip())

    print("\n[清洗纪律] 只做'无损或低损'操作：不改语义、不删 markdown 结构——")
    print("    标题符号 '#' 是 ch32 按语义切分的信号，去格式属于过度清洗。")
    print("    敏感内容在注释里也一样敏感：注释应废弃或脱敏，而不是指望清洗兜底。")
    print(f"[文件位置] 真实工程版见 综合项目/项目一_文档知识库/ingest/cleaner.py 与 loaders.py")


if __name__ == "__main__":
    main()
