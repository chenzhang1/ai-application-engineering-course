# AI 应用工程教材（面向 Java 开发者）· Python × LLM 全栈

> 一套可以实际阅读、运行代码、完成练习、开发项目、复盘面试的系统教材。
> 资料核实日期：2026-10-19。教材基于下述**实际安装并运行验证**的版本编写，不接受凭记忆的版本号。

## 交付物与下载

| 交付物 | 位置 |
|---|---|
| 主教材 PDF | `exports/ai_application_engineering.pdf` |
| 教材 Markdown 源稿 | `textbook/partNN_*.md`（合并版 `exports/ai_application_engineering.md`） |
| 示例与项目代码 | `examples/`、`projects/`（打包 `exports/ai_application_code.zip`） |
| 依赖配置 | `requirements.txt`、`requirements-lock.txt` |
| 代码验证报告 | `verification/verification_report.md`、运行日志 `verification/run_logs/` |
| 练习与考核 | 各章"练习/自测/阶段考核"小节 |
| 面试题库 | `interview/`（正文 `textbook/part12_interview.md`） |

## 学习路径速览

1. **从头完整学习**：按卷一→卷二→卷三顺序，每章完成练习与自测。
2. **Java 开发者加速**：读 `syllabus.md` 路径 2。
3. **面试冲刺**：读 `syllabus.md` 路径 3。
4. **项目驱动**：读 `syllabus.md` 路径 4。

## 环境要求

- Python 3.12+（本书代码在 3.14.7 上全部验证）
- `pip install -r requirements.txt`
- 无 API Key 也能学完全书：所有 LLM 示例默认 `MODE=mock`；真实模式需自行配置 `OPENAI_API_KEY`（兼容 OpenAI 接口的服务均可，注意功能支持边界，见第四部分）。

## 诚实声明

- 本教材不承诺"读完必进大厂/必拿 Offer"；目标限定为可验证的知识、项目与面试能力。
- 所有模型示例输出均为 Mock 或示例输出，非真实模型记录；真实效果以读者实际调用为准。
- 未经生产环境验证的能力在文中明确标注（教学可运行 ≠ 生产可上线）。
- 全部面试题均为自拟模拟题，并说明真题辨认方法。

## 目录

见 [syllabus.md](syllabus.md)；逐章进度见 [progress.md](progress.md)。
