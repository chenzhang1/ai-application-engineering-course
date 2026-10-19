# 第一部分（ch01~ch03）运行记录

> 执行日期：2026-10-19。环境：沙箱 Linux，Python 3.14.7（pyenv），pip 26.2.1，pytest 9.1.1。
> 所有输出均来自真实执行；涉及真实模型调用的示例本部分没有（ch01 示例不联网、ch02/ch03 为纯工程演示）。

## 0. 环境核查

| 命令 | 退出码 | 摘要 |
|---|---|---|
| `python3 --version && pip --version` | 0 | Python 3.14.7；pip 26.2.1 |
| `python3 -c "import pydantic_settings, pydantic; ..."` | 0 | pydantic-settings 2.16.0 / pydantic 2.14.1，与 requirements.txt 一致 |
| `pip check`（项目环境） | 0 | `No broken requirements found.` |
| `python3 -c "import importlib.metadata as m; ..."` | 0 | typing_extensions 4.16.0（requirements-lock 一致） |

## 1. ch01 示例

| 命令 | 退出码 | 摘要 |
|---|---|---|
| `python3 examples/ch01_concepts/ex_01_01_concept_sketches.py` | 0 | 五种形态（直调/RAG/工具调用/工作流/Agent）结构示意全部打印；输出已贴入教材 EX-01-01 |

## 2. ch02 示例与 shell 演示链

| 命令 | 退出码 | 摘要 |
|---|---|---|
| `python3 examples/ch02_env/ex_02_01_where_am_i.py`（全局环境） | 0 | 是否在venv=否；prefix=base_prefix=/root/.pyenv/versions/3.14.7 |
| `python3 examples/ch02_env/ex_02_02_settings_env.py`（环境变量方式） | 0 | app_name=客服助手；SecretStr 打码 `**********` |
| `python3 examples/ch02_env/ex_02_02_settings_env.py examples/ch02_env/.env.example` | 0 | .env 文件加载成功，输出同上 |
| `APP_APP_NAME=命令行优先 python3 ... .env.example` | 0 | 环境变量优先于 .env 文件，输出"命令行优先" |
| `python3 examples/ch02_env/ex_02_03_logging_basics.py` | 0 | DEBUG/INFO/ERROR 输出正常；`logger.exception` 打印完整堆栈；stderr 捕获合并显示 |
| `python3 examples/ch02_env/ex_02_04_debug_me.py` | 0 | 窗口=10 输出 `[]`（文档声称应返回全体平均——即练习要找的边界 bug） |
| venv 链：`python3 -m venv /tmp/venv_demo && source .../activate && which python && python -m pip list && deactivate` | 0 | VIRTUAL_ENV=/tmp/venv_demo；`pip list` 仅含 pip 26.2.1；venv 内 EX-02-01 显示"是否在venv=是" |
| venv 内跑 `ex_03_01_env_check.py` | 1 | 三个依赖均"缺失"，体检未通过，退出码 1（教学预期） |
| pyproject 链：/tmp/pkg_demo（pyproject.toml+src/greet）内 `pip install -e .` | 0 | `Successfully installed greet-0.1.0`；`python -c "from greet import hello"` 输出问候语；`pip show greet` 正常 |
| uv 链：`pip install uv` → `uv --version` → `uv venv /tmp/uv_demo` → `uv pip install --python ... httpx==0.28.1` | 0 | uv 0.13.1；安装成功；`httpx 0.28.1` 导入验证通过 |

**遇到的问题与修复：**

1. `pip show greet | head -n 6` 产生 `ERROR: Pipe to stdout was broken` 噪音（管道提前关闭所致，非安装失败）。修复：去掉 head 重拍，`pip show greet` 完整输出已入教材。
2. Windows 的 activate/PowerShell 命令无法在本沙箱（Linux）执行——教材中该表已标注"未实测，以官方 venv 文档为准"。
3. pip 换源命令（清华镜像等）未验证连通性（沙箱经代理直连官方 PyPI 完成所有安装）——教材标注"未验证"。

## 3. ch03 示例与依赖冲突链

| 命令 | 退出码 | 摘要 |
|---|---|---|
| `python3 examples/ch03_first_program/ex_03_01_env_check.py`（项目环境） | 0 | Python/3 个依赖全绿，"体检通过" |
| `python3 examples/ch03_first_program/ex_03_03_import_probe.py`（项目环境） | 0 | pydantic 2.14.1、pydantic_settings 2.16.0 均 [OK] |
| EX-03-02 场景 1（CWD 无 config.json） | 1 | FileNotFoundError 完整 traceback（逐行讲解素材） |
| EX-03-02 场景 2（config.json 内容 `{不是json`） | 1 | JSONDecodeError → ConfigError 异常链，"The above exception was the direct cause..." |
| EX-03-02 场景 3（合法 JSON，分母 0） | 1 | ZeroDivisionError: division by zero |
| 冲突链①：`venv_conflict` 内安装 pydantic==2.14.1 + pydantic-settings==2.16.0 → `pip check` | 0 | 初始干净；探针 [OK] |
| 冲突链②：`pip install typing-extensions==4.10.0` | 0（但打印冲突 ERROR 提示） | pip 仍装成功：`typing-inspection/pydantic/pydantic-core` 三条 requires 不满足——**pip install 成功 ≠ 依赖一致** |
| 冲突链③：`pip check` | 1 | 三行 `has requirement typing-extensions>=4.16.0, but you have typing-extensions 4.10.0` |
| 冲突链④：跑 `ex_03_03_import_probe.py` | 0（探针自身兜底） | 真实症状：`ImportError: cannot import name 'Sentinel' from 'typing_extensions'`（两个包都 [FAIL]） |
| 冲突链⑤修复：`pip install typing_extensions==4.16.0` → `pip check` → 探针 | 0 / 0 / 0 | `No broken requirements found.`；探针恢复 [OK] |
| `pip freeze`（修复后的 venv_conflict） | 0 | 7 个包版本清单（教材用于讲 lock 文件来源） |
| `/tmp/venv_demo/bin/python -c "import pydantic"`（裸 venv） | 1 | `ModuleNotFoundError: No module named 'pydantic'`（ch02 排错节的真实样本） |
| `python -m pipdeptree -p pydantic-settings`（venv_conflict 内，pipdeptree 4.2.8） | 0 | 完整依赖树（pydantic-settings→pydantic→typing_extensions 等） |

**遇到的问题与修复：**

1. `pipdeptree --warn silence` 的输出混入了宿主环境残留包（nab-*），不符合演示预期。处理：教材只采用带 `-p pydantic-settings` 过滤的干净输出，异常输出不采用并在此记录。
2. 冲突制造未走 `--no-deps` 后门：直接 `pip install typing-extensions==4.10.0` 在 pip 26.2.1 下"警告但照装"，恰好展示了真实世界最常见的踩坑路径（比强制安装更有教学价值），已如实记录退出码 0 与 ERROR 提示并存的现象。

## 4. 测试

| 命令 | 退出码 | 摘要 |
|---|---|---|
| `python3 -m pytest tests/test_ch02.py tests/test_ch03.py -v` | 0 | `20 passed in 0.10s`（test_ch02 8 项 + test_ch03 12 项；覆盖正常/边界/非法输入） |

## 5. Mock 验证声明

- 本部分所有示例**均不发起真实模型调用**（EX-01-01 的 `fake_llm` 是确定性规则函数，输出为真实运行输出，不涉联网）。
- 沙箱无 `OPENAI_API_KEY`，本部分也无需；凡涉及真实模型回答的内容一律未在本书使用。

## 6. 未验证项

1. Windows（cmd/PowerShell）下的 venv 创建/激活/退出命令——沙箱为 Linux，未实测，教材已标注。
2. pip 镜像源（清华等）连通性——未验证，教材已标注。
3. `uv` 版本 0.13.1 为演示日快照，安装与用法以官方文档为准（uv 迭代快）。
4. VSCode 调试步骤（F5/断点/条件断点）为编辑器操作，无法在沙箱内自动化验证，步骤按官方文档书写并标注。

## 7. 交付前复验（同日）

| 项 | 结果 |
|---|---|
| `python3 -m pytest tests/test_ch02.py tests/test_ch03.py` | 0，`20 passed in 0.09s` |
| 8 个 EX 全部复跑 | EX-01-01/02-01/02-02/02-03/02-04/03-01/03-03 退出码 0；EX-03-02 退出码 1（预期失败设计） |
| EX 引用一致性 | 教材 8 个 EX 引用 ↔ 8 个示例文件 ↔ 文件首行注释三方对应，无缺失 |
| 排版自查 | 无"此处从略/篇幅有限/读者自行实现"；无超 5 列表格行 |
| 字数 | 正文汉字（不含代码块）约 1.2 万；含代码块约 1.42 万 |
| 修正记录 | ex_02_02 文件头演示命令路径与教材统一为仓库根路径（仅注释改动，重跑通过）；EX-02-03 输出块曾有一处排版标注错误，已替换为精确真实输出 |
