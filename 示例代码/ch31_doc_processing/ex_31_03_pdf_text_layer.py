# EX-31-03 | PDF 文本层：生成/提取实验与扫描件 OCR 的边界 | 运行: python3 示例代码/ch31_doc_processing/ex_31_03_pdf_text_layer.py
"""完整可运行（确定性程序，真实运行输出）：理解"PDF 提取"提取的到底是什么。

实验 1：用纯标准库手写一个最小 PDF 生成器（含文本绘制指令 Tj），
        再用 poppler-utils 的 pdftotext 提取——证明提取读的是"文本层"。
实验 2：生成一个没有任何文本指令的 PDF（模拟扫描件：只有"纸"，没有"字"），
        pdftotext 提取为空——这就是为什么扫描件要走 OCR 另一条流水线。

版本事实：本沙箱未安装 pypdf/pdfminer（不在 requirements.txt）；
poppler-utils 24.02.0（pdftotext/pdftoppm）为环境预装，实际验证可用。
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

TEXT_PAGE_LINES = [
    "Company Leave Policy v1.2",
    "Annual leave expires on Dec 31 every year.",
    "Sick leave over 3 days requires a doctor note.",
]


def build_pdf(lines: list[str], *, with_text: bool) -> bytes:
    """手写最小合法 PDF：with_text=True 时每行文字生成一条 BT/Tj/ET 指令。"""
    if with_text:
        content = "\n".join(
            f"BT /F1 11 Tf 72 {720 - i * 18} Td ({_esc(line)}) Tj ET"
            for i, line in enumerate(lines)).encode("latin-1")
    else:
        content = b""  # 空内容流：页面上什么都没有（真实扫描件是一整页位图图像）
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n"
        + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n".encode() + b"0000000000 65535 f \n"
    out += "".join(f"{off:010d} 00000 n \n" for off in offsets).encode()
    out += (f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref}\n%%EOF\n").encode()
    return bytes(out)


def _esc(text: str) -> str:
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def extract_with_pdftotext(pdf_path: Path) -> str:
    result = subprocess.run(["pdftotext", str(pdf_path), "-"],
                            capture_output=True, text=True, check=True)
    return result.stdout.strip()


def main() -> None:
    if shutil.which("pdftotext") is None:
        raise SystemExit("本示例需要 poppler-utils（pdftotext）。"
                         "Ubuntu/Debian: sudo apt install poppler-utils")

    with tempfile.TemporaryDirectory() as td:
        pdf_text = Path(td) / "policy_text.pdf"
        pdf_scan = Path(td) / "policy_scan.pdf"
        pdf_text.write_bytes(build_pdf(TEXT_PAGE_LINES, with_text=True))
        pdf_scan.write_bytes(build_pdf([], with_text=False))

        got = extract_with_pdftotext(pdf_text)
        print(f"[实验 1] 含文本层的 PDF（{pdf_text.stat().st_size} bytes）：")
        print("    pdftotext 提取结果 →")
        for line in got.splitlines():
            print(f"      | {line}")
        print("    ✓ 提取成功。原理：PDF 里存的是'绘制指令'（把字形 B 画在坐标 (72,720)），")
        print("      提取器把指令流还原成字符串——这也是为什么'复制出来乱码/顺序错乱'在 PDF 上高发。")

        empty = extract_with_pdftotext(pdf_scan)
        print(f"\n[实验 2] 无文本层的 PDF（模拟扫描件，{pdf_scan.stat().st_size} bytes）：")
        print(f"    pdftotext 提取结果 → {empty!r}  ← 空！")
        print("    ✗ 没有'字'只有'纸'（位图）。文本层提取对扫描件彻底失效。")

    print("\n[扫描件流水线：OCR 原理与工具名单]（原理讲解，本沙箱未安装未实测）")
    print("    流程：PDF 页面 → 渲染成位图（pdftoppm 等光栅化）→ OCR 引擎识别文字 → 输出文本+置信度")
    print("    工具名单：开源——Tesseract（tesseract-ocr，需装中文包 chi_sim）、PaddleOCR（中文强，")
    print("    含版面分析）；云服务——各厂商 OCR API（表格/印章/手写等专门能力，按调用量计费）。")
    print("    工程要点：① OCR 输出带错误率，入库前要做置信度过滤与人工抽检；")
    print("             ② 版面（表格/双栏）决定要不要专门的版面分析，不是所有文档都值得 OCR；")
    print("             ③ 能要电子版就别 OCR——优先向文档所有方要源文件。")
    print("\n[Python 库说明] pypdf/pdfminer.six 是纯 Python 的 PDF 文本层提取库（未列入本书")
    print("    requirements，未实测）；本沙箱用 poppler-utils 命令行验证了同等能力。")


if __name__ == "__main__":
    main()
