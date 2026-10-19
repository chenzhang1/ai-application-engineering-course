# 测试/test_ch31.py | ch31 文档处理：markdown 清洗 / 网页提取 / PDF 文本层
"""覆盖：front-matter 解析（正常+非法输入）、清洗规则、HTML script 跳过、
PDF 文本层提取与扫描件空结果（pdftotext 缺失时 skip）。"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from 示例代码.ch31_doc_processing.ex_31_01_markdown_clean import (MESSY_DOC,
                                                                  clean_markdown,
                                                                  parse_front_matter)
from 示例代码.ch31_doc_processing.ex_31_02_html_to_text import (INTRANET_HTML,
                                                                html_to_text)
from 示例代码.ch31_doc_processing.ex_31_03_pdf_text_layer import (TEXT_PAGE_LINES,
                                                                  _esc,
                                                                  build_pdf)


def test_parse_front_matter_extracts_fields() -> None:
    meta, body = parse_front_matter(MESSY_DOC)
    assert meta["doc_id"] == "hr_leave_policy"
    assert meta["tenant_id"] == "acme"
    assert meta["department"] == "hr"
    assert body.startswith("# 员工请假制度")
    assert not body.startswith("---")


def test_parse_front_matter_missing_colon_raises() -> None:
    with pytest.raises(ValueError, match="冒号"):
        parse_front_matter("---\ndoc_id no-colon-here\n---\n正文")


def test_clean_markdown_removes_comments_zero_width_and_blank_lines() -> None:
    cleaned = clean_markdown(MESSY_DOC)
    assert "<!--" not in cleaned
    assert "\u200b" not in cleaned  # 零宽空格已移除
    assert "\n\n\n" not in cleaned  # 空行收敛
    assert "评审备注" not in cleaned  # 注释内容整体消失
    assert "12 月 31 日 24 点清零" in cleaned  # 正文语义无损


def test_html_to_text_skips_script_and_collects_comments() -> None:
    text, comments = html_to_text(INTRANET_HTML)
    assert "trackPageView" not in text          # script 内容被跳过
    assert ".nav{display:none}" not in text     # style 内容被跳过
    assert "VPN 双因素认证已全员启用" in text      # 正文保留
    assert "首页 | OA | 邮箱" in text            # 可见导航文字保留（教学：正文判定交给上游）
    assert comments == ["hidden-note: 旧版公告已废弃，请勿引用"]


@pytest.mark.skipif(shutil.which("pdftotext") is None,
                    reason="需要 poppler-utils（沙箱已预装 24.02.0）")
def test_pdf_text_layer_roundtrip_and_scan_empty() -> None:
    with_pdf = build_pdf(TEXT_PAGE_LINES, with_text=True)
    assert with_pdf.startswith(b"%PDF-1.4") and b"Helvetica" in with_pdf
    scan_pdf = build_pdf([], with_text=False)
    with __import__("tempfile").TemporaryDirectory() as td:
        p1 = Path(td) / "a.pdf"
        p2 = Path(td) / "b.pdf"
        p1.write_bytes(with_pdf)
        p2.write_bytes(scan_pdf)
        out1 = subprocess.run(["pdftotext", str(p1), "-"],
                              capture_output=True, text=True, check=True).stdout
        out2 = subprocess.run(["pdftotext", str(p2), "-"],
                              capture_output=True, text=True, check=True).stdout
    assert "Annual leave expires on Dec 31 every year." in out1
    assert out2.strip() == ""  # 无文本层（模拟扫描件）→ 提取为空


def test_pdf_escape_special_chars() -> None:
    assert _esc("a(b)c\\d") == r"a\(b\)c\\d"
