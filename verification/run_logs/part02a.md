# 第二部分（上）验证记录（part02a：ch04~ch08）

> 验证环境：沙箱 Python 3.14.7（pyenv），pytest 9.1.1（requirements.txt 锁定版本）。
> 验证日期：2026-10-19。全部示例与测试均在 `/workspace/ai_application_course` 下实际执行。

## 1. 示例运行（28 个，全部 exit=0）

命令模板（分章循环执行）：

```bash
cd /workspace/ai_application_course
for f in examples/ch04_objects/*.py; do echo "===== $f"; python3 "$f"; echo "--- exit=$?"; done
for f in examples/ch05_datastructures/*.py; do echo "===== $f"; python3 "$f"; echo "--- exit=$?"; done
for f in examples/ch06_functions/*.py; do echo "===== $f"; python3 "$f"; echo "--- exit=$?"; done
for f in examples/ch07_classes/*.py; do echo "===== $f"; python3 "$f"; echo "--- exit=$?"; done
for f in examples/ch08_exceptions/*.py; do echo "===== $f"; python3 "$f"; echo "--- exit=$?"; done
```

结果：28/28 exit=0。输出摘要（真实记录，已按原样贴入教材对应 EX 小节）：

| 示例 | 退出码 | 输出要点 |
|---|---|---|
| ex_04_01_everything_is_object | 0 | int/str/list/None/函数/类的 type 与 isinstance 均符合预期；int 的类型是 type |
| ex_04_02_name_binding | 0 | `b.append(4)` 后 `a=[1,2,3,4]`，`a is b: True`；rebind 不可见 |
| ex_04_03_is_vs_eq | 0 | 运行时 257：`== True`、`is False`；256 缓存命中 True |
| ex_04_04_mutable_immutable | 0 | tuple 槽位赋值 -> `TypeError: 'tuple' object does not support item assignment` |
| ex_04_05_copy | 0 | shallow 内层 `is` True，deep 内层 `is` False；互不污染 |
| ex_04_06_gc | 0 | getrefcount 1→2→1；`gc.collect()` 回收 2 个循环引用对象 |
| ex_05_01_list_ops | 0 | sort 原地、sorted 副本、key=len 稳定排序 |
| ex_05_02_tuple_unpacking | 0 | `(42,)` 为 tuple、`(42)` 为 int；星号解包/swap 正确 |
| ex_05_03_dict_set | 0 | dict 插入序 `['name','role','email']`；set 四则运算（sorted 展示） |
| ex_05_04_comprehensions | 0 | 四种推导式 + 生成器表达式 + 嵌套展平 |
| ex_05_05_slicing | 0 | `data[5:100]` 越界不报错；`data[:] is data` False；切片赋值改长度 |
| ex_05_06_hashable | 0 | `cannot use 'list' as a dict key (unhashable type: 'list')`；含 list 的 tuple 不可哈希 |
| ex_05_07_defaultdict_counter | 0 | defaultdict 访问即写入 key 99；Counter 缺失 key 返回 0 不写入 |
| ex_06_01_default_mutable | 0 | `r1 is r2: True`；`__defaults__` 被污染为 `(['a','b'],)`；哨兵 None 修复 |
| ex_06_02_args_kwargs | 0 | args/kwargs 形状正确；keyword-only 报 `create_user() takes 1 positional argument but 2 were given` |
| ex_06_03_legb | 0 | UnboundLocalError 实录；global 计数 2；nonlocal 累加器 3→7 |
| ex_06_04_closure_late_binding | 0 | 坏写法 `[2,2,2]`、好写法 `[0,1,2]`；`__closure__` 捕获 `[2]` |
| ex_06_05_lambda | 0 | sorted key / map / filter 正例与两个反例 |
| ex_07_01_class_basics | 0 | 遮蔽/删除遮蔽过程；可变类属性共享 `c2.items=['书']` |
| ex_07_02_magic_methods | 0 | len/下标/迭代/eq/hash/set 去重全通 |
| ex_07_03_property | 0 | setter 校验 ValueError；只读赋值 `AttributeError: property 'fahrenheit' of 'Temperature' object has no setter` |
| ex_07_04_dataclass | 0 | 自动 `__repr__`/`__eq__`；`FrozenInstanceError: cannot assign to field 'temperature'`；asdict 递归 |
| ex_07_05_inheritance_composition | 0 | super 覆写；组合换部件不改管道 |
| ex_07_06_protocol | 0 | 结构化 isinstance True/False；不满足协议 -> `AttributeError: 'NoMethod' object has no attribute 'summarize'` |
| ex_08_01_eafp | 0 | LBYL/EAFP 等价；脏数据逐条转换；FileNotFoundError strerror/filename |
| ex_08_02_custom_exceptions | 0 | NOT_FOUND 与 VALIDATION_ERROR 两分支，`except AppError` 一次接住 |
| ex_08_03_exception_chain | 0 | 完整链式堆栈含 "The above exception was the direct cause..."；`from None` 后 `__cause__ = None` |
| ex_08_04_context_manager | 0 | 类实现与 @contextmanager 等价；异常路径 finally 仍执行（计时数值每次运行不同） |

## 2. 报错探针（用于教材 N.7 小节的真实报错信息）

```bash
python3 /tmp/probe_errors.py    # 第 1 次在 dataclass 可变默认值定义处崩溃（exit=1），恰好取得真实 ValueError
python3 /tmp/probe_errors2.py   # 补跑剩余探针，exit=0
```

采集到的真实报错（已写入教材 N.7）：

- `[ch04] TypeError: can only concatenate str (not "int") to str`
- `[ch04] AttributeError: 'NoneType' object has no attribute 'append'`
- `[ch05] KeyError: 'phone'`、`IndexError: list index out of range`、`ValueError: list.remove(x): x not in list`
- `[ch06] TypeError: f_multi() got multiple values for argument 'a'`
- `[ch07] TypeError: OrderTypo() takes no arguments`、`TypeError: OrderNoSelf.with_tax() takes 0 positional arguments but 1 was given`、`ValueError: mutable default <class 'list'> for field tags is not allowed: use default_factory`
- `[ch08] TypeError: exceptions must derive from BaseException`；`SyntaxWarning: 'return' in a 'finally' block`（Python 3.14 对 finally 中 return 的告警，实测出现）

## 3. pytest 测试

命令（任务指定）与结果：

```bash
cd /workspace/ai_application_course && python3 -m pytest tests/test_ch04.py tests/test_ch05.py tests/test_ch06.py tests/test_ch07.py tests/test_ch08.py
# 摘要行：33 passed in 0.11s（exit=0）
```

明细：ch04 6 项 / ch05 7 项 / ch06 7 项 / ch07 7 项 / ch08 6 项，共 33 项，覆盖正常/边界/非法输入三类断言。

## 4. 失败与修复过程（如实记录）

1. **测试加载器文件名不匹配**：第一轮 pytest `17 failed, 16 passed`——`load_module("ex_06_01")` 按 `ex_06_01.py` 精确查找，实际文件名含主题 slug（如 `ex_06_01_default_mutable.py`）→ `FileNotFoundError`。修复：加载器改为 `EX_DIR.glob(f"{stem}*.py")` 前缀匹配并断言唯一命中（ch04/ch06/ch07/ch08 四个测试文件同步修正）。复测 33 passed。
2. **ex_04_01 输出含内存地址**：`describe(describe, ...)` 打印函数 repr 带 `0x...` 地址，每次运行不同，不适合作为教材"真实输出"复现 → 改为只打印类型与 isinstance 结果。复跑 exit=0。
3. **ex_04_06 注释与 3.14 实测不符**：教科书惯例写"getrefcount 恒 +1"，实测 Python 3.14.7 返回 1/2/1（临时引用未计入）→ 修正示例注释，明确"绝对值依赖实现细节、看趋势"，教材正文加说明，避免与真实输出矛盾。
4. **ex_08_02 测试数据缺 NotFound 分支**：初版 `["A1001","B2002","X999"]` 三条都命中格式校验 → 改为 `["A1001","A4040","B2002"]`，三条分别覆盖成功/NOT_FOUND/VALIDATION_ERROR。复跑 exit=0。
5. **报错探针脚本在 dataclass 定义处崩溃（exit=1）**：可变默认值在类定义时即抛 ValueError——这本身就是真实行为，顺势把该报错写入教材 7.7；其余探针拆到第二个脚本补跑成功。

## 5. 未验证项 / 待核实（与教材各章"待核实"一致）

- `sys.getrefcount` 临时引用是否计入随 CPython 版本实现变化（本章 3.14.7 实测值已如实记录）。
- 小整数缓存/字符串驻留为 CPython 实现细节，其他实现（PyPy 等）不保证一致。
- ruff/mypy 对可变默认值的规则编号（B006 等）未在沙箱安装 lint 工具核实。
- Protocol `@runtime_checkable` 的校验范围（仅方法存在性）以官方 typing 文档为准；dataclass `slots`/`kw_only` 未展开。
- ExceptionGroup/`except*`（3.11+）留待 ch13 结合 asyncio 演示。
- ex_08_04 的计时数值（2.2 ms 等）为本次真实运行记录，每次运行不同；教材已标注。

## 6. 产物清单

- 教材：`textbook/part02a_python_basics_1.md`（17,750 汉字 / 2,280 行 / 28 个 EX）
- 示例：`examples/ch04_objects/`（6）、`ch05_datastructures/`（7）、`ch06_functions/`（5）、`ch07_classes/`（6）、`ch08_exceptions/`（4）
- 测试：`tests/test_ch04.py` ~ `tests/test_ch08.py`（33 个用例）
- 本记录：`verification/run_logs/part02a.md`
