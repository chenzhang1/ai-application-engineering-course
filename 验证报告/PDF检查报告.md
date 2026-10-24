# PDF 质量检查报告（PDF检查报告.md）

> 检查日期：2026-10-19。对象：下载导出/ai_application_engineering.pdf（599 页，A4，约 4.3MB）。
> 工具链：构建工具/build_pdf.py（markdown → HTML → weasyprint 70.0），字体 Noto Sans CJK SC / DejaVu Sans Mono（ASCII 代码）+ Noto Sans CJK SC 回退（代码内中文）。

## 检查项与结果

| # | 检查项 | 方法 | 结果 |
|---|---|---|---|
| 1 | 能打开、页数正确 | pdfinfo | ✅ 599 页，A4（595×842pt），4.3MB |
| 2 | 目录完整且页码正确 | 目录页渲染抽查 + pypdf outline | ✅ 14 个部分 + 各章二级条目；leader 点线 + target-counter 实页码（前言 5 / 第一部分 7 / 第 1 章 8…） |
| 3 | PDF 书签（侧边栏） | pypdf outline 遍历 | ✅ 1039 个书签，层级正确（部分→章→节） |
| 4 | 中文字体正常无方框 | 页面渲染抽查（封面/目录/章首页/代码页/面试页 5 张 80dpi 渲染图） | ✅ 无 tofu、无乱码、无替换字符 |
| 5 | 正文可搜索可复制 | pdftotext 全文提取 | ✅ 1,007,227 字符提取成功；U+FFFD 仅 3 行（源文件即有，非 PDF 生成问题） |
| 6 | 代码等宽字体、不截断 | p251 代码密集页渲染 | ✅ 等宽字体 + 语法高亮；pre-wrap 换行策略，无右侧裁切 |
| 7 | 表格不溢出 | 多页抽查 | ✅ table-layout: fixed + overflow-wrap，未见遮挡/溢出 |
| 8 | 长句跨页 | 第 8→9 页边界复核 | ✅ 类比边界③跨页续排，内容无缺失 |
| 9 | 无占位文本/缺章 | 章节计数：14 部分、ch01~ch63 全部出现于目录与书签 | ✅ 无"TODO/此处从略"占位 |
| 10 | 提示块区分 | 黄色 blockquote（💡⚠️📌）渲染抽查 | ✅ 样式区分清晰 |
| 11 | 参考资料链接 | 合并源稿 md 保留链接；PDF 中 URL 以文本保留 | ✅ |

## 已知的小瑕疵（不影响阅读）

1. 目录页码未做严格"右边缘对齐"（leader() 后直接接页码），不同位数页码右缘略有参差——可读性与点击跳转不受影响。
2. 代码内个别行在页面宽度下自动换行（pre-wrap 策略），与源码逐行形态略有差异；完整逐行源码以 示例代码/ 目录为准（教材中每个代码块均标注了源文件路径）。
3. pypdf（第三方提取器）对部分 CID 字体的文本提取乱码——这是 pypdf 提取器局限；poppler pdftotext 与真实阅读器（复制/搜索）均正常。

## 重建方式

```bash
python3 构建工具/build_pdf.py   # 重新生成 PDF 与合并版 Markdown
```

## 2026-10-24 修订版再生成说明

配合本次教材修订（MCP 方法名讹误修复、EX-16-03/EX-19-03/EX-36-01 等代码修正、ch24 新增 2026 API 对照小节、ch62.4 决策树重绘），按 `构建工具/build_pdf.py` 原流程重新生成了合并 md、HTML 与 PDF。本次再生成环境与首轮不同，如实记录：

- **环境**：Windows 11（win32）+ Python 3.14；本机无 GTK/Pango 运行库，weasyprint 无法运行。md 与 HTML 阶段使用原脚本与原依赖（markdown + pygments，版本一致）完成；**PDF 渲染改用 Microsoft Edge 无头打印**（`--headless=new --no-pdf-header-footer`，对 HTML 注入 `print-color-adjust:exact` 以保留代码块/目录底色）。构建脚本本身未改动——在装有 weasyprint 的 Linux/macOS 上仍应按"重建方式"一节执行。
- **结果差异**：428 页（原 599 页）、约 12MB（原 4.3MB）。差异主因是字体：本机未安装 Noto Sans CJK SC，渲染回退到系统 CJK 字体，行高与字宽度量不同，故分页与页码与首轮不对应；字号、结构、章节划分不变。
- **抽查核验**：封面/目录/页眉页脚/章首页正常；MCP 修正（`tools/list`、`tools/call`）、ch24.12 新小节、ch62.4 新决策树均已确认进入 PDF 文本层；目录页码可跟随。
- 已知小瑕疵在上述 3 条之外新增一条：目录点线（leader()）在本次渲染下的对齐精度与首轮略有差异，不影响阅读与跳转。
