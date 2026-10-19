# 第二部分下册（ch09~ch12）验证运行日志

> 执行环境：沙箱 Python 3.14.7（pyenv）；核实日期 2026-10-19；时区 UTC（输出中的本地时间为机器时间）。
> 执行人：part02b 作者（AI 协作工程会话）。所有"真实运行输出"均由下述命令实际产生。

## 1. 示例运行记录

### ch09（examples/ch09_iterators/，零第三方依赖）

| 文件 | 命令 | 退出码 | 输出摘要 |
|---|---|---|---|
| ex_09_01_iter_protocol.py | `python3 examples/ch09_iterators/ex_09_01_iter_protocol.py` | 0 | for 等价展开；可迭代对象可重复遍历；裸迭代器二次消费为 `[]` |
| ex_09_02_generator_yield.py | `python3 examples/ch09_iterators/ex_09_02_generator_yield.py` | 0 | 生成器暂停/恢复 5 步轨迹；第 4 次 next 抛 StopIteration |
| ex_09_03_genexpr_lazy.py | `python3 examples/ch09_iterators/ex_09_03_genexpr_lazy.py` | 0 | 列表推导式 8,448,728 字节 vs 生成器 208 字节；二次 sum=0 陷阱 |
| ex_09_04_llm_stream.py | `python3 examples/ch09_iterators/ex_09_04_llm_stream.py` | 0 | 20 token 流式消费；首字延迟 0.0186ms vs 全量 100.07ms（mock，不联网） |
| ex_09_05_yield_from.py | `python3 examples/ch09_iterators/ex_09_05_yield_from.py` | 0 | yield from 透传 3 轮子流；islice 截断无限生成器 |

### ch10（examples/ch10_decorators/，零第三方依赖）

| 文件 | 命令 | 退出码 | 输出摘要 |
|---|---|---|---|
| ex_10_01_first_class.py | `python3 examples/ch10_decorators/ex_10_01_first_class.py` | 0 | 一等公民/手动装饰；`slow_triple.__name__` 变 `wrapper`（无 wraps 对照） |
| ex_10_02_timer_decorator.py | `python3 examples/ch10_decorators/ex_10_02_timer_decorator.py` | 0 | wraps 前后 `__name__/__doc__` 对比；`__wrapped__` 指回原函数 |
| ex_10_03_retry_decorator.py | `python3 examples/ch10_decorators/ex_10_03_retry_decorator.py` | 0 | 重试成功/耗尽上抛/装饰时参数校验三场景，指数退避 0.01s→0.02s |
| ex_10_04_call_log.py | `python3 examples/ch10_decorators/ex_10_04_call_log.py` | 0 | trace_id 调用日志；幂等键二次命中返回 duplicated；异常记录后上抛 |
| ex_10_05_class_decorator.py | `python3 examples/ch10_decorators/ex_10_05_class_decorator.py` | 0 | CountCalls 跨调用计数；注册表登记 query_weather/query_order |

### ch11（examples/ch11_modules_typing/，零第三方依赖）

| 文件 | 命令 | 退出码 | 输出摘要 |
|---|---|---|---|
| ex_11_01_module_main.py | 直接运行 + `python3 -c "import ex_11_01_module_main"`（在示例目录内） | 0 / 0 | 双身份输出：`__name__='__main__'` vs `'ex_11_01_module_main'` |
| ex_11_02_import_paths.py | `python3 examples/ch11_modules_typing/ex_11_02_import_paths.py` | 0 | sys.path 前 3 项；demo_shop 门面；textfmt 两级相对导入；ModuleNotFoundError 演示 |
| ex_11_03_typing_modern.py | `python3 examples/ch11_modules_typing/ex_11_03_typing_modern.py` | 0 | TypedDict/Literal/Protocol isinstance/TypeVar/Callable/Annotated 全通过 |
| ex_11_04_annotations_runtime.py | `python3 examples/ch11_modules_typing/ex_11_04_annotations_runtime.py` | 0 | 注解不拦截 `double('ab')`；运算处才 TypeError；注解为字符串形式 |
| ex_11_05_circular_import.py | `python3 examples/ch11_modules_typing/ex_11_05_circular_import.py` | 0（子进程 1） | 真实捕获 `ImportError: cannot import name 'greet_b' from partially initialized module 'circular_bad.b' (most likely due to a circular import)`；好包正常 |

### ch12（examples/ch12_stdlib_project/）

| 文件 | 命令 | 退出码 | 输出摘要 |
|---|---|---|---|
| ex_12_01_json_encoder.py | `python3 examples/ch12_stdlib_project/ex_12_01_json_encoder.py` | 0 | datetime 非 JSON 序列化真实 TypeError；ensure_ascii 对比；SafeEncoder；roundtrip 为 str |
| ex_12_02_pathlib_timezone.py | `python3 examples/ch12_stdlib_project/ex_12_02_pathlib_timezone.py` | 0 | naive/aware 混比 TypeError；UTC↔UTC+8 转换；utcnow() DeprecationWarning 真实输出 |
| ex_12_03_re_extract.py | `python3 examples/ch12_stdlib_project/ex_12_03_re_extract.py` | 0 | 命名组解析 Java 日志行；semver 元组排序 vs 字符串排序对比；sub 脱敏 |
| ex_12_04_argparse_basics.py | 正常参数 / `--rate abc` / `--rate -0.1` / `--help` | 0 / 2 / 2 / 0 | argparse 类型校验与退出码约定 |
| ex_12_05_report_cli.py --source local | 同左 | 0 | 完整 JSON 报告（stars=43463 等，真实抓取快照） |
| ex_12_05_report_cli.py（auto，网络被限流时） | 同左 | 0 | stderr 打印两条"[模式提示]"，data_source=local-fallback |
| ex_12_05_report_cli.py --source online（限流时） | 同左 | 1 | "[错误] 在线获取失败且指定 --source online，不回退" |
| ex_12_05_report_cli.py --source bogus | 同左 | 2 | argparse invalid choice 报错 |

### 静态检查（非锁定依赖，仅验证用）

```
$ python3 -m mypy --version        # mypy 1.19.1（临时 pip 安装，未写入 requirements.txt）
$ python3 -m mypy examples/ch11_modules_typing/ex_11_04_annotations_runtime.py
examples/ch11_modules_typing/ex_11_04_annotations_runtime.py:23: error: Argument 1 to "double" has incompatible type "str"; expected "int"  [arg-type]
examples/ch11_modules_typing/ex_11_04_annotations_runtime.py:27: error: Argument 1 to "price_with_tax" has incompatible type "str"; expected "float"  [arg-type]
Found 2 errors in 1 file (checked 1 source file)
[exit 1]   ← 教材正文引用的就是这两行真实报错（该示例故意写错以演示静态检查）
$ python3 -m mypy examples/ch11_modules_typing/ex_11_03_typing_modern.py
Success: no issues found in 1 source file
[exit 0]
```

## 2. sample_data.json 的来源（诚实记录）

- 内容：`GET https://api.github.com/repos/langchain-ai/langgraph` 与 `GET .../tags?per_page=5` 的**真实响应**，2026-10-19 01:21 UTC 抓取（经沙箱代理出网，请求头与 CLI 的 `fetch_online()` 完全一致），另加 `_meta` 自述字段。
- 抓取过程：GitHub 匿名 API 60 次/小时/IP，共享出口 IP 两次撞上 403 rate limit exceeded；重试至额度重置后成功。CLI 的 auto/local 模式在该限流环境下全部验证通过（这正是内置回退路径的意义）。
- 在线模式验证：见下节。

## 3. 在线模式（--source online）验证

- 2026-10-19 01:21 UTC：临时抓取脚本（与 CLI fetch_online 相同端点/请求头）在线成功，取得 repo + tags 数据并落盘 sample_data.json。
- 2026-10-19 01:50 UTC（09:50 UTC+8）：CLI 自身 `--source online` 在额度重置后**端到端成功**（后台重试第 11 次尝试），退出码 0，`data_source: "online"`，stars=43465（与 01:21 快照的 43463 不同，体现 online 与快照的数据源差异；完整报告已贴入教材 12.6.2①）。

## 4. pytest 测试记录

```
$ cd /workspace/ai_application_course && python3 -m pytest tests/test_ch09.py tests/test_ch10.py tests/test_ch11.py tests/test_ch12.py
............................                                             [100%]
28 passed in 0.44s
```

- test_ch09.py：7 个（协议正常/耗尽边界/暂停恢复轨迹/一次性陷阱/流式 mock/real 模式拒绝/yield from+islice）
- test_ch10.py：6 个（wraps 元数据/重试恢复/耗尽上抛/非法配置/幂等键/类装饰器与注册表）
- test_ch11.py：8 个（__name__ 双身份/包门面/子包相对导入/缺失模块/注解不强制/typing 行为/循环导入好包）
- test_ch12.py：7 个（JSON 往返/编码器协议/时区比较/正则解析/CLI 本地报告/落盘/非法参数/样本丢失兜底——其中 CLI 三项为子进程端到端）
- 失败与修复过程：首次全绿（0 修复）。此前 ex_12_01 示例曾因未传编码器直接崩（已改为教材设计的"故意触发→捕获→修复"教学流）；ex_12_02 的 DeprecationWarning 因 stderr 缓冲顺序错位（已改 warnings.record=True 内联打印）。两处修复后复跑全绿。

## 5. 未验证项 / 待核实

1. Windows 环境 zoneinfo 缺 tzdata 的回退分支：逻辑为 try/except 固定偏移，未在真实 Windows 上验证。
2. mypy/pyright 输出格式随版本变化；pyright 未安装未验证。
3. ex_09_03 的 getsizeof 字节数与 ex_09_04 的耗时数字随机器/版本浮动，教材已注明。
4. 全书 LLM 相关输出均为 Mock/示例输出（沙箱无 OPENAI_API_KEY），与本册无关但一并声明。

## 6. 交付清单

- 教材：textbook/part02b_python_basics_2.md（4 章，14290 汉字，EX-09-01 ~ EX-12-05 共 20 个编号）
- 示例：examples/ch09_iterators/（5 个 .py）、ch10_decorators/（5 个）、ch11_modules_typing/（5 个 .py + demo_shop/circular_bad/circular_good 三个包）、ch12_stdlib_project/（5 个 .py + sample_data.json）
- 测试：tests/test_ch09.py（7）、test_ch10.py（6）、test_ch11.py（8）、test_ch12.py（7），共 28 个，全绿
- 本运行日志：verification/run_logs/part02b.md
