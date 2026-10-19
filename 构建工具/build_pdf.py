#!/usr/bin/env python3
"""build_pdf.py — 教材 PDF 构建工具（weasyprint 70.0 + markdown + pygments）

用法: python3 构建工具/build_pdf.py [输出路径]
产出: 下载导出/ai_application_engineering.pdf 与 下载导出/ai_application_engineering.md
"""
import re
import sys
from pathlib import Path

import markdown
from pygments.formatters import HtmlFormatter
from weasyprint import HTML

ROOT = Path(__file__).resolve().parent.parent
TEXTBOOK = ROOT / "教材"
EXPORTS = ROOT / "下载导出"

# (注入的部分标题, 文件, 是否前言)
PARTS = [
    ("前言与全书导读", "part00_preface.md", True),
    ("第一部分 整体认知与环境（第1~3章）", "part01_overview_env.md", False),
    ("第二部分（上）Python 语言基础：对象、数据结构、函数、类与异常（第4~8章）", "part02a_python_basics_1.md", False),
    ("第二部分（下）Python 语言基础：迭代器、装饰器、模块与类型、标准库（第9~12章）", "part02b_python_basics_2.md", False),
    ("第三部分 Python 工程化与服务开发（第13~20章）", "part03_engineering.md", False),
    ("第四部分 大模型与模型 API（第21~25章）", "part04_llm_api.md", False),
    ("第五部分 Prompt 与上下文工程（第26~29章）", "part05_prompt_context.md", False),
    ("第六部分 RAG 从原理到生产（第30~36章）", "part06_rag.md", False),
    ("第七部分 LangChain（第37~42章）", "part07_langchain.md", False),
    ("第八部分 LangGraph（第43~51章）", "part08_langgraph.md", False),
    ("第九部分 Agent、MCP 与复杂应用（第52~56章）", "part09_agent_mcp.md", False),
    ("第十部分 企业级架构、安全与运维（第57~61章）", "part10_production.md", False),
    ("第十一部分 微调与算法知识边界（第62~63章）", "part11_finetuning.md", False),
    ("第十二部分 面试与求职（专题一~专题八）", "part12_interview.md", False),
]

RE_PART_TITLE = re.compile(r"^# (第.{1,4}部分|前言)")
RE_CHAPTER = re.compile(r"^# (第\s*\d+\s*章|ch\d+|专题[一二三四五六七八九十]|12\.\d+ 专题)")
RE_TOPIC_H2 = re.compile(r"^## .*(专题[一二三四五六七八])")

def normalize_part(text: str, is_preface: bool) -> str:
    """标题归一化：部分标题行删除（由注入标题替代）；章级 h1→h2；其余 h1→h3；h2→h3（专题除外）；h3→h4；h4→h5"""
    out, first_h1_skipped = [], False
    for line in text.splitlines():
        if line.startswith("# "):
            if RE_PART_TITLE.match(line) and not first_h1_skipped:
                first_h1_skipped = True
                continue  # 注入标题替代
            if RE_CHAPTER.match(line):
                out.append("## " + line[2:])
            else:
                out.append("### " + line[2:])
        elif line.startswith("## "):
            if RE_TOPIC_H2.match(line):
                out.append("## " + line[3:])
            else:
                out.append("### " + line[3:])
        elif line.startswith("### "):
            out.append("#### " + line[4:])
        elif line.startswith("#### "):
            out.append("##### " + line[5:])
        else:
            out.append(line)
    return "\n".join(out)

def build_body_markdown() -> str:
    chunks = []
    for title, fname, is_preface in PARTS:
        raw = (TEXTBOOK / fname).read_text(encoding="utf-8")
        body = normalize_part(raw, is_preface)
        chunks.append(f"\n\n# {title}\n\n" + body.strip() + "\n")
    merged = "\n".join(chunks)
    return merged

MD_EXTS = ["fenced_code", "tables", "toc", "codehilite", "sane_lists"]
MD_EXT_CFG = {
    "toc": {"toc_depth": "1-2"},
    "codehilite": {"guess_lang": False, "css_class": "codehilite"},
}

CSS = """
@page {
  size: A4; margin: 20mm 16mm 18mm 16mm;
  @bottom-center { content: counter(page); font-family: 'Noto Sans CJK SC'; font-size: 8.5pt; color: #888; }
  @top-center { content: "AI 应用工程教材（Python × LLM）· 面向 Java 开发者"; font-family: 'Noto Sans CJK SC'; font-size: 7.5pt; color: #aaa; }
}
@page :first { @top-center { content: none; } @bottom-center { content: none; } }
@page toc { @top-center { content: none; } }
html { font-family: 'Noto Sans CJK SC', sans-serif; font-size: 10pt; line-height: 1.75; color: #1f2328; }
body { margin: 0; }
h1 { font-size: 20pt; color: #0b3d66; bookmark-level: 1; page-break-before: always; margin: 0 0 12pt; }
h2 { font-size: 14.5pt; color: #0b3d66; bookmark-level: 2; page-break-before: always; page-break-after: avoid; border-bottom: 2px solid #d8e2ec; padding-bottom: 4pt; margin: 18pt 0 10pt; }
h3 { font-size: 12pt; color: #14507f; bookmark-level: 3; page-break-after: avoid; margin: 14pt 0 6pt; }
h4 { font-size: 10.5pt; color: #1f2328; page-break-after: avoid; margin: 10pt 0 4pt; }
h5 { font-size: 10pt; color: #444; page-break-after: avoid; }
p { margin: 5pt 0; orphans: 2; widows: 2; }
li { margin: 2pt 0; }
strong { color: #0b3d66; }
hr { border: none; border-top: 1px solid #ddd; margin: 10pt 0; }
code { font-family: 'DejaVu Sans Mono', 'Noto Sans CJK SC', monospace; font-size: 8.5pt; background: #f2f4f7; padding: 0.5pt 3pt; border-radius: 3px; overflow-wrap: anywhere; }
.codehilite { background: #f6f8fa; border: 1px solid #e3e8ee; border-left: 3px solid #4a89b8; border-radius: 4px; padding: 7pt 9pt; margin: 7pt 0; page-break-inside: auto; }
.codehilite pre { margin: 0; font-family: 'DejaVu Sans Mono', 'Noto Sans CJK SC', monospace; font-size: 8pt; line-height: 1.45; white-space: pre-wrap; overflow-wrap: anywhere; }
.codehilite code { background: none; padding: 0; font-size: 8pt; }
blockquote { border-left: 3px solid #f0a63a; background: #fffaf0; margin: 7pt 0; padding: 5pt 9pt; color: #5c4a1e; }
blockquote p { margin: 2pt 0; }
table { border-collapse: collapse; width: 100%; font-size: 8.5pt; margin: 7pt 0; table-layout: fixed; }
th, td { border: 1px solid #cfd8e0; padding: 3pt 5pt; overflow-wrap: anywhere; text-align: left; vertical-align: top; }
th { background: #eef3f8; color: #0b3d66; }
/* 封面 */
.cover { page: first; text-align: center; padding-top: 55mm; page-break-after: always; }
.cover h1.t { font-size: 30pt; bookmark-level: none; page-break-before: auto; color: #0b3d66; border: none; }
.cover .sub { font-size: 14pt; color: #444; margin-top: 10pt; }
.cover .meta { font-size: 10pt; color: #666; margin-top: 26pt; line-height: 2; }
.cover .honest { font-size: 9pt; color: #8a5a00; background: #fffaf0; border: 1px solid #f0d9a8; border-radius: 6px; padding: 10pt 14pt; margin: 26pt auto 0; width: 78%; text-align: left; }
/* 目录 */
.toc-page { page: toc; page-break-after: always; }
.toc-page h1 { bookmark-level: none; page-break-before: auto; }
.toc ol { list-style: none; padding-left: 0; margin: 4pt 0; }
.toc ol ol { padding-left: 14pt; }
.toc li { margin: 2.5pt 0; font-size: 9.5pt; }
.toc li.l1 { font-weight: bold; margin-top: 7pt; font-size: 10.5pt; }
.toc a { text-decoration: none; color: #1f2328; }
.toc a::after { content: leader('. ') target-counter(attr(href), page); color: #888; }
/* 部分扉页 */
.part-divider { page-break-before: always; }
"""

def build_cover() -> str:
    return """
<div class="cover">
  <h1 class="t">AI 应用工程教材</h1>
  <div class="sub">Python × 大模型应用开发 · 面向 Java 开发者的系统教材</div>
  <div class="sub" style="font-size:11pt;color:#666;">语言基础 · 工程化 · 模型 API · Prompt · RAG · LangChain · LangGraph · Agent/MCP · 生产架构 · 面试</div>
  <div class="meta">
    资料核实日期：2026-10-19（依赖在本环境实际安装并运行验证，两轮全量通过）<br/>
    Python 3.14.7→3.14.8 · openai 2.54.0 · FastAPI 0.141.1 · Pydantic 2.13.4<br/>
    LangChain 1.2.15 · LangGraph 1.1.10 · pytest 9.1.1（详见 requirements.txt）
  </div>
  <div class="honest">
    <strong>诚实声明</strong>：本教材不承诺任何就业结果；示例默认 Mock 模式（不联网），所有模型输出均标注为 Mock 运行输出或示例输出，非真实模型记录；"教学环境可运行"≠"生产环境可上线"；全部面试题为自拟模拟题；未经生产验证的能力在文中明确标注。
  </div>
</div>
"""

def build_toc(toc_tokens) -> str:
    items = []
    for tok in toc_tokens:
        items.append(f'<li class="l1"><a href="#{tok["id"]}">{tok["name"]}</a></li>')
        for ch in tok.get("children", []):
            items.append(f'<li class="l2"><a href="#{ch["id"]}">{ch["name"]}</a></li>')
    return '<div class="toc-page"><h1 id="toc-head">目录</h1><div class="toc"><ol>' + "\n".join(items) + "</ol></div></div>"

def main():
    out_pdf = Path(sys.argv[1]) if len(sys.argv) > 1 else EXPORTS / "ai_application_engineering.pdf"
    EXPORTS.mkdir(exist_ok=True)

    merged_md = build_body_markdown()
    (EXPORTS / "ai_application_engineering.md").write_text(merged_md, encoding="utf-8")

    md = markdown.Markdown(extensions=MD_EXTS, extension_configs=MD_EXT_CFG)
    body_html = md.convert(merged_md)
    toc_tokens = md.toc_tokens
    md.reset()

    formatter = HtmlFormatter(style="default")
    pyg_css = formatter.get_style_defs(".codehilite")
    html = (
        "<html><head><meta charset='utf-8'><style>"
        + CSS + pyg_css +
        "</style></head><body>"
        + build_cover()
        + build_toc(toc_tokens)
        + body_html
        + "</body></html>"
    )
    (EXPORTS / "ai_application_engineering.html").write_text(html, encoding="utf-8")
    HTML(string=html, base_url=str(ROOT)).write_pdf(out_pdf)
    print(f"PDF written: {out_pdf}")
    print(f"TOC top-level entries: {len(toc_tokens)}")

if __name__ == "__main__":
    main()
