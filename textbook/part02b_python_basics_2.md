# 第二部分（下册）Python 语言基础：ch09~ch12

> 前置知识：ch04~ch08（对象模型、数据结构、函数与作用域、类与魔术方法、异常体系）。
> 本册四章把语言基础收尾：**ch09 迭代器与生成器**（惰性求值，直接服务于后面的 LLM 流式输出）、**ch10 装饰器**（全书框架代码的共同语法基础）、**ch11 模块与类型系统**（工程组织与 typing）、**ch12 标准库实战**（用一个小 CLI 项目把 json/pathlib/datetime/re/argparse 一次串起来）。
> 代码环境：Python 3.12+（本书全部示例在 3.14.7 上实际运行验证，核实日期 2026-10-19）；本章示例不依赖任何第三方包（ch12 项目联网模式用到 httpx，已在 requirements.txt 中）。

---

# 第 9 章 迭代器与生成器

> **本章目标**：理解迭代协议的两层结构（Iterable/Iterator）；掌握生成器函数的暂停/恢复语义；会用生成器表达式做惰性管道；理解为什么 LLM 流式输出天然就是一个生成器。
> **前置知识**：ch05 列表推导式、ch06 闭包、ch07 `__getitem__` 等魔术方法。
> **学完你能做什么**：把"处理 10GB 日志不爆内存"这类需求写对；看懂 LangGraph 的 `stream()` 返回值并正确消费；为 ch23 的流式 chunk 拼接做好语言层准备。

## 9.1 真实问题引入

你在 Java 里写过这样的代码：一个 10GB 的应用日志文件，要统计 ERROR 行数。用 `Files.readAllLines()` 直接 OOM；老手的做法是 `BufferedReader.readLine()` 一行行读，或用 `Stream` + `Files.lines()` 的惰性管道。**"不要把全部数据装进内存，而要建立一个'按需生产'的管道"**——这就是本章要讲的东西在 Java 里的对应直觉。

AI 应用开发把这个问题变得更日常：调用大模型 API 生成一段 2000 字回答，非流式模式要等几十秒才能拿到完整结果；流式模式下服务端每算出一个 token 就推给你一个 HTTP chunk，用户 1 秒内就看到第一个字。这个"逐 token 推送→客户端逐个消费"的模型，在 Python 里就是生成器（generator）——LangChain 的流式接口、LangGraph 的 `stream()`、FastAPI 的 SSE `StreamingResponse`，底层全部是它。学完本章，你看这些框架代码时看到的是"母语"，而不是魔法。

## 9.2 一句话解释 + 生活类比 + 类比边界

**一句话解释**：迭代器是"会用完的对象"——它只承诺一件事：你再要下一个，我就给你一个，没了就喊停（StopIteration）；生成器是"写起来最省事的迭代器"——函数体里放一个 `yield`，Python 就自动替你实现了整套迭代器协议。

**生活类比**：列表像**水桶**——先把所有水（数据）打满拎回家，随取随用，代价是桶要足够大；生成器像**水龙头**——拧开才出水，用多少接多少，水管里永远只有一股水在流。10GB 日志、百万行数据、无限序列（传感器流、消息队列），都该用水龙头。

**Java 对照**：`Iterable`/`Iterator` 接口 Python 也有同名对应物；`Stream.of(...).map(...).filter(...)` 的"中间操作惰性、终端操作才触发"与生成器表达式管道 `（x for x in ... if ...)` 惰性一致。

> 💡 类比边界：Java Stream 是**声明式管道**——你描述转换规则，JDK 负责拉取，还带短路操作与并行流（`parallelStream()`）；Python 生成器是**语言级的暂停/恢复机制**——函数在 `yield` 处真的停下来，把控制权交还调用方，下次从断点继续。生成器没有"并行流"概念，要并行去 ch13/ch14 找 asyncio 与线程池。此外 Java Stream 只能消费一次，Python 生成器同样只能消费一次——这点两者一致，都是"水龙头关了要重新拧"。

## 9.3 正式原理与准确术语

- **可迭代对象（Iterable）**：实现了 `__iter__()` 方法、能被 `for` 遍历的对象。`list`、`str`、`dict`、文件对象都是。它只负责"发号施令"：每次 `__iter__()` 返回一个（通常是新的）迭代器。
- **迭代器（Iterator）**：实现了 `__next__()` 的对象，负责真正"逐个吐值"；没有下一个值时抛出 `StopIteration`。协议要求迭代器自己也实现 `__iter__()` 并返回 `self`——这样迭代器本身也能被 `for` 消费。
- **迭代协议（iteration protocol）**：`for item in x` 的真实机制是三步——`it = iter(x)` → 反复 `next(it)` → 捕获 `StopIteration` 正常退出。`iter(x)` 等价于调用 `x.__iter__()`，`next(it)` 等价于 `it.__next__()`。
- **生成器函数（generator function）**：函数体中含 `yield` 的函数。调用它**不执行函数体**，而是返回一个**生成器（generator）**对象——生成器是迭代器的一种，由解释器自动实现协议。
- **生成器表达式（generator expression）**：`(expr for x in iterable if cond)`，语法同列表推导式但括号换形，惰性求值。
- **惰性求值（lazy evaluation）**：值在被需要的那一刻才计算。对照：列表推导式是急切求值（eager evaluation）。
- **一次性消费**：迭代器/生成器耗尽后即"空"，再次遍历得到空结果而**不报错**——这是 Java 工程师最容易踩的静默 bug。

> 📌 生产提示：判断"能不能重复遍历"只看一件事——它是**可迭代对象**（每次 for 都拿到新迭代器）还是**裸迭代器/生成器**（一次性）。文件对象是迭代器，读一遍就到 EOF；`list` 是可迭代对象，随便遍历几遍都行。

## 9.4 最小完整示例

`EX-09-01` 手写一遍完整协议，再看 `for` 的等价展开——`for` 循环没有任何魔法：

EX-09-01 | examples/ch09_iterators/ex_09_01_iter_protocol.py

```python
# 完整可运行（节选，完整文件含类型注解与自测）
from collections.abc import Iterator

class Countdown:
    """一个从 start 倒数到 1 的可迭代对象（每次 for 都能重新倒数）。"""
    def __init__(self, start: int) -> None:
        self.start = start
    def __iter__(self) -> Iterator[int]:      # Iterable 的义务：返回一个全新迭代器
        return CountdownIterator(self.start)

class CountdownIterator:
    """迭代器（Iterator）：真正负责"逐个吐出元素"的对象。"""
    def __init__(self, current: int) -> None:
        self.current = current
    def __iter__(self) -> Iterator[int]:      # 协议要求：迭代器必须可迭代
        return self
    def __next__(self) -> int:
        if self.current <= 0:
            raise StopIteration               # "没有下一个了"，for 靠它正常收尾
        value = self.current
        self.current -= 1
        return value
```

真实运行输出（`python3 examples/ch09_iterators/ex_09_01_iter_protocol.py`）：

```text
for 循环拿到: 3
for 循环拿到: 2
for 循环拿到: 1
--- for 的等价展开 ---
手动 next 拿到: 3
手动 next 拿到: 2
手动 next 拿到: 1
第一次: [3, 2, 1]
第二次: [3, 2, 1]
迭代器第一次消费: [3, 2, 1]
迭代器第二次消费: []
```

两个关键观察：`Countdown` 被 `for`/`list()` 消费两次结果一致（可迭代对象每次给新迭代器）；而 `iter(Countdown(3))` 拿到的裸迭代器第二次消费就是 `[]`（一次性）。

Java 对照：`Countdown` 相当于实现了 `Iterable<Integer>`，`CountdownIterator` 相当于 `Iterator<Integer>`——但 Java 的 for-each 不需要 `hasNext()`/`next()` 手写展开给你看，Python 这里的"等价展开"代码就是解释器在幕后做的事。

## 9.5 逐段解释：yield 的暂停/恢复语义

手写迭代器要维护状态（`self.current`）、写两个类。生成器把这一切压缩成一个带 `yield` 的函数。EX-09-02 用日志把执行轨迹打出来：

EX-09-02 | examples/ch09_iterators/ex_09_02_generator_yield.py

```python
# 节选
def trace_generator(steps: list[str], n: int) -> Iterator[int]:
    """生成器函数：只要函数体里出现 yield，它就不再是普通函数。"""
    steps.append("1. 生成器函数体开始执行（第一次 next 时才启动，调用时不执行！）")
    for i in range(1, n + 1):
        steps.append(f"2. 准备 yield {i}")
        steps.append(f"3. yield {i}：值交给调用方，函数在此【暂停】")
        yield i
        steps.append(f"4. 恢复执行：调用方又调了 next，i={i} 这一轮结束")
    steps.append("5. 函数体执行完毕，隐式抛出 StopIteration")

gen = trace_generator([], 3)   # ← 此刻函数体一行都没执行，只返回生成器对象
first = next(gen)              # 执行到第一个 yield 暂停，值 1 交出
second = next(gen)             # 从上一个 yield 的"下一行"恢复，走到下一个 yield
```

真实运行输出（`python3 examples/ch09_iterators/ex_09_02_generator_yield.py`）：

```text
刚创建生成器，steps = []
gen 是: generator

next() -> 1
1. 生成器函数体开始执行（第一次 next 时才启动，调用时不执行！）
2. 准备 yield 1
3. yield 1：值交给调用方，函数在此【暂停】

next() -> 2
4. 恢复执行：调用方又调了 next，i=1 这一轮结束
2. 准备 yield 2
3. yield 2：值交给调用方，函数在此【暂停】

next() -> 3
4. 恢复执行：调用方又调了 next，i=2 这一轮结束
2. 准备 yield 3
3. yield 3：值交给调用方，函数在此【暂停】

第 4 次 next(): 抛出 StopIteration（生成器结束）
4. 恢复执行：调用方又调了 next，i=3 这一轮结束
5. 函数体执行完毕，隐式抛出 StopIteration
```

逐条对应协议：**调用生成器函数**≠调用普通函数，它只造出对象；**第一次 next** 启动函数体跑到第一个 `yield`，交出值并冻结局部状态（连 `for` 循环变量 `i` 都冻在原地）；**后续 next** 从断点恢复；**函数体走完**隐式抛 `StopIteration`。`yield` 与 `return` 的区别就此清晰：`return` 终结函数帧，`yield` 只是挂起它。生成器函数里也可以写 `return`，裸 `return` 等价于"到此为止"。

Java 里最接近的体验是 `Stream.iterator()` 的拉取，但 Stream 管道你无法在中间"暂停一个正在执行的函数体"——`yield` 的暂停/恢复是协程思想（ch13 的 `async/await` 与它是同一套底层机制，`await` 本质上就是 `yield` 的异步版）。

### 9.5.1 生成器表达式与惰性求值

EX-09-03 | examples/ch09_iterators/ex_09_03_genexpr_lazy.py

```python
# 节选
list_comp = [x * x for x in range(1_000_000)]   # 急切：100 万个数立刻算完进内存
gen_expr  = (x * x for x in range(1_000_000))   # 惰性：只"记住怎么算"
total = sum(x * x for x in range(100))          # 作为唯一实参时可省一层括号
```

真实运行输出（`python3 examples/ch09_iterators/ex_09_03_genexpr_lazy.py`，字节数因解释器版本略有差异）：

```text
列表推导式占用内存: 8,448,728 字节
生成器表达式占用内存: 208 字节
创建 gen_expr 时算过任何数了吗？答案：没有——此刻才惰性地算第一个:
第一个值: 0
sum(生成器表达式) 1..99 的平方和: 328350
第一次 sum: 30
第二次 sum: 0
管道结果: [5, 5, 6, 6]
```

8.4 MB 对 208 字节——这就是"水桶 vs 水龙头"的量化。末尾的"第二次 sum: 0"就是 9.3 说的静默 bug：生成器耗尽后不报错、只给空。生成器管道的写法（多条 `(w for w in ...)` 链起来）对应 Java Stream 的 `.map().filter()` 链——数据流过管道时中间不落大集合。

### 9.5.2 AI 场景挂钩：模拟 LLM 流式输出

EX-09-04 | examples/ch09_iterators/ex_09_04_llm_stream.py

```python
# 节选（MODE=mock，离线演示；真实 API 流式调用见 ch23/ch24）
MOCK_TOKENS: list[str] = ["迭代器", "是", "Python", "中", "实现", "惰性", "求值", ...]

def stream_tokens(mode: str | None = None, delay: float = 0.0) -> Iterator[str]:
    """模拟流式 API：每被要一次，才吐出一个 token。"""
    for token in MOCK_TOKENS:
        if delay > 0:
            time.sleep(delay)      # 模拟模型出字延迟
        yield token

for token in stream_tokens():
    print(token, end="", flush=True)   # 边生成边显示 = 打字机效果
```

真实运行输出（`python3 examples/ch09_iterators/ex_09_04_llm_stream.py`；耗时数字随机器浮动）：

```text
[1] 逐 token 消费（用户看到打字机效果）:
迭代器是Python中实现惰性求值的基石。LLM流式输出正是它的最佳实战场景。EOF
    共 20 个 token，消费耗时 0.53 ms

[2] 首字延迟对比（惰性的价值）:
    全量模式拿到第一个字: 100.07 ms
    流式模式拿到第一个字: 0.0186 ms（token='迭代器'）

[3] 中途停止消费（生成器被抛弃，后面的 token 根本不会生成）:
迭代器 是 Python 中 实现 惰性 求值 … 用户点了"停止生成"，循环 break
```

三个输出对应三个生产事实：**[1]** 前端"打字机效果"就是 for 循环逐个消费 token；**[2]** 首字延迟（first-token latency）从"全量等待"的 100ms 降到"流式"的 0.02ms——真实场景中这个差距是"几十秒 vs 一秒"；**[3]** 用户点"停止生成"时，服务端只需放弃这个生成器，还没生成的 token 根本不会被计算——**惰性求值直接变成了算力省钱**。ch23 的流式 chunk 拼接、ch17 的 SSE `StreamingResponse`，消费端写的都是今天这个 for 循环。

### 9.5.3 yield from 委托与无限生成器

流式场景再进一步：Agent 的多轮工具调用中，外层循环每轮产生一段流式输出，最终消费者只想"拿到一条连续的 token 流"——把子生成器的值逐个透传出去的语法就是 `yield from`。EX-09-05 | examples/ch09_iterators/ex_09_05_yield_from.py：

```python
# 节选
def stream_round(round_id: int) -> Iterator[str]:
    """子生成器：模拟"一轮"的流式输出。"""
    for token in (f"[r{round_id}]", "模型", "输出", "片段", "|"):
        yield token

def agent_stream(rounds: int) -> Iterator[str]:
    """外层生成器：yield from 把每一轮的子流原样透传给最终消费者。"""
    for r in range(1, rounds + 1):
        yield from stream_round(r)   # 委托：子生成器的每个值都"直通"外层
    yield "DONE"

head = list(itertools.islice(counter(2), 5))   # 无限生成器 + islice 安全截断
```

真实运行输出（`python3 examples/ch09_iterators/ex_09_05_yield_from.py`）：

```text
[1] yield from 透传多轮流式输出:
[r1]模型输出片段|[r2]模型输出片段|[r3]模型输出片段|DONE

[2] 无限生成器 + islice 安全截断（取前 5 个）:
前 5 个: [0, 2, 4, 6, 8] ← 无限生成器也没撑爆内存

[3] 危险示范：直接对无限生成器 list() 会永远卡住——所以永远别这么做
```

两个工程要点：`yield from` 是"生成器套生成器"的标准接法，省掉手写 `for t in sub: yield t` 的转发循环（它还能接收子生成器的返回值，本章不展开）；无限生成器（`while True: yield`）是消息队列/传感器流/分页轮询的模型，**必须配 `islice`/`break`/超时截断消费**——对它 `list()` 程序会永远卡住，这是生成器一章最危险的一行代码。

## 9.6 安装 / 文件位置 / 运行命令

| 项目 | 内容 |
|---|---|
| 文件位置 | `examples/ch09_iterators/`（ex_09_01 ~ ex_09_05，零第三方依赖） |
| 运行命令 | `python3 examples/ch09_iterators/ex_09_01_iter_protocol.py`（其余同理） |
| 安装 | 无需安装任何东西，Python 3.10+ 自带 |

## 9.7 常见错误与排查

**① `TypeError: 'list' object is not an iterator`**
原因：对 `list` 直接 `next(lst)`。列表是可迭代对象（Iterable）不是迭代器，协议第一层与第二层不能混。
修复：`it = iter(lst)` 后再 `next(it)`。

**② `TypeError: object of type 'generator' has no len()`**
原因：把生成器当列表用——`len(squares)`、`squares[0]`、`for x in squares` 之外的一切"容器操作"。
修复：确定要随机访问/多次消费就 `list(gen)` 物化；只要遍历一次就保持生成器。

**③ 生成器"第二次消费为空"的静默 bug**
现象：`sum(gen)` 得 30，再 `sum(gen)` 得 0，无任何报错。原因：迭代器一次性。修复：需要多次消费时每次重新创建生成器（把生成器表达式包进函数，调用几次就新建几次），或先物化成列表。

**④ 生成器函数被"当普通函数调用"**
现象：`result = my_gen(x)` 后 `result` 是 `generator` 对象，函数体一行未执行。原因：含 `yield` 的函数调用即造对象。修复：用 `for`/`next()`/`list()` 消费它；不需要惰性就删掉 `yield`。

## 9.8 企业场景中的使用方式

- **大文件 ETL/日志清洗**：`def read_lines(path): ... yield line` 逐行管道，内存占用恒定，对应 Java 的 `Files.lines()`。ch12 的收束项目里你会看到同样的"管道式清洗"。
- **SSE 流式接口**：FastAPI 的 `StreamingResponse(generator)`（ch17）——你给框架一个生成器，框架负责把它变成 HTTP chunk 流。
- **LangGraph/LangChain 流式**：`graph.stream(input, stream_mode="updates")` 返回的就是生成器（ch50），本章的暂停/恢复语义是理解"节点执行到一半也能吐状态"的基础。
- **分页拉取上游 API**：把"while 循环翻页 + yield 每页数据"包成生成器，调用方用 `for page in fetch_all(): ...` 一行消费，翻页细节被封装——比 Java 手写 `while (hasNext) { ... }` 更干净。

## 9.9 练习

1. **基础**：不运行代码，写出 `list(zip("ab", (x for x in range(5))))` 的结果，并说明第二个参数为什么不耗内存。
2. **基础**：`gen = (i for i in range(3))`，执行 `list(gen)` 两次，各得到什么？为什么？
3. **代码**：写生成器函数 `chunked(items: list[T], size: int)`，把列表按 size 切块逐块 yield，如 `chunked([1,2,3,4,5], 2)` → `[1,2]`、`[3,4]`、`[5]`。
4. **代码**：写一个可重复遍历的 `Fibonacci` 类（可迭代对象），前 n 项斐波那契；并用生成器函数重写一版，对比代码量。
5. **调试**：下面的函数想"边解析边返回"，但调用方拿到的是空结果，找出来并修复：
   `def parse(lines): for l in lines: if "ERROR" in l: print(l); return l`——提示：函数里既没有 yield 也没有累积。

### 参考答案

<details>
<summary>点开查看参考答案</summary>

1. `[('a', 0), ('b', 1)]`。生成器表达式只是"生产计划"，zip 拉到 2 个就停（`a`、`b` 消费完了），剩余计划从未执行——惰性。
2. 第一次 `[0, 1, 2]`，第二次 `[]`。生成器一次性消费，耗尽后为空且不报错。
3. 参考实现：
   ```python
   def chunked(items: list[T], size: int) -> Iterator[list[T]]:
       for i in range(0, len(items), size):
           yield items[i:i + size]
   ```
4. 类版本需要 `__init__`/`__iter__`/`__next__`/`StopIteration` 四件套；生成器版本 3 行：`def fib(n): a, b = 0, 1; for _ in range(n): yield a; a, b = b, a + b`。生成器赢在状态由解释器的函数帧自动保存。
5. `return l` 在第一行 ERROR 就退出了整个函数，且函数无 `yield`，调用方拿到的是 `None`（不是生成器）。修复：把 `return l` 改成 `yield l`——函数含 `yield` 后调用即返回生成器，调用方 `for hit in parse(lines)` 逐个拿到 ERROR 行。
</details>

## 9.10 自测检查表

- 我能说清 Iterable 与 Iterator 两层协议各自的职责与联系。
- 我能手写出"for 循环的等价展开"三步（iter/next/StopIteration）。
- 我能解释：为什么调用生成器函数时函数体一行都不执行。
- 我能区分哪些对象可重复遍历、哪些一次性，并说出生成器二次消费为 0/空而不报错这个静默坑。
- 我能用 `sys.getsizeof` 证明生成器表达式的惰性。
- 我能讲清 LLM 流式输出与生成器的对应关系，以及"停止生成"为什么省钱。
- 我知道什么时候不该用生成器：需要 len/索引/多次遍历时。

## 9.11 面试追问

1. **[模拟题] 生成器和迭代器什么区别？** 迭代器是协议（`__next__`+`StopIteration`）；生成器是"用 yield 自动实现该协议的函数/表达式"。所有生成器都是迭代器，反之不成立；生成器的增量价值是暂停/恢复语义与零成本状态保存。
2. **[模拟题] 为什么生成器省内存？省的是什么？** 省"中间全量物化"：急切方式要把全部中间结果放进容器（8.4MB→208 字节实测）；惰性方式任一时刻只存在"一个在路上的值"。但它不省总计算量——该算的一个都不会少，只是摊开到消费时。
3. **[模拟题] yield 的暂停恢复是怎么做到的？** CPython 把生成器函数编译成特殊的字节码帧：yield 时帧不销毁、栈与局部变量冻结在生成器对象里；next 时恢复栈指针继续执行。你能拿到的面试结论：状态保存在函数帧里，不是闭包变量。
4. **[模拟题] LLM 流式输出里，客户端断开了怎么办？** 消费端放弃生成器（for 循环 break/连接断开触发框架丢弃迭代器），生成器被 GC 后其帧销毁，后续 token 不再计算；服务端还要配合取消 HTTP 上游连接——只答"break 就行"不完整，需提上游取消。

### 待核实

- `sys.getsizeof` 的具体字节数随 CPython 版本/平台浮动（本书记录的是 3.14.7 实测值）。
- 生成器 `return 值` 会成为 `StopIteration.value`（`yield from` 可接住）——本章未展开，细节以官方语言参考为准。

---

# 第 10 章 装饰器

> **本章目标**：理解"函数是一等公民→高阶函数→装饰器"这条推导链；掌握带参数装饰器的三层嵌套；写出计时、重试、调用日志三个生产可用的装饰器；能对照 Spring AOP 说清异同。
> **前置知识**：ch06 闭包（`*args/**kwargs`）、ch08 异常。
> **学完你能做什么**：看懂 FastAPI 的 `@app.get(...)`、LangChain 的 `@tool`、Pydantic 的 `@field_validator` 在做什么；为后文的重试/幂等/审计埋点写出自己的装饰器。

## 10.1 真实问题引入

Java 里你要给 20 个服务方法统一加计时和重试，答案是 Spring AOP：写一个 `@Around` 切面 + 自定义注解 `@Timed`/`@Retryable`，容器在启动时为 bean 生成代理对象织入逻辑。**注解本身没有行为，行为来自框架的注解处理器。**

Python 里没有编译期注解处理，也没有容器代理——但函数是一等公民：函数可以赋值给变量、当作参数传递、从别的函数里返回。于是"包装一个函数"不需要任何框架，语言原生就能表达：`timed(fetch_order)` 返回一个包了计时逻辑的新函数。装饰器语法 `@timed` 只是它的缩写。本章你会亲手写出 Spring AOP 里那三类最常用通知（计时、重试、日志）的 Python 原生版本，每个不超过二十行。

## 10.2 一句话解释 + 生活类比 + 类比边界

**一句话解释**：装饰器是一个"接收函数、返回新函数"的函数；`@deco` 写在被装饰函数上方，等价于 `f = deco(f)`——用包装后的新函数顶替原名字。

**生活类比**：手机壳。手机（原函数）功能不变，套上壳（包装函数）就多了防摔（计时/日志/重试）能力；`f = deco(f)` 相当于"把套了壳的手机放回原来的盒子"——外人拿到的还是那个名字，里面的东西已经升级。

**Java 对照**：装饰器 ≈ **注解 + AOP 通知**的组合体。`@timed` 的"标记"角色像 `@Timed` 注解，wrapper 的"包裹执行"角色像 `@Around` 通知。

> 💡 类比边界：① Spring AOP 由容器在**代理层**织入，可以按切点表达式批量匹配几十个 bean，还能管到"你没写注解的方法"；Python 装饰器是**函数级的显式包装**，作用范围就是你写了 `@` 的那一行——没有隐式魔法，也因此更可见。② Java 注解是数据（反射读取），AOP 是行为；Python 装饰器本身就是行为，装饰的那一刻（import 时）就执行了。③ AOP 能做事务传播、异常回滚这类需要框架运行时的复杂逻辑；装饰器裸写时没有事务管理器可用，需要什么就得显式传什么。

## 10.3 正式原理与准确术语

- **一等公民（first-class object）**：函数与 int/str 地位相同——可赋值、可传参、可返回、可放进容器。`fn = slow_double` 拿到的是函数对象本身（不带括号！）。
- **高阶函数（higher-order function）**：接收函数为参数或返回函数的函数。`timed(func)` 两者都是。
- **闭包（closure）**：wrapper 记住了外层函数的 `func` 变量（ch06 已讲），这是包装逻辑能调用原函数的原因。
- **装饰器（decorator）**：`@deco` 语法糖，`f = deco(f)`，**发生在 import/定义时，只执行一次**。
- **装饰器工厂（decorator factory）**：带参数的装饰器外再多包一层：`@retry(times=3)` 先执行 `retry(times=3)` 得到真正的装饰器，再装饰函数。
- **functools.wraps**：把原函数的 `__name__/__doc__/__module__/__qualname__/__wrapped__` 等元数据拷回 wrapper 的标准工具。不加的后果见 10.5.1。
- **类装饰器**：`__init__` 接收函数、`__call__` 执行包装的类；实例本身就是可调用对象，适合需要"跨调用状态"的场景。

## 10.4 最小完整示例

EX-10-01 | examples/ch10_decorators/ex_10_01_first_class.py

```python
# 节选
def timed(func: Callable[..., Any]) -> Callable[..., Any]:
    """接收一个函数，返回一个"包了一层计时逻辑"的新函数。"""
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.perf_counter()
        result = func(*args, **kwargs)          # 原函数在这里才真正执行
        print(f"[timed] {func.__name__} 耗时 {(time.perf_counter() - start) * 1000:.2f} ms")
        return result
    return wrapper

slow_double_timed = timed(slow_double)   # 手动装饰

@timed                                    # 语法糖，与上一行完全等价
def slow_triple(x: int) -> int: ...
```

真实运行输出（`python3 examples/ch10_decorators/ex_10_01_first_class.py`）：

```text
fn 是函数吗: True | 调用结果: 20
手动装饰后调用:
[timed] slow_double 耗时 50.07 ms

@timed 版本:
[timed] slow_triple 耗时 50.07 ms
手动 timed(...) 版本:
[timed] slow_triple 耗时 50.07 ms
[timed] wrapper 耗时 50.08 ms

wrapper 替换原函数后:
slow_triple.__name__ = wrapper ← 已不是 slow_triple！
```

最后一行埋下本章第一个雷：装饰后模块里的名字 `slow_triple` 已经指向 `wrapper`——这就是 10.5.1 要用 `functools.wraps` 修的问题。

## 10.5 逐段解释

### 10.5.1 functools.wraps 的必要性

EX-10-02 | examples/ch10_decorators/ex_10_02_timer_decorator.py

```python
# 节选
def timed(func: Callable[..., Any]) -> Callable[..., Any]:
    @functools.wraps(func)          # ← 只加这一行：把元数据拷回 wrapper
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.perf_counter()
        result = func(*args, **kwargs)
        print(f"[timed] {func.__name__} 耗时 {(time.perf_counter() - start) * 1000:.2f} ms")
        return result
    return wrapper
```

真实运行输出（`python3 examples/ch10_decorators/ex_10_02_timer_decorator.py`）：

```text
[timed_naive] fetch_order_naive 耗时 20.07 ms
order:A001
[timed] fetch_order 耗时 20.07 ms
order:A002

--- 元数据对比 ---
naive.__name__: wrapper
naive.__doc__  : None
wraps.__name__: fetch_order
wraps.__doc__  : 查询订单（docstring 被 wraps 保留）。

--- 为什么这很重要：help()/调试器/日志都会读元数据 ---
带 wraps 后函数签名模块: __main__
带 wraps 的 __wrapped__ 指回原函数: fetch_order
```

不加 wraps：`__name__` 变 `wrapper`、docstring 丢失。受害的是**工具链**：日志里函数名全叫 wrapper、`help()` 显示不了文档、调试器堆栈可读性崩塌、基于函数名做路由/注册的框架直接失效。`@functools.wraps(func)` 是装饰器的标配，写上不需要理由，不写才需要理由。

### 10.5.2 带参数装饰器：三层嵌套

EX-10-03 | examples/ch10_decorators/ex_10_03_retry_decorator.py

```python
# 节选：三层各管一件事
def retry(times: int, base_delay: float = 0.0):
    # 第一层（装饰器工厂）：接收装饰器自己的参数；参数校验放这里，装饰时立刻报错
    if times < 1:
        raise ValueError(f"times 必须 >= 1，收到 {times}")
    def decorator(func):
        # 第二层：接收被装饰函数（和普通装饰器一样）
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # 第三层：真正执行的包装逻辑——十行重试核心
            for attempt in range(1, times + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:
                    if attempt == times:
                        raise                      # 最后一次失败：原样上抛
                    delay = base_delay * (2 ** (attempt - 1))   # 指数退避
                    print(f"  第 {attempt} 次失败: {exc}，{delay:.2f}s 后重试")
                    time.sleep(delay)
        return wrapper
    return decorator

@retry(times=3, base_delay=0.01)
def flaky_fetch(url: str, fail_times: int) -> str: ...
```

真实运行输出（`python3 examples/ch10_decorators/ex_10_03_retry_decorator.py`）：

```text
[场景1] 前两次失败，第三次成功：
  第 1 次失败: ConnectionError: 连接 https://api.example.com/orders 超时，0.01s 后重试（指数退避）
  第 2 次失败: ConnectionError: 连接 https://api.example.com/orders 超时，0.02s 后重试（指数退避）
结果: 200 OK from https://api.example.com/orders

[场景2] 重试次数用尽，异常向上抛：
  第 1 次失败: TimeoutError: 服务端一直 503，0.01s 后重试（指数退避）
捕获到最终异常: TimeoutError: 服务端一直 503

[场景3] 参数非法，装饰时就报错（不用等运行）：
ValueError: times 必须 >= 1，收到 0
```

记忆锚点：**@后面带不带括号，决定你写几层**。`@retry` → 两层（retry 直接当装饰器）；`@retry(times=3)` → 三层（先求值 `retry(times=3)` 得到装饰器）。场景 2 的"最后一次异常原样上抛"与场景 3 的"配置错误装饰时就炸"是生产代码的两个关键素质——这个十行重试是 ch15「HTTP 重试+指数退避」和 ch50 LangGraph `RetryPolicy` 的种子代码：到那时你会看到框架的重试只是把这里的手写循环换成了策略对象。

### 10.5.3 调用日志：为幂等与审计埋点

EX-10-04 | examples/ch10_decorators/ex_10_04_call_log.py

```python
# 节选：logging 而非 print（工程规范）；记录 trace_id / 入参 / 结果 / 耗时 / 异常
@functools.wraps(func)
def wrapper(*args: Any, **kwargs: Any) -> Any:
    call_id = uuid.uuid4().hex[:8]              # trace_id 思想：一次调用一个标识
    logger.info("[%s] -> %s args=%s kwargs=%s", call_id, func.__name__, args, kwargs)
    try:
        result = func(*args, **kwargs)
    except Exception:
        logger.exception("[%s] !! %s 失败", call_id, func.__name__)
        raise                                    # 记录后原样上抛，绝不吞异常
    logger.info("[%s] <- %s 返回=%r", call_id, func.__name__, result)
    return result
```

真实运行输出（`python3 examples/ch10_decorators/ex_10_04_call_log.py`，时间与 trace_id 每次不同）：

```text
2026-10-19 01:23:46,882 INFO __main__ - [97937ece] -> submit_refund args=('SO-1001', 199.0) kwargs={'idem_key': 'idem-001'}
2026-10-19 01:23:46,882 INFO __main__ - [97937ece] <- submit_refund 返回='refunded:SO-1001:199.00' 耗时 0.01 ms
2026-10-19 01:23:46,882 INFO __main__ - [145501fb] -> submit_refund args=('SO-1001', 199.0) kwargs={'idem_key': 'idem-001'}
2026-10-19 01:23:46,882 INFO __main__ - 幂等命中：idem-001 已处理过，直接返回，不重复退款
2026-10-19 01:23:46,882 INFO __main__ - [145501fb] <- submit_refund 返回='duplicated:idem-001' 耗时 0.08 ms
2026-10-19 01:23:46,882 INFO __main__ - [9b871018] -> risky_divide args=(10, 0) kwargs={}
2026-10-19 01:23:46,882 ERROR __main__ - [9b871018] !! risky_divide 失败，耗时 0.00 ms
Traceback (most recent call last):
  ...（logger.exception 打印完整堆栈）
ZeroDivisionError: division by zero
2026-10-19 01:23:46,883 INFO __main__ - 上层已按预期捕获 ZeroDivisionError
2026-10-19 01:23:46,883 INFO __main__ - [4aafa3e2] -> risky_divide args=(10, 4) kwargs={}
2026-10-19 01:23:46,883 INFO __main__ - [4aafa3e2] <- risky_divide 返回=2.5 耗时 0.00 ms
```

注意三个工程细节：日志用 `logging`+参数化格式（`%s` 惰性格式化，非 f-string，ch02 讲过原因）；异常路径用 `logger.exception` 记录堆栈后 `raise` 原样上抛（装饰器吞异常是生产事故常见根源）；退款示例内置**幂等键**检查——同一个 `idem_key` 第二次调用直接返回 `duplicated:`，不重复执行副作用。这套"调用日志+幂等键"的组合，在 ch48（LangGraph 人工介入恢复后的副作用幂等）和 ch54（工具治理的审计日志）会原样复用——今天埋的点，就是那两章的扣子。

### 10.5.4 类装饰器与注册表

EX-10-05 | examples/ch10_decorators/ex_10_05_class_decorator.py

```python
# 节选
class CountCalls:
    def __init__(self, func):
        functools.update_wrapper(self, func)   # 类装饰器同样要拷元数据
        self.func = func
        self.calls = 0
    def __call__(self, *args, **kwargs):       # 实例变可调用对象
        self.calls += 1
        return self.func(*args, **kwargs)

TOOL_REGISTRY: dict[str, Callable[..., Any]] = {}
def register(name: str):
    def decorator(func):
        TOOL_REGISTRY[name] = func
        return func                             # 注册器不替换函数，只登记
    return decorator
```

真实运行输出（`python3 examples/ch10_decorators/ex_10_05_class_decorator.py`）：

```text
[1] 类装饰器跨调用计数：
  [CountCalls] ping 第 1 次调用
  [CountCalls] ping 第 2 次调用
  [CountCalls] ping 第 3 次调用
  ping 一共被调用 3 次（状态在实例上，函数自身做不到）

[2] 注册表装饰器（工具注册，LangChain @tool 同思想）：
  注册工具 'query_weather'
  注册工具 'query_order'
  按名调用: 上海：晴，26℃
  按名调用: 订单 SO-2002：已发货
```

跨调用状态用类（状态存实例属性），"登记不替换"用注册表装饰器——FastAPI 的 `@app.get("/x")` 把路径→函数登记进路由表、LangChain 的 `@tool` 把函数登记成工具并生成参数 schema，都是 `register` 这二十行的放大版。**你今天写的不是玩具，是框架核心机制的等比模型。**

## 10.6 安装 / 文件位置 / 运行命令

| 项目 | 内容 |
|---|---|
| 文件位置 | `examples/ch10_decorators/`（ex_10_01 ~ ex_10_05，零第三方依赖） |
| 运行命令 | `python3 examples/ch10_decorators/ex_10_03_retry_decorator.py`（其余同理） |
| 安装 | 无需安装（生产重试可评估 tenacity，但不在本书锁定依赖内，使用前自行核实版本） |

## 10.7 常见错误与排查

**① 忘写 `@functools.wraps`**
现象：日志/报错里函数名全是 `wrapper`；`help(f)` 空白；按名字注册的框架行为错乱。
原因：wrapper 顶替了原函数名，元数据没拷贝。
修复：wrapper 定义上方加 `@functools.wraps(func)`（类装饰器用 `functools.update_wrapper`）。

**② 带参装饰器少写一层**
现象：写 `@retry` 却把 `retry` 写成了三层工厂——被装饰函数被当成 `times` 参数，调用时报 `TypeError: 'function' object is not subscriptable` 之类；反向错误是 `@retry(times=3)` 却只写两层，装饰时直接 `TypeError: 'int' object is not callable`（把 `3` 当装饰器去调用 func）。
修复：记住口诀——**@后面带括号=三层，不带括号=两层**；报错发生在"装饰时"还是"调用时"能帮你定位少/多了哪层。

**③ 装饰器吞异常**
现象：加了日志/重试装饰器后，上层永远捕获不到异常，接口返回 None。
原因：wrapper 里 `try/except` 后没有 `raise`（或 `return func(...)` 写进了 try 的 except 分支）。
修复：日志装饰器 except 里 `logger.exception(...)` 后必须 `raise`；重试装饰器只在"还有重试机会"时继续循环。

**④ 用同步装饰器包装 async 函数（提前预警 ch13）**
现象：装饰异步接口后返回值变成 coroutine，`RuntimeWarning: coroutine 'xxx' was never awaited`。
原因：同步 wrapper 调用 `func(*args)` 只是创建了协程对象，没有 await。
修复：异步函数要配 `async def wrapper` + `await func(...)` 的异步装饰器（ch13 展开）。

**⑤ 多个装饰器的执行顺序想反**
`@a` `@b` `def f` 等价于 `f = a(b(f))`——**自下而上装饰，自上而下执行**。计时套重试时想清楚哪层在外（重试在外层时，计时统计的是"含重试的总耗时"）。

## 10.8 企业场景中的使用方式

| 需求 | Java（Spring） | Python |
|---|---|---|
| 方法计时 | `@Timed`（Micrometer）+ AOP 切面 | `@timed` 装饰器（本章 EX-10-02） |
| 自动重试 | `@Retryable`（Spring Retry） | `@retry(times=N)`（本章 EX-10-03）/ tenacity |
| 审计日志 | AOP + MDC traceId | `@call_log`（本章 EX-10-04）+ trace_id |
| 路由注册 | `@GetMapping("/x")` | `@app.get("/x")`（ch17） |
| 工具注册 | —— | `@tool`（ch39） |

规律：Spring 用"注解标记+容器扫描"做**隐式批量**织入；Python 社区习惯"装饰器显式"声明——每个函数头上一行，肉眼可见，无容器魔法。AI 应用代码里装饰器密度远高于典型 Java 业务代码（FastAPI/LangChain/Pydantic 全靠它），所以本章不是"语法糖课"，而是框架源码的阅读预科。

## 10.9 练习

1. **基础**：`@a` `@b` `def f(): ...` 等价于哪一行赋值语句？a、b 的调用顺序是？
2. **基础**：装饰器什么时候执行——函数被调用时，还是模块被导入时？执行几次？
3. **代码**：写装饰器 `@suppress_errors(default_value)`：被装饰函数抛异常时记录 warning 并返回 default_value（思考：这个装饰器用在什么场景是危险的？）。
4. **代码**：给 EX-10-03 的 retry 增加参数 `exceptions=(Exception,)`，只对元组里的异常重试，其他异常立刻上抛。写出完整三层。
5. **调试**：小王写了 `@cache_result` 装饰器把结果存进字典，单元测试发现第二个不同参数的调用返回了第一个参数的结果。最可能的 bug 是什么？（提示：检查缓存键是怎么算的——`str(args)` 会把 `'1'` 和 `1` 混淆吗？）

### 参考答案

<details>
<summary>点开查看参考答案</summary>

1. `f = a(b(f))`。装饰自下而上（先 b 后 a），调用时 wrapper 逻辑自上而下（先 a 的外层逻辑）。
2. 导入/定义时执行一次；之后每次调用函数执行的只是 wrapper。
3. 参考实现（省略类型注解）：`def suppress_errors(default_value): def deco(f): @wraps(f) def w(*a, **k): try: return f(*a, **k) except Exception: logger.warning("...", exc_info=True); return default_value; return w; return deco`。危险场景：支付/写库等有副作用的操作——失败被静默吞掉返回默认值，调用方以为成功了；它只适合"展示类可降级"读路径。
4. 要点：`except exceptions as exc:`（元组捕获）；最后一次失败 `raise`；注意 `exceptions` 必须可迭代且元素是异常类。完整结构与 EX-10-03 相同，仅 except 行变化。
5. 缓存键用 `str(args)` 之类会撞键（`(1,)` 与 `('1',)` 的字符串表示可能冲突，或 kwargs 未参与键计算）。正确做法：键 = `(args, tuple(sorted(kwargs.items())))`，或用 `functools.lru_cache`（生产首选，别手写缓存）。
</details>

## 10.10 自测检查表

- 我能不看书写出"手动装饰"三步：定义 wrapper、闭包引用 func、返回 wrapper。
- 我能解释 `@deco` 为什么等价于 `f = deco(f)`，以及它发生在 import 时。
- 我能写出带参数装饰器的三层结构，并说出每层接收什么。
- 我知道不加 functools.wraps 会坏掉哪些工具链（日志名/help/注册）。
- 我能对照 Spring AOP 说清装饰器与注解+AOP 的两条差异（显式 vs 切点批量；装饰时执行 vs 容器代理）。
- 我写装饰器时会默认：拷元数据、不吞异常、参数校验放工厂层。
- 我能说出多装饰器"自下而上装饰、自上而下执行"。

## 10.11 面试追问

1. **[模拟题] 装饰器和 Java 注解是一回事吗？** 不是。Java 注解只是元数据，行为靠注解处理器/AOP 反射织入；Python 装饰器本身就是可执行的高阶函数，装饰发生在 import 时。功能上"注解+AOP"≈"装饰器"，机制完全不同。
2. **[模拟题] 为什么带参数装饰器要三层？每一层是什么？** `@retry(times=3)` 先求值 `retry(times=3)`（第一层工厂，收参数、做校验）返回装饰器（第二层，收函数）返回 wrapper（第三层，收调用参数、执行包装逻辑）。
3. **[模拟题] functools.wraps 不加会怎样？举一个真实事故形态。** 元数据丢失。事故形态：基于函数名注册的插件路由（类似 FastAPI 路由表）在装饰后名字全变 wrapper，导致两个路由互相覆盖、请求 404/错路由。
4. **[模拟题] 装饰器、闭包、高阶函数三者关系？** 高阶函数是"收/返函数"的函数；闭包是 wrapper 能访问 func 的机制（内层函数记住外层变量）；装饰器是"高阶函数+闭包"在 `@` 语法下的工程化应用。

### 待核实

- tenacity 等生产重试库的当前 API 与版本不在本书锁定依赖内，使用前请以官方文档为准。
- Python 3.12+ 对装饰器新增了 PEP 695 之外的语法演进（如 PEP 649 延迟注解对装饰器的影响），本章未涉及；如需深挖以官方发布说明为准。

---

# 第 11 章 模块与类型系统

> **本章目标**：吃透 `__name__ == "__main__"` 与 import 搜索机制；会用包结构组织工程、识别并解开循环导入；掌握 typing 现代写法（`list[str]`、`X | None`、TypedDict、Protocol、Literal、Annotated、TypeVar）；分清"静态类型检查"与"运行时校验"的边界。
> **前置知识**：ch04 名字绑定、ch07 Protocol、ch08 异常。
> **学完你能做什么**：把散装脚本重构成规范的包结构；写出 mypy/pyright 友好的类型注解；看懂 LangGraph 的 `State`（就是 TypedDict）与 FastAPI 的类型驱动设计。

## 11.1 真实问题引入

Java 工程师初到 Python 常撞三堵墙：① 写了个 `utils.py`，想直接跑它做自测，加了个 `main()` 却发现 `python utils.py` 与被别的文件 import 时行为一样，自测逻辑污染了调用方；② 工程一多，`import xxx` 时而 `ModuleNotFoundError` 时而突然能用，说不清解释器到底去哪找模块；③ 两个模块互相 import，一启动就 `ImportError: cannot import name ... (most likely due to a circular import)`——Maven 里这叫循环依赖，构建期就被拦住，Python 到运行时才炸。此外还有一个选择题：类型注解到底写多严？它和 Java 的类型系统是一回事吗？本章一次讲清。

## 11.2 一句话解释 + 生活类比 + 类比边界

**一句话解释**：模块（module）就是一个 `.py` 文件，包（package）是"带 `__init__.py` 的目录"；`__name__` 是每个模块自带的身份证——直接运行时身份证上写着 `"__main__"`，被导入时写着模块名，所以 `if __name__ == "__main__":` 是 Python 版的 `public static void main`（但它是**人人遵守的惯例**，不是语言强制入口）。

**生活类比**：包结构像公司的组织架构——包是部门（有挂牌：`__init__.py`），模块是员工工位；`sys.path` 是前台手上的"访客名录"，`import` 就是按名录一层层找人，找不到就 `ModuleNotFoundError`。相对导入（`from .core import X`）是"在本部门内找人"，`from ..core import X` 是"去上级部门找人"。

**Java 对照**：`import demo_shop.core` ↔ `import com.acme.shop.core`；`__init__.py` 的门面导出 ↔ package-info/门面类；`__main__` 块 ↔ `main()` 方法；循环导入 ↔ Maven 循环依赖。

> 💡 类比边界：① Java 的包名与目录结构**编译期强绑定**，classpath 由构建工具管理；Python 的 import 是**运行时**按 `sys.path` 逐目录搜索，目录名即包名，没有任何"注册"仪式——灵活但也因此更依赖你对搜索路径的理解。② Maven 循环依赖在构建期报错；Python 循环导入是运行时按"模块初始化到一半"的状态决定成败——**同样的循环结构，换个 import 写法可能不报错**，这既是逃生门也是深坑。③ Java 类型检查在编译期强制，注解 `@NotNull` 也要靠运行时框架才生效；Python 注解**默认完全不强制**（下文有实证），静态保证靠 mypy/pyright 这类外部检查器，运行时保证靠 Pydantic（ch16）。

## 11.3 正式原理与准确术语

- **模块（module）与模块对象**：每个 `.py` 文件被 import 后变成模块对象，全局变量/函数/类都是它的属性；`sys.modules` 是"已加载模块"的缓存（同一模块只执行一次）。
- **`__name__ == "__main__"`**：直接运行脚本时，解释器把该文件的 `__name__` 设为 `"__main__"`；被导入时设为模块名。惯例用途：直接运行时跑自测/CLI，被导入时只提供定义。
- **import 搜索路径**：按 `sys.path` 顺序搜索——`sys.path[0]`（脚本所在目录，或交互环境的 `''`）→ `PYTHONPATH` 环境变量 → 解释器安装目录的 stdlib → `site-packages`（pip 装的第三方包）。`python -m 包.模块` 把"当前工作目录"加入搜索路径并执行模块。
- **包（package）与 `__init__.py`**：三个作用——声明常规包；`from 包 import *` 时受 `__all__` 约束；作为"门面"把常用名字从子模块提前导入。子包就是包里的包（目录套目录，每层都有 `__init__.py`）。
- **相对导入（relative import）**：`from . import x`（本包）、`from .. import y`（上级包）。**只能在包内模块使用**——把包内模块当脚本直接运行会报 `ImportError: attempted relative import with no known parent package`（见 11.7①）。
- **循环导入（circular import）**：模块 A 顶层 import B、B 又顶层 import A。机制：A 初始化到一半（`sys.modules` 里已有半成品），B 回头要 A 里"还没执行到"的名字，于是 `ImportError: cannot import name 'xxx' from partially initialized module ...`。
- **类型注解（type annotations）**：写在变量/参数/返回值旁的元数据，存进 `__annotations__`，**解释器默认不校验**。静态检查器（mypy/pyright）读它做源码级分析；Pydantic/FastAPI 读它做运行时校验与文档生成。`from __future__ import annotations`（PEP 563）让注解变成字符串（惰性），ex_11_04 的输出里 `'int'` 带引号就是实证。
- **typing 组件速查**（现代写法，Python 3.10+）：

| 需求 | 现代写法 | 旧写法（≤3.8，过时） | Java 近亲 |
|---|---|---|---|
| 整数列表 | `list[int]` | `List[int]` | `List<Integer>` |
| 可空字符串 | `str \| None` | `Optional[str]` | `@Nullable String` |
| 联合类型 | `int \| str` | `Union[int, str]` | 密封接口多态（近似） |
| 字典结构 | `TypedDict` | —— | `record`（远亲） |
| 鸭子类型接口 | `Protocol` | —— | `interface`（结构化 vs 名义化） |
| 字面量约束 | `Literal["A","B"]` | —— | `enum`（近似） |
| 带元数据的类型 | `Annotated[float, "..."]` | —— | 注解属性（近似） |
| 泛型 | `TypeVar("T")` | 同 | `<T>` |
| 函数类型 | `Callable[[int], str]` | 同 | `Function<Integer,String>` |

- **TypedDict（类型化字典）**：给"字典"声明键和值类型。**运行时还是普通 dict**——静态检查器帮你查键名/值类型拼写错误。第八部分你会看到 LangGraph 的 `State` 就是 TypedDict（`MessagesState` 是内置例子）。
- **Protocol（结构化子类型/静态鸭子类型）**：不看继承关系，只看"有没有这些方法"——与 Java `interface` 的**名义化**（必须声明 implements）相对，是 Python 鸭子类型的静态化。ch07 已见过，本节补运行时视角：`@runtime_checkable` 后可以 `isinstance()`（但只检查方法存在，不检查签名）。
- **静态检查思想（mypy/pyright）**：不运行代码，顺着 import 图把注解当类型规则做数据流检查；CI 里跑，等价于"把 javac 的类型检查剥离出来单独当工具"。**注解不是运行时强制的，Pydantic 才是**——这句话是本章最重要的一句。

## 11.4 最小完整示例：__name__ 的双身份

EX-11-01 | examples/ch11_modules_typing/ex_11_01_module_main.py

```python
# 节选
def total_price(unit_price: float, quantity: int) -> float:
    """本模块对外提供的功能。"""
    return unit_price * quantity

print(f"本模块正在被谁执行？__name__ = {__name__!r}")

if __name__ == "__main__":
    print("→ 身份是 __main__：作为脚本直接运行，执行自测逻辑")
    print(f"自测：total_price(3.5, 4) = {total_price(3.5, 4)}")
else:
    print("→ 身份是模块名：被别的代码 import，只定义功能，不执行自测")
```

**运行方式一**——直接运行（真实运行输出）：

```text
$ python3 examples/ch11_modules_typing/ex_11_01_module_main.py
本模块正在被谁执行？__name__ = '__main__'
→ 身份是 __main__：作为脚本直接运行，执行自测逻辑
自测：total_price(3.5, 4) = 14.0
```

**运行方式二**——被导入（在 `examples/ch11_modules_typing/` 目录下执行 `python3 -c "import ex_11_01_module_main"`，真实运行输出）：

```text
本模块正在被谁执行？__name__ = 'ex_11_01_module_main'
→ 身份是模块名：被别的代码 import，只定义功能，不执行自测
```

同一个文件，两种身份：`__main__` 块只有直接运行才执行。这是"写库的人"与"用库的人"共享一个文件的契约——Java 的 `main()` 只有一个入口，Python 的每个模块都可以自带一个"仅当直接运行时生效"的入口。

## 11.5 逐段解释

### 11.5.1 包结构、搜索路径与相对导入

EX-11-02 | examples/ch11_modules_typing/ex_11_02_import_paths.py（配套包 `demo_shop/` 结构如下）

```text
demo_shop/                 ← 包（有 __init__.py：门面 + __all__）
├── core.py                ← CURRENCY 常量 + Order dataclass
├── pricing.py             ← from .core import Order（一层相对导入）
└── textfmt/               ← 子包
    ├── __init__.py
    └── textutil.py        ← from ..core import CURRENCY, Order（两级相对导入）
```

`demo_shop/__init__.py`（门面写法）：

```python
from .core import CURRENCY, Order          # 相对导入：. 指 demo_shop 包自己
from .pricing import calc_total
__all__ = ["CURRENCY", "Order", "calc_total"]
```

真实运行输出（`python3 examples/ch11_modules_typing/ex_11_02_import_paths.py`）：

```text
[1] sys.path 前 3 项（解释器找模块的搜索顺序）:
    sys.path[0] = /workspace/ai_application_course/examples/ch11_modules_typing
    sys.path[1] = /root/.pyenv/versions/3.14.7/lib/python314.zip
    sys.path[2] = /root/.pyenv/versions/3.14.7/lib/python3.14

[2] 导入包并使用包门面导出的名字:
    demo_shop.__file__ = /workspace/ai_application_course/examples/ch11_modules_typing/demo_shop/__init__.py
    demo_shop.__all__  = ['CURRENCY', 'Order', 'calc_total']
    calc_total: 5648.87
    format_receipt（textfmt 里用了 from ..core 相对导入）:
    ===== 收据 =====
    订单 SO-3001（李工）：2 件商品
      - 键盘
      - 显示器
    金额：CNY 4999.00

[3] 包的层次就是一个目录树:
    demo_shop/            ← 包（有 __init__.py）
    ├── core.py           ← 模块
    ├── pricing.py        ← 模块
    └── textfmt/          ← 子包
        ├── __init__.py
        └── textutil.py   ← 模块（from ..core import ...）

[4] 导入不存在的模块会怎样（EAFP 风格，ch08 呼应）:
    ModuleNotFoundError: No module named 'demo_shop.nonexistent'
```

三个要点：① `sys.path[0]` 是**脚本所在目录**——这就是"为什么同目录的包能直接 import"；② 门面让调用方 `from demo_shop import Order` 而不必知道 Order 住在 core.py——重构内部模块时调用方零改动，与 Java 门面模式同理；③ 两级相对导入 `from ..core import` 让子包访问上级包，目录树即命名空间。

### 11.5.2 循环导入：报错现场与解开

EX-11-05 | examples/ch11_modules_typing/ex_11_05_circular_import.py（坏包 `circular_bad/`：a 顶层 `from circular_bad.b import greet_b`，b 顶层 `from circular_bad.a import A_VALUE`，互相等待；好包 `circular_good/`：a **先定义 `A_VALUE` 再导入 b 模块对象**）

真实运行输出（`python3 examples/ch11_modules_typing/ex_11_05_circular_import.py`，坏包部分由子进程真实运行捕获）：

```text
[1] 坏写法现场：python -m circular_bad.a（子进程真实运行，捕获真实报错）
    退出码: 1
    Traceback (most recent call last):
      File "<frozen runpy>", line 203, in _run_module_as_main
      File "<frozen runpy>", line 88, in _run_code
      File ".../circular_bad/a.py", line 3, in <module>
        from circular_bad.b import greet_b  # ← 灾祸之源：此刻 b 也在等 a
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
      File ".../circular_bad/b.py", line 3, in <module>
        from circular_bad.a import A_VALUE  # ← a 还没执行到 A_VALUE = "A"，这里拿不到
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
      File ".../circular_bad/a.py", line 3, in <module>
        from circular_bad.b import greet_b  # ← 灾祸之源：此刻 b 也在等 a
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    ImportError: cannot import name 'greet_b' from partially initialized module 'circular_bad.b' (most likely due to a circular import)

[2] 好写法验证：调整顺序/导入模块对象后，环解开
    a 调用 b → b 使用 A

[3] 三种解法备忘：
    a) 重排模块内语句顺序（把被依赖的定义放在 import 之前）
    b) from xx import yy → import xx（用模块对象，调用时才解析属性）
    c) 把 import 挪进函数体内（延迟导入，最后手段）
```

读懂这个 traceback：执行链 a→b→a 绕了一圈，最后死在"从**初始化到一半**（partially initialized）的模块里取一个**还没定义**的名字"。报错信息 `(most likely due to a circular import)` 是 Python 官方给的提示。三种解法按优先级排列，**根治手段是重构边界**——环出现的根因通常是两个模块职责纠缠（比如 models 和 service 互相引用），把共享定义抽到第三个模块（Java 里同理：把共同依赖下沉到公共包）才是治本，上面三条是"不想大动"时的实用招。

### 11.5.3 typing 现代写法速览

EX-11-03 | examples/ch11_modules_typing/ex_11_03_typing_modern.py

```python
# 节选
class OrderDict(TypedDict):
    order_id: str
    amount: float
    status: Literal["CREATED", "PAID", "SHIPPED"]   # Literal：值只能取列出的字面量

def find_order(order_id: str) -> dict[str, str] | None:   # 可空 = str | None
    db = {"SO-1": {"status": "PAID"}}
    return db.get(order_id)

@runtime_checkable
class Greeter(Protocol):
    def greet(self) -> str: ...                  # 长得像就行，不用继承

T = TypeVar("T")
def first_or_default(items: list[T], default: T) -> T:    # 泛型 ↔ Java <T>
    return items[0] if items else default

def make_adder(step: int) -> Callable[[int], int]:        # 函数类型标注
    return lambda x: x + step

OrderAmount = Annotated[float, "必须 > 0，由 Pydantic 在运行时校验（ch16）"]
```

真实运行输出（`python3 examples/ch11_modules_typing/ex_11_03_typing_modern.py`）：

```text
[TypedDict+Literal] SO-1（PAID）: 99.50 元
[Optional 现代写法] {'status': 'PAID'} | 查不到 → None
[Protocol] Robot 是 Greeter 吗: True
[Protocol] Stone 是 Greeter 吗: False
[TypeVar] 1 | 空列表: 空
[Callable] 123
[Annotated] 金额 88.8（注解里的元数据运行时不校验，见 ex_11_04）
```

**TypedDict ↔ Java record 的异同**：相似处——都是"给一坨字段一个名字"，静态检查器都会查你有没有拼错键/类型；**关键差异**——record 是真类，实例是不可变对象，方法与不变式（invariant）可挂在类上；TypedDict 运行时就是普通 dict，无方法、无校验、键可以动态增删，类型信息只活在静态检查器眼里。需要"record 的形状 + 运行时校验"时，用 Pydantic 的 `BaseModel`（ch16）。

**Protocol ↔ interface 的关键差异**：Java 是名义化类型（nominal typing）——类必须 `implements Greeter` 才算实现；Python Protocol 是结构化（structural）——`Robot` 什么都没继承，只要真有 `greet()` 方法就 `isinstance` 通过。这让"给遗留代码套接口"零侵入，代价是接口约束弱（只看方法存在，不看语义）。

### 11.5.4 注解 ≠ 运行时校验（本章最重要的一节）

EX-11-04 | examples/ch11_modules_typing/ex_11_04_annotations_runtime.py

真实运行输出（`python3 examples/ch11_modules_typing/ex_11_04_annotations_runtime.py`）：

```text
double.__annotations__ = {'x': 'int', 'return': 'int'}
double('ab') = abab  ← 注解说 int，实际 str 也'跑通了'
price_with_tax('100', 0.13) → 运行到运算处才崩: TypeError: can't multiply sequence by non-int of type 'float'
结论：注解 ≠ 运行时校验；mypy 管'源码层面'，Pydantic 管'数据层面'
```

同一文件交给 mypy 静态检查（本书环境实测 mypy 1.19.1，真实输出）：

```text
$ python3 -m mypy examples/ch11_modules_typing/ex_11_04_annotations_runtime.py
examples/ch11_modules_typing/ex_11_04_annotations_runtime.py:23: error: Argument 1 to "double" has incompatible type "str"; expected "int"  [arg-type]
examples/ch11_modules_typing/ex_11_04_annotations_runtime.py:27: error: Argument 1 to "price_with_tax" has incompatible type "str"; expected "float"  [arg-type]
Found 2 errors in 1 file (checked 1 source file)
```

对比结论直接读输出：**运行时**——`double('ab')` 照跑不误（str 自己定义了 `*`），直到语义层面撑不住才崩；**静态检查**——mypy 在代码**还没运行**时就标出两处参数类型错误。另一个细节：`double.__annotations__` 里 `'int'` 是**带引号的字符串**——因为文件头有 `from __future__ import annotations`（PEP 563 惰性注解，也避免循环导入式的类型引用问题）。最终分工记三行：**注解写给人和检查器看；mypy/pyright 在 CI 里管源码；Pydantic 在运行时管真实数据（HTTP 请求体、JSON）**。Java 工程师可以记成：注解 ≈ 编译期检查（javac/mypy）而不是 Bean Validation（Pydantic）。

## 11.6 安装 / 文件位置 / 运行命令

| 项目 | 内容 |
|---|---|
| 文件位置 | `examples/ch11_modules_typing/`（ex_11_01 ~ ex_11_05 + demo_shop/circular_bad/circular_good 三个包） |
| 运行命令 | `python3 examples/ch11_modules_typing/ex_11_02_import_paths.py`；包内模块用 `python -m` 方式运行 |
| 安装 | 运行示例无需第三方包；静态检查可选 `pip install mypy`（本书仅验证用，非锁定依赖） |

## 11.7 常见错误与排查

**① `ImportError: attempted relative import with no known parent package`**
原因：把包内模块当脚本直接跑（`python3 demo_shop/pricing.py`）——直接运行的脚本没有"所属包"，相对导入无从解析。
修复：改用 `python3 -m demo_shop.pricing`（从包的父目录运行）；或包内模块全部使用绝对导入。

**② `ModuleNotFoundError: No module named 'xxx'`**
原因：`sys.path` 里没有 `xxx` 所在目录。常见于"从错误的目录启动脚本"或"包没安装"。
修复：三选一——从正确目录运行；`pip install -e .` 把自己工程装成可编辑包（生产工程推荐，配合 pyproject.toml）；临时演示用 `sys.path.insert`（本书测试里用了，工程代码别用）。

**③ `ImportError: cannot import name 'xxx' from partially initialized module ... (most likely due to a circular import)`**
原因与修复：见 11.5.2，三种解法 + 下沉公共模块治本。

**④ mypy 报 `error: Argument 1 has incompatible type ...`**
原因：调用处实参与注解不符（如上节实测）。修复：改实参类型；如果注解本身写窄了（比如实际可为 None），把注解改成 `X | None` 并在代码里显式处理 None——**改注解永远优先于加 `# type: ignore`**。

## 11.8 企业场景中的使用方式

- **工程组织**：Java 多模块 Maven 工程 ↔ Python 单仓库 + `src/` 布局 + `pyproject.toml`（ch02）；`python -m 包.模块` ↔ `mvn exec:java`。本书 examples 的"每目录独立可运行"就是最小实践。
- **LangGraph 的 State 是 TypedDict**：第八部分 `class State(TypedDict): messages: Annotated[list, add_messages]`——你将直接用 TypedDict 定义图状态、用 Annotated 挂 reducer。本章的语法就是那章的词汇表。
- **FastAPI 的类型驱动**：路径函数的参数注解（`item_id: int`、`body: OrderIn`）同时服务三件事——运行时校验（Pydantic）、OpenAPI 文档生成、编辑器补全。没有类型注解，FastAPI 基本不可用——这就是"注解文化"在 AI 服务开发中的现实回报。
- **CI 静态检查**：Java 工程默认有编译器把关，Python 工程需要你主动把 `mypy/pyright + ruff` 加进 CI（ch18 有完整一条龙）。Java 工程师迁移动作：把"编译通过"的执念转成"mypy --strict 渐进达标"。

## 11.9 练习

1. **基础**：`python3 mypkg/utils.py` 与 `python3 -m mypkg.utils` 对相对导入的影响有何不同？为什么？
2. **基础**：写出三种"可空字符串"注解写法（现代/旧 typing/注释风格），并说明哪种是本书标准。
3. **代码**：为 `demo_shop` 增加 `orders.py`，定义 `OrderRepo` Protocol（含 `save(order: Order) -> None` 与 `get(order_id: str) -> Order | None`），再写一个内存实现类 `InMemoryOrderRepo`——不继承任何东西，仅靠结构匹配。
4. **代码**：写 `TypedDict` 描述 LLM API 响应片段 `{"role": Literal["system","user","assistant"], "content": str}`，并用它注解一个消息列表变量。
5. **调试**：`a.py` 顶层 `from b import STATUS`，`b.py` 顶层 `from a import APP_NAME`。启动报循环导入。给出至少两种不动业务逻辑的解法，并说明哪种最优。

### 参考答案

<details>
<summary>点开查看参考答案</summary>

1. 前者把 `mypkg/` 目录本身放进 `sys.path[0]`，`utils.py` 的"所属包"信息丢失，相对导入报 `attempted relative import with no known parent package`；后者按模块路径 `mypkg.utils` 加载，包上下文完整。包内模块一律用 `-m` 运行。
2. `str | None`（现代，本书标准）；`Optional[str]`（旧，等价，见到要认识）；`# type: str | None` 注释风格（仅当语法不允许写注解时用）。
3. 参考实现：
   ```python
   class OrderRepo(Protocol):
       def save(self, order: Order) -> None: ...
       def get(self, order_id: str) -> Order | None: ...

   class InMemoryOrderRepo:          # 不写 (OrderRepo)，结构匹配即可
       def __init__(self) -> None:
           self._data: dict[str, Order] = {}
       def save(self, order: Order) -> None:
           self._data[order.order_id] = order
       def get(self, order_id: str) -> Order | None:
           return self._data.get(order_id)
   ```
   静态检查器会认定 `InMemoryOrderRepo` 满足 `OrderRepo`——这就是结构化子类型。
4. ```python
   class ChatMessage(TypedDict):
       role: Literal["system", "user", "assistant"]
       content: str
   history: list[ChatMessage] = [{"role": "user", "content": "你好"}]
   ```
5. 解法一（最优）：把共享常量下沉到 `consts.py`，a、b 都只 import 它——环直接消失；解法二：`b.py` 改 `import a`，用 `a.APP_NAME`（调用时才解析属性，初始化顺序容错）；解法三：`from a import APP_NAME` 挪进函数体内延迟导入（最后手段，隐藏依赖可读性差）。
</details>

## 11.10 自测检查表

- 我能解释 `__name__` 的双身份，并知道"被导入时不跑自测"该怎么写。
- 我能说出 `sys.path` 的前三项搜索顺序，以及 `python -m` 对搜索路径的影响。
- 我能设计一个含子包与门面导出的包结构，并正确使用 `.` 与 `..` 相对导入。
- 我能读懂循环导入的 traceback 并给出 ≥2 种解法。
- 我能用现代写法写出 `list[str]`、`X | None`、TypedDict、Protocol、Literal、Callable、TypeVar、Annotated。
- 我能一句话说清"注解不是运行时强制的，Pydantic 才是"，并展示实证。
- 我能说清 TypedDict 与 Java record、Protocol 与 interface 的"哪里像、哪里不像"。

## 11.11 面试追问

1. **[模拟题] `if __name__ == "__main__"` 的原理是什么？** 每个模块有 `__name__` 属性；直接运行时解释器将其设为 `"__main__"`，被导入时设为模块名。用途是让模块兼具"库"与"脚本"双身份。可深挖：`python -m` 用 runpy 机制把模块按 `__main__` 身份执行。
2. **[模拟题] Python 的类型注解会被运行时强制吗？和 Pydantic 什么关系？** 不会——注解只是元数据（存 `__annotations__`），解释器不校验。静态保证由 mypy/pyright 在不运行代码时检查；Pydantic 在运行时对真实数据（请求体/JSON）做校验与转换，两者互补不互替。
3. **[模拟题] TypedDict、dataclass、Pydantic BaseModel 怎么选？** 内部传"字典形状的数据"且追求零运行时开销→TypedDict（LangGraph State 场景）；纯内存中的不可变/值对象→dataclass；数据来自系统边界（HTTP/文件/LLM 输出）需要校验与错误信息→Pydantic（ch16）。
4. **[模拟题] Protocol 和 ABC（abc.ABC）怎么选？** Protocol 结构化、零侵入、适合"给既有类套接口"；ABC 名义化、显式注册/继承、可提供模板方法与运行时钩子。团队协作强约束场景 ABC 更醒目，库的边界抽象 Protocol 更灵活。

### 待核实

- mypy 输出格式随版本变化（本书实测 1.19.1；mypy 非本书锁定依赖，读者使用时以官方文档为准）。
- Python 各小版本对 `from __future__ import annotations` 与惰性注解的演进（PEP 649/749 在 3.14 的最终形态）未在本书展开，深入使用前请查阅官方发布说明。

---

# 第 12 章 标准库实战小项目：接口数据清洗报告

> **本章目标**：掌握 json（ensure_ascii/indent/自定义 JSONEncoder）、pathlib、datetime 时区（naive vs aware）、re（命名组）、argparse 五件套；用它们完成一个真实可运行的 CLI 收束项目——拉取 GitHub 公开 API 做数据清洗并输出 JSON 报告。
> **前置知识**：ch05 字典推导式、ch08 异常链、ch10 装饰器（可选）、ch11 类型注解。
> **学完你能做什么**：独立完成"调 API→清洗→出报告"类脚本；避开 datetime 时区与 JSON 序列化两大高频坑；为 ch15 的 HTTP 客户端工程化做好准备。

## 12.1 真实问题引入

一个典型的 Java 后端日常：上游系统给你一个 REST 接口，你要拉数据、清洗字段、格式化时间、提取版本号、生成日报。Java 里的工具箱是 Jackson + `java.time` + `java.util.regex` + picocli。今天我们用 Python 标准库（外加一个 HTTP 客户端）完成同一件事，项目真实运行：**拉取 `https://api.github.com/repos/langchain-ai/langgraph` 与其最近 tag，做字段提取、时区转换、版本号正则提取，输出 JSON 报告**——并且必须内置"网络不可用时回退到本地样本"的路径（本章写作时的沙箱就真实触发了它：GitHub 匿名 API 对共享出口 IP 限流，403 rate limit exceeded，这正是生产环境的日常，不是教学造景）。

## 12.2 一句话解释 + 生活类比 + 类比边界

**一句话解释**：Python 标准库就是"自带的 JDK"——`json` 管 JSON、`pathlib` 管路径、`datetime`/`zoneinfo` 管时间与时区、`re` 管正则、`argparse` 管命令行；本章把它们组装成一条"获取→清洗→输出"的数据管道。

**Java 对照表**（本章的地图）：

| Python 标准库 | Java 近亲 | 一句话差异 |
|---|---|---|
| `json` | Jackson `ObjectMapper` | 无注解驱动、无流式 API；自定义类型靠 `JSONEncoder.default()` 钩子；强校验交给 Pydantic |
| `pathlib.Path` | `java.nio.file.Path` | 路径即对象，`/` 运算符拼接；`read_text/write_text` 一行搞定小文件 |
| `datetime` + `zoneinfo` | `java.time` | `LocalDateTime` ≈ naive（无时区）、`ZonedDateTime` ≈ aware（带时区）；**naive/aware 不可比较** |
| `re` | `java.util.regex` | 语法同源；命名组 `(?P<name>...)` ↔ `(?<name>...)`；raw string `r"..."` 防转义 |
| `argparse` | picocli / args4j | 标准库自带；自动生成 `--help` 与类型校验，退出码约定 0/1/2 |

> 💡 类比边界：Jackson 靠注解（`@JsonProperty`）和数据模块（`JavaTimeModule`）做复杂映射；`json` 模块刻意保持极简——字典进出，类型不认识的就用 `default=` 或子类 `JSONEncoder` 兜底。`java.time` 一套 API 覆盖本地时间/时区/时间戳，Python 则是 `datetime`（含 naive/aware 两族）+ `zoneinfo`（IANA 时区库）的组合，**选错族（naive/aware 混用）会当场 TypeError**——这是防御，不是缺陷。

## 12.3 正式原理与准确术语

- **`json.dumps/loads`**：序列化/反序列化。常用参数：`ensure_ascii=False`（中文不转义成 `\uXXXX`）、`indent=2`（人读缩进）、`cls=自定义编码器` 或 `default=回调`（处理 datetime 等类型）。**roundtrip 不对称**：`datetime` 出去变字符串，回来还是字符串。
- **JSONEncoder.default 协议**：自定义编码器必须对"不认识的类型"返回可序列化对象，对真的处理不了的抛 `TypeError`——这是 json 模块与编码器之间的协议。
- **naive vs aware datetime**：naive（天真）不带时区信息（`tzinfo=None`），aware（自知）带。`datetime.now(timezone.utc)` 得 aware；`datetime.utcnow()` 返回 naive 且**自 3.12 起废弃**（本章有真实警告输出）。naive 与 aware 混合比较直接 `TypeError`。
- **ISO 8601 与 `fromisoformat`**：`2024-01-30T17:33:42Z` 是 UTC 的 ISO 写法；Python 3.11+ 的 `fromisoformat` 直接认 `Z`，3.10 需先 `replace("Z", "+00:00")`（本书兼容写法两者通吃）。
- **`zoneinfo.ZoneInfo("Asia/Shanghai")`**：IANA 时区；Windows 缺 tzdata 时需 `pip install tzdata`，工程上常用 try/except 回退固定偏移。
- **`re` 命名组**：`(?P<name>pattern)` + `m.group("name")`/`m.groupdict()`，让正则可读可维护；`match`（从头匹配）/`search`（扫描首处）/`findall`（全部）；元组 `(major, minor, patch)` 天然可排序，**字符串排序会把 "0.10.2" 排在 "0.9.1" 前面**。
- **argparse 三层**：`ArgumentParser()` 建解析器 → `add_argument` 声明参数（`type=float` 自动类型校验，`choices` 枚举约束）→ `parse_args()` 解析。非法参数 argparse 直接打印用法并**以退出码 2 退出**（业务错误建议退出码 1，约定俗成）。

## 12.4 最小完整示例：json 与 datetime 的正确姿势

EX-12-01 | examples/ch12_stdlib_project/ex_12_01_json_encoder.py

```python
# 节选
class SafeEncoder(JSONEncoder):
    """自定义编码器：遇到 json 不认识的类型（如 datetime）时被 default() 回调。
    对照 Java：Jackson 的 ObjectMapper.registerModule(new JavaTimeModule()) 干的是同一件事。"""
    def default(self, o: object) -> str:
        if isinstance(o, datetime):
            return o.isoformat()          # 统一转 ISO 8601 字符串（带时区）
        return super().default(o)         # 兜底必须抛 TypeError（协议要求）
```

真实运行输出（`python3 examples/ch12_stdlib_project/ex_12_01_json_encoder.py`）：

```text
[1] 直接 json.dumps(record) 会怎样：
    TypeError: Object of type datetime is not JSON serializable
    → 报错信息已经告诉你原因；解法见下面 [2][3]
[2] ensure_ascii 对比（default=str 临时兜底 datetime）：
    ensure_ascii=True（默认）:
    {"order_id": "SO-4001", "customer": "\u5f20\u4e09", "amount": 199.0, "created_at": "2026-10-19 09:30 ...
    ensure_ascii=False:
    {"order_id": "SO-4001", "customer": "张三", "amount": 199.0, "created_at": "2026-10-19 09:30:00+00:00" ...
[3] indent=2 + 自定编码器 SafeEncoder:
{
  "order_id": "SO-4001",
  "customer": "张三",
  "amount": 199.0,
  "created_at": "2026-10-19T09:30:00+00:00"
}
[4] 读回后 created_at 的类型: str 值 = 2026-10-19T09:30:00+00:00
    → 反序列化不会'还原'datetime；需要强类型/强校验时用 Pydantic（ch16）
```

四个知识点一条龙：最常见报错（`datetime is not JSON serializable`）→ `ensure_ascii` 的中文可读性差异 → 自定编码器的标准解法 → roundtrip 不对称（`str` 进、`str` 出）。

## 12.5 逐段解释

### 12.5.1 pathlib 与 datetime 时区

EX-12-02 | examples/ch12_stdlib_project/ex_12_02_pathlib_timezone.py

真实运行输出（`python3 examples/ch12_stdlib_project/ex_12_02_pathlib_timezone.py`）：

```text
[1] pathlib：路径是对象，不是字符串拼接（告别 \ 和 / 的地狱）
    创建: .../ch12_stdlib_project/_demo_files/logs/app-2026-10-19.log
    name = app-2026-10-19.log | stem = app-2026-10-19 | suffix = .log | parent.name = logs

[2] datetime：naive（天真）vs aware（带时区）
    naive     = 2026-10-19T09:30:00 | tzinfo = None
    aware_utc = 2026-10-19T09:30:00+00:00
    naive < aware → TypeError: can't compare offset-naive and offset-aware datetimes

[3] 时区转换：同一时刻，不同钟面
    2026-10-19T09:30:00+00:00  ==  2026-10-19T17:30:00+08:00（同一时刻！）

[4] 解析 ISO 8601 字符串（GitHub API 返回的时间长这样）
    fromisoformat('...Z') → 2026-10-19T01:23:45+00:00

[5] 历史坑：utcnow() 已废弃（3.12 起警告），它返回的是 naive 对象
    触发警告 DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    datetime.utcnow() → 2026-10-19T01:32:44.794715  tzinfo=None ← 没有时区！
    datetime.now(timezone.utc) → 2026-10-19T01:32:44.794732+00:00 ← aware，放心用
```

时区坑的 Java 记忆锚点：`LocalDateTime.now()` 就是 naive——它表示"墙上的钟"，没有时区语义；需要跨时区/持久化时间戳时一律 `Instant`/`ZonedDateTime`。Python 对应规则：**存时间戳与跨服务传输用 aware UTC；只在本进程展示才允许 naive**。naive/aware 混比被语言直接禁止（TypeError），这是帮你挡住"悄悄差 8 小时"的 bug。

### 12.5.2 正则：命名组解析日志与版本号

EX-12-03 | examples/ch12_stdlib_project/ex_12_03_re_extract.py

```python
# 节选
LOG_PATTERN = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})\s+"   # 时间戳
    r"(?P<level>[A-Z]+)\s+"                                     # 日志级别
    r"\[(?P<service>[\w-]+)\]\s+"                               # 服务名
    r"(?P<message>.*)$"                                         # 正文
)
TAG_PATTERN = re.compile(r"^v(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)$")
```

真实运行输出（`python3 examples/ch12_stdlib_project/ex_12_03_re_extract.py`）：

```text
[1] 命名组解析 Java 风格日志行:
    ts       = 2026-10-19 09:30:01.123
    level    = ERROR
    service  = order-svc
    message  = 订单超时：下游 503
    无法解析的行 → None

[2] findall / finditer / search 的区别:
    findall 全部数字版本: ['1.0.0', '1.2.16', '2.0.0']
    search 只找第一处  : 1.0.0

[3] tag 名 → semver 元组（可排序）:
    v0.0.8     → (0, 0, 8)
    v0.0.7     → (0, 0, 7)
    v1.2.16    → (1, 2, 16)
    nightly    → None
    v0.10.2    → (0, 10, 2)
    v0.9.1     → (0, 9, 1)

[4] 字符串排序 vs semver 排序（'0.10.2' > '0.9.1' 但 '10'<'9' 字符串序会错）:
    semver 排序: ['v0.0.7', 'v0.0.8', 'v0.9.1', 'v0.10.2', 'v1.2.16']
    字符串排序: ['v0.0.7', 'v0.0.8', 'v0.10.2', 'v0.9.1', 'v1.2.16'] ← 错误示范

[5] sub 替换：把日志级别打码（脱敏常见操作）
    2026-10-19 09:30:01.123 *** [order-svc] ***
```

命名组让正则从"天书"变成"带字段名的查询"；semver 元组排序是数据清洗的经典技巧——**把字符串比较问题转成整数元组比较**。`[5]` 的脱敏（把 message 打码）是 ch58 安全章"日志脱敏"的最小雏形。

### 12.5.3 argparse：把脚本变成正规 CLI

EX-12-04 | examples/ch12_stdlib_project/ex_12_04_argparse_basics.py

三种真实运行输出：

```text
$ python3 ex_12_04_argparse_basics.py SO-123 --rate 0.13 --verbose
[verbose] order_id='SO-123' rate=0.13
订单 SO-123 含税金额: 113.0
[exit 0]

$ python3 ex_12_04_argparse_basics.py SO-123 --rate abc
usage: order-fee [-h] [-r RATE] [-v] order_id
order-fee: error: argument -r/--rate: invalid float value: 'abc'
[exit 2]

$ python3 ex_12_04_argparse_basics.py --help
usage: order-fee [-h] [-r RATE] [-v] order_id

计算订单含税费用（教学演示：argparse 基本面）

positional arguments:
  order_id         订单编号，如 SO-123

options:
  -h, --help       show this help message and exit
  -r, --rate RATE  税率（默认 0，如 0.13 表示 13%）
  -v, --verbose    输出详细过程
[exit 0]
```

注意退出码约定：**参数/类型错误 argparse 自动退出 2**；业务错误（如税率负数）由我们主动 `return 2`/`1`；成功 0。CI 与 shell 脚本靠退出码判断成败——与 Java `System.exit(n)` 同理。

## 12.6 收束项目：接口数据清洗报告 CLI

### 12.6.1 设计

```text
examples/ch12_stdlib_project/
├── ex_12_05_report_cli.py     ← 主程序（三层：数据获取 / 清洗统计 / CLI）
└── sample_data.json           ← 打包的真实 GitHub API 响应（离线兜底样本）
```

- **数据获取层**：`fetch_online()` 用 httpx（requirements.txt 已锁定 0.28.1）请求 `GET /repos/{slug}` 与 `GET /repos/{slug}/tags?per_page=5`，带 10 秒超时与 User-Agent；`load_local()` 用 pathlib 读 `sample_data.json`。
- **清洗统计层**：`build_report()` 做三类清洗——字段提取（`dict.get` 带缺省兜底）、时间格式化（ISO `Z` → 北京时间 `strftime`）、正则提版本（tag 名 → semver 元组 → 排序 → 批内最大值）。
- **CLI 层**：`--source {auto,online,local}`（默认 auto：先联网，失败回退本地并打印模式提示）、`--output`（报告落盘）、`--dump-json`（重新抓取并更新本地样本）。

关键代码节选（EX-12-05 | examples/ch12_stdlib_project/ex_12_05_report_cli.py，完整可运行）：

```python
# 节选：回退逻辑（auto 模式）
try:
    payload = fetch_online()
    data_source = "online"
except Exception as exc:                       # 网络/HTTP 一切失败都走这里
    if args.source == "online":
        print(f"[错误] 在线获取失败且指定 --source online，不回退：{exc}", file=sys.stderr)
        return 1                               # 用户明确要在线，失败就失败，不悄悄降级
    print(f"[模式提示] 网络不可用（{type(exc).__name__}: {exc}）", file=sys.stderr)
    print("[模式提示] 已自动回退到打包的本地样本 sample_data.json"
          "（真实抓取于 2026-10-19，数字为抓取时点快照）", file=sys.stderr)
    data_source = "local-fallback"

# 节选：时间格式化与版本提取
def to_shanghai(iso_text: str) -> str:
    dt = datetime.fromisoformat(iso_text.replace("Z", "+00:00"))   # 3.10 兼容写法
    target = ZoneInfo("Asia/Shanghai")     # Windows 缺 tzdata 时回退 timezone(timedelta(hours=8))
    return dt.astimezone(target).strftime("%Y-%m-%d %H:%M:%S") + " (UTC+8)"
```

### 12.6.2 真实运行输出

**① 在线模式**（`python3 examples/ch12_stdlib_project/ex_12_05_report_cli.py --source online`，真实运行输出，2026-10-19 09:50 (UTC+8) 抓取）：

```json
{
  "meta": {
    "data_source": "online",
    "generated_at": "2026-10-19T09:50:37+08:00",
    "upstream_api": "https://api.github.com/repos/langchain-ai/langgraph"
  },
  "repo": {
    "full_name": "langchain-ai/langgraph",
    "description": "Build resilient agents.",
    "language": "Python",
    "stars": 43465,
    "forks": 7412,
    "open_issues": 579,
    "default_branch": "main",
    "license": "MIT",
    "created_at_utc": "2023-08-09T18:33:12Z",
    "created_at_cn": "2023-08-10 02:33:12 (UTC+8)",
    "pushed_at_cn": "2026-10-19 03:18:52 (UTC+8)"
  },
  "versions": {
    "count": 5,
    "versions": [
      { "tag": "v0.0.4", "version": "0.0.4" },
      { "tag": "v0.0.5", "version": "0.0.5" },
      { "tag": "v0.0.6", "version": "0.0.6" },
      { "tag": "v0.0.7", "version": "0.0.7" },
      { "tag": "v0.0.8", "version": "0.0.8" }
    ],
    "max_in_batch": "0.0.8",
    "skipped_non_semver": []
  }
}
```

**② 本地模式**（`python3 examples/ch12_stdlib_project/ex_12_05_report_cli.py --source local`，真实运行输出）：

```json
{
  "meta": {
    "data_source": "local",
    "generated_at": "2026-10-19T09:32:45+08:00",
    "upstream_api": "https://api.github.com/repos/langchain-ai/langgraph"
  },
  "repo": {
    "full_name": "langchain-ai/langgraph",
    "description": "Build resilient agents.",
    "language": "Python",
    "stars": 43463,
    "forks": 7411,
    "open_issues": 652,
    "default_branch": "main",
    "license": "MIT",
    "created_at_utc": "2023-08-09T18:33:12Z",
    "created_at_cn": "2023-08-10 02:33:12 (UTC+8)",
    "pushed_at_cn": "2026-10-19 03:18:52 (UTC+8)"
  },
  "versions": {
    "count": 5,
    "versions": [
      { "tag": "v0.0.4", "version": "0.0.4" },
      { "tag": "v0.0.5", "version": "0.0.5" },
      { "tag": "v0.0.6", "version": "0.0.6" },
      { "tag": "v0.0.7", "version": "0.0.7" },
      { "tag": "v0.0.8", "version": "0.0.8" }
    ],
    "max_in_batch": "0.0.8",
    "skipped_non_semver": []
  }
}
```

> 📌 诚实说明：本地样本是 2026-10-19 真实抓取的快照。对比 ①② 两份真实输出你会发现 `stars` 不同（在线 43465 vs 快照 43463）——**同一仓库、同一天、数据源不同**，这正是报告必须携带 `data_source` 字段的原因。`/tags` 接口按其默认排序返回的这 5 个 tag 恰好是该仓库 2023~2024 年间的早期版本（v0.0.x），因此 `max_in_batch: "0.0.8"` 只是**本批 5 个 tag 里的最大值**，不代表仓库当前最新版本——报告字段名如实叫 `max_in_batch` 而不是 `latest`。

**③ auto 模式 + 网络不可用**（真实运行输出，stderr 的两条模式提示是任务要求的回退路径）：

```text
$ python3 examples/ch12_stdlib_project/ex_12_05_report_cli.py
[模式提示] 网络不可用（HTTPStatusError: Client error '403 rate limit exceeded' for url 'https://api.github.com/repos/langchain-ai/langgraph'）
[模式提示] 已自动回退到打包的本地样本 sample_data.json（真实抓取于 2026-10-19，数字为抓取时点快照）
{
  "meta": {
    "data_source": "local-fallback",
    ...（报告内容同上，data_source 标记为 local-fallback）
```

这不是演出来的故障：GitHub 匿名 API 每小时 60 次、按出口 IP 计数，共享环境的额度经常被用光。**"网络拿不到→降级到本地样本→明确告知数据来源"**是数据类 CLI 的标准生产姿势，报告里的 `data_source` 字段让每个消费方都知道自己看到的是实时数据还是快照。

**④ 非法参数**（真实运行输出）：

```text
$ python3 ex_12_05_report_cli.py --source bogus
usage: report-cli [-h] [--source {auto,online,local}] [--output OUTPUT] [--dump-json PATH]
report-cli: error: argument --source: invalid choice: 'bogus' (choose from 'auto', 'online', 'local')
[exit 2]
```

### 12.6.3 与全书验收的呼应

syllabus 对第二部分的验收是"写出含 dataclass + 装饰器 + 生成器 + 异常链的 CLI 工具并通过给定 pytest"。本章项目正是这个验收的雏形：argparse CLI（ch12）、异常兜底与退出码（ch08）、`ZoneInfo` 兜底与字段防御（ch04/ch05）、类型注解全量（ch11）——你完全可以自己动手，把 EX-10-03 的 `@retry` 加到 `fetch_online()` 上（ch15 之前先手工体验一次重试的价值）。

## 12.7 安装 / 文件位置 / 运行命令

| 项目 | 内容 |
|---|---|
| 文件位置 | `examples/ch12_stdlib_project/`（ex_12_01 ~ ex_12_05 + sample_data.json） |
| 运行命令 | `python3 examples/ch12_stdlib_project/ex_12_05_report_cli.py`（默认 auto 模式） |
| 安装 | 离线路径零依赖；在线模式需 `pip install -r requirements.txt`（httpx 已锁定 0.28.1） |

## 12.8 常见错误与排查

**① `TypeError: Object of type datetime is not JSON serializable`**
原因：json 模块只认识基础类型，datetime 不在名单。修复：`cls=SafeEncoder` 或 `default=lambda o: o.isoformat()`；要还原成 datetime 需要 Pydantic（ch16）或手动 `fromisoformat`。

**② `TypeError: can't compare offset-naive and offset-aware datetimes`**
原因：naive 与 aware 混用（典型：`utcnow()` 的结果与 API 返回的 aware 时间比较）。修复：统一 aware——`datetime.now(timezone.utc)` 替代 `utcnow()`；解析 ISO 字符串后 `astimezone()` 到目标时区再比较。

**③ `ValueError: Invalid isoformat string: '...Z'`（Python ≤3.10）**
原因：3.10 及更早的 `fromisoformat` 不认 `Z` 后缀。修复：`s.replace("Z", "+00:00")`（本书兼容写法）；3.11+ 已无此问题。

**④ `DeprecationWarning: invalid escape sequence '\d'`**
原因：正则忘写 raw string，`"\d"` 被 Python 当无效转义。修复：正则一律 `r"..."`。命名组从 `(?P<name>...)` 取值时也别拼字符串，用 `m.group("name")`。

## 12.9 练习

1. **基础**：`json.dumps({"t": datetime.now()})` 报什么错？给出两种修法并说出适用场景。
2. **基础**：`2026-10-19T01:00:00Z` 与 `2026-10-19T09:00:00+08:00` 是同一时刻吗？写成 Python 代码验证。
3. **代码**：给报告增加 `issues_per_kilo_star`（每千星 open issues 数）字段，保留 2 位小数，并处理 stars=0 的除零边界。
4. **代码**：用 `re` 从 `"订单号 SO-2026-1019-0001，金额 ¥1,299.00"` 中提取订单号与金额（含千分位），命名组命名。
5. **调试**：小王的 CLI 在 CI 里偶发失败，日志显示报告里 `created_at_cn` 有时是 `02:33:12 (UTC+8)`、有时差 8 小时。CI 机器时区被改过。请指出代码里最可能的问题并修复（提示：哪一步用了"本地时区"而不是显式时区？）。

### 参考答案

<details>
<summary>点开查看参考答案</summary>

1. `TypeError: Object of type datetime is not JSON serializable`。修法一 `default=str`/`default=lambda o: o.isoformat()`（脚本级、一行）；修法二子类 `JSONEncoder`（工程级、可复用多类型）。选型：一次性脚本用 default，被多处复用用 cls。
2. 是同一时刻：`datetime.fromisoformat("2026-10-19T01:00:00+00:00") == datetime.fromisoformat("2026-10-19T09:00:00+08:00")` → `True`（aware 比较按绝对时刻）。
3. ```python
   stars = repo.get("stargazers_count") or 0
   issues = repo.get("open_issues_count") or 0
   report["repo"]["issues_per_kilo_star"] = round(issues * 1000 / stars, 2) if stars else None
   ```
   除零边界返回 None（或显式标记 "-"），绝不让 CLI 崩在一条统计字段上。
4. ```python
   m = re.search(r"订单号\s*(?P<order_id>SO-\d{4}-\d{4}-\d{4}).*?¥(?P<amount>[\d,]+\.\d{2})", text)
   order_id = m["order_id"]              # SO-2026-1019-0001
   amount = float(m["amount"].replace(",", ""))   # 1299.0
   ```
5. 某处用了 `dt.astimezone()`（不带参数时按**本地时区**转换）或 `datetime.now()`（naive 本地时间）参与计算。修复：所有转换显式指定时区——`astimezone(ZoneInfo("Asia/Shanghai"))`、当前时刻用 `datetime.now(timezone.utc)`；CI 里"时区随机器漂移"的 bug 从此根除。
</details>

## 12.10 自测检查表

- 我能不查文档写出 ensure_ascii=False、indent=2、自定义 JSONEncoder 的 json.dumps。
- 我能解释 JSON roundtrip 对 datetime 的不对称性。
- 我能说清 naive 与 aware 的区别、`utcnow()` 为什么废弃、混用会抛什么异常。
- 我能用命名组写出日志行/版本号解析并做 semver 排序。
- 我能用 argparse 写出带类型校验、choices、--help 的 CLI，并说清退出码 0/1/2。
- 我能说清"auto/online/local"三档数据来源语义，以及 data_source 字段为什么必须进报告。
- 我能独立完成"调 API→清洗→出 JSON 报告"的完整脚本。

## 12.11 面试追问

1. **[模拟题] 自定义 JSON 序列化有哪几种方式？工程上怎么选？** `default=` 回调（脚本级）、子类 `JSONEncoder`（可复用）、数据出门前自己转 dict（边界显式化，大型工程首选——序列化规则不藏在编码器里）。
2. **[模拟题] naive 和 aware 的本质区别？生产上你的时间规范是什么？** naive 无时区语义（钟面时间），aware 带偏移可换算绝对时刻。规范：存储与传输一律 aware UTC（ISO 8601 + Z）；展示层才转本地时区；禁止 `utcnow()`。
3. **[模拟题] 为什么 semver 要转元组排序而不是字符串排序？** 字符串逐字符比较会让 "0.10.2" < "0.9.1"（'1'<'9'）；元组按数值逐级比较，`(0,10,2) > (0,9,1)` 正确。
4. **[模拟题] CLI 的退出码为什么重要？argparse 的约定是什么？** CI/shell 靠退出码判断成败并决定是否继续流水线；argparse 用法错误退出 2，约定业务失败用 1、成功 0；退出码也是脚本可组合性的基础。

### 待核实

- GitHub REST API 的限流额度与响应字段以官方文档（docs.github.com/rest）当前版本为准；本书实测：匿名 60 次/小时/IP，字段如 `stargazers_count`/`pushed_at` 结构与上文一致。
- `sample_data.json` 是 2026-10-19 的快照；`/tags` 默认排序规则 GitHub 未在文档中承诺稳定性，教学演示不依赖其排序。
- httpx 的超时/重试工程化细节（connect/read/pool 三件套）属 ch15 内容，本章只用最基本的 `timeout=10.0`。

