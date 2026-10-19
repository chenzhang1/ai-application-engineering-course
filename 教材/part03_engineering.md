# 第三部分 Python 工程化与服务开发：ch13~ch20

> 前置知识：ch04~ch12（对象模型、数据结构、函数、异常、生成器、装饰器、类型注解、标准库）。
> 本册八章是 Java 工程师转入 Python AI 应用开发的主干道：**ch13 asyncio**（并发的地基）、**ch14 线程/进程/GIL**（什么时候不用 asyncio）、**ch15 HTTP 客户端工程化**（调模型 API 的正确姿势）、**ch16 Pydantic v2**（数据校验与配置）、**ch17 FastAPI**（服务框架 + 收束演练）、**ch18 测试与质量**、**ch19 数据与缓存**、**ch20 部署基础**。Syllabus 的综合演练"订单查询+风控限流 FastAPI 服务"落在 ch17 收束演练（EX-17-06），部署在 ch20 收尾。
> 代码环境：Python 3.12+（全部示例在沙箱 3.14.7 实际运行验证，核实日期 2026-10-19）；依赖版本见 requirements.txt（fastapi 0.146.0 / uvicorn 0.54.0 / httpx 0.28.1 / pydantic 2.14.1 / pytest 9.1.1 / fakeredis 2.40.0 等）。本部分 30 个示例全部真实执行（记录见 验证报告/运行日志/part03.md），测试/test_ch13~19.py 共 40 个测试全绿（`40 passed in 12.90s`）；uvicorn+curl、SSE、真实 Redis 7.0.15 的启动证据均在对应章节标注"本沙箱实测"。

---

# 第 13 章 asyncio：事件循环、协程与并发

> **本章目标**：理解事件循环（event loop）与协程（coroutine）的协作式调度模型；掌握 create_task/gather/wait_for/Semaphore 四件套；能用对照实验说清"sync 阻塞调用混进 async 代码"为什么是事故。
> **前置知识**：ch09 生成器（yield 的暂停/恢复直觉）、ch08 异常体系（try/finally 清理）。
> **学完你能做什么**：写出批量并发调用模型 API 的脚本；看懂 FastAPI/LangChain 中所有 async 函数的执行时序；在代码评审中指出"在 async def 里调 requests"这类问题。

## 13.1 真实问题引入

你在 Java 里写过这样的批量任务：200 个用户逐个调下游接口，每次 100ms，`for` 循环要 20 秒；`ExecutorService` + 线程池把等待重叠，压到 2 秒。线程是 Java 世界唯一的并发原语——JVM 线程直接映射 OS 线程，池大小、队列、拒绝策略你天天在调。

现在切到 Python AI 场景：给 500 段文本逐段调大模型 API 做摘要，每次等 2~10 秒网络往返，服务端几乎不给本地 CPU 派活。按 Java 直觉开 500 个线程，仅线程栈就可能吃掉数百 MB，而且 Python 的 GIL（第 14 章细讲）让这些线程在等待之外帮不上忙。AI 应用的负载是**极端 IO 密集**：等 API、等数据库、等向量检索。这个场景下 Python 给了比线程更轻的答案——协程：单线程内成千上万个"等待中"的任务共享一个事件循环，每个任务只在 `await` 处挂起，内存开销 KB 级。

但协程有一条 Java 线程没有的铁律：**循环里只要有一处同步阻塞，所有任务一起停摆**。本章的对照实验（EX-13-02）把这条事故现场拍给你看。

## 13.2 一句话解释 + 生活类比 + 类比边界

**一句话解释**：asyncio 是单线程内的协作式调度器——函数用 `async def` 声明为协程，在 `await` 处主动交还控制权，事件循环趁机去跑别的协程，等 IO 就绪再回来续跑。

**生活类比**：事件循环像一个**单人前台接待员**。协程是来办事的客人：`await` 相当于客人说"我在等传真，好了叫我"，然后离开窗口坐到等候区；接待员立刻叫下一位。只要每个客人"等传真"时都让出窗口，一个接待员也能同时服务几百位客人。而同步阻塞调用（如 `time.sleep`、`requests.get`）是客人**赖在窗口不走**——他睡着，后面所有客人干瞪眼。

**Java 对照**：最容易混的是它与 Java 21 虚拟线程（Virtual Thread）的关系——两者都解决"IO 等待浪费线程"，但机制完全不同。虚拟线程由 JVM **抢占式**调度：代码照常写阻塞调用，JVM 在底层自动把阻塞的虚拟线程卸载，载体线程去跑别人。asyncio 是**协作式**：切换只发生在你显式写 `await` 的地方，忘写就是事故。`CompletableFuture.supplyAsync()` 写法上像 `create_task` + `await` 的合体，但它的任务是普通函数跑在线程池里，不是协程。

> 💡 类比边界：**asyncio 协程 ≠ 虚拟线程，也 ≠ 线程池**。三处最不等价：①调度方式——协程靠显式 `await` 让位（协作式，"哪里会切"可预测），虚拟线程由 JVM 强制切换（抢占式）；②并行能力——单事件循环**只有一个线程**，CPU 计算不会因 asyncio 变快，虚拟线程背后的载体线程池是真并行；③生态隔离——Java 的 IO 生态天然适配虚拟线程（阻塞即让出），Python 生态分裂成同步库（requests）与异步库（httpx.AsyncClient）两个世界，混用同步库就回到"赖在窗口"的事故。另外 `gather` 也不等价于 `CompletableFuture.allOf`：gather 直接按提交顺序返回结果列表。

## 13.3 正式原理与准确术语

- **事件循环（event loop）**：单线程调度器，维护"就绪任务队列"与"定时器堆"，不断取出可运行的协程执行到下一个 await 点。`asyncio.run(main())` 创建循环、跑完、关闭——一个程序通常只调它一次。
- **协程（coroutine）**：`async def` 定义的函数的返回值。**调用协程函数不执行函数体**，只返回协程对象（与 ch09 生成器函数"调用不执行"同构）；必须被 `await` 或包装成 Task 才会运行。
- **await**：挂在可等待对象（协程、Task、Future）上——"我暂时做不了，把控制权还给事件循环；条件就绪后从这一行继续"。
- **任务（Task）**：`asyncio.create_task` 把协程包装后**立即排入循环**调度，返回句柄——可查 `done()`、可 `cancel()`、可 `await` 收结果（对照 `executor.submit()` 返回 `Future`）。
- **gather**：并发等待一批协程/Task，**按提交顺序**返回结果列表；默认首个异常立刻抛出，`return_exceptions=True` 时异常作为值进列表。
- **wait_for(coro, timeout=)**：限时等待；超时给内部协程发取消信号并向调用方抛 `TimeoutError`。
- **取消（cancellation）**：`task.cancel()` 在协程当前 await 点抛出 `asyncio.CancelledError`——它不是事故而是协作机制：被取消方应清理后**重新抛出**。
- **信号量（`asyncio.Semaphore`）**：限流原语，`async with sem` 拿不到许可的协程挂起排队，不占 CPU。
- **异步上下文管理器**：`__aenter__`/`__aexit__` 或 `@asynccontextmanager`，用于异步资源的进入/退出（连接池、span）。
- **同步阻塞对循环的伤害**：事件循环内执行不 await 的阻塞调用（`time.sleep`、同步 HTTP、CPU 大循环）会让**所有**协程停摆——本章最重要的工程红线。

## 13.4 最小完整示例：第一个协程的执行时序

EX-13-01 | 示例代码/ch13_asyncio/ex_13_01_hello_coroutine.py

```python
# 完整可运行
import asyncio
import time


async def fetch_order(order_id: str) -> str:
    """模拟一次异步 IO：await 处挂起，事件循环转去跑别人，到期回来续跑。"""
    print(f"[{time.perf_counter():.3f}] 开始查询订单 {order_id}")
    await asyncio.sleep(0.3)  # 挂起点：不是睡眠，而是"交还控制权，0.3s 后再叫我"
    print(f"[{time.perf_counter():.3f}] 查询订单 {order_id} 完成")
    return f"订单{order_id}"


async def main() -> None:
    started = time.perf_counter()
    r1 = await fetch_order("A001")   # await 会等协程跑完才继续：顺序执行
    r2 = await fetch_order("A002")
    print(f"结果：{r1} / {r2}，总耗时 {time.perf_counter() - started:.2f}s（0.3+0.3=0.6s）")


if __name__ == "__main__":
    asyncio.run(main())  # 事件循环入口：程序退出前它负责调度所有协程
```

真实运行输出（本沙箱实测；方括号内是 perf_counter 相对秒，每次运行不同）：

```text
[4589.857] 开始查询订单 A001
[4590.158] 查询订单 A001 完成
[4590.158] 开始查询订单 A002
[4590.458] 查询订单 A002 完成
结果：订单A001 / 订单A002，总耗时 0.60s（0.3+0.3=0.6s）
```

三个观察点：①两个查询是**顺序**的——`await` 一个协程就是"跑完它才走下一行"；②A002 在 A001 完成的**同一毫秒**开始——A001 结束时控制权回到 main，main 立刻创建 A002 协程，没有调度空隙；③总耗时 0.60s 是两个 0.3s 相加——想重叠它们，得让它们**同时**被调度，这正是下一节 create_task/gather 的用武之地。

Java 对照：`async def fetch_order(...)` 大致像返回 `CompletableFuture<String>` 的方法签名（"结果还没好"被类型化），但 `await` 比链式 `.thenApply()` 直观得多——代码形状就是同步代码的形状，只是挂起点被显式标出。

## 13.5 逐段解释：并发、超时、异常、限流、阻塞伤害

### 13.5.1 对照实验：time.sleep 是事故，asyncio.sleep 是让位

EX-13-02 | 示例代码/ch13_asyncio/ex_13_02_sleep_compare.py（节选，完整版见该文件）

```python
# [B] 并发版任务：asyncio.sleep 只"登记"一个 0.2s 后的回调，随后立刻让出控制权
async def async_task(name: str, delay: float) -> str:
    await asyncio.sleep(delay)
    return f"{name}完成"

async def demo_blocking_harm() -> None:
    async def should_finish_fast() -> str:
        await asyncio.sleep(0.1)  # 本任务只需求 0.1s
        return "我本应在 0.1s 后完成"

    started = time.perf_counter()
    task = asyncio.create_task(should_finish_fast())  # 已被调度，等 0.1s 就该完成
    time.sleep(0.5)  # 同步阻塞：事件循环整个被卡住 0.5s，谁也无法被调度
    result = await task
    print(f"[C] 事件循环内调用 time.sleep(0.5)：任务实际"
          f"{time.perf_counter() - started:.2f}s 后才返回（需求 0.1s）")
```

真实运行输出：

```text
[A] time.sleep 顺序睡 5 次：总耗时 1.00s（0.2×5=1.0s）
[B] asyncio.sleep 并发 5 个任务：总耗时 0.20s（近似单个任务的时长），结果 5 个
[C] 事件循环内调用 time.sleep(0.5)：任务实际 0.60s 后才返回（需求 0.1s）→ 我本应在 0.1s 后完成
```

[C] 是本章的"事故现场"：任务只需要 0.1s，实际 0.6s 才完成。时间线——create_task 排队 → `time.sleep(0.5)` 把**整个线程**睡死，事件循环无法执行任何回调 → 0.5s 后循环恢复，任务才开始跑它的 0.1s → 0.6s 处返回。线上表现就是"P99 突刺、健康检查超时、全部请求一起慢"。真实工程里的肇事者通常是：`requests`（换 httpx.AsyncClient）、`time.sleep`（换 asyncio.sleep）、重 CPU 计算（丢进 `asyncio.to_thread` 或进程池）。

> ⚠️ 常见坑：`asyncio.sleep(0)` 是"让出一轮循环"的惯用法，用于把单次大计算切成多片，让其他协程有机会插进来——不是"睡零秒等于没睡"。

### 13.5.2 create_task + gather：并发收集，按提交顺序返回

EX-13-03 | 示例代码/ch13_asyncio/ex_13_03_create_task_gather.py（完整可运行）

```python
async def main() -> None:
    started = time.perf_counter()
    # 方式一：create_task 立刻把协程包装成 Task 排入事件循环，不等 await 就开始跑
    t_fast = asyncio.create_task(fetch("fast-api", 0.1))
    t_slow = asyncio.create_task(fetch("slow-api", 0.4))
    print(f"create_task 之后、await 之前，任务已在调度中：fast.done={t_fast.done()}")

    # 方式二：gather 接收协程/Task 列表，全部完成后按"提交顺序"返回结果列表
    results = await asyncio.gather(t_slow, t_fast)  # 先提交的 slow 排在前面
    print(f"gather 结果（按提交顺序）：{results}")
    print(f"总耗时 {time.perf_counter() - started:.2f}s（取最慢任务的 0.4s，而不是 0.1+0.4=0.5s）")
```

真实运行输出：

```text
create_task 之后、await 之前，任务已在调度中：fast.done=False
gather 结果（按提交顺序）：['slow-api@0.4', 'fast-api@0.1']
总耗时 0.40s（取最慢任务的 0.4s，而不是 0.1+0.4=0.5s）
fast.done=True，slow.done=True
```

三个关键语义：①create_task 后任务**立即**被调度（`fast.done=False` 说明已排入未完成）；②gather 结果**按提交顺序**对齐，与完成先后无关——`t_slow` 先提交所以排第一，哪怕它最后完成；③总耗时取最慢者 0.4s，等待完全重叠。批量调模型 API 的"扇出"模式就是这个形状：`gather(*(summarize(doc) for doc in docs))`。

### 13.5.3 wait_for 超时与取消：CancelledError 是协作信号

EX-13-04 | 示例代码/ch13_asyncio/ex_13_04_timeout_cancel.py（节选，完整版见该文件）

```python
async def slow_query(seconds: float) -> str:
    try:
        await asyncio.sleep(seconds)
        return "查询结果"
    except asyncio.CancelledError:
        # 取消不是异常"事故"，而是协程间协作的常规机制：收到后应尽快清理并重新抛出
        print("  收到取消信号：回滚事务/关闭游标，然后重新抛出 CancelledError")
        raise
    finally:
        print("  finally：无论正常完成还是被取消都会执行（清理资源的好位置）")
```

真实运行输出（本沙箱实测）：

```text
  开始一个需要 1.0s 的查询…
  收到取消信号：回滚事务/关闭游标，然后重新抛出 CancelledError
  finally：无论正常完成还是被取消都会执行（清理资源的好位置）
[场景一] wait_for 超时：调用方捕获 TimeoutError（Java 对照：Future.get(timeout) 抛 TimeoutException）
  开始一个需要 0.1s 的查询…
  finally：无论正常完成还是被取消都会执行（清理资源的好位置）
[场景二] 未超时：正常拿到 查询结果
  开始一个需要 1.0s 的查询…
  收到取消信号：回滚事务/关闭游标，然后重新抛出 CancelledError
  finally：无论正常完成还是被取消都会执行（清理资源的好位置）
[场景三] 手动 task.cancel()：await task 处收到 CancelledError
```

三个场景对应三件事：wait_for 超时（内部协程收到取消、调用方拿 TimeoutError）、正常完成（finally 一样执行）、手动 cancel（异常在 `await task` 处浮出）。与 Java 的本质差异：`Future.cancel(true)` 只是"请求"，线程在**下次检查中断标志**时才感知；asyncio 的取消通过在 await 点**注入异常**实现——只要协程还在 await，取消必然送达。

> 📌 生产提示：给模型 API 调用统一包 `wait_for(..., timeout=30)` 是 AI 服务的基本卫生：模型偶尔的挂起不能拖死你的事件循环与连接池。ch15 会把超时下沉到 HTTP 客户端层。

### 13.5.4 gather 的异常传播：默认策略 vs return_exceptions

EX-13-05 | 示例代码/ch13_asyncio/ex_13_05_exception_propagation.py（节选，完整版见该文件）

```python
    # 场景一：默认 return_exceptions=False——第一个异常立刻抛给调用方，
    # 但注意：其他兄弟任务不会被自动取消，它们会继续跑完！
    async def gather_pair() -> list[object]:
        # gather 返回的是 Future 而非协程，要用 Task 包一层需先再包一个 async 函数
        return await asyncio.gather(ok_task("先成功的", 0.05), bad_task(0.05))

    # 场景二：return_exceptions=True——异常作为"值"出现在结果列表的对应位置，
    # 所有任务都跑完才返回；适合"部分失败可接受"的批量调用（如批量摘要）。
    mixed = await asyncio.gather(
        ok_task("A", 0.05), bad_task(0.05), ok_task("B", 0.05),
        return_exceptions=True,
    )
```

真实运行输出：

```text
[场景一] 默认策略：await gather 处抛出 ValueError: 业务处理失败（0.05s 后）
[场景一] 兄弟任务没有被自动取消，仍可继续等待：幸存者成功
[场景二] return_exceptions=True：['A成功', ValueError('业务处理失败（0.05s 后）'), 'B成功']
  位置 0 是正常值：A成功
  位置 1 是异常：ValueError: 业务处理失败（0.05s 后）
  位置 2 是正常值：B成功
```

两条必须记住的语义：①默认策略下异常立刻抛出，但**兄弟任务不会被自动取消**，会继续在后台跑完——若之后无人 await 它们，其异常就成了"从未被观察"的悬空任务（3.12+ 的 `TaskGroup` 异常时会取消兄弟任务并聚合成 ExceptionGroup，语义更严格，本书示例保持 gather 以贴近存量代码）；②`return_exceptions=True` 把异常降格为"值"，适合"500 段摘要失败 3 段可接受、逐个补跑"的批量场景。

### 13.5.5 Semaphore 并发限制：保护对端

EX-13-06 | 示例代码/ch13_asyncio/ex_13_06_semaphore.py（节选，完整版见该文件）

```python
MAX_CONCURRENCY = 3

async def call_remote_api(task_id: int, sem: asyncio.Semaphore) -> int:
    async with sem:  # 进入信号量：拿不到许可的协程在此挂起，不会占用事件循环
        await asyncio.sleep(0.2)  # 模拟一次 200ms 的远程调用
    return task_id
```

真实运行输出：

```text
10 个任务全部完成：[0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
实际观测到的最大并发 = 3（信号量上限 3，未被突破）
总耗时 0.80s（理论下限 = ceil(10/3)×0.2 = 0.8s）
```

协程足够轻，轻到随手 `gather` 一万条——但对端（模型 API 的 RPM 配额、数据库连接数）扛不住。`Semaphore(3)` 把"批量扇出"变成"最多 3 路在飞"，超出的在 `async with sem` 处安静排队。总耗时 0.80s 正好是 ceil(10/3)×0.2——排队是严格的流水线。对照 Java：相当于用 `Semaphore.acquire()` 包住每次调用，但协程挂起不占线程，1 万个排队任务也不产生 1 万个线程。

### 13.5.6 异步上下文管理器与真实网络实验

EX-13-07 | 示例代码/ch13_asyncio/ex_13_07_async_context.py（节选，完整版见该文件）

```python
@asynccontextmanager
async def request_span(name: str):
    """装饰器写法：yield 之前=进入逻辑，之后=退出逻辑，8 行顶一个类。"""
    try:
        yield name
    finally:
        print(f"[装饰器写法] span {name} 结束（即使内部抛异常也会走到这里）")
```

真实运行输出：

```text
[类写法] 已连接 postgres://demo
[类写法] 使用连接：closed=False
[类写法] 连接已归还（异常信息：无）
[装饰器写法] span 批量摘要 开始
[装饰器写法] span 批量摘要 结束（即使内部抛异常也会走到这里）
[装饰器写法] 外层捕获到异常：模拟业务异常——但 span 的清理已经先执行了
```

ch08 的 `__enter__`/`__exit__` 在异步世界长成 `__aenter__`/`__aexit__`（`async with`），两段式与 yield 生成器写法完全平行；异步建连是真实的 await（如 asyncpg），所以上下文协议必须异步。ch17 的 FastAPI lifespan（启动/关闭钩子）就是这套协议。

EX-13-08 把前面所有知识合起来打一场真实网络：本地起一个"每个请求睡 100ms"的 HTTP 服务，20 个请求顺序 vs 并发。

EX-13-08 | 示例代码/ch13_asyncio/ex_13_08_concurrent_fetch.py（节选，完整版见该文件）

```python
class SlowServer(ThreadingHTTPServer):
    # 默认 request_queue_size（backlog）只有 5：20 个并发连接会溢出并触发 1s 的 SYN 重传，
    # 这本身就是一条真实的排障经验——并发压测时服务端吞吐异常，先查 backlog。
    daemon_threads = True
    request_queue_size = 128

async def fetch_concurrent(client: httpx.AsyncClient, n: int) -> float:
    started = time.perf_counter()
    rs = await asyncio.gather(*(client.get("/work") for _ in range(n)))
    assert all(r.status_code == 200 for r in rs)
    return time.perf_counter() - started
```

真实运行输出（本沙箱实测，单次运行结果）：

```text
20 个请求、单个 100ms：顺序 await 总耗时 2.08s
20 个请求、单个 100ms：gather 并发 总耗时 0.12s（理论下限≈0.1s）
加速比 ≈ 17.2 倍——并发瓶颈从'总睡眠时间'变成'单次最慢请求'
```

顺序 2.08s ≈ 20×100ms；并发 0.12s ≈ 单次最慢的 100ms——协程把 20 份等待重叠成 1 份。这条示例在开发期曾暴露过一个真实故障（加速比只有 1.8×），排查过程写在 13.7——它是"性能问题不总在你的代码里"的绝佳案例。

### 13.5.7 同步世界的桥：asyncio.to_thread 与 run_in_executor

现实工程里你不可能只用异步库：某个向量数据库只有同步 SDK、某个遗留模块全是阻塞函数。硬混进 async def 就是 EX-13-02[C] 的事故；正确的桥是**把阻塞调用扔进线程池**：

```python
# 语法示意（非落盘示例）：在协程中安全调用同步阻塞函数
result = await asyncio.to_thread(sync_sdk_search, query)      # 3.9+ 首选写法
result = await loop.run_in_executor(None, sync_fn, *args)     # 等价的底层写法
```

`to_thread` 把同步函数派到默认线程池执行，事件循环继续调度其他协程，函数完成后结果回到协程——"阻塞被隔离在线程里，循环不被传染"。三个使用要点：①它适合**阻塞 IO 与会释放 GIL 的同步调用**；纯 CPU 大计算要走 ch14 的进程池（`run_in_executor(ProcessPoolExecutor(), fn, ...)`）；②默认线程池有并发上限（约 `min(32, cpu+4)`），批量调用同样要用 Semaphore 控制并发，否则只是把"打挂事件循环"换成"打挂线程池"；③传进线程的函数若读写共享状态，需要线程锁（ch14.5.3 展开）。

Java 对照：`CompletableFuture.supplyAsync(fn, ioExecutor)` 的直觉完全一致——阻塞任务丢给独立线程池，调用方（这里是事件循环）不被阻塞。差别在于 Python"异步主干 + 同步孤岛"的生态现状让这座桥比 Java 更常用。

## 13.6 安装 / 文件位置 / 运行命令

- 依赖：本章只用标准库 asyncio + requirements.txt 中的 httpx（`pip install -r requirements.txt` 已含）。
- 文件位置：`示例代码/ch13_asyncio/`（8 个示例，文件名首行注释含 EX 编号与运行命令）；测试 `测试/test_ch13.py`。
- 运行命令（在仓库根目录）：

```bash
python3 示例代码/ch13_asyncio/ex_13_01_hello_coroutine.py   # 逐个替换 01~08
python3 -m pytest 测试/test_ch13.py -v                     # 6 个测试
```

## 13.7 常见错误与排查（真实踩坑记录）

**错误一：`TypeError: a coroutine was expected, got <_GatheringFuture pending>`**

```text
TypeError: a coroutine was expected, got <_GatheringFuture pending>
```

原因：`asyncio.create_task(asyncio.gather(...))`——`gather()` 返回的是 Future，不是协程，而 create_task 只接受协程。EX-13-05 开发时真实触发。修复：外包一层 async 函数再 create_task（`async def gather_pair(): return await asyncio.gather(...)` 然后 `create_task(gather_pair())`），或直接 `await` gather。

**错误二：并发实验加速比只有 1.8×（应 ~17×）**

EX-13-08 首跑结果异常：并发 20 个 100ms 请求耗时远超理论值，但代码并发语义正确。插桩定位到**服务端** `socketserver.request_queue_size` 默认 backlog=5——20 个瞬时连接溢出监听队列，触发约 1s 的 SYN 重传，把并发收益吃掉。修复：自定义服务器类设 `request_queue_size = 128`，加速比恢复到 16~17×。教训：压测/并发实验里"对端配置"（backlog、连接数上限、防火墙）是隐形嫌疑人；同一表现（慢）可能来自完全不同的层。

**错误三：`RuntimeWarning: coroutine 'fetch' was never awaited`，且函数体一行没执行**

```text
<string>:7: RuntimeWarning: coroutine 'fetch' was never awaited
```

原因：调用了协程函数但忘了 await——`fetch("A001")` 只创建了协程对象，没人调度它；对象被垃圾回收时 Python 补一条 RuntimeWarning（本沙箱实测输出如上）。修复：`await fetch("A001")` 或 `asyncio.create_task(fetch("A001"))`。这条静默 bug 在重构时高发：把 `return await x()` 改成 `return x()`（少了个 await），测试还可能绿——返回值类型从 str 变成了 coroutine，只有下游 await 它时才"碰巧"工作。

**错误四：`RuntimeWarning` 被忽略后，超时/取消逻辑"不生效"**

协程从未被调度意味着 wait_for/task.cancel 都作用在"没人跑的协程"上，超时后才发现任务没开始。排查顺序：先确认每个协程对象都被 await 或 create_task，再谈超时参数。

> 📌 生产提示：代码评审 async 代码时扫两眼就够——每个 `async def` 的返回值有没有被 await/create_task？async 函数体内有没有同步库调用（requests/time.sleep/重 CPU 循环）？这两条覆盖了 asyncio 线上事故的大多数。

## 13.8 企业场景中的使用方式

- **AI 网关批量扇出**：Spring 服务通过 REST 调你的 Python AI 服务；服务内部用 `gather + Semaphore(8)` 并发调模型 API。对 Spring 来说它就是一次普通 HTTP 调用，asyncio 并发被封装在服务边界内。
- **SSE 流式代理**：ch17 的 SSE 端点本质是"异步生成器逐条 yield"——LangChain/LangGraph 的流式输出（卷二）在 FastAPI 里落地为 `async for chunk in ...: yield ...`。
- **后台收尾**：响应先返回、审计/统计后置——用 ch17 的 BackgroundTasks，不必为"收个尾"引入消息队列；超过"秒级可完成"边界的任务才上队列。
- **与 Java 集成的边界**：Java 侧若已是虚拟线程 + 阻塞式调用，不需要"为了对齐"把 Python 服务改成同步——两边并发模型各自自洽，边界是 HTTP。Python 服务暴露给 Java 的接口不要设计成"回调我"（协程对象无法跨进程传输），以请求-响应或 SSE 为界。

## 13.9 练习

1. **基础**：EX-13-01 中把两行 await 改成 `r1, r2 = await asyncio.gather(fetch_order("A001"), fetch_order("A002"))`，总耗时变成多少？为什么？
2. **基础**：`asyncio.gather` 默认策略下第一个异常抛出后，兄弟任务会怎样？如果这批任务是"给 1000 个用户发推送"，这个语义会 造成什么实际问题？
3. **代码**：写一个 `async def fetch_all(urls: list[str], concurrency: int) -> list[str]`：用 httpx.AsyncClient 并发 GET 所有 url，全程最多 concurrency 路在飞，返回按输入顺序的结果列表（失败的位置放异常对象）。可参考 EX-13-06 与 EX-13-05 组合。
4. **代码**：给 13.9.3 的函数加"单条 5s 超时"（用 wait_for），并保证一条超时不影响其余结果。
5. **调试题**：同事报告"FastAPI 服务一接模型回调就整体变慢，日志显示每个请求都多了 3 秒"，他的 handler 里有一行 `time.sleep(3)  # 模拟限速`。说出事故机制与两种修复方式，并说明哪种更通用。

<details>
<summary>点开查看参考答案</summary>

1. 约 0.30s。gather 让两个协程同时被调度，两个 0.3s 的等待重叠，总耗时取最慢者；原顺序版是 0.3+0.3=0.6s。
2. 兄弟任务**继续跑完**，不被取消。对"发推送"场景：一封失败立刻把异常抛给调用方（外层可能整批中断重试），但其余 999 封仍在后台发送——重试会造成大量重复推送。方案：改用 `return_exceptions=True` 收集后逐个补跑，或用 TaskGroup（异常时统一取消兄弟任务）。
3. 骨架：`sem = asyncio.Semaphore(concurrency)`；`async def one(u): async with sem: return await client.get(u)`；`return await asyncio.gather(*(one(u) for u in urls), return_exceptions=True)`。AsyncClient 应复用（连接池，见 ch15），gather 结果天然按输入顺序对齐。
4. 在 `one()` 内改为 `return await asyncio.wait_for(client.get(u), timeout=5)`；超时抛出的 `asyncio.TimeoutError` 会被 `return_exceptions=True` 收进结果列表对应位置——注意区分"单条超时"（wait_for 包在里面）与"整批超时"（包在 gather 外面），面试常追问。
5. 机制：handler 运行在事件循环里，`time.sleep(3)` 把整个线程睡死——期间所有请求（含健康检查）都无法被调度，表现为"每个请求都慢 3 秒"。修复一（就地）：换 `await asyncio.sleep(3)`；修复二（更通用）：`await asyncio.to_thread(blocking_fn, ...)` 丢线程池——当"3 秒"来自无法改造的同步库（如 requests）时是通用解；CPU 计算则用进程池（衔接 ch14）。
</details>

## 13.10 自测检查表

- 我能说清"调用协程函数不执行函数体"以及让函数体真正跑起来的两种方式（await / create_task）。
- 我能画出 EX-13-02[C] 的时间线，解释 0.1s 的任务为什么 0.6s 才完成。
- 我能说出 gather 结果列表的排序规则（提交顺序）与默认异常策略（首个异常抛出、兄弟任务继续）。
- 我能解释 wait_for 超时为什么会让内部协程执行 finally 清理（超时即取消，取消在 await 点注入 CancelledError）。
- 我知道 `Semaphore` 解决什么问题（对端并发上限），并能在批量扇出代码里正确放置它。
- 我能列出三个"async 函数里最常见的同步阻塞肇事者"及各自的替代品。
- 我能说出 asyncio 与 Java 虚拟线程的两处不等价（协作式 vs 抢占式、单线程 vs 真并行）。

## 13.11 面试追问[模拟题]

1. **[模拟题]** "asyncio 是单线程的，为什么能提高吞吐？"——合格回答要落到"吞吐来自**等待重叠**而不是计算加速"：IO 等待期间事件循环调度其他协程；CPU 密集任务在 asyncio 下毫无收益（衔接 ch14 的 GIL 实验）。追问：那 CPU 密集怎么办？（to_thread / 进程池 / 换语言组件。）
2. **[模拟题]** "task.cancel() 之后协程一定会停吗？"——要分情况：若协程正在 await，取消异常在最近 await 点抛出，若协程用 try/except 吞掉 CancelledError 不 re-raise，取消会被"吃掉"（所以约定是捕获后必须 re-raise）；若协程正在执行不 await 的同步代码，取消要等它回到 await 点才送达——这也解释了"长 CPU 段会推迟取消"。
3. **[模拟题]** "gather 和 TaskGroup 该用哪个？"——gather 是历史主流、语义（异常不取消兄弟）被大量存量代码依赖；TaskGroup（3.11+）异常时取消兄弟任务并聚合 ExceptionGroup，更接近结构化并发。新代码在严格语义下用 TaskGroup，批量部分失败场景用 gather(return_exceptions=True)。两者本书环境（3.14.7）都可用，示例选 gather 以贴近存量工程。

### 待核实

- `asyncio.TaskGroup` 的取消传播细节（兄弟任务收到的异常聚合顺序）以所用 Python 版本官方文档为准，本章未展开实测。
- 事件循环的底层实现（selector/epoll）随平台不同，本章示例不依赖其差异；性能调优话题（uvloop 等）不在本书范围。
- 本书代码以 3.10+ 兼容为编写目标，但 run log 未验证项声明：3.10/3.11 解释器上的回归未逐条执行（本书实测环境为 3.14.7）；个别特性有版本门槛（`TaskGroup`、`asyncio.timeout` 需 3.11+），使用前核对你自己的解释器版本。

---

# 第 14 章 线程、进程与 GIL：选型靠证据，不靠玄学

> **本章目标**：建立"IO 密集 vs CPU 密集"的选型判据表；会用 ThreadPoolExecutor/ProcessPoolExecutor 及其代价；能按版本事实陈述 GIL，而不是背口号。
> **前置知识**：ch13（asyncio 的适用边界）、ch07（函数是一等对象——理解"函数要能被 pickle"）。
> **学完你能做什么**：给一个具体任务选对并发方案并说出理由；解释"为什么我的多线程代码不加速"；看懂 start method 与 `if __name__ == "__main__"` 守卫的因果。

## 14.1 真实问题引入

上一章留了个悬念：asyncio 对 CPU 密集任务毫无帮助。变成你团队的真实场景——AI 服务里两个功能：A 批量调模型 API（每次等 3s 网络往返）；B 对上传文本做"敏感词全量匹配 + 统计"（纯 Python 循环，单次 1.2s），都被要求"批量并发"。

你给 A 用了线程池：10 个线程把 20 个任务从 4s 压到 0.4s，完美。顺手把 B 也套上线程池——1.2s 还是 1.2s，四个线程跟一个线程一样快；日志显示线程确实都在跑，但 CPU 时间没有变快。这就是本章第一个判据：**线程在 Python 里只对"会释放 GIL 的等待"有效**。time.sleep、socket 读写、文件 IO 会释放 GIL（全局解释器锁，Global Interpreter Lock）；纯 Python 字节码计算不释放。B 的正确答案是进程池。本章用三个真实实验把选型表钉死。

## 14.2 一句话解释 + 生活类比 + 类比边界

**一句话解释**：IO 密集用线程池或 asyncio（等待可重叠），CPU 密集只能用进程池（每进程独立 GIL 才有真并行）；GIL 保证同一时刻只有一个线程执行 Python 字节码，它是 CPython 的实现细节而非语言规范。

**生活类比**：把 Python 解释器想成**一间只有一把钥匙的会议室**（GIL）。线程是排队进门的员工：纯计算的人进门后不放手，别人只能干等；**等快递的人**（IO）会带着钥匙去门口等，门空出来给别人用。进程则是**再开一间会议室**（每间有自己的钥匙），真并行，但开新房间要花钱（启动开销）、跨房间传话要复印文件（pickle 序列化）。

**Java 对照**：对"GIL"的第一反应是"这不就是没有并发吗"——对，JVM 线程直接映射内核线程，`new Thread().start()` 就是真并行。所以 Java 的"线程池包打天下"直觉在 Python 失效：ThreadPoolExecutor 只对释放 GIL 的操作有效。`ProcessPoolExecutor` 在 Java 里没有直接对应物——最接近的是"多开几个 JVM 实例 + 消息队列"，但 Python 把"多进程"做成了标准库里的一个池子。

> 💡 类比边界：类比"会议室钥匙"有两处不像。①线程切换不只发生在释放 GIL 时——CPython 每约 5ms 会强制让当前线程交出 GIL 给候补线程，但"交钥匙不等于能并行执行"（一次仍只有一个线程跑字节码），所以多线程对纯 CPU 是"分时"而非"并行"。②GIL 只管**字节码执行**：numpy、torch 的底层 C 代码执行时会主动释放 GIL，"调 numpy/torch 的代码"常不受此限制——AI 应用里"预处理用多线程居然有加速"的原因就在这（加速来自 C 扩释放 GIL，不是 Python 字节码并行）。

## 14.3 正式原理与准确术语

- **GIL（Global Interpreter Lock，全局解释器锁）**：CPython 解释器的互斥锁，保证同一时刻仅一个线程执行 Python 字节码。**版本事实**：CPython 3.12 前的所有正式版本默认带 GIL；3.13 起提供 free-threading（自由线程）**实验性**构建（可用 `python3.13t` 类构建关闭 GIL），截至本书核实的版本仍非默认、生态适配有限——具体状态以官方发布说明为准。
- **IO 密集（IO-bound）**：耗时主要在等待外部系统（网络、磁盘）。特征：CPU 占用低、吞吐瓶颈在等待。
- **CPU 密集（CPU-bound）**：耗时主要在计算。特征：CPU 占用打满，等待可忽略。
- **线程池（`ThreadPoolExecutor`）**：`concurrent.futures` 标准库；`submit()` 返回 `Future`（与 Java `ExecutorService.submit` 同名同义），`map()` 与内置 map 同形，`as_completed()` 按完成顺序消费。
- **进程池（`ProcessPoolExecutor`）**：每 worker 一个独立解释器进程；参数与返回值经 pickle 跨进程传输；**任务函数必须定义在模块顶层**（可被按名字找回），且脚本必须有 `if __name__ == "__main__"` 守卫。
- **启动方式（start method）**：`fork`（复制父进程，Linux 传统默认）/`spawn`（重新启动解释器，Windows 与 macOS 默认）/`forkserver`（由服务进程 fork，Python 3.14 起 Linux 默认改为 forkserver——以官方发布说明为准）。spawn/forkserver 下子进程会重新导入主模块，这就是 main 守卫成为硬要求的原因。
- **多进程的代价**：池启动开销（百毫秒级）、序列化传输成本、函数可 pickle 限制。适合**粗粒度**任务。

## 14.4 最小完整示例：线程池对 IO 任务的真实加速

EX-14-01 | 示例代码/ch14_threads_processes/ex_14_01_thread_pool.py（完整可运行）

```python
import time
from concurrent.futures import ThreadPoolExecutor, as_completed


def call_remote(task_id: int) -> int:
    time.sleep(0.2)  # 模拟一次 200ms 的远程调用：time.sleep 释放 GIL，线程可以真正并行
    return task_id


def run_pool(max_workers: int, n_tasks: int) -> float:
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        # submit 返回 Future（Java 对照：ExecutorService.submit → Future<T>）
        futures = [pool.submit(call_remote, i) for i in range(n_tasks)]
        # as_completed：谁先完成先处理谁，不按提交顺序
        for fut in as_completed(futures):
            _ = fut.result()
    return time.perf_counter() - started


if __name__ == "__main__":
    n = 20
    seq = run_pool(max_workers=1, n_tasks=n)
    par = run_pool(max_workers=10, n_tasks=n)
    print(f"20 个 200ms 的 IO 任务：单线程（max_workers=1）总耗时 {seq:.2f}s")
    print(f"20 个 200ms 的 IO 任务：线程池（max_workers=10）总耗时 {par:.2f}s")
    print(f"加速比 ≈ {seq / par:.1f} 倍——IO 等待期间线程释放 GIL，等待可重叠")
```

真实运行输出（本沙箱实测）：

```text
20 个 200ms 的 IO 任务：单线程（max_workers=1）总耗时 4.00s
20 个 200ms 的 IO 任务：线程池（max_workers=10）总耗时 0.40s
加速比 ≈ 10.0 倍——IO 等待期间线程释放 GIL，等待可重叠
```

4.00s → 0.40s，10 倍——和 Java 线程池处理 IO 的手感一致。API 三件套也对齐：`submit` 返回 Future、`as_completed` 类似"轮询 CompletionService"、`with` 块相当于 `shutdown + awaitTermination`。**注意**：若单任务 3s、批量 500 个，线程池 10 worker 要 150s——同样的等待重叠，但线程成本（每任务一线程栈）比协程高一个数量级，此时 ch13 的 asyncio 是更优解。线程池是"同步库生态下"的并发兜底，不是首选。

## 14.5 逐段解释：CPU 密集实验与进程池的代价

### 14.5.1 一锤定音的 CPU 密集实验

EX-14-02 | 示例代码/ch14_threads_processes/ex_14_02_cpu_bound_experiment.py（节选，完整版见该文件）

```python
def count_primes_in_range(lo: int, hi: int) -> int:
    """统计 [lo, hi) 内素数个数——纯 Python 试除法，刻意不用 numpy，让每条字节码都吃 GIL。"""
    total = 0
    for n in range(lo, hi):
        is_prime = True
        d = 2
        while d * d <= n:
            if n % d == 0:
                is_prime = False
                break
            d += 1
        if is_prime:
            total += 1
    return total

# 试除成本近似正比于 n^1.5，按等成本把 [2, 400000) 切成 4 片（每片约 0.3s，总 ~1.2s）
BOUNDS = [2, 158_740, 251_984, 341_995, 400_000]
CHUNKS = list(zip(BOUNDS[:-1], BOUNDS[1:]))

if __name__ == "__main__":
    t_seq, n1 = run_serial()
    t_thr, n2 = run_threads()
    t_prc, n3 = run_processes()
    assert n1 == n2 == n3, "三种方式算出的素数总数必须一致（正确性先行）"
```

真实运行输出（本沙箱实测，单次运行结果）：

```text
纯 Python 素数计数（4 片等成本工作，总素数 33860 个）：
  串行           1.04s  （基准 1.00x）
  线程池 4 线程  1.06s  （0.98x —— 几乎无加速：CPU 计算独占 GIL，甚至更慢）
  进程池 4 进程  0.79s  （1.32x —— 接近核数加速：每个进程有独立 GIL）
（本机 CPU 核数 os.cpu_count() = 3，加速比上界受核数限制）
```

这是本章的"证据章"：同一份计算跑三遍。线程 4 条 0.98×——四个线程分时共享一个 GIL，总工作量不变还多了切换开销；进程 1.32×——每进程独立 GIL 真并行，但 0.79s 距离"除以核数"的理想值还有距离，因为进程池启动、pickle 传输都要花钱，且本机只有 3 核。三个数字合起来就是选型表：

| 任务类型 | 首选 | 次选 | 不选 |
|---|---|---|---|
| IO 密集 + 同步库生态 | 线程池 | asyncio.to_thread | 多进程（浪费） |
| IO 密集 + 异步库生态 | asyncio | 线程池 | 多进程（浪费） |
| CPU 密集（纯 Python） | 进程池 | 换 numpy/模型推理等释放 GIL 的实现 | 线程/asyncio（无加速） |
| CPU 密集（C 扩展已释放 GIL） | 线程池 | 进程池 | — |

### 14.5.2 进程池的三笔账：启动、序列化、可 pickle

EX-14-03 | 示例代码/ch14_threads_processes/ex_14_03_process_pool.py（节选，完整版见该文件）

```python
def square(x: int) -> int:
    # 注意：这个函数必须定义在模块顶层——子进程要按名字"找回"它（可 pickle），嵌套函数不行
    return x * x

def main() -> None:
    from multiprocessing import get_start_method
    print(f"当前平台默认启动方式：{get_start_method()}")
    with ProcessPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(square, range(8)))
    print(f"pool.map(square, 0..7) = {results}，含池启动共耗时 {(time.perf_counter() - started) * 1000:.0f}ms")
```

真实运行输出：

```text
当前平台默认启动方式：forkserver
pool.map(square, 0..7) = [0, 1, 4, 9, 16, 25, 36, 49]，含池启动共耗时 168ms
100 个 submit+result：total=328350，耗时 35ms
```

三笔账对应三行输出：①启动方式是 forkserver（3.14 起 Linux 默认变化，run log 记录了本次实测），池冷启动 168ms——进程池要**常驻复用**，别每个请求建一个；②100 个小任务 35ms，传输成本占比可观——**粒度太细的任务不值得进进程池**，攒批再提交；③`square` 必须在模块顶层：子进程启动时要重新导入模块、按限定名找回函数，`lambda` 与闭包内函数没有名字，pickle 不了。对照 Java：Java lambda 捕获的是同一 JVM 内的对象引用，Python 跨进程是真的"换了个内存空间"。

### 14.5.3 线程的共享状态与锁：GIL 不等于"线程安全"

Java 工程师最容易从"GIL"推出错误结论："反正一次只有一个线程执行，共享 dict 不用加锁吧？"——**错**。GIL 保证的是单条字节码的原子性，不保证"检查-再动作"（check-then-act）序列的原子性：`counter[key] = counter.get(key, 0) + 1` 在两个线程交错时会丢计数（get 与赋值之间可能切换线程）。EX-13-06 用全局 `_running` 计数演示并发时，代码注释专门写了"演示用全局计数，工程代码请用上下文隔离"。需要跨线程共享可变状态时的正确姿势：

```python
# 语法示意：线程锁保护共享计数
lock = threading.Lock()
with lock:
    counter[key] = counter.get(key, 0) + 1
```

对照 Java：`synchronized`/`ReentrantLock`/`AtomicInteger`/`BlockingQueue` 都有对应物——`threading.Lock`（不可重入）/`RLock`（可重入）/无内建 Atomic（锁或队列替代）/`queue.Queue`。但选型顺序要强调：**能不共享就不共享**（参数传入、结果返回、queue 传消息），共享则必须锁，锁粒度尽量小——这与 Java 的并发纪律完全一致，GIL 没有豁免权。

另一个从示例里顺手学到的细节：EX-13-08/EX-15-01 的测试服务器都设了 `daemon_threads = True`——守护线程随主进程退出而被强制终止，测试代码用它让"主程序退出不必等清理"；生产服务的线程池**绝不该是 daemon**（任务做一半被腰斩，等于没有优雅停机）。

## 14.6 安装 / 文件位置 / 运行命令

- 依赖：纯标准库（concurrent.futures、multiprocessing、time）。
- 文件位置：`示例代码/ch14_threads_processes/`（3 个示例）；测试 `测试/test_ch14.py`（3 个，含真实计时的加速比断言）。
- 运行命令：

```bash
python3 示例代码/ch14_threads_processes/ex_14_01_thread_pool.py
python3 示例代码/ch14_threads_processes/ex_14_02_cpu_bound_experiment.py   # ~3s
python3 示例代码/ch14_threads_processes/ex_14_03_process_pool.py
python3 -m pytest 测试/test_ch14.py -v
```

## 14.7 常见错误与排查（真实踩坑记录）

**错误一：`RuntimeError: An attempt has been made to start a new process before the current process has finished its bootstrapping phase.`**

前一位工程师写探测脚本时把 ProcessPoolExecutor 放在模块顶层且没写 main 守卫：spawn/forkserver 下子进程重新导入主模块 → 顶层代码再次执行 → 又起池 → 递归。run log 记录了该 RuntimeError；本书在本沙箱（3.14 forkserver）复现的堆栈尾部为子进程 `runpy.run_path` 重新执行主模块后连接被重置（`ConnectionResetError: [Errno 104]`）——两种表象同一根因。修复：所有起进程的代码放进 `if __name__ == "__main__":`。这条在 Windows/新版 macOS（默认 spawn）必然报错，在旧版 Linux（默认 fork）"碰巧能跑"——环境一变就炸。

**错误二：多线程跑 CPU 任务"不加速"且无报错（静默失效）**

EX-14-02 的线程结果 0.98×是"正确但不加速"的形态——最迷惑人，因为没有异常、结果也对。判据：任务里若只有纯 Python 计算（字符串处理、dict 操作、自写算法），线程不加速；若有 `time.sleep`/socket/文件读写/numpy、torch 调用，线程才可能加速。修复：改进程池，或改用底层释放 GIL 的库。

**错误三：`PicklingError` / `AttributeError: Can't pickle local object`**

把 `lambda x: x*x` 或嵌套函数 submit 给进程池必然如此：pickle 按限定名序列化函数，局部对象没有限定名。修复：提到模块顶层定义具名函数；需要携带状态就作为参数传入（参数也必须可 pickle——打开的文件句柄、数据库连接都不可）。

**错误四：进程池启动一次要 168ms，被误当"进程池很慢"**

有团队在高频接口里每个请求 `with ProcessPoolExecutor() as pool:`，P99 多出 170ms 就下结论"多进程不行"。正确姿势：进程池是**长驻资源**——模块级创建或用 lifespan 管理，复用 worker；这和 Java 里"不要每个请求 new 一个 ExecutorService"是同一条军规。

## 14.8 企业场景中的使用方式

- **Java 服务里的调用边界**：你的 Spring 服务不需要感知 Python 内部用的是线程还是进程——边界是 HTTP。Python AI 服务内部：IO（调模型/检索）用 asyncio；偶发的重 CPU 步骤（长文本统计、图片缩放）用 `asyncio.to_thread` 或常驻进程池包一层，对请求方仍是异步接口。
- **uvicorn 多 worker 是"进程池"的服务化形态**：ch20 的 `uvicorn --workers 2` 就是每个 worker 一个进程（各自独立 GIL），并行能力来自进程模型——这也解释了为什么"进程内计数器限流"在多 worker 下必然失灵，必须用 Redis（ch19）。
- **模型推理不受纯 Python GIL 讨论**:本地跑模型时，真正的计算在 torch/ONNX 的 C/CUDA 层，会释放 GIL；"预处理慢"与"推理慢"要分开测（衔接 ch59 的性能分析思路）。

## 14.9 练习

1. **基础**：把 EX-14-01 的 `time.sleep(0.2)` 换成纯 Python 循环（如累加到 2000 万）模拟 CPU 任务，线程池加速比会变成多少？为什么？
2. **基础**：`os.cpu_count()` 为 3 的机器上，`ProcessPoolExecutor(max_workers=8)` 会怎样？max_workers 设多少合适？
3. **代码**：写一个函数 `def process_batch(paths: list[pathlib.Path]) -> list[int]`：统计每个文本文件的行数（IO+CPU 混合），先用线程池实现；再把"逐文件字符统计"改成"每文件一个进程任务"的实现，说明你的选择依据。
4. **代码**：给 14.9.3 的进程池版本加 main 守卫并解释：如果把 `pool` 的创建写在模块顶层，spawn 环境下会发生什么？
5. **调试题**：同事的预处理脚本在同事自己 Mac 上跑得好好的，部署到 Linux 服务器 `ProcessPoolExecutor` 直接 `RuntimeError: ...bootstrapping phase`。给出最可能的原因与两步排查。

<details>
<summary>点开查看参考答案</summary>

1. 约 1.0×（EX-14-02 实测 0.98×）。纯 Python 字节码执行受 GIL 互斥，多线程只是分时共享一把锁，总耗时不变甚至略增（切换开销）。
2. 8 个 worker 全部能创建（上限不是核数），但超额 worker 只会排队争抢 3 个核，加速比上界仍约 3×，多余 worker 只增加内存与调度成本；CPU 密集任务的合理上限是 `os.cpu_count()`（或减 1 留主线程余量）。
3. 行数统计以 IO 为主：线程池即可（读文件释放 GIL）。字符统计若为纯 Python 实现：数据量大到单文件处理 >10ms 时改进程池（粗粒度），否则线程池就够——依据是"任务粒度 vs 进程池启动/序列化开销"的比值。
4. spawn/forkserver 启动的子进程会重新导入主模块，顶层"创建进程池"的代码在子进程里再次执行 → 递归创建进程，最终 RuntimeError（bootstrapping phase）或连接被重置。守卫让子进程导入模块时跳过这段代码。
5. 原因：Mac 默认 start method 是 spawn（一直是），Linux 上 Python 3.14 起默认也改成了 forkserver（旧版是 fork）——旧版 fork 不重新导入主模块所以顶层起池"碰巧能跑"，forkserver/spawn 重新导入就炸了。排查两步：①确认脚本是否缺 `if __name__ == "__main__"` 守卫（大概率是）；②`python3 -c "import multiprocessing; print(multiprocessing.get_start_method())"` 确认当前默认方式。
</details>

## 14.10 自测检查表

- 我能不查资料画出"IO 密集 vs CPU 密集"选型表，并说出每一格的判据。
- 我能解释 EX-14-02 的三个数字（串行/线程/进程）为什么是 1.00×/0.98×/1.32×。
- 我知道 GIL 是 CPython 实现细节，能按版本事实陈述（3.13 free-threading 实验性），不把它当语言规范背。
- 我能说出进程池的三笔账（启动开销、pickle 传输、可 pickle 限制）并各自给出规避手段。
- 我知道 start method 有哪三种、3.14 起 Linux 默认是什么、为什么 main 守卫成为硬要求。
- 我能解释 uvicorn --workers 与本章进程池的亲缘关系，以及它对"进程内计数器"方案的否定。
- 我知道 numpy/torch 代码为何常不受"线程无加速"结论影响。

## 14.11 面试追问[模拟题]

1. **[模拟题]** "Python 的 GIL 是什么？Python 3.13 之后还存在吗？"——合格回答：GIL 是 CPython 的互斥锁，保证同一时刻一个线程执行字节码；3.13 起提供 free-threading 实验构建，但默认构建仍有 GIL，第三方扩展兼容性在演进中——回答边界是"以官方发布说明为准"，别把"GIL 已死"当现状。追问：free-threading 下单线程性能如何？（实验版有开销，具体数字随版本变化，别背。）
2. **[模拟题]** "Java 里一个 `ExecutorService` 就能处理 IO 和 CPU，Python 为什么要分两个池？"——先纠正前提：Java 线程对 CPU 任务有效是因为 JVM 线程真并行、无 GIL；Python 线程对纯 CPU 无效才有"分池"。再给判据：看瓶颈是等待还是计算。
3. **[模拟题]** "你的 AI 服务里什么时候会同时用到 asyncio 和线程池？"——典型答案：asyncio 为主干（HTTP/SSE/并发调模型），`asyncio.to_thread` 包同步库（某个只有同步 SDK 的向量库），常驻进程池包偶发重 CPU（本地 embedding 归一化）——三者共存且各司其职，关键是别让同步阻塞混进事件循环（ch13 红线）。

### 待核实

- GIL/free-threading 的版本演进按"以官方发布说明为准"处理（FACTS 约束）；本书未在 3.13 free-threading 构建上实测，相关性能结论不写死。
- Python 3.14 起 Linux 默认 start method 为 forkserver 是本书沙箱实测（`get_start_method()` 输出 forkserver）；更早小版本的默认值变化以官方 changelog 为准。

---

# 第 15 章 HTTP 客户端工程化：超时、重试与幂等

> **本章目标**：掌握 httpx 超时三件套（connect/read/pool）的语义与配置；会写"指数退避+抖动"的可复用重试封装；理解幂等性与 Idempotency-Key 的服务端实现思想。
> **前置知识**：ch12（urllib/httpx 基础调用）、ch08（异常体系）。
> **学完你能做什么**：为"调模型 API"写出带完整超时与重试的客户端封装；在故障评审时说清 502/503/504 与超时各自该如何对待；解释重复扣款事故的根因。

## 15.1 真实问题引入

Java 里你大概被 OkHttp/Apache HttpClient 的"默认配置"坑过：没设 read timeout，一次下游抖动就把几十个 Tomcat 线程挂住。到 Python AI 应用，这个场景更高频：**每个核心功能都依赖模型 API**——它比数据库更慢（秒级）、更容易 429/503（限流与过载是常态）、按 token 计费所以重复请求是真实损失。

某电商平台（合成案例）的客服机器人上线第一周出了三件事：①模型 API 网络抖动时服务 P99 从 2s 飙到 60s——httpx 默认 `timeout=5` 的语义被理解错，长响应阶段无超时；②修复超时后引入重试，又出事故：**给"创建工单"这种非幂等操作无脑重试**，用户提交一次、系统创建三次；③重试风暴——下游恢复瞬间，几百个客户端同一毫秒一起重试，把刚喘过气来的下游再次打挂。三件事对应本章三节：超时三件套、重试策略、幂等性。

## 15.2 一句话解释 + 生活类比 + 类比边界

**一句话解释**：把每次出站 HTTP 调用当成"可能失败的远程操作"来配置——建连/读响应/等连接池分别限时（connect/read/pool），可重试的错误用"指数退避+抖动"重发，非幂等操作用 Idempotency-Key 让服务端识别重复。

**生活类比**：超时三件套像给快递定规矩——**connect** 是"拨通电话要多久"（对方不接就算了）；**read** 是"拨通后等对方说话要多久"（电话通了但一直沉默）；**pool** 是"电话机都被占着，排队等电话机要多久"（线路全忙）。重试退避像客服回拨策略：第一次失败等 1 分钟再拨，第二次等 2 分钟……（指数），而所有客服**各自加一点随机偏移**（抖动），避免整点一起回拨把线路再次挤爆。幂等键像外卖订单号：骑手重送一次，你报订单号，店家说"这单已送过"，不会给你做两份。

**Java 对照**：`httpx.Client` ↔ Apache HttpClient 的 `CloseableHttpClient`（连接池 + keep-alive 同构）；`httpx.Timeout(connect=, read=, pool=)` ↔ `RequestConfig.setConnectTimeout/setSocketTimeout/setConnectionRequestTimeout`——三件套一一对应，其中 pool 超时就是"从连接池租借连接的等待上限"。重试封装 ↔ Resilience4j Retry（`waitDuration` + 指数 backoff + jitter，思想完全一致）。

> 💡 类比边界：客户端重试 ≠ 服务端可靠性。客户端只能对"网络层错误与 5xx"负责，4xx 是"你自己的请求有问题"，重试只会放大错误；而重试的三大前提——**请求可重发（幂等或带幂等键）、下游能承受（限流配合）、调用方能等待（预算内）**——任何一条不满足都不该重试。Resilience4j 还有熔断器（CircuitBreaker）防重试风暴，本章的手写退避+抖动只解决"错峰"，熔断在 ch59 稳定性章节展开。

## 15.3 正式原理与准确术语

- **超时三件套**：`httpx.Timeout(connect=…, read=…, write=…, pool=…)`——connect 建 TCP 连接时限；read 两次数据到达之间的时限（**不是**整个响应的总时限）；write 发请求体时限；pool 从连接池获得空闲连接的排队时限。四参数必须显式给全或给一个默认值（排错节有真实报错）。
- **连接池与 keep-alive**：`httpx.Client`（同步）/`httpx.AsyncClient`（异步）维护 TCP 连接复用；`httpx.Limits(max_connections=…)` 控制池容量。
- **重试与退避（backoff）**：对瞬时故障重发；第 n 次重试等待上限 `min(max_delay, base_delay * 2**(n-1))` 即指数退避。
- **抖动（jitter）**：在退避上限内随机取真实等待（`random.uniform(0, ceiling)`），防止所有客户端失败后同步重试。
- **幂等性（idempotence）**：同一操作执行一次与多次效果相同。GET/PUT/DELETE 天然幂等；**POST 不幂等**——超时后你不知道请求是否已生效，重发可能重复扣款。
- **Idempotency-Key**：客户端为"同一笔业务操作"生成唯一键放请求头；服务端以键为账本主键——首执记账，重复回放首次响应（Stripe 等支付 API 的标准做法）。
- **可重试集合**：传输层错误（`httpx.TransportError`）与 502/503/504；**4xx 一律不重试**。

## 15.4 最小完整示例：连接池与超时三件套的真实验证

本章共用一个本地测试服务器（标准库 http.server 实现，含慢端点/不稳定端点/幂等端点），所有示例离线可跑：

辅助设施 | 示例代码/ch15_http_client/server_stub.py（非编号示例，供 EX-15-01~03 与 测试/test_ch15.py 共用；节选）

```python
# 完整版见该文件（含 /slow /flaky /pay /reset 四类端点的实现）
GET  /ok                 → 200 {"ok": true}
GET  /slow?ms=N          → 等 N 毫秒再返回 200（默认 200ms）
GET  /flaky?fail=N&key=K → 对同一个 key 前 N 次返回 503，之后返回 200（模拟"先失败后成功"）
POST /pay                → 带 Idempotency-Key 头时同一 key 只扣款一次，重复请求回放首次响应
```

EX-15-01 | 示例代码/ch15_http_client/ex_15_01_client_pool_timeout.py（节选，完整版见该文件）

```python
    # 超时三件套：connect=建连、read=等响应、pool=排队等连接池里的空闲连接
    timeout = httpx.Timeout(connect=1.0, read=2.0, write=1.0, pool=1.0)
    shared = httpx.Client(base_url=base, timeout=timeout)
    started = time.perf_counter()
    for _ in range(10):
        shared.get("/ok")
    shared_time = time.perf_counter() - started
    # ...对照：每次 with httpx.Client(...) 重新建连...
    # ── 2. read 超时：服务端睡 2s，客户端 read=0.3s 先超时 ──
    # ── 3. pool 超时：连接池只有 1 条连接，两个慢请求并发，第二个排队超时 ──
    limits = httpx.Limits(max_connections=1, max_keepalive_connections=1)
```

真实运行输出（本沙箱实测）：

```text
[1] 10 次请求，共享 Client（keep-alive 复用连接）：399ms
[1] 10 次请求，每次新建 Client（重新 TCP 建连）：  637ms
[2] read 超时：301ms 后抛出 httpx.ReadTimeout（服务端要 2000ms）
[3] pool 超时：808ms 后抛出 httpx.PoolTimeout（排队等连接超过 0.3s）
```

三组数字各说一件事：①复用连接 399ms vs 每次新建 637ms——省下 10 次 TCP 握手，**Client 要复用不要随手 new**（HttpClient 同理）；②read=0.3s 在 301ms 处准时触发 ReadTimeout——read 超时保护的是"响应阶段的挂起"；③pool 超时 808ms：两条并发请求共享 1 条连接的池，第二条排队超过 pool=0.3s 抛 PoolTimeout——当 QPS 超过连接池容量时，报错的是 pool 而不是 read，**见到 PoolTimeout 先扩池或限流，别去调 read**。

## 15.5 逐段解释：重试封装与幂等键

### 15.5.1 指数退避 + 抖动的完整实现

EX-15-02 | 示例代码/ch15_http_client/ex_15_02_retry_backoff.py（节选，完整版见该文件）

```python
def request_with_retry(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    max_attempts: int = 4,
    base_delay: float = 0.1,
    max_delay: float = 1.0,
    retry_status: tuple[int, ...] = (502, 503, 504),
    retry_on: tuple[type[Exception], ...] = (httpx.TransportError,),
    **kwargs: Any,
) -> httpx.Response:
    """可复用的同步重试封装：指数退避 + 完全抖动（full jitter）。

    指数退避：第 n 次重试的等待上限 = min(max_delay, base_delay * 2**(n-1))
    完全抖动：真实等待 = random.uniform(0, 上限)，避免失败后所有客户端同一时刻再撞一次
    """
    for attempt in range(1, max_attempts + 1):
        try:
            resp = client.request(method, url, **kwargs)
            if resp.status_code in retry_status and attempt < max_attempts:
                log.warning("第 %d 次：%d，准备退避重试", attempt, resp.status_code)
            else:
                return resp
        except retry_on as exc:  # 网络层错误（超时/连接拒绝/断连）才重试；4xx 参数错误不重试
            if attempt >= max_attempts:
                raise
        ceiling = min(max_delay, base_delay * 2 ** (attempt - 1))
        delay = random.uniform(0, ceiling)
        log.info("退避 %.0f ms（上限 %.0f ms）", delay * 1000, ceiling * 1000)
        time.sleep(delay)
```

真实运行输出（本沙箱实测；退避时长含抖动，每次运行不同）：

```text
WARNING 第 1 次：503，准备退避重试
INFO 退避 19 ms（上限 100 ms）
WARNING 第 2 次：503，准备退避重试
INFO 退避 105 ms（上限 200 ms）
最终结果：200 {'ok': True, 'attempt': 3}，总耗时 212ms（含两次退避）
404 不重试：404（若错误地重试 4xx，只会放大数据库压力并拉长尾延迟）
```

逐段看设计决策：①**签名带 `**kwargs`**——把 query/headers/json 等原样透传给 client.request 的通道，排错节记录了缺它的真实 TypeError；②**重试集合显式列举**（502/503/504 + TransportError），4xx 直接返回不重试；③**重试耗尽返回最后一次真实响应**而不是抛异常——调用方（比如要回给前端 503）需要最后一次的响应体，该语义由 测试/test_ch15.py 固化；④退避上限 100→200→400ms 指数增长，真实等待在 `[0, 上限]` 随机（19ms/105ms 即抖动效果）。

### 15.5.2 幂等键：让"重发"变得安全

EX-15-03 | 示例代码/ch15_http_client/ex_15_03_idempotency_key.py（完整可运行）

```python
        # 场景一：无幂等键——网络抖动导致客户端重发同一笔支付 → 两次扣款
        r1 = client.post("/pay", json={"amount": 99})
        r2 = client.post("/pay", json={"amount": 99})  # 同样的业务请求重发了一次
        print(f"[无幂等键] 第一次：{r1.json()['order_id']}  第二次：{r2.json()['order_id']}")

        # 场景二：带 Idempotency-Key——客户端为"同一笔业务操作"生成唯一键，重发也不重复扣款
        headers = {"Idempotency-Key": "user-42-order-2024-0601"}
        r3 = client.post("/pay", json={"amount": 99}, headers=headers)
        r4 = client.post("/pay", json={"amount": 99}, headers=headers)  # 网络重试/用户双击都重发它
        print(f"[带幂等键] 第二次响应头 X-Idempotent-Replay={r4.headers.get('X-Idempotent-Replay')}")
```

真实运行输出（本沙箱实测；订单号含随机成分，每次运行不同）：

```text
[无幂等键] 第一次：ORD-52853  第二次：ORD-02786
[无幂等键] 两笔订单号不同 → 被服务端当成两笔扣款（资金事故的根源）
[带幂等键] 第一次：ORD-65973  第二次：ORD-65973
[带幂等键] 订单号相同，第二次响应头 X-Idempotent-Replay=true
```

服务端账本逻辑（server_stub.py）：收到带键请求 → 键已存在则**回放首次响应**并打 `X-Idempotent-Replay: true` 头 → 不存在则执行并记账。工程要点：账本要落库（带 TTL）、回放要存完整响应（状态码+头+体）、键要绑定业务语义（"user-42-order-2024-0601"——用户+业务+日期），不能随机数（否则每次重试生成新键等于没键）。对照 Java：Spring 生态通常落在"幂等表 + 唯一索引"或消息中间件的幂等消费——**键是业务契约，不是技术细节**。

### 15.5.3 429 与 Retry-After：跟限流的下游"跳舞"

模型 API 最常见的拒绝不是 503 而是 429（限流）。它落在"不盲目重试"与"不能不重试"的缝隙里，正确姿势是**读 Retry-After**：

- 响应头带 `Retry-After: N`（秒）→ 等待至少 N 秒再重试，且这次等待**替代**常规退避计算；
- 没有 Retry-After → 退避重试，但基数调大（429 说明你在逼近配额，指数退避应从更晚开始）；
- 429 频繁出现本身就是信号：你的并发/配额规划有问题——去和平台谈配额，或在客户端用 ch13 的 Semaphore 主动限流，而不是让重试机制硬扛。

与 ch17 服务端的 429 对照着看最有感觉：那边响应带三个头——`retry-after: 59`、`x-ratelimit-limit: 60`、`x-ratelimit-remaining: 0`（ch17.6 实测）——一个合格的客户端恰好消费这三个头：等待、自限、上报监控。openai SDK 内建重试对 429 的处理在 ch24 展开；自己写客户端（本章的 `request_with_retry`）时，要把 429 显式加入 `retry_status` 并优先尊重 Retry-After 头——本章练习 4 就是这个改造。

## 15.6 安装 / 文件位置 / 运行命令

- 依赖：httpx 0.28.1（requirements.txt）；测试服务器为标准库实现，无需联网。
- 文件位置：`示例代码/ch15_http_client/`（3 个示例 + server_stub.py 共用服务器）；测试 `测试/test_ch15.py`（6 个）。
- 运行命令：

```bash
python3 示例代码/ch15_http_client/ex_15_01_client_pool_timeout.py
python3 示例代码/ch15_http_client/ex_15_02_retry_backoff.py
python3 示例代码/ch15_http_client/ex_15_03_idempotency_key.py
python3 示例代码/ch15_http_client/server_stub.py 8931     # 独立起服务器（可选）
python3 -m pytest 测试/test_ch15.py -v
```

## 15.7 常见错误与排查（真实踩坑记录）

**错误一：`ValueError: httpx.Timeout must either include a default, or set all four parameters explicitly`**

```text
ValueError: httpx.Timeout must either include a default, or set all four parameters explicitly
```

原因：写了 `httpx.Timeout(connect=1.0, read=2.0, pool=1.0)`——漏了 write。httpx 拒绝"部分显式"的超时（它无法替你猜 write 该多长）。修复：四参数显式齐全，或 `httpx.Timeout(5.0, connect=1.0)` 给默认值再覆盖个别项。EX-15-01/02 开发时都真实触发过。

**错误二：`TypeError: request_with_retry() got an unexpected keyword argument 'params'`**

调用方写 `request_with_retry(client, "GET", "/flaky", params={"fail": 2})` 直接 TypeError。原因：封装函数签名没有 `**kwargs`，params 落不进去。修复：签名末尾加 `**kwargs: Any` 并 `client.request(method, url, **kwargs)` 透传（EX-15-02 现在的写法）。教训：给客户端函数做包装时，**透传参数是第一天的需求**，签名从第一天就该留。

**错误三：把 `timeout=5` 当成"整个请求 5 秒"**

`httpx.get(url, timeout=5)` 的 5 秒按三件套拆分语义各自计时，read 超时是"两次数据到达之间"，不是总时长——一个每 4s 吐一个字节的慢接口永远不会触发 read=5。要总时长控制，在调用层再包 `asyncio.wait_for(...)`（ch13）。这也是"为什么配了超时还会挂 60 秒"的常见谜底。

**错误四：重试把非幂等 POST 打成三笔订单**

没有幂等键就给"创建工单"加重试，15.1 的真实事故形态。修复优先级：能改成天然幂等就改（PUT 语义）；改不了就上 Idempotency-Key（15.5.2）；都做不到就对该操作**禁用自动重试**，把重试决策留给用户。

## 15.8 企业场景中的使用方式

- **模型 API 客户端统一封装**：在 Java 网关背后，Python AI 服务里所有对 OpenAI 兼容端点的调用走一个模块：`httpx.AsyncClient` 常驻 + 三件套超时 + 退避重试 + 429 特殊处理（读 Retry-After 头）。ch59 的稳定性参数表就建立在这套封装上。
- **Resilience4j 对照速查**：`Timeout(connect=, read=, pool=)` ↔ RequestConfig 三超时；`request_with_retry` ↔ Retry + ExponentialBackoffWithJitter；`Semaphore`（ch13）↔ Bulkhead 隔离；熔断（不重试直接失败一段时间）↔ CircuitBreaker——Python 侧常用 tenacity 等库，但思想一致，面试时讲思想不背库名。
- **与 Spring 集成的幂等链路**：Java 网关生成 Idempotency-Key 透传给 Python 服务，Python 服务落 Redis 账本（ch19 的 SETNX+TTL 正好够用），重复请求回放——幂等账本跨语言共享，键规范要写进接口文档。

## 15.9 练习

1. **基础**：说出三件套各自保护什么。你的服务报了大量 `httpx.PoolTimeout` 而 read 超时几乎为零，最可能的原因是什么？
2. **基础**：为什么 4xx 一律不重试，而 503 可以？给一个"503 重试反而危险"的场景。
3. **代码**：把 EX-15-02 的 `request_with_retry` 改造成异步版 `arequest_with_retry(client: httpx.AsyncClient, ...)`（`await client.request(...)`、`await asyncio.sleep(delay)`），并用 respx（ch18）写一个"两次 503 后 200"的测试。
4. **代码**：给 15.9.3 的函数加"尊重 Retry-After"逻辑：响应头带 `Retry-After: N`（秒）时，退避时长取 `max(计算出的退避, N)`。
5. **调试题**：同事的客户端"偶发"收到 `httpx.ReadTimeout`，但他确认服务端日志显示该请求 20ms 就处理完了。列出三个可能的原因（提示：从 read 语义、连接池、代理/网关各想一个）。

<details>
<summary>点开查看参考答案</summary>

1. connect=TCP 建连时限；read=等响应数据（两次到达之间）时限；pool=排队等空闲连接时限。大量 PoolTimeout：并发量超过 `max_connections`（或池被慢请求占满），先看 `Limits` 配置与下游 P99，扩池/加并发限制/排查慢请求，而不是调大 read。
2. 4xx 表示请求本身有问题（参数错、无权限、不存在），重发结果必然相同，只放大压力；503 表示服务端暂时不可用，稍后可能恢复。503 重试危险的场景：非幂等 POST 得到 503 时，服务端可能其实已处理（响应在路上丢了），重试=重复扣款——所以重试 5xx 也必须以幂等为前提。
3. 骨架：`async def arequest_with_retry(client, method, url, *, max_attempts=4, base_delay=0.1, max_delay=1.0, retry_status=(502,503,504), retry_on=(httpx.TransportError,), **kwargs)`，循环内 `resp = await client.request(method, url, **kwargs)`、`await asyncio.sleep(random.uniform(0, ceiling))`。测试：`@respx.mock` 装饰，`respx.get(url).mock(side_effect=[httpx.Response(503), httpx.Response(503), httpx.Response(200, json={"ok": True})])`，断言 `route.call_count == 3`。
4. 在计算 delay 后：`ra = resp.headers.get("Retry-After") if isinstance(resp, httpx.Response) else None`（异常分支无头）；`delay = max(delay, float(ra)) if ra else delay`。注意 Retry-After 还可能是 HTTP 日期格式，工程实现要两态兼容。
5. ①read 是"两次数据到达之间"：服务端 20ms 处理完但响应分块/延迟到达（如代理缓冲），客户端仍可能 read 超时；②连接池里复用了已被服务端/防火墙静默关闭的"半死连接"（keep-alive 空闲超时比服务端长），第一次写入后等待响应超时；③中间有 LB/网关，它对上游的超时或重试策略与客户端不一致。定位手段：抓包看连接是否复用、对比网关日志的 request id。
</details>

## 15.10 自测检查表

- 我能说出 httpx.Timeout 四参数各自的保护对象，并写出显式齐全的正确构造。
- 我能解释共享 Client 与随手 new Client 的性能差异来源（keep-alive 复用）。
- 我能默写指数退避+完全抖动的核心三行（上限公式、随机取值、sleep）。
- 我能说清重试集合的边界：哪些状态码/异常重试、哪些绝不重试、前提是什么。
- 我能解释 Idempotency-Key 的服务端账本实现（首执记账、重复回放）与键的生成规则。
- 我见到 PoolTimeout 与 ReadTimeout 时能分别给出排查方向。
- 我能对照 Resilience4j 说出 Python 侧等价物与差异。

## 15.11 面试追问[模拟题]

1. **[模拟题]** "重试次数和退避参数怎么定？拍脑袋吗？"——合格回答给框架：总重试预算=调用方可容忍延迟（如接口 SLA 2s → 3 次 × 平均退避 200ms 内）；退避上限受调用频率约束；再按下游 SLA 校准（下游恢复中位数 5s 就别 1s 内重试 4 次）。强调"参数写配置不写死代码"。
2. **[模拟题]** "客户端超时设 3s，服务端 P99 是 2.5s，这配置健康吗？"——不健康：P99 贴着超时线意味着 1% 请求必然超时并触发重试放大流量。原则：客户端超时 > 下游 P99.9 且 < 调用方自己的 SLA 预算；留出重试预算后再算总账。
3. **[模拟题]** "Idempotency-Key 冲突了怎么办（两个不同请求用了同一个键）？"——生产实现要校验：同键但请求体指纹不同 → 返回 409/422 拒绝，防止"键被复用导致回放错误响应"；本书 stub 未实现指纹校验，回答时说明这是生产化的必补项。

### 待核实

- 各模型 API 网关对 Retry-After 的具体格式（秒数/HTTP 日期）与 429 语义差异，以所用厂商文档为准。
- httpx 连接池在多进程（uvicorn --workers>1）下是每进程独立池——池参数需按"每进程"视角计算，本书未做压测验证。

---

# 第 16 章 Pydantic v2：校验、配置与 JSON Schema

> **本章目标**：掌握 BaseModel 的字段约束与错误结构；会写 field_validator/model_validator；用 pydantic-settings 管理配置与密钥；会用 model_json_schema 生成结构化输出的契约。
> **前置知识**：ch07（dataclass）、ch11（类型注解系统）。
> **学完你能做什么**：把"外部输入不可信"落到代码层；给 FastAPI 提供请求/响应模型（ch17 的地基）；给大模型的结构化输出提供 schema（卷二 ch24 的地基）。

## 16.1 真实问题引入

Java 里数据校验是"分层"的事：DTO 用 Jackson 反序列化，再用 Bean Validation 的 `@NotNull`/`@Size` 校验，两套体系靠 `@Valid` 串起来。Python 生态把这两件事合成一件：**类型注解即校验规则**——Pydantic（v2）读你的类型注解，在对象构造那一刻完成"反序列化 + 校验 + 类型转换"，失败立刻抛出带字段定位的 `ValidationError`。

对 AI 应用开发者，Pydantic 的地位更高一层，因为它守着三个"不可信边界"：①用户/上游服务的输入（ch17 的 FastAPI 请求体）；②环境配置与密钥（不能让 `os.environ["XXX"]` 的 KeyError 出现在生产凌晨三点）；③**大模型的输出**——模型返回的 JSON 可能缺字段、值越界、类型乱来，第 24 章的结构化输出就是"把 JSON Schema 交给模型、把模型输出喂回 Pydantic"的闭环。本章用订单与退款两类模型，把三层校验（字段约束/字段规范化/跨字段规则）一次讲透。

## 16.2 一句话解释 + 生活类比 + 类比边界

**一句话解释**：Pydantic v2 用类型注解定义数据契约，在运行时构造对象时强制执行——类型不符自动尝试转换，规则不满足立即抛出带字段定位的 ValidationError，坏数据进不了系统。

**生活类比**：Pydantic 像**海关安检**，不是"礼貌提醒"。行李（外部数据）必须过 X 光（类型注解 + 约束）：超规的液体（amount=-5）当场拦下并出具清单（errors() 里告诉你哪件行李、违反哪条）；而能自动矫正的（quantity 传字符串 "3"）工作人员会顺手替你倒进正确容器——宽松转换。对比 Java 的感觉：Jackson 只是"卸行李"，Bean Validation 才是"安检"，两站合一就是 Pydantic。

**Java 对照**：`BaseModel` 子类 ↔ DTO + Bean Validation 注解合体；`Field(gt=0, le=100_000)` ↔ `@DecimalMin("0") @DecimalMax("100000")`；`field_validator` ↔ `@ConstraintValidator` 自定义校验器；`ValidationError.errors()` ↔ `BindingResult` 的字段错误列表；pydantic-settings ↔ Spring 的 `@ConfigurationProperties`（含 profile 覆盖优先级）。

> 💡 类比边界：**Pydantic ≠ DTO**，这是 FACTS 术语基线里点名的误区。Java DTO 是"数据搬运的形状"，校验是可选附件；Pydantic 模型是"运行时强制的门禁"，校验是构造行为本身——你**造不出**一个校验不过的实例（除非用 `model_construct()` 跳过校验，那是给性能敏感场景的后门）。第二处边界：Pydantic 的宽松转换（str→int）与 Jackson 默认严格相反——团队若要"严格模式"需显式配置，别把"Pydantic 会转"当成 Jackson 也会转。第三处：类型注解本身（ch11）不做任何运行时检查，是 Pydantic 让注解"活了"——别指望普通函数参数上的 `int` 注解自动拦截字符串。

## 16.3 正式原理与准确术语

- **BaseModel**：Pydantic 模型基类。字段=带类型注解的类属性；构造时运行校验（v2 核心是 Rust 实现的 pydantic-core）。
- **Field()**：字段级约束与元数据：`pattern`、`gt/ge/lt/le`、`min_length/max_length`、`default_factory`（可变默认值的正确姿势）、`description`/`examples`（进 JSON Schema）。
- **ValidationError 与 errors()**：构造失败抛出；`exc.errors()` 是错误列表，每项含 `loc`（字段路径）、`type`（机器可读错误码）、`msg`（人话）、`input`（原始输入）。
- **宽松模式（lax mode）**：默认允许无损转换（"3"→3）；严格模式（`StrictInt` 等）拒绝转换。
- **field_validator**：单字段校验/规范化装饰器；返回值成为字段的最终值——既能拦也能**洗**数据。
- **model_validator(mode="after")**：模型级校验器，拿到完整 self，写跨字段业务规则。
- **model_dump / model_dump_json / model_validate_json**：模型与 dict/JSON 字符串的双向转换。
- **BaseSettings（pydantic-settings）**：配置模型——优先级**真实环境变量 > .env 文件 > 默认值**，`env_prefix` 自动加前缀，密钥不进代码。
- **model_json_schema()**：生成标准 JSON Schema——ch24 把它交给模型当"输出格式契约"。

## 16.4 最小完整示例：订单模型的三条校验路径

EX-16-01 | 示例代码/ch16_pydantic/ex_16_01_basics.py（完整可运行）

```python
from pydantic import BaseModel, Field, ValidationError


class Order(BaseModel):
    """订单模型：类型注解即校验规则（Java 对照：Bean Validation 注解 + Jackson 二合一）。"""
    order_id: str = Field(pattern=r"^ORD-\d{5}$", examples=["ORD-12345"])
    amount: float = Field(gt=0, le=100_000)          # 0 < amount ≤ 10万
    quantity: int = Field(ge=1, default=1)            # ≥1，缺省 1
    tags: list[str] = Field(default_factory=list)     # 可变默认值必须用 default_factory
    memo: str | None = None                           # 可选字段（None 是合法值）


def main() -> None:
    order = Order(order_id="ORD-12345", amount=99.5, tags=["vip", "urgent"])
    print(f"[正常] {order.model_dump()}")
    try:
        Order(order_id="ORD-12", amount=-5)  # 两个约束都不满足
    except ValidationError as exc:
        print(f"[失败] 共捕获 {exc.error_count()} 个错误：")
        for err in exc.errors():
            print(f"    loc={err['loc']}  type={err['type']}  msg={err['msg']}")
    order2 = Order(order_id="ORD-00001", amount=10, quantity="3")
    print(f"[宽松转换] quantity 收到字符串 '3'，实际类型 {type(order2.quantity).__name__}，值 {order2.quantity}")
```

真实运行输出：

```text
[正常] {'order_id': 'ORD-12345', 'amount': 99.5, 'quantity': 1, 'tags': ['vip', 'urgent'], 'memo': None}
[正常] quantity 取了默认值 1：1，memo 为 None：True
[失败] 共捕获 2 个错误：
    loc=('order_id',)  type=string_pattern_mismatch  msg=String should match pattern '^ORD-\d{5}$'
    loc=('amount',)  type=greater_than  msg=Input should be greater than 0
[宽松转换] quantity 收到字符串 '3'，实际类型 int，值 3
```

三段输出对应三门课：①`default_factory=list`——可变默认值必须用它（ch06 默认参数陷阱在模型字段上的变体）；②一次构造**收集全部错误**而非见错就停（两个字段的 loc 同场出现）——前端能一次展示所有表单错误，这就是 Bean Validation 的 `BindingResult` 行为；③宽松转换把 `"3"` 变成 int `3`——对 Web 输入友好，对"模型输出的 JSON"要警惕（ch24 讨论何时收紧）。

## 16.5 逐段解释：三层校验、配置管理、JSON Schema

### 16.5.1 字段规范化与跨字段业务规则

EX-16-02 | 示例代码/ch16_pydantic/ex_16_02_validators.py（节选，完整版见该文件）

```python
class RefundRequest(BaseModel):
    """退款申请：演示三种校验层次的分工——字段格式 / 字段规范化 / 跨字段业务规则。"""
    order_id: str
    amount: float
    currency: str = "CNY"
    reason: str

    @field_validator("order_id")
    @classmethod
    def normalize_order_id(cls, v: str) -> str:
        """单字段规范化：去空格、转大写，再检查格式。返回值会成为字段的最终值。"""
        v = v.strip().upper()
        if not v.startswith("ORD-"):
            raise ValueError("order_id 必须以 ORD- 开头")
        return v

    @model_validator(mode="after")
    def check_business_rules(self) -> "RefundRequest":
        """跨字段规则：校验的是整个模型（self），适合'字段之间'的约束。"""
        if self.reason == "质量投诉" and self.amount > 10_000:
            raise ValueError("质量投诉类退款单笔上限 10000，请走人工审核通道")
        return self
```

真实运行输出：

```text
[通过] order_id 被规范化为：ORD-00999（strip+upper 生效）
[拦截] 跨字段规则：loc=()  msg=Value error, 质量投诉类退款单笔上限 10000，请走人工审核通道
[拦截] 字段规则：loc=('order_id',)  type=value_error  msg=Value error, order_id 必须以 ORD- 开头
```

分工原则：**能规范化就别拒绝**（`" ord-00999 "` 洗成 `ORD-00999`，体验与数据质量双赢）；**字段间规则用 model_validator**（单独看每个字段都合法、合在一起才违规——跨字段错误 `loc=()` 是空元组，因为没有单一字段可指认）。注意装饰器顺序：`@field_validator` 下必须叠 `@classmethod`。对照 Java：校验器通常只"判"不"改"，Pydantic 的返回值替换语义让它天然适合"清洗+校验"一体。

### 16.5.2 pydantic-settings：配置的三层优先级

EX-16-03 | 示例代码/ch16_pydantic/ex_16_03_settings.py（节选，完整版见该文件）

```python
class Settings(BaseSettings):
    """应用配置：默认值 < .env < 真实环境变量（后者覆盖前者）。"""
    model_config = SettingsConfigDict(
        env_file=".env",        # 相对当前工作目录；工程里常用 env_file=(".env",)
        env_file_encoding="utf-8",
        env_prefix="ORDER_",    # 环境变量名自动变成 ORDER_APP_ENV 这种形式
        extra="ignore",         # .env 里的无关变量不报错
    )
    app_env: str = "dev"                      # ORDER_APP_ENV
    openai_api_key: str = ""                  # ORDER_OPENAI_API_KEY——只在环境/.env，绝不硬编码

    # 层级 2：真实环境变量优先级最高（Java 对照：System.getenv / Spring 的 profile 配置覆盖）
    os.environ["ORDER_APP_ENV"] = "production"
    s2 = Settings(_env_file=".env")
```

真实运行输出（示例目录自带演示 .env，其中密钥是占位符）：

```text
[.env]      app_env='staging'  redis_url='redis://127.0.0.1:6379/0'  rate_limit=60
[.env]      openai_api_key 是否像占位符：True
[env覆盖]   app_env='production'  rate_limit=120（env > .env > 默认值）
```

与 Spring 的 `application.yml` + profile 覆盖同构：默认值 ≡ 代码默认配置，.env ≡ application-staging.yml，环境变量 ≡ 启动参数/ConfigMap 注入。示例末尾还有一行工程检查——`app_env == "production"` 且密钥为空就 `raise RuntimeError`：**配置也是校验对象**，让"忘配密钥"在启动时爆炸，而不是在第一个用户请求时 500。ch17 收束演练的 Settings 正是这套用法。

### 16.5.3 JSON 往返与 JSON Schema：给模型立契约

EX-16-04 | 示例代码/ch16_pydantic/ex_16_04_json_schema.py（节选，完整版见该文件）

```python
class ExtractionResult(BaseModel):
    """第 21~24 章的'结构化输出'会用同一思路：把 JSON Schema 交给模型，把模型输出喂回 Pydantic。"""
    intent: str = Field(description="用户意图，取值 query_order | complain | other")
    order_id: str | None = Field(default=None, description="订单号，形如 ORD-12345，无法提取时为 null")
    confidence: float = Field(ge=0, le=1, description="模型自评置信度")

    raw = '{"intent": "query_order", "order_id": "ORD-67890", "confidence": 0.7}'
    parsed = ExtractionResult.model_validate_json(raw)  # 校验失败会抛 ValidationError
    schema = ExtractionResult.model_json_schema()
```

真实运行输出（JSON Schema 段）：

```text
[序列化] model_dump_json() → {"intent":"query_order","order_id":"ORD-12345","confidence":0.92}
[反序列化] order_id=ORD-67890，类型 ExtractionResult
[拦截] {"intent": "query_order"}… → loc=('confidence',) type=missing
[拦截] {"intent": "query_order", "order_id": "O… → loc=('confidence',) type=less_than_equal
[JSON Schema]
{
  "properties": {
    "intent": {
      "description": "用户意图，取值 query_order | complain | other",
      "title": "Intent",
      "type": "string"
    },
    "confidence": {
      "maximum": 1,
      "minimum": 0,
      "type": "number"
    }
  },
  "required": ["intent", "confidence"],
  "type": "object"
}
```

（完整输出含全部字段与 description，上面为节选。）这段是卷二 ch24 的预告：`model_json_schema()` 的输出就是交给模型"照此输出 JSON"的契约；模型吐回的字符串经 `model_validate_json()` 验关——缺 `confidence` 报 `missing`、置信度 1.5 报 `less_than_equal`。**模型输出是用户输入的一种**，同样不可信——这是 AI 应用工程师与普通后端最大的思维差异之一。

### 16.5.4 Settings 的落位：从环境变量到服务依赖

配置模型写好了，它在服务里怎么"活"？ch17 收束演练给出标准答案（EX-17-06 节选）：

```python
# 节选自 示例代码/ch17_fastapi_service/app.py（完整版见该文件）
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ORDER_SVC_", extra="ignore")
    api_key: str = "demo-key-123"            # 演示用；生产从密钥管理系统注入
    rate_limit_per_minute: int = 60          # 固定窗口限流阈值
    redis_url: str = ""                      # 为空则使用 fakeredis（离线可运行）

def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()        # 生产：模块级 create_app() 走真实环境
```

三个落位要点：①**Settings 实例在应用工厂里构造一次**，其余代码只接收 Settings（或其中的字段），不让 `os.environ` 散落到业务代码——配置读取点收敛到一处，排查"配置为什么是这个值"时只有一个入口；②**测试注入靠工厂参数**——测试/test_ch17.py 的 `make_client` 传入低阈值 Settings（限流 1000/分钟、审计日志指向临时目录），比在测试里改环境变量更可控（两种手段 ch18 都会用，工厂注入优先）；③密钥字段的默认值只能是演示占位符（本例 `demo-key-123` 有注释声明），真实部署用环境变量/密钥管理服务注入，并复用 EX-16-03 的启动检查模式：生产环境空密钥直接 `RuntimeError` 拒绝启动。

## 16.6 安装 / 文件位置 / 运行命令

- 依赖：pydantic 2.14.1、pydantic-settings 2.16.0（requirements.txt）。
- 文件位置：`示例代码/ch16_pydantic/`（4 个示例 + 演示 .env，其中密钥为占位符非真实密钥）；测试 `测试/test_ch16.py`（6 个）。
- 运行命令（**必须在示例目录内运行**，ex_16_03 依赖目录中的 .env）：

```bash
cd 示例代码/ch16_pydantic
python3 ex_16_01_basics.py     # 01~04 同理
cd /workspace/ai_application_course && python3 -m pytest 测试/test_ch16.py -v
```

## 16.7 常见错误与排查（真实踩坑记录）

**错误一：`ValidationError` 里 `extra inputs are not permitted`，其实是环境变量前缀写错**

测试/test_ch16.py 初版把环境变量前缀写成 `ORDER_SVC_APP_ENV`（作者混淆了 ch17 服务的 `ORDER_SVC_` 前缀与本章示例的 `ORDER_` 前缀），测试读到的是默认值而非注入值，断言失败。修复：对准模型里 `env_prefix` 的真实取值。教训：`extra="ignore"` 会**静默忽略**不认识的环境变量——前缀打错不报错，只是"配置没生效"，这是配置类 bug 最阴的形态；排查手段是打印 `Settings().model_dump()` 对比期望值。

**错误二：`ValidationError` 的 `loc` 是空元组，前端表单对不上号**

model_validator 抛出的跨字段错误 `loc=()`——没有字段可挂。修复思路：仍返回 422 但错误信息用业务语言（"质量投诉类退款单笔上限 10000"），前端按"表单级错误"展示；不要为了凑 loc 硬塞进某个字段。

**错误三：`tags: list[str] = []` 的共享默认值**

直接写 `= []` 时 Pydantic 会拒绝（或复制语义因版本而异，以官方文档为准），正确姿势是 `Field(default_factory=list)`——这与 ch06 的"默认参数陷阱"同根因：默认值在**定义时求值一次**，不是每次调用重建。

**错误四：mypy 报错"Str 下不支持比较"之类，代码明明能跑**

run log 第 5 节的实测：`mypy 示例代码/ch16_pydantic` 报 4 errors，全部是动态行为误报——宽松转换（str→int）、`_env_file` 魔法参数、`except Exception` 上的 `.errors()`。结论不是"关掉 mypy"，而是**per-project 规则 + 人的判断**：这类误报值得单独配置排除，而不是全局禁用严格模式（ch18 展开）。

## 16.8 企业场景中的使用方式

- **接口契约层**：FastAPI 的请求/响应模型全部是 Pydantic（ch17）；对 Java 团队的意义是"Python 侧的 DTO 定义可以在两边共享同一份 JSON Schema 作为契约"——schema 进仓库、评审时对齐。
- **配置中心替代**：小服务用 pydantic-settings + 环境变量足够；K8s 场景 ConfigMap/Secret 注入环境变量，Settings 原样接收——Spring 团队熟悉的"配置外置"模式平移即可。
- **模型输出的门禁**：ch24 的 `with_structured_output` 内部就是"Pydantic 模型 → schema → 模型 → 校验回填"；本章的 validator 思想（洗数据、跨字段规则）直接复用于"模型提取结果的后处理"。

## 16.9 练习

1. **基础**：写出 `Order(order_id="ORD-12", amount=-5)` 会抛出的两个错误的 `type` 值，并解释 `errors()` 为什么是列表而不是单数。
2. **基础**：`memo: str | None = None` 与 `memo: str = ""` 语义差异是什么？各适合什么业务？
3. **代码**：为 `RefundRequest` 增加 `proof_url: HttpUrl | None` 字段（pydantic 的网络类型），并写一个 model_validator：`amount > 10000` 时 `proof_url` 必填，否则 ValidationError 提示"请附凭证链接"。
4. **代码**：写一个 `Settings` 子类：`redis_url: str`、`rate_limit_per_minute: int`（默认 60，env 前缀 `DEMO_`），并写测试证明"环境变量 > 默认值"（用 monkeypatch.setenv）。
5. **调试题**：同事报告"Settings 里的字段全是默认值，环境变量怎么都不生效"，他的模型配置了 `env_prefix="ORDER_"`，启动命令 `ORDER__APP_ENV=prod python3 app.py`（注意双下划线）。说出 bug 与两种修复。

<details>
<summary>点开查看参考答案</summary>

1. `string_pattern_mismatch` 与 `greater_than`。errors() 是列表因为 Pydantic **收集全部错误**后一次性抛出——表单场景需要一次展示所有错误，这是与"见错就停"异常的关键设计差异。
2. `str | None = None`：三态——"没填（None）/填了空串/填了值"，适合"用户可能显式留空"的表单；`str = ""`：二态——缺省与空串合并，适合"空串就是合法业务值"的场景。API 设计里前者更常见，JSON 里 `null` 与缺省字段语义才不混淆。
3. `from pydantic import HttpUrl`；`proof_url: HttpUrl | None = None`；model_validator 里 `if self.amount > 10_000 and self.proof_url is None: raise ValueError("大额退款请附凭证链接")`。HttpUrl 会在校验时检查 URL 格式——免费得到一层输入卫生。
4. 骨架：`class S(BaseSettings): model_config = SettingsConfigDict(env_prefix="DEMO_"); redis_url: str = "redis://localhost:6379/0"; rate_limit_per_minute: int = 60`。测试：`monkeypatch.setenv("DEMO_RATE_LIMIT_PER_MINUTE", "120"); assert S().rate_limit_per_minute == 120`；不设 env 时断言 60——两条对照证明优先级。
5. bug：环境变量名多了一个下划线——pydantic-settings 按 `env_prefix + 字段名` 匹配（`ORDER_APP_ENV`），`ORDER__APP_ENV` 对不上号，又被 `extra="ignore"` 静默吞掉。修复一：改成 `ORDER_APP_ENV=prod`；修复二（更稳）：把 `extra="ignore"` 改为 `extra="forbid"` 让不认识的环境变量启动即报错（工程取舍：forbid 可能被无关变量误伤，按团队约定选）。
</details>

## 16.10 自测检查表

- 我能写出带 pattern/gt/le/default_factory 的字段定义，并说出每个约束对应的错误 type。
- 我能区分 field_validator（单字段、可洗数据）与 model_validator(mode="after")（跨字段）的适用场景。
- 我能说出 pydantic-settings 的三层优先级与 env_prefix 的作用，并知道 extra="ignore" 的静默风险。
- 我能用 model_validate_json / model_dump_json 完成 JSON 往返，并说清"模型输出要过校验"的理由。
- 我能解释"Pydantic ≠ DTO"：运行时强制校验 vs 数据搬运形状。
- 我知道 ValidationError.errors() 的结构（loc/type/msg/input）并能设计前端友好的错误响应。

## 16.11 面试追问[模拟题]

1. **[模拟题]** "Pydantic v2 相比 v1 快在哪？你们为什么直接用 v2？"——合格回答：v2 校验核心重写为 Rust（pydantic-core），API 层面 validator/`model_dump` 等命名统一；v1 的 `.dict()`/`@validator` 已废弃（`@deprecated` 提示迁移）。边界：只谈自己核实过的迁移点，不背具体倍数。
2. **[模拟题]** "大模型结构化输出失败了怎么办（JSON 解析不过）？"——分层答：重试时把 ValidationError 的 msg 喂回模型让它自纠（一次为限）；schema 侧简化（嵌套深度、枚举替代自由文本）；降级路径（兜底"无法解析"分支）。落到代码就是本章 model_validate_json 抛错后的策略，卷二 ch24 完整展开。
3. **[模拟题]** "为什么不直接用 dataclass 加手动 if 校验？"——dataclass 只管形状（ch07），校验逻辑散落各处不可复用；Pydantic 把"契约、错误结构、序列化、Schema 生成"四件事统一，且错误结构机器可读（错误码可直接做监控告警）。边界：纯内部数据结构（不出边界、不序列化）用 dataclass 足够，别过度设计。

### 待核实

- Pydantic 各小版本对可变默认值（`= []`）的报错/复制行为细节有差异，以所用版本官方文档为准。
- `model_json_schema()` 输出的字段顺序与 title 生成规则属实现细节，勿在测试中断言整个 dict 相等（本书测试只断言 required/maximum 等关键键）。

---

# 第 17 章 FastAPI：依赖注入、SSE 与收束演练

> **本章目标**：掌握路径/查询/Body 参数声明与 422 语义；会用 Depends 组合鉴权与限流；会用异常处理器与 contextvars 中间件贯穿 trace_id；会写 SSE 流式与后台任务；完整读懂一个可部署的订单查询服务。
> **前置知识**：ch13（asyncio）、ch16（Pydantic）。
> **学完你能做什么**：从零写出含鉴权/限流/SSE/健康检查的服务；用 uvicorn 真实启动并用 curl 验证；读懂本章收束演练的每一行并复述其架构决策。

## 17.1 真实问题引入

Java 团队新组建 AI 小组，第一周就撞上"框架之争"：Flask 太裸（自己拼校验、文档、并发模型），Django 太重（ORM/Admin 全家桶用不上）。FastAPI 的卖点正对 Java 工程师的胃口——**声明式参数校验**（Pydantic 接管）、**依赖注入**（像 Spring 但更"函数式"）、**自动 OpenAPI 文档**、**原生 async**。

真正值得写的是三个"上手后才会遇到"的问题：①**依赖注入到底和 Spring DI 像不像**——`Depends(get_user)` 看似 `@Autowired`，其实它解决的是"请求级"的横切组合，不是应用级的对象装配；②**SSE 流式**——AI 应用回答要逐字推给前端，Java 的 SseEmitter 经验能平移多少？③**trace_id 全链路**——asyncio 单线程跑几十个请求，ThreadLocal 没了，日志怎么串起来？本章用 5 个渐进示例 + 1 个收束演练（订单查询 + 限流 + SSE + 后台任务）回答这三问，收束演练就是 syllabus 指定的综合项目。

## 17.2 一句话解释 + 生活类比 + 类比边界

**一句话解释**：FastAPI 把"函数签名"当作接口契约——参数注解决定参数从哪来（路径/查询/头/体）与怎么校验，`Depends` 声明"这个函数运行前先运行谁"，返回值经 response_model 过滤后序列化为 JSON。

**生活类比**：FastAPI 的依赖注入像**餐厅的备菜流水线**。端点函数是主厨只管炒菜；`Depends(get_user)` 是"上菜前先有个验菜员"（鉴权），`Depends(rate_limit)` 是验菜员之后还要过称重台（限流，且称重台需要验菜员的结果——依赖可以再依赖）。主厨不必知道备菜细节，菜单上写清楚"需要验菜、需要称重"即可。Spring 的 `@Autowired` 则是**仓库管理员**——装配的是"应用级"的单例/组件，生命周期是整个容器；Depends 装配的是"请求级"的值与检查，每次请求重新执行。

**Java 对照**：`@app.get("/orders/{id}")` ↔ `@GetMapping`；`Path(pattern=...)`/`Query(ge=0)` ↔ `@PathVariable @Validated` + 约束注解；Body 模型 ↔ `@RequestBody @Valid` DTO；`Depends` ↔ "Filter→Interceptor→@PreAuthorize"链，但粒度到**每个参数**、显式写在函数签名里、无反射魔法；`response_model` ↔ 手写 Response DTO（FastAPI 用它做输出过滤）；`BackgroundTasks` ↔ `@Async` 事件监听（进程内、非持久化）；SSE `StreamingResponse` ↔ `SseEmitter`。

> 💡 类比边界：Depends 与 Spring DI 的三处不等价。①**解析时机**：Spring 在容器启动时装配（单例为主），Depends 在**每次请求**时执行依赖函数（默认每请求缓存一次）；②**注入的是计算过程**：Depends 的本质是"先跑这个函数，值给参数"——它天然承载横切逻辑（鉴权/限流/分页解析），而 Spring 横切要靠 AOP/拦截器这套"绕开函数签名"的机制；③**可测性方向不同**：`app.dependency_overrides` 一行替换依赖（本章测试用了它），比 Spring 的 `@MockBean` + 上下文缓存轻得多。另注意 Depends **不是** IoC 容器——它不做生命周期管理，长驻资源（连接池）要自己用 lifespan 管理。

## 17.3 正式原理与准确术语

- **参数声明的来源推断**：路径里出现的参数→路径参数（`Path`）；标量类型→查询参数（`Query`）；Pydantic 模型→请求体（自动 422 校验）；`Header(alias="X-API-Key")`→请求头。
- **422 Unprocessable Entity**：校验失败的统一响应码，body 含 `detail` 数组（loc/type/msg）——FastAPI 把"格式非法"（422）与"业务不存在"（404）天然分开。
- **response_model**：输出过滤——模型没有的字段**不会**出现在响应里（cost_price 泄露防线），还能补文档。
- **Depends / Annotated**：`def ep(x: Annotated[str, Depends(get_x)])` 声明依赖；依赖函数的参数也可以是 Depends——依赖链。同一请求内同一依赖默认只执行一次（缓存）。
- **HTTPException(status_code, detail, headers=)**：抛出即中断请求链，转成 HTTP 响应（headers 用于 Retry-After 等语义头）。
- **exception_handler**：把自定义业务异常映射为响应——业务代码 throw、框架翻译，告别 controller 里的 try/except 糊墙。
- **中间件（@app.middleware("http")）**：请求进/响应出的外层包装；trace_id 用 **contextvars**（ContextVar）保存——它是 asyncio 时代的"ThreadLocal"（每个任务一个上下文，await 穿透）。
- **StreamingResponse + 异步生成器**：SSE 的载体；`media_type="text/event-stream"`，消息格式 `event: 名\ndata: JSON\n\n`；客户端断连靠 `request.is_disconnected()` + 生成器 finally 兜底。
- **BackgroundTasks**：响应返回后由框架执行的任务（进程内、不持久化）——与 Celery/RabbitMQ 的分界线是"丢不丢得起"。
- **lifespan**：应用启动/关闭钩子（异步上下文管理器），管连接池等长驻资源。

## 17.4 最小完整示例：参数声明与输出过滤

EX-17-01 | 示例代码/ch17_fastapi_service/ex_17_01_params_models.py（节选，完整版见该文件）

```python
class OrderCreate(BaseModel):
    """请求体模型：FastAPI 自动用它校验 JSON，失败自动返回 422。"""
    sku: str = Field(min_length=2, max_length=32)
    quantity: int = Field(ge=1, le=999)

class OrderOut(BaseModel):
    """响应模型：response_model 做"输出过滤"，内部字段（如成本价）不会被泄露。"""
    order_id: str
    sku: str
    quantity: int
    unit_price: float

@app.post("/orders", response_model=OrderOut, status_code=201)
def create_order(body: OrderCreate) -> OrderOut:
    _DB[order_id] = {"order_id": order_id, "sku": body.sku, "quantity": body.quantity,
                     "unit_price": 9.9, "cost_price": 6.6}  # cost_price 不该出现在响应里
    return OrderOut(**_DB[order_id])

@app.get("/orders/{order_id}")
def get_order(order_id: str = Path(pattern=r"^ORD-\d{5}$")) -> dict:
    """路径参数：pattern 在进入函数前校验，格式不对直接 422。"""
    return _DB[order_id]  # KeyError 在这里只可能因为"不存在"，与"格式非法"已被 422 分离
```

真实运行输出（TestClient 驱动，本沙箱实测）：

```text
[正常创建] status=201  body={'order_id': 'ORD-10001', 'sku': 'A100', 'quantity': 2, 'unit_price': 9.9}
[查询列表] status=200  total=1
[非法Body] status=422（422=不可处理的实体）  loc=[['body', 'sku'], ['body', 'quantity']]
[非法路径参数] status=422  detail=String should match pattern '^ORD-\d{5}$'
```

四行输出四层语义：①创建成功但响应里**没有 cost_price**——`response_model=OrderOut` 的输出过滤，"内部字段泄露"的机制级防线；②422 的 loc 精确到 `['body', 'sku']`，前端直接用；③路径参数 pattern 在函数体**之前**执行，非法格式进不了业务代码；④函数体内 KeyError 只剩"不存在"一种含义，错误语义被分层了。

## 17.5 逐段解释：依赖链、trace_id、SSE、后台任务

### 17.5.1 Depends 鉴权链：依赖可以再依赖

EX-17-02 | 示例代码/ch17_fastapi_service/ex_17_02_depends_auth.py（节选，完整版见该文件）

```python
def get_user(api_key: str = Header(alias="X-API-Key")) -> dict:
    """一级依赖：从请求头取 Key 查用户。查不到抛 401——异常会中断请求，不会进入业务函数。"""
    user = _FAKE_USERS.get(api_key)
    if user is None:
        raise HTTPException(status_code=401, detail="无效的 API Key")
    return user

def require_admin(user: dict = Depends(get_user)) -> dict:
    """二级依赖：依赖另一个依赖（Java 对照：Filter→Interceptor→@PreAuthorize 链，
    但 Depends 是"函数参数级"的组合，粒度到每个端点，显式声明、无反射魔法）。"""
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="需要 admin 角色")
    return user

@app.delete("/orders/{order_id}")
def delete_order(order_id: str, admin: dict = Depends(require_admin)) -> dict:
    return {"deleted": order_id, "by": admin["name"]}
```

真实运行输出：

```text
[合法Key]  status=200  body={'name': 'alice', 'role': 'admin'}
[缺Key]    status=422  detail=[{'type': 'missing', 'loc': ['header', 'X-API-Key'], 'msg': 'Field required', 'input': None}]
[Key存在但未注册/无效] bob 在册：200
[非法Key]  status=401  detail=无效的 API Key
[权限不足] status=403  detail=需要 admin 角色（403 由二级依赖抛出）
[管理员]   status=200  body={'deleted': 'ORD-00001', 'by': 'alice'}
```

鉴权链的完整语义图谱：**缺头 → 422**（Header 是必填参数，校验层拦截）、**键无效 → 401**（一级依赖的业务拒绝）、**角色不足 → 403**（二级依赖）、**管理员 → 200**。与 Spring 的差异在这里最直观：这条链写在**函数签名**里，评审时代码一眼可见"这个端点需要什么"；Spring 的 Filter 链是"全局隐形"的，要看配置才知道。收束演练会把这条链再加一级：`rate_limit` 依赖 `verify_api_key` 的返回值做计数主体——先鉴权后限流，匿名流量不消耗限流计数。

### 17.5.2 trace_id 中间件 + contextvars：异步时代的 MDC

EX-17-03 | 示例代码/ch17_fastapi_service/ex_17_03_exception_middleware.py（节选，完整版见该文件）

```python
# trace_id 用 contextvars 保存：协程安全（每个请求一个独立上下文），
# Java 对照：ThreadLocal 存 MDC——但 asyncio 下多协程共用一个线程，必须用 contextvars。
trace_id_var: ContextVar[str] = ContextVar("trace_id", default="-")

@app.middleware("http")
async def trace_middleware(request: Request, call_next):
    tid = request.headers.get("X-Trace-Id") or uuid.uuid4().hex[:16]
    token = trace_id_var.set(tid)
    try:
        response = await call_next(request)
        response.headers["X-Trace-Id"] = tid
        # 注意时序：先打访问日志（此刻上下文里还有 trace_id），再在 finally 里 reset
        log.info("%s %s -> %d", request.method, request.url.path, response.status_code)
        return response
    finally:
        trace_id_var.reset(token)

@app.exception_handler(BillingUnavailable)
async def billing_handler(request: Request, exc: BillingUnavailable) -> JSONResponse:
    return JSONResponse(status_code=503,
                        content={"detail": "计费服务暂不可用，请稍后重试", "trace_id": trace_id_var.get()})
```

真实运行输出（本沙箱实测；trace_id 每次运行不同）：

```text
INFO [trace=91c6871a88bc4101] 发起扣款 amount=9.90
INFO [trace=91c6871a88bc4101] GET /pay -> 200
INFO [trace=3aa6d25176cf4a0e] 发起扣款 amount=5000.00
INFO [trace=3aa6d25176cf4a0e] GET /pay -> 503
INFO [trace=my-trace-42] 发起扣款 amount=1.00
INFO [trace=my-trace-42] GET /pay -> 200
[正常]   status=200  body={'ok': True, 'amount': 9.9}  X-Trace-Id=91c6871a…
[业务异常] status=503  body={'detail': '计费服务暂不可用，请稍后重试', 'trace_id': '3aa6d25176cf4a0e'}（trace_id 与日志中的相同）
[透传]   status=200  X-Trace-Id=my-trace-42（服务端沿用调用方的）
```

四件事同场发生：①同一请求的所有日志行共享一个 trace（`91c6871a…` 两行），不同请求互不串号——这就是 contextvars 替代 ThreadLocal 的原因：asyncio 里几十个请求跑在一个线程上，ThreadLocal 会把所有请求混成同一个值；②业务异常由专门 handler 翻译成 503，响应体里**带着 trace_id**——用户报障时拿着这个 id，运维在日志里一查一条线；③网关透传（`my-trace-42`）被沿用——与 Java 的 MDC 传递完全同构；④`reset(token)` 防止上下文泄漏到复用的任务里。

### 17.5.3 SSE 流式：异步生成器逐条推

EX-17-04 | 示例代码/ch17_fastapi_service/ex_17_04_sse_stream.py（节选，完整版见该文件）

```python
async def progress_events(order_id: str, request: Request):
    """异步生成器：像挤牙膏一样每次产出一条 SSE 消息（Java 对照：SseEmitter.send 循环）。"""
    try:
        for pct in (20, 40, 60, 80, 100):
            if await request.is_disconnected():
                break
            payload = json.dumps({"order_id": order_id, "percent": pct}, ensure_ascii=False)
            yield f"event: progress\ndata: {payload}\n\n"
            await asyncio.sleep(0.05)
        else:
            yield "event: done\ndata: {}\n\n"
    finally:
        print("[服务端] SSE 生成器已退出（finally 兜底清理）")

@app.get("/stream/{order_id}")
async def stream(order_id: str, request: Request) -> StreamingResponse:
    return StreamingResponse(
        progress_events(order_id, request),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},  # 禁缓存/禁代理缓冲
    )
```

真实运行输出（本沙箱实测）：

```text
[完整消费] content-type=text/event-stream; charset=utf-8
[服务端] SSE 生成器已退出（finally 兜底清理）
[完整消费] 收到 6 条 data：最后一条={}
[提前断连] 读到第 1 条：{"order_id": "ORD-10001", "percent": 20}
[服务端] SSE 生成器已退出（finally 兜底清理）
[提前断连] 客户端已关闭，未报错（服务端靠 is_disconnected + finally 兜底）
```

对照 Java 的 SseEmitter：Java 要自己管理 emitter 的 onCompletion/onTimeout 回调；FastAPI 把"流"交给你一个**异步生成器**——yield 一条推一条，退出即清理，finally 是唯一要记住的兜底位。两个工程细节：`X-Accel-Buffering: no` 防止 Nginx 把流缓冲成一坨最后才发（线上 SSE"卡住不动"的头号原因）；断连有两条路径——uvicorn 直接取消生成器（走 finally）与 `is_disconnected()` 主动检测，两条都在代码里。

### 17.5.4 BackgroundTasks：响应先行，收尾随后

EX-17-05 | 示例代码/ch17_fastapi_service/ex_17_05_background_tasks.py（节选，完整版见该文件）

```python
def write_audit(order_id: str, action: str) -> None:
    """真实收尾动作：写审计日志（也可能发通知、更新统计）。故意慢 0.3s。"""
    time.sleep(0.3)
    with AUDIT.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"order_id": order_id, "action": action, "ts": time.time()}) + "\n")

@app.post("/orders", status_code=201)
def create_order(order: Order, background: BackgroundTasks) -> dict:
    background.add_task(write_audit, order.order_id, "create")  # 注册任务，不等待
    return {"accepted": True, "order_id": order.order_id}
```

真实运行输出（TestClient 驱动）：

```text
[响应] status=201  body={'accepted': True, 'order_id': 'ORD-77777'}  测得耗时 309ms
[审计] 后台任务确实执行了：{"order_id": "ORD-77777", "action": "create", "ts": 1792375800.5241766}
```

一个诚实的注意点（也是 run log 里的真实踩坑）：**TestClient 会等整个 ASGI 生命周期**——包括后台任务——所以这里测得 309ms（含 0.3s 审计写入），看起来"响应没有先返回"。真实 uvicorn 下时序是"响应立刻发出、任务随后执行"——run log 第 3 节用 curl 实测：POST 返回 201 后约 0.8s，审计文件里出现与响应头一致 trace_id 的记录。这是"测试环境行为 ≠ 生产行为"的典型样本，值得记住。

### 17.5.5 lifespan 与依赖覆盖：服务的入口与测试的后门

两个"服务级"机制在收束演练里各就各位。**lifespan**（启动/关闭钩子）用 ch13 的异步上下文管理器实现（EX-17-06 节选）：

```python
# 节选自 示例代码/ch17_fastapi_service/app.py（完整版见该文件）
@asynccontextmanager
async def lifespan(_app: FastAPI):
    log.info("服务启动：rate_limit=%d/分钟, redis=%s", ...)
    yield          # yield 之前=启动逻辑（进程就绪前执行），之后=关闭逻辑（停止时执行）
    log.info("服务关闭")
```

适合放连接池初始化、后台任务启动、优雅关闭清理——与 Java 的 `@PostConstruct`/`@PreDestroy` 对位，但整个钩子可以是 async 的（异步建连驱动如 asyncpg 直接 await）。注意 ch17.2 类比边界说的：Depends 不是 IoC 容器、不做生命周期管理——**长驻资源就该住在 lifespan 里**，依赖函数只负责"每请求借一份"。

**依赖覆盖（dependency_overrides）**是测试的"后门"：`app.dependency_overrides[get_user] = lambda: {"name": "test", "role": "admin"}` 一行把任意依赖换成测试替身，用完 `del app.dependency_overrides[...]` 即还原。本章收束演练用的是另一种更彻底的路——`create_app(settings)` 工厂注入（连限流阈值和 Redis 后端都能换），测试/test_ch17.py 的 `make_client` 就靠它。两种手段的分工：**换"行为"（某个依赖的返回）用 dependency_overrides，换"配置/资源"（整组设置、后端实现）用工厂注入**。

## 17.6 收束演练：订单查询 + 限流 + SSE + 后台任务（EX-17-06）

EX-17-06 | 示例代码/ch17_fastapi_service/app.py（架构总览，节选自文件头注释与关键段，完整版见该文件）

```python
# 启动：cd 示例代码/ch17_fastapi_service && uvicorn app:app --port 8917
# 验证：curl http://127.0.0.1:8917/healthz
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ORDER_SVC_", extra="ignore")
    api_key: str = "demo-key-123"            # 演示用；生产从密钥管理系统注入
    rate_limit_per_minute: int = 60          # 固定窗口限流阈值
    redis_url: str = ""                      # 为空则使用 fakeredis（离线可运行）

def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    limiter = FixedWindowLimiter(build_redis_client(settings), settings.rate_limit_per_minute)
    # 中间件：trace_id（ch17.5.2）→ 依赖一 verify_api_key → 依赖二 rate_limit（ch19 算法）
    @app.get("/orders/{order_id}", response_model=OrderOut)
    def get_order(order_id: Annotated[str, Path(pattern=r"^ORD-\d{5}$")],
                  _verdict: Annotated[dict, Depends(rate_limit)]) -> OrderOut: ...
    @app.get("/orders/{order_id}/stream")   # SSE（ch17.5.3）
    @app.post("/orders", status_code=201)   # BackgroundTasks 审计（ch17.5.4）
    return app

app = create_app()  # uvicorn app:app 使用这个实例
```

（此为架构摘录；限流器实现、异常处理器、SSE 生成器等完整代码见 app.py，共 234 行，每个部分都在本章前文讲过。）它把 ch13（SSE 生成器、断连取消）、ch16（Settings/Pydantic）、ch19（Redis 固定窗口限流）各章成果组装成一个服务。`create_app` 工厂模式让测试注入低阈值配置（测试/test_ch17.py 的 `make_client`）。

**真实启动证据（本沙箱实测）**——启动 `python3 -m uvicorn app:app --host 127.0.0.1 --port 8933` 后：

```text
=== healthz ===
HTTP/1.1 200 OK
server: uvicorn
x-trace-id: 7b104a69b5494352

{"status":"ok","backend":"fakeredis","rate_limit_per_minute":60}
=== order ===（curl -s -i -H "X-API-Key: demo-key-123" .../orders/ORD-10001）
HTTP/1.1 200 OK
x-trace-id: b2ad233e59214c25

{"order_id":"ORD-10001","user":"alice","amount":129.0,"status":"paid"}
=== SSE ===（curl -s -N .../orders/ORD-10001/stream）
event: progress
data: {"order_id": "ORD-10001", "percent": 20, "stage": "已支付"}
event: progress
data: {"order_id": "ORD-10001", "percent": 40, "stage": "已发货"}
（…60/80/100…）
event: done
data: {}
=== 限流实测（连打 70 发，前序已用部分配额） ===
58 个 200 + 12 个 429
429 响应头：retry-after: 59  x-ratelimit-limit: 60  x-ratelimit-remaining: 0
```

POST + 后台任务的时序（run log 第 3 节记录，端口 8920 复验）：`curl -X POST …/orders` 返回 `201 + {"accepted":true,"order_id":"ORD-30001"}`，约 0.8s 后 `_audit.log` 出现 `{"ts": 1792374512.15, "order_id": "ORD-30001", "trace_id": "601cefcd3e41467f"}`——trace_id 与响应头一致。SSE 断连：`curl -N -m 0.15 …/stream` 提前关闭，应用日志出现"SSE 生成器退出（完成/断连/异常统一清理）"。全部验证后服务进程已停止。

> 📌 生产提示：CI/沙箱里验证长驻服务，要把"启动→验证→停止"放进**同一条命令**——命令结束后台进程会被回收（run log 记录了首轮 curl 全部返回 000 的失败），这是脚本化验证服务的第一坑。

## 17.7 常见错误与排查（真实踩坑记录，本章是全书排错重镇）

**错误一：所有带 Depends 的端点 422 "Field required"，loc 精确指向依赖参数**

```text
{"detail":[{"type":"missing","loc":["query","_verdict"],"msg":"Field required","input":null}]}
```

app.py 开发期的头号真实故障：所有依赖端点 422，框架把依赖参数 `_verdict` 当成了 query 参数。最小复现逐步定位（run log 记录）：与 `Annotated`、下划线参数名都无关——**真凶是 `from __future__ import annotations` + 工厂函数闭包内定义依赖**：future 导入把所有注解字符串化，FastAPI 解析字符串注解时在模块全局找不到闭包里的 `rate_limit` 名字，于是静默降级把它当 query 参数。修复：移除 future 导入（app.py 文件头注释记录了这一点；代码用运行时兼容 3.10+ 的 `X | None` 写法）。这条的价值：**静默降级比报错更可怕**——它给你一个"合理"的 422，把注意力引向参数校验而非注解解析。

**错误二：fastapi 的 `Path` 遮蔽 `pathlib.Path`**

`from fastapi import Path` 后，文件操作处的 `Path("_audit.log")` 变成了 fastapi 的参数声明类，报出难懂的 AttributeError。修复：`import pathlib` 后用模块引用 `pathlib.Path(...)`。命名冲突在"框架提供常用名词"时高发，Java 里 `Path` 也有 `java.nio.file.Path` 与 Spring 的 `@PathVariable PathVariable` 的类似混淆。

**错误三：非法路径参数返回 404 而不是 422**

`get_order` 最初漏配 `Path(pattern=...)`——`ORD-99999999!` 直接进函数查库未命中返回 404。后果是**错误语义被污染**：前端无法区分"格式打错了"与"真没有这个单"。修复：补上 pattern 约束，非法格式 422、不存在 404，测试/test_ch17.py 的 `test_invalid_path_param_returns_422` 固化该语义。

**错误四：中间件日志里 trace 永远是 "-"**

ex_17_03 初版在 `finally` 里先 `reset(token)` 再打访问日志——日志执行时上下文已清空，全部打 `-`。修复：调整时序（先打日志，finally 里 reset）。教训：contextvar 的 reset 有**作用域时序**，Java 的 MDC 也有同款问题（filter 里 finally 先 remove 再 log）。

**错误五：测试断言"响应先于后台任务"在 TestClient 下必然失败**

见 17.5.4——TestClient 等整个 ASGI 生命周期。修复：接受测试环境语义（断言任务确实执行），生产时序用真实 uvicorn + curl 复验（run log 已做）。

**错误六（附）：uvicorn 起了但 curl 全 000**

CI 环境里"后台启动、下一条命令再 curl"失败：命令结束后台进程被回收。修复：单条命令内 `启动 && sleep && curl && kill`。这不是 FastAPI 的 bug，是执行环境的生命周期语义。

## 17.8 企业场景中的使用方式

- **给 Spring 体系当 AI 微服务**：本章服务对外就是一组 REST/SSE 端点，Java 网关用 WebClient/SseEmitter 对接；`X-Trace-Id` 透传协议与 SkyWalking/自建 trace 完全兼容。鉴权建议：网关层做用户身份，Python 服务做 API Key/服务间鉴权（两层不重复）。
- **依赖图即权限文档**：每个端点的 Depends 链就是这个端点的"准入条件清单"，代码评审与安全审计时按签名逐个核对——比翻 Spring Security 配置直观。
- **SSE 的前端契约**：`event:`/`data:` 格式与 Java SseEmitter 产出一致，EventSource 前端代码两端通用；注意反向代理必须禁缓冲（17.5.3 的 X-Accel-Buffering）。
- **限流位置的选择**：本章限流在应用内（Redis 计数）；Java 侧已有网关限流时，应用内限流是"第二道闸"——保护的是下游模型 API 配额，与网关的"保护自己"目标不同，两层都留（ch19/ch59 展开）。

## 17.9 练习

1. **基础**：说出 422/401/403/404/429 在本章服务里各自由谁产生（校验层/一级依赖/二级依赖/业务/限流器）。
2. **基础**：为什么 asyncio 服务里存 trace_id 必须用 contextvars 而不能用 threading.local？一句话说明两者的差异。
3. **代码**：给 app.py 加一个 `GET /orders` 列表端点：`offset: int = Query(0, ge=0)`、`limit: int = Query(10, ge=1, le=100)`，返回 `{"total": n, "items": [...]}`，并继承 rate_limit 依赖。
4. **代码**：为 `BillingUnavailable` 场景写一个 pytest：请求 `/pay?amount=5000`（可仿 ex_17_03 搭最小 app），断言 503 且 `body["trace_id"] == response.headers["X-Trace-Id"]`。
5. **调试题**：同事给端点加了依赖 `def db_conn(): return create_conn()`，声称"Depends 会像 Spring 单例一样只建一次连接"。他错在哪？两种正确做法是什么？

<details>
<summary>点开查看参考答案</summary>

1. 422=参数校验层（Path/Query/Header/Body 约束）；401=一级鉴权依赖；403=二级角色依赖；404=业务异常处理器（OrderNotFound→404）；429=限流依赖，带 Retry-After 头。
2. asyncio 所有协程共享一个线程，threading.local 以线程为键——所有请求读到同一个值；contextvars 以"任务上下文"为键，每个请求（任务链）一份，且 await 调用链自动传播。
3. 骨架：`@app.get("/orders")` / `def list_orders(offset: Annotated[int, Query(ge=0)] = 0, limit: Annotated[int, Query(ge=1, le=100)] = 10, _v: Annotated[dict, Depends(rate_limit)] = None) -> dict:` 返回 `{"total": len(_ORDERS), "items": list(_ORDERS.values())[offset:offset+limit]}`。限流依赖对 GET 同样计数（防爬）。
4. 仿 ex_17_03 建 app（含 trace 中间件与 billing_handler），`client.get("/pay", params={"amount": 5000})`；断言 `r.status_code == 503`、`r.json()["trace_id"] == r.headers["X-Trace-Id"]`。
5. Depends 默认**每请求执行一次**依赖函数（同一请求内缓存），不是应用级单例——他会在每个请求建一个新连接，泄漏到打爆数据库。做法一：依赖内部用模块级/ lifespan 级连接池（借还而非新建）；做法二：连接池放 lifespan 初始化、挂到 app.state，依赖从 `request.app.state.pool` 取。
</details>

## 17.10 自测检查表

- 我能不看资料说出四种参数来源的声明方式与各自的 422 行为。
- 我能写出两级依赖链（鉴权→限流）并解释依赖函数的返回值如何成为下一级的参数。
- 我能解释 contextvars 与 ThreadLocal 的差异，以及 trace_id 从中间件到异常处理器、后台任务全程可用的机制。
- 我能写出 SSE 端点（异步生成器 + media_type + 禁缓冲头 + finally 兜底）并说出断连的两条处理路径。
- 我知道 TestClient 与真实 uvicorn 在后台任务时序上的差异及原因。
- 我能用 uvicorn 真实启动本章服务并用 curl 验证 /healthz、订单查询、SSE、429 四条路径。
- 我能复述 `from __future__ import annotations` 导致 Depends 失效的完整因果链。

## 17.11 面试追问[模拟题]

1. **[模拟题]** "FastAPI 的 Depends 和 Spring 的 @Autowired 是一回事吗？"——不是（见 17.2 类比边界三处不等价）。加分项：说出"Depends 注入的是**请求级计算**，Spring 注入的是**容器级对象**"，并给出 `dependency_overrides` 的测试用法。
2. **[模拟题]** "SSE 和 WebSocket 怎么选？"——单向推送（AI 回答流、进度条）用 SSE：HTTP 协议直通、自动重连、代理友好；双向交互（协作编辑）才要 WebSocket。Java 对照：SseEmitter vs WebSocketHandler，选型逻辑相同。
3. **[模拟题]** "你的限流为什么要放 Redis 而不是进程内存？"——两个 worker 就是两个进程、两份计数，60/分钟会变成 120/分钟；Redis 的 INCR 是原子的、跨进程共享的（ch19）。追问：Redis 挂了限流怎么办？（降级策略：放行但告警，或本地兜底阈值——失效开放 vs 失效关闭的取舍，ch59。）

### 待核实

- uvicorn 多 worker（--workers 2）的进程模型与优雅停机行为未在本沙箱做长时压测，参数存在性已用 `--help` 核实（EX-20-02）；生产参数建议结合 ch20 与官方文档。
- `request.is_disconnected()` 在不同 ASGI 服务器/代理组合下的触发时机有差异（run log 记录本沙箱走的是"uvicorn 取消生成器"路径），生产环境应两条路径都保留。

---

# 第 18 章 测试与质量：pytest、异步测试与 Mock HTTP

> **本章目标**：掌握 fixture/参数化/MonkeyPatch/tmp_path 四件测试武器；会写 pytest-asyncio 异步测试；会用 respx 不联网测 httpx 客户端；会用 TestClient 测 FastAPI（正常/非法输入/限流三类全覆盖）；了解 ruff/mypy 一条龙的落地方式。
> **前置知识**：ch12（logging）、ch17（FastAPI 服务——被测对象）。
> **学完你能做什么**：给 Python 服务写出与 JUnit 5 等价且更省事的测试；把 ch15 的重试逻辑、ch17 的限流/SSE 全部纳入自动测试；看懂本仓库 测试/ 的组织方式并复用。

## 18.1 真实问题引入

Java 的测试栈很重：JUnit 5 + Mockito + AssertJ + WireMock/Testcontainers，注解满天飞，测试启动 Spring 上下文要几秒。转到 Python 你会先不适应再离不开：pytest 没有注解、没有基类、没有 runner 配置——**测试就是普通函数**，断言就是普通 `assert`，setup/teardown 靠"声明一个形参"（fixture 按名注入），Mock 靠一个会自动还原的 monkeypatch。

但 Python 测试有自己的坑，Java 经验反而会误导你：①**异步代码怎么测**——JUnit 的 `CountDownLatch` 样板不需要了，但 fixture 作用域、事件循环生命周期有新规则；②**测试隔离**——本仓库真实发生过：限流计数器是模块级 dict，上一个用例消耗了配额，下一个用例莫名其妙 429（run log 第 4 节第 14 条，修复是用例开头清零计数）——"每个测试方法新实例"的直觉要重建；③**不联网测 HTTP**——respx 之于 httpx，相当于 MockRestServiceServer 之于 RestTemplate，连"失败序列"都能编排。本章全部武器都拿本仓库的真实服务练手。

## 18.2 一句话解释 + 生活类比 + 类比边界

**一句话解释**：pytest 用"函数 + assert + fixture 按名注入"替代 JUnit 的"类 + 注解 + 反射扫描"；monkeypatch 提供自动还原的运行时替换；respx 在传输层拦截 httpx，让 HTTP 客户端测试完全不联网。

**生活类比**：fixture 像**乐高底板**——测试函数声明"我要一块 cart 底板"，pytest 就把拼好的递进来，用完自己拆（yield 后半段做 teardown）；参数化像**流水线上同一张图纸配不同原料**，一次声明跑出 N 个用例，每个有名字（ids）；monkeypatch 像**贴在墙上的临时告示**，测试结束自动揭掉，不会贴到别的房间；respx 像**电话线的仿真插头**——你的客户端照常拨号，电话根本没出大楼，对面是你要什么音就给你什么音的应答机。

**Java 对照**：`@pytest.fixture` ↔ `@BeforeEach`（函数级）；fixture 作用域 `scope="session"` ↔ `@BeforeAll`；`@pytest.mark.parametrize` ↔ `@ParameterizedTest + @CsvSource`；`monkeypatch.setattr/setenv` ↔ Mockito `when(...)` + `System.setProperty`（且自动还原，不用 @DirtiesContext）；`tmp_path` ↔ `@TempDir`；respx ↔ WireMock/MockRestServiceServer；pytest-asyncio ↔ 没有直接对应（JUnit 里异步测试靠 CompletableFuture.join 样板）。

> 💡 类比边界：pytest 与 JUnit 的最大差异在**依赖解析方向**：JUnit 靠注解扫描 + 反射（框架找你的生命周期方法），pytest 靠**函数签名的按名注入**（你的函数声明要什么，框架按名供给）——这让"测试要什么依赖"显式可见，也让 fixture 之间能互相依赖（fixture 参数里声明另一个 fixture）形成依赖图，思路倒与 FastAPI 的 Depends（ch17）同源。边界一：pytest 的 assert 靠重写字节码给出 detailed diff（assertion rewriting），所以 assert 必须写在测试文件顶层语句里，包进 `try` 不影响但包进 lambda 会丢信息。边界二：monkeypatch 替换的是**名字的绑定**（ch04 名字绑定模型的直接应用），替换 `模块.函数` 时所有调用方必须通过"模块.名字"路径访问，直接 `from x import f` 进来的本地名字 patch 不到——这是 Java 工程师最常困惑的一点。

## 18.3 正式原理与准确术语

- **fixture**：`@pytest.fixture` 装饰的工厂函数；测试函数**声明同名形参**即获得其实例；`yield` 前为 setup、后为 teardown；`scope`（function/module/session）控制复用粒度。
- **参数化（parametrize）**：`@pytest.mark.parametrize(("a","b","expected"), [...], ids=[...])` 一份函数体跑多组输入，`ids` 给用例起可读名。
- **MonkeyPatch**：`monkeypatch.setattr("pkg.mod.name", fake)` 替换属性、`setenv/delenv` 改环境变量、`chdir` 切目录——测试结束**自动还原**。
- **tmp_path**：每用例唯一的临时目录（pathlib.Path），测试后自动清理——文件写入类测试不再手搓 setup/清理。
- **pytest-asyncio**：让 `async def test_` 直接可跑；`asyncio_mode=auto`（本仓库 pytest.ini 的配置）下异步测试与异步 fixture 都免装饰器。
- **respx**：`with respx.mock() as router:` 拦截 httpx 全部传输；`router.get(url).respond(json=..., status_code=...)` 固定响应；`.mock(side_effect=[...])` 编排响应/异常序列；`route.call_count` 断言调用次数。
- **TestClient**：FastAPI 自带（基于 httpx）的进程内测试客户端——不发真实网络包，但走完整 ASGI 栈（含中间件/依赖/异常处理，但等整个生命周期，见 17.5.4）。
- **测试隔离**：每个测试拿到全新的 fixture 实例；**模块级可变状态**（计数器、缓存）是隔离的天敌，用例间要显式清零或注入。
- **lint/类型检查**：ruff（极快的 linter，`--fix` 自动修）+ mypy（静态类型检查）——两者都是"人的判断的放大器"，不是真理（17.7 与本章 18.7 的误报案例）。

## 18.4 最小完整示例：fixture + 参数化

EX-18-01 | 示例代码/ch18_testing/ex_18_01_fixture_parametrize.py（节选，完整版见该文件）

```python
# Java 对照：@BeforeEach/@AfterEach + @ParameterizedTest + @CsvSource 的合体，
# 但 fixture 是"按名注入"（测试函数声明形参即获得实例），不靠注解扫描。

@pytest.fixture
def cart() -> Cart:
    """setup：每个测试拿到一个新 Cart（函数级作用域，互不污染）。"""
    c = Cart()
    c.add("SKU-A", 1)
    print("\n  [setup] 已建购物车并放入 1 件 SKU-A")
    yield c  # yield 之前是 setup，之后是 teardown（对照 @AfterEach）
    print("  [teardown] 清理完成")

@pytest.mark.parametrize(
    ("sku", "qty", "expected_total"),
    [("SKU-B", 1, 2), ("SKU-B", 3, 4), ("SKU-C", 10, 11)],
    ids=["加1件", "加3件", "加10件"],
)
def test_add_items(cart: Cart, sku: str, qty: int, expected_total: int) -> None:
    cart.add(sku, qty)
    assert cart.total_qty() == expected_total

@pytest.mark.parametrize("bad_qty", [0, -1], ids=["零件", "负数"])
def test_add_invalid_qty(cart: Cart, bad_qty: int) -> None:
    with pytest.raises(ValueError, match="数量必须为正"):
        cart.add("SKU-B", bad_qty)
```

真实运行输出（`python3 -m pytest 示例代码/ch18_testing/ex_18_01_fixture_parametrize.py -v -s`）：

```text
collected 5 items

示例代码/ch18_testing/ex_18_01_fixture_parametrize.py 
  [setup] 已建购物车并放入 1 件 SKU-A
.  [teardown] 清理完成

  [setup] 已建购物车并放入 1 件 SKU-A
.  [teardown] 清理完成
（……共 5 组 setup/teardown……）

============================== 5 passed in 0.02s ===============================
```

输出证明了三件事：每个用例**各跑一遍 setup/teardown**（5 组，函数级作用域互不污染）；异常用例用 `pytest.raises(ValueError, match=...)` 断言"抛对类型且消息匹配"（比 assertThrows 更省样板）；5 passed 0.02s——没有 Spring 上下文启动，快到可以随时全量跑。

## 18.5 逐段解释：MonkeyPatch/tmp_path、异步测试、respx

### 18.5.1 环境变量替换与临时目录

EX-18-02 | 示例代码/ch18_testing/ex_18_02_monkeypatch_tmp_path.py（节选，完整版见该文件）

```python
def classify_by_env(score: int) -> str:
    """被测函数：依赖一个环境变量阈值（外部依赖，测试时需要隔离）。"""
    threshold = int(os.environ.get("VIP_THRESHOLD", "100"))
    return "vip" if score >= threshold else "normal"

def test_vip_threshold_overridden(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIP_THRESHOLD", "200")  # 改环境变量，结束自动还原
    assert classify_by_env(150) == "normal"  # 默认实现下是 vip，阈值改高后变 normal
    assert classify_by_env(250) == "vip"

def test_report_written_into_tmp_path(tmp_path) -> None:
    result = send_report(tmp_path)  # tmp_path 每个测试唯一，测试后自动清理
    assert result.endswith("report.txt")
    assert (tmp_path / "report.txt").read_text(encoding="utf-8") == "ok"
```

真实运行输出：`4 passed in 0.03s`（`python3 -m pytest 示例代码/ch18_testing/ex_18_02_monkeypatch_tmp_path.py -v`，本沙箱实测）。两个"自动"值得品味：setenv 的环境变量在用例结束自动还原——不会泄漏给并行/后续用例（对照 Java：`System.setProperty` 后忘记清理是最经典的测试串扰源）；tmp_path 每用例唯一目录自动清理——写文件的测试从此不碰真实工作目录。同文件的 `test_with_fake_impl` 还演示了 `monkeypatch.setattr(f"{__name__}.classify_by_env", fake)`——按"模块限定名"替换函数实现，fake 里还能记录调用（`calls == [1]`），这就是 Mockito 的 `verify` 语义。

### 18.5.2 异步测试：pytest-asyncio

EX-18-03 | 示例代码/ch18_testing/ex_18_03_async_tests.py（节选，完整版见该文件）

```python
# 根目录 pytest.ini 已配置 asyncio_mode=auto：async 测试无需装饰器。
async def test_fetch_batch_concurrent() -> None:
    started = asyncio.get_running_loop().time()
    results = await fetch_batch([1, 2, 3])
    elapsed = asyncio.get_running_loop().time() - started
    assert results == ["id-1", "id-2", "id-3"]  # gather 保序
    assert elapsed < 0.15  # 并发执行：3×0.05s 的任务总耗时 ≈ 0.05s

async def test_timeout_wraps_slow_task() -> None:
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(slow_but_cancelable(1.0), timeout=0.05)

@pytest.fixture
async def event_loop_probe() -> list[str]:
    await asyncio.sleep(0.01)
    yield ["from-async-fixture"]
```

真实运行输出：`3 passed in 0.13s`（本沙箱实测，`asyncio: mode=Mode.AUTO` 生效）。三个要点：①`async def test_` 直接写 await，没有 JUnit 里"等 Future 完成"的样板；②**时间断言是并发正确性的证据**——若 gather 被误写成顺序 for-await，3×0.05=0.15s+ 必挂；③异步 fixture 同样支持 yield。对照：JUnit 5 测异步要么阻塞 join 丢并发验证能力，要么引入 Awaitility——pytest 天生在同一线程里等，超时/并发断言都是一等公民。

### 18.5.3 respx：不联网测 HTTP 客户端（含失败序列）

EX-18-04 | 示例代码/ch18_testing/ex_18_04_respx_mock.py（完整可运行）

```python
def fetch_json(client: httpx.Client, url: str) -> dict:
    resp = client.get(url)
    resp.raise_for_status()
    return resp.json()

def main() -> None:
    with respx.mock(assert_all_called=False) as router:  # 拦截 httpx 的全部传输
        route = router.get("https://api.example.com/user/1").respond(
            json={"id": 1, "name": "alice"}, status_code=200)
        # 2) 失败序列：第一次 503，第二次 200——重试逻辑测试的标配
        router.get("https://api.example.com/flaky").mock(
            side_effect=[httpx.Response(503), httpx.Response(200, json={"ok": True})])
        # 3) 抛异常模拟网络层故障
        router.get("https://api.example.com/timeout").mock(
            side_effect=httpx.ConnectTimeout("connection timed out"))
        print(f"[断言] /user/1 被调用 {route.call_count} 次")
```

真实运行输出（本沙箱实测）：

```text
[固定响应] {'id': 1, 'name': 'alice'}
[失败序列] 第 1 次：503 → raise_for_status 抛出（真实网络里这就是重试触发点）
[失败序列] 第 2 次：{'ok': True}
[网络故障] 捕获 ConnectTimeout（不联网也能测超时处理）
[断言] /user/1 被调用 1 次，最后一次请求头 host=api.example.com
[验证] respx 上下文退出后自动停止拦截
```

三种编排覆盖了 HTTP 客户端测试的全部需求：固定响应（正常路径）、**失败序列**（503→200，正好测 ch15 的重试——`side_effect` 列表按次弹出）、抛异常（`ConnectTimeout`，测传输层错误处理）。`route.call_count` 与请求头断言对应 Mockito 的 verify；测试/test_ch18.py 用同款手法测异步重试。对照 Java：WireMock 的"场景状态机"，但零网络零端口——拦截发生在 httpx 传输层。

### 18.5.4 TestClient 测 FastAPI + ruff/mypy 一条龙

测试/test_ch18.py（本仓库测试，节选）覆盖了被测 FastAPI 服务的四类路径：

```python
def test_normal_request():          # 正常：200 + echo
def test_empty_input_422():         # 空输入：detail[0]["type"] == "missing"
def test_invalid_param_422():       # 非法：string_too_short / string_too_long
def test_rate_limit_triggered():    # 限流：[200,200,200,429]，第 4 次 429
```

注意 `test_invalid_param_422` 第一行的 `_hit_counter.clear()`——这是 run log 记录的真实修复：限流计数器（模块级 dict）跨用例累计，非法参数用例先消耗完配额导致断言 429 失败。**测试隔离问题的标准症状是"单独跑绿、全量跑红"**，遇到先查模块级可变状态。

ch18 的 ○选修"lint/format/mypy 一条龙"在本沙箱实测（run log 第 5 节）：`ruff check 示例代码/ch15_http_client 示例代码/ch17_fastapi_service` 首跑 10 errors（导入排序等 7 项自动修复 + 3 项 B008——"Depends 出现在参数默认值"，这正是 FastAPI 官方文档的标准写法）；`ruff check --fix` 后 7 fixed、3 remaining，剩余项改用 `Annotated` 风格可消除；`mypy 示例代码/ch16_pydantic 示例代码/ch19_data_cache` 报 4 errors 全为动态行为误报（Pydantic 宽松转换、`_env_file` 魔法参数等）。结论：**lint/类型检查是放大人的判断的工具，误报要逐条甄别而不是全局关闭**——B008 是"工具不懂框架惯例"的样本，mypy 的 4 报是"静态检查不懂运行时魔法"的样本。

## 18.6 安装 / 文件位置 / 运行命令

- 依赖：pytest 9.1.1、pytest-asyncio 1.4.0、respx 0.23.1（requirements.txt）；ruff 0.16.0 / mypy 1.19.1 在沙箱环境中可用（○选修，非锁定依赖）。
- 文件位置：`示例代码/ch18_testing/`（4 个示例）；本仓库测试 `测试/test_ch13~19.py`。
- 运行命令：

```bash
python3 -m pytest 示例代码/ch18_testing/ex_18_01_fixture_parametrize.py -v   # 01~03 同理
python3 示例代码/ch18_testing/ex_18_04_respx_mock.py
python3 -m pytest 测试/test_ch13.py 测试/test_ch14.py 测试/test_ch15.py \
  测试/test_ch16.py 测试/test_ch17.py 测试/test_ch18.py 测试/test_ch19.py -v
# 期望摘要行：40 passed（run log 记录 12.90s；本沙箱复跑同绿）
```

## 18.7 常见错误与排查（真实踩坑记录）

**错误一：限流用例"单独跑绿、全量跑红"（429 提前出现）**

测试/test_ch18.py 的非法参数用例在全量运行时拿到 429 而非预期 422——限流计数器是模块级 dict，前序用例已消耗配额（run log 第 4 节第 14 条真实记录）。修复：用例开头 `_hit_counter.clear()`。诊断口诀：**"单独绿、一起红" = 隐藏的共享状态**；Java 里同款问题是静态字段/单例缓存，Python 里还要加一个"模块本身就是单例"。

**错误二：monkeypatch 替换后"没生效"**

`from mymod import fetch` 后 `monkeypatch.setattr("mymod.fetch", fake)`，但测试里调的是本地名字 `fetch`——它还绑着旧函数（ch04 名字绑定）。修复：调用方统一走 `mymod.fetch(...)`，或 patch 后重新 import；更稳的写法是把被替换物作为参数（依赖注入）传入被测函数——与 ch17 的 Depends 同一思想。

**错误三：异步测试被跳过（`async def functions are not natively supported`）**

环境缺 pytest-asyncio 或 asyncio_mode 未配置时报 collected 但 skip/error。修复：确认 pytest.ini 含 `asyncio_mode = auto`（本仓库配置）或给测试加 `@pytest.mark.asyncio` 装饰器；注意 pytest-asyncio 1.x 的 fixture 事件循环作用域配置项与旧版不同，以所用版本文档为准。

**错误四：ruff 的 B008 大量误报（Depends 写在参数默认值里）**

`ruff check` 把 FastAPI 官方写法 `def ep(x=Depends(...))` 标为 B008（函数调用不应作默认值）。处理：迁移到 `Annotated[str, Depends(...)]` 风格（顺带获得更清晰的注解），或在 ruff 配置中对 B008 做 per-project 豁免——两条路都比"关掉 ruff"正确。run log 记录了 `ruff check --fix` 修 7 项、留 3 项 B008 的完整过程。

**错误五：TestClient 下后台任务"抢先"执行（时序断言失败）**

见 17.5.4/17.7 错误五：TestClient 等整个 ASGI 生命周期。这不是测试 bug 而是环境语义差异——测试中断言"任务确实执行"，生产时序用真实服务复验。

**错误六：重试测试的"次数"数错（off-by-one）**

测试/test_ch15.py 初版断言退避次数时，把"fail=3、max_attempts=5"的场景算成了 4 次退避——实际是 **3 次**：第 1~3 次请求各失败一次、各退避一次，第 4 次成功、不再退避（run log 第 4 节第 12 条真实记录）。修复后的断言是 `len(seen) == 3` 加退避上限序列 `[0.1, 0.2, 0.4]`（第 3 次已到 max_delay=0.4 封顶），两条断言互相校验。元教训：**计数型断言要先把状态机画清楚**（每次请求→成功/失败→是否退避→是否封顶），凭感觉数次数必错；测试里的循环边界与生产循环的边界是同一份逻辑，数错说明你对被测行为的模型就有偏差——断言失败反而是测试在救你。

## 18.8 企业场景中的使用方式

- **CI 流水线的 Python 侧**：`ruff check --fix && mypy && pytest` 三连（与 Java 的 checkstyle/spotbugs/test 对位）；40 个测试 13 秒内跑完，AI 服务的回归成本远低于 Java 栈的上下文启动开销——**敢频繁全量跑**本身就是质量优势。
- **测试金字塔在 AI 服务里的落点**：单元层（fixture/monkeypatch，测校验与算法）→ 客户端层（respx 编排失败序列，测重试/超时）→ 服务层（TestClient 走完整 ASGI 栈，测鉴权/限流/SSE 契约）——本仓库 测试/ 就是这个分层。
- **与 Java 团队共享测试思维**：respx 的失败序列编排 ↔ WireMock 场景；`dependency_overrides` ↔ `@MockBean`；monkeypatch 自动还原 ↔ Mockito 的 scoped mock。术语可翻译，评审标准一致：正常/边界/非法输入三类必须齐（STYLE_GUIDE 验证义务）。

## 18.9 练习

1. **基础**：fixture 的 `scope="session"` 与默认函数级有何差异？什么样的 fixture **不该**用 session 作用域？
2. **基础**：`pytest.raises(ValueError, match="数量")` 中 match 参数用什么匹配？断言"抛了异常"和"抛对了异常"差在哪？
3. **代码**：给 EX-15-02 的 `request_with_retry` 写测试（参照 测试/test_ch15.py 的 `stub` fixture）：断言"两次 503 后成功"、断言 `max_attempts=3` 时 99 连败返回最后一次 503 而非抛异常。
4. **代码**：用 respx 写异步测试：路由 `side_effect=[httpx.ConnectError("boom"), httpx.Response(200)]`，被测函数"传输错误重试一次"，断言最终 200 且 `call_count == 2`。
5. **调试题**：同事的测试套件加了两个新用例后，原有一个用例开始随机失败，报错与被改的模块无关。给出排查三板斧。

<details>
<summary>点开查看参考答案</summary>

1. session 作用域整个会话只创建一次、所有用例共享同一实例。**有状态**的 fixture 不该 session 化（计数器、累积缓存），否则用例间互相污染——本仓库限流计数器事故就是"共享可变状态"的反面教材；session 适合只读资源（配置对象、共享连接池的**只读借用**）。
2. match 用 `re.search` 正则匹配异常消息的字符串表示。"抛了异常"用 `pytest.raises(ValueError)` 不加 match；"抛对了异常"再限定消息——防止"恰好有别的 ValueError 路径"让测试假绿（异常类型宽 + 消息窄是惯用组合）。
3. 骨架：fixture 起本地 stub 服务器（`make_server()` + daemon 线程 + `/reset`）；`resp = request_with_retry(stub, "GET", "/flaky", params={"fail": 2, "key": "t"}, base_delay=0.01)` 断言 `resp.status_code == 200 and resp.json()["attempt"] == 3`；`request_with_retry(stub, "GET", "/flaky", params={"fail": 99, "key": "t2"}, max_attempts=3, base_delay=0.01)` 断言 `resp.status_code == 503`（重试耗尽返回最后响应，不抛异常——本封装的既定语义）。
4. `@respx.mock` 装饰异步测试；`route = respx.get("https://api.example.com/x").mock(side_effect=[httpx.ConnectError("boom"), httpx.Response(200)])`；`r = await get_with_retry_once(url)`；`assert r.status_code == 200 and route.call_count == 2`。注意 `httpx.ConnectError` 是 `TransportError` 子类，落在 ch15 封装的重试集合里。
5. 三板斧：①`pytest -p no:randomly`（若装了随机排序插件）或固定顺序复跑，确认"顺序依赖"；②`pytest --lf` 与单独运行可疑用例对照，定位"单独绿一起红"；③审查新用例引入的**共享状态**（模块级变量、环境变量、工作目录文件、monkeypatch 是否成对还原）——上一章 ch18.5.1 说的 monkeypatch 自动还原只在"用了 fixture 参数"时保证。
</details>

## 18.10 自测检查表

- 我能用 fixture + 参数化写出含 setup/teardown 与多组输入的测试，并说出它与 JUnit 注解体系的对应关系。
- 我能用 monkeypatch.setenv/setattr 隔离外部依赖，并解释"为什么它会自动还原"与"替换名字而非对象"的语义。
- 我能写 `async def test_` 并用时间断言证明并发正确性（pytest-asyncio auto 模式）。
- 我能用 respx 编排固定响应/失败序列/异常，并断言调用次数——不联网测完 HTTP 客户端逻辑。
- 我能用 TestClient 覆盖 FastAPI 的正常/非法输入/限流三类路径，并知道 422 的 type 字段怎么断言。
- 我能诊断"单独跑绿、全量跑红"并说出第一嫌疑人（模块级可变状态）。
- 我知道 ruff B008 与 mypy 动态误报该如何正确处置（迁移写法/定向豁免/人工甄别，而非全局关闭）。

## 18.11 面试追问[模拟题]

1. **[模拟题]** "pytest 的 fixture 和 Spring 的 @Autowired 有什么相通之处？"——都是**按声明供给依赖**、都支持作用域、都构成依赖图；差异在供给时机（测试会话 vs 容器生命周期）与解析方式（按参数名 vs 按类型）。加分：举 yield fixture 对应 @AfterEach 的 teardown 语义。
2. **[模拟题]** "怎么测一个'调用大模型 API 的函数'但不联网、不花钱？"——分层：客户端逻辑用 respx 拦 httpx（编排 200/429/超时序列）；业务决策用 monkeypatch 替换"调模型"的函数为 fake（返回固定结果并记录调用）；端到端留冒烟测试真调一次（标 slow/marker，每日跑）。Ch24 的 llm_client Mock/Real 双模式就是工程化答案。
3. **[模拟题]** "为什么你们的测试要求'正常/边界/非法输入'三类？"——对应本书风格指南验证义务的三类风险：主路径回归、边界值精度、恶意/误用输入。落到本章：422 的 type 断言（missing/string_too_short）就是"非法输入类"的可执行化——测的是错误语义而不只是错误码。

### 待核实

- pytest-asyncio 1.4.0 的 loop scope 配置项（`asyncio_default_fixture_loop_scope`）在新旧版本间迁移语义变化较大，升级时以官方迁移指南为准（本仓库 pytest.ini 未显式配置该项）。
- ruff/mypy 非本书锁定依赖（沙箱环境版本 0.16.0 / 1.19.1），规则编号与默认集随版本变化，以官方文档为准。

---

# 第 19 章 数据与缓存：SQL 注入防线、Redis 缓存与限流

> **本章目标**：用真实 payload 理解 SQL 注入与参数化查询的因果；建立"只读账户"防线思想；实现 cache-aside 缓存（fakeredis/真实 Redis 双后端）；实现 Redis 固定窗口限流并接入 ch17 服务。
> **前置知识**：ch16（Settings）、ch17（Depends——限流的挂载点）。
> **学完你能做什么**：评审一段 SQL 拼接代码并指出注入路径；为订单查询加"命中缓存"层并解释 TTL 取舍；解释 ch17 服务 429 背后的算法与多实例语义。

## 19.1 真实问题引入

AI 应用让"程序执行 SQL"多了一个新变数：**LLM 生成的 SQL**（text-to-SQL 场景）本质是"用自然语言拼 SQL"的升级版——传统注入是攻击者输入拼进 SQL，text-to-SQL 是模型输出本身就是 SQL。防线思想完全一致，本章先讲透最基础的版本。

某电商平台（合成案例）的客服系统出过一次未遂事故：查询接口 `f"SELECT ... WHERE name = '{user_input}' AND password = '...'"`。安全扫描器用最经典的 payload `' OR '1'='1` 测试——**居然没打穿**（返回 0 行）；换 payload `' OR '1'='1' --` 一次击穿，全表泄露。为什么第一个 payload 失败？这是本章最有意思的教学点（19.5.1：AND 优先级）。同一家公司后来给订单查询上缓存与限流，又发现"多实例部署后限流阈值翻倍"——计数器最初放在进程内存。三个问题共享同一个母题：**边界处的数据与代码/状态的隔离**。

## 19.2 一句话解释 + 生活类比 + 类比边界

**一句话解释**：参数化查询让用户输入永远只是"数据"不进入 SQL 语法解析；缓存用 Redis 把昂贵调用的结果暂存（cache-aside + TTL）；限流用 Redis 的原子 INCR 把"每单位时间允许的次数"变成跨实例共享的计数器。

**生活类比**：参数化像**银行柜台的双语翻译**——"名字"写在纸条上递进去，柜员按单查人；纸条上就算写着"抢银行"，也只会被当成"名字叫'抢银行'"查一遍，绝不会被当成指令执行。拼接 SQL 则是把你的纸条**直接钉进柜员的操作手册**——每个字都成了指令。缓存像**便利店的常温柜**：畅销品提前上架（写回），拿货三秒（命中）；过期就现去仓库调货（回源），保质期（TTL）一到必须重新进货。限流像**景区闸机计数器**：每分钟放 60 人，计数牌（Redis key）对所有入口（多实例）是同一块——这就是计数必须放 Redis 的原因。

**Java 对照**：`conn.execute(sql, params)` ↔ `PreparedStatement`（占位符预编译，防注入原理一字不差）；PRAGMA query_only ↔ 只读账户 `GRANT SELECT`；Redis INCR 限流 ↔ Resilience4j RateLimiter——关键差异：Resilience4j 默认**单机内存**计数，Redis 是**跨实例共享**；fakeredis ↔ 嵌入式 H2（接口一致、行为可替换）。

> 💡 类比边界：①**"只读账户"防的是危害半径，不是注入本身**——注入成功了只是只能 SELECT 不能 DELETE；防注入的第一道墙永远是参数化，只读账户是纵深防御的第二道墙（ch58）。②**固定窗口限流有边界毛刺**：窗口切换瞬间可能放过"上一窗口末尾 + 下一窗口开头"的 2 倍突发（59 秒处 60 发 + 61 秒处 60 发）；滑窗/令牌桶更平滑，但固定窗口实现最简单、够用于大多数 API 保护——本书如实讲缺陷而不掩盖。

## 19.3 正式原理与准确术语

- **SQL 注入（SQL injection）**：用户输入被拼进 SQL 文本，改变语句语法树。防御：参数化查询、最小权限账户、ORM 参数化 API。
- **参数化查询（parameterized query）**：`conn.execute("... WHERE name = ? AND password = ?", (a, b))`——SQL 先预编译定型，参数值**永不参与语法解析**；sqlite3 的 `?` ↔ JDBC 的 `?`。
- **executescript 的多语句风险**：`execute()` 单语句天然安全；`executescript()` 接受任意多条 SQL——拼接输入可"夹带"第二条语句（本章实测复现）。
- **只读防线**：SQLite 用 `PRAGMA query_only = ON` 模拟；PostgreSQL/MySQL 的等价物是只读账户 + GRANT SELECT（思想可平移，语法以官方文档为准）。
- **cache-aside（旁路缓存）**：读请求先查缓存 → 未命中回源 → 写回缓存带 TTL；命中率是缓存有效性的唯一裁判。
- **TTL（time to live）**：键的存活秒数；`set(key, value, ex=ttl)` ↔ Redis `SET key value EX ttl`。
- **固定窗口限流（fixed window）**：把时间轴切成 window 秒的窗口，`window_id = int(time.time()) // window` 作 key 的一部分；`INCR` 原子自增 + 首次 `EXPIRE(window+1)` 自动清零。
- **fakeredis**：Redis 接口的内存实现（测试/离线用）；`decode_responses=True` 让返回值是 str 而非 bytes。

## 19.4 最小完整示例：看见注入，再看防线

EX-19-01 | 示例代码/ch19_data_cache/ex_19_01_sql_injection.py（节选，完整版见该文件）

```python
    # 模拟攻击者输入：注释掉密码条件 + 永真化（经典 payload，-- 是 SQL 行注释）
    evil_input = "' OR '1'='1' --"

    # ── 写法一（错误示范）：f-string 拼接——输入被当成了 SQL 代码 ──
    sql_vuln = f"SELECT id, name FROM users WHERE name = '{evil_input}' AND password = 'whatever'"
    rows_vuln = conn.execute(sql_vuln).fetchall()

    # 教学插叙：不带注释的永真 payload（' OR '1'='1）其实防不住这一句——
    # AND 优先级高于 OR，密码条件仍然生效，返回 0 行。

    # ── 写法二（正确）：参数化查询——输入永远是"数据"，不进入 SQL 解析器 ──
    sql_safe = "SELECT id, name FROM users WHERE name = ? AND password = ?"
    rows_safe = conn.execute(sql_safe, (evil_input, "whatever")).fetchall()
```

真实运行输出（本沙箱实测）：

```text
[拼接查询] 生成的 SQL：SELECT id, name FROM users WHERE name = '' OR '1'='1' --' AND password = 'whatever'
[拼接查询] 返回 2 行 → 密码校验被 -- 注释，全表用户泄露！
    泄露：id=1 name=alice
    泄露：id=2 name=bob
[教学] 朴素永真 payload 返回 0 行（AND 优先级救了它，但别指望攻击者写错）
[参数化]   同样的恶意输入 → 返回 0 行（数据库只找一个名字恰好为 "' OR '1'='1" 的用户）
[升级危害] executescript 拼接被夹带 DELETE：执行后 log 表剩 0 行（原 1 行被删空）
```

## 19.5 逐段解释：AND 优先级的教学点、只读防线、缓存、限流

### 19.5.1 为什么第一个 payload "防住了"——AND 优先级

输出的第二、三行是本章的招牌教学点。朴素 payload `' OR '1'='1` 拼进模板后语法树是：

```sql
WHERE name = '' OR '1'='1' AND password = 'whatever'
-- SQL 里 AND 优先级高于 OR，实际是：
WHERE name = '' OR ('1'='1' AND password = 'whatever')
```

`'1'='1' AND password='whatever'` 恒为假（密码不对），`name=''` 无人命中——返回 0 行。**它不是防住了，是语法树上恰好没打穿**。而 `' OR '1'='1' --` 用注释吃掉尾巴上的密码条件，`WHERE name = '' OR '1'='1'` 恒真——全表泄露。教训：**payload 必须与目标语句的语法树对齐**，扫描器一次失败不代表安全。参数化之所以彻底：占位符在预编译时定型，`?` 的值无论写成什么——哪怕就是 `' OR '1'='1' --`——都只是字符串比较的一个操作数，语法树纹丝不动（Java PreparedStatement 同理）。"升级危害"段演示 `executescript` 拼接被夹带 `DELETE`——多语句接口的拼接是删库级风险，业务代码永远不该用拼接输入构造 script。

### 19.5.2 只读防线：让"改不了"由数据库保证

EX-19-02 | 示例代码/ch19_data_cache/ex_19_02_readonly_connection.py（节选，完整版见该文件）

```python
    # SQLite 的"只读账户"替代物：连接级开关 query_only（生产等价物是只读账户+白名单）
    conn.execute("PRAGMA query_only = ON")
    try:
        conn.execute("INSERT INTO orders (amount) VALUES (1.0)")
    except sqlite3.OperationalError as exc:
        print(f"[写] 被数据库拒绝：sqlite3.OperationalError: {exc}")
```

真实运行输出：

```text
[开关] query_only = 1
[读] 参数化查询正常：[(1, 99.0)]
[写] 被数据库拒绝：sqlite3.OperationalError: attempt to write a readonly database
[写] DELETE 同样被拒绝：attempt to write a readonly database
[结果] 数据完好：orders 仍有 1 行
```

读正常、写与 DELETE 全部被**数据库本身**拒绝——应用层有 bug 也写不进去。文件头的注释给出了真实数据库的等价物（PostgreSQL `GRANT SELECT`、MySQL 只读账户）。对 AI 应用的特殊意义（文件注释原话）：**LLM 生成的 SQL 也不该用高权限账户执行**——text-to-SQL 的执行账户应当只读 + 表白名单，这是 ch58 纵深防御的一环。

### 19.5.3 cache-aside：先查缓存、未命中回源、写回带 TTL

EX-19-03 | 示例代码/ch19_data_cache/ex_19_03_redis_cache.py（节选，完整版见该文件）

```python
def build_client() -> Any:
    url = os.environ.get("REDIS_URL", "")
    if url:
        import redis  # redis-py（fakeredis 的传递依赖）
        client = redis.Redis.from_url(url, decode_responses=True, socket_connect_timeout=2.0)
        client.ping()
        return client
    return fakeredis.FakeRedis(decode_responses=True)  # 默认离线后端

def get_order_cached(client: Any, order_id: str, ttl: int = 2) -> dict[str, Any]:
    """cache-aside 模式：先查缓存 → 未命中回源 → 写回缓存（带 TTL）。"""
    key = f"order:{order_id}"
    cached = client.get(key)
    if cached is not None:
        _hit += 1
        return {"data": json.loads(cached), "from": "cache"}
    _miss += 1
    data = expensive_query(order_id)               # 模拟昂贵调用：查库/调模型，耗时 100ms
    client.set(key, json.dumps(data), ex=ttl)      # ex=TTL 秒
    return {"data": data, "from": "db"}
```

真实运行输出（本沙箱实测，两种后端行为一致）：

```text
fakeredis 默认：
[后端] fakeredis（未配置 REDIS_URL，离线可运行）
[首次]  db  耗时 105ms（含 100ms 回源）
[第2次] cache  [第3次] cache（同一进程内 ~0ms）
[过期后] db（TTL 到期，重新回源）
[统计] 命中 2 次 / 未命中 2 次——命中率是缓存有效性的唯一裁判

切真实 Redis（REDIS_URL=redis://127.0.0.1:6379/5，Redis 7.0.15）：
[后端] 真实 Redis：redis://127.0.0.1:6379/5
[首次]  db  耗时 101ms（含 100ms 回源）
[第2次] cache  [第3次] cache（同一进程内 ~0ms）
[过期后] db（TTL 到期，重新回源）
[统计] 命中 2 次 / 未命中 2 次——命中率是缓存有效性的唯一裁判
```

（真实 Redis 验证后 `redis-cli -n 5 keys "order:*"` 可见 `order:ORD-10001`，缓存键真实落在了 Redis 里。）要点：①**cache-aside 三步**都在一个函数里，回源与写回之间没有锁——并发未命中时会重复回源（缓存击穿，生产可用 SETNX 或单飞协程优化）；②TTL=2s 是演示值，生产按"数据可接受的陈旧度"定（订单状态 30s~5min 常见）；③fakeredis 与真实 Redis 接口一致——测试跑 fakeredis、生产跑真 Redis，代码零改动，这正是 H2 之于 MySQL 的测试策略。

### 19.5.4 固定窗口限流：INCR + EXPIRE 的原子舞步

EX-19-04 | 示例代码/ch19_data_cache/ex_19_04_rate_limit_fixed_window.py（节选，完整版见该文件）

```python
class FixedWindowLimiter:
    def __init__(self, client: Any, limit: int, window_seconds: int = 1) -> None: ...

    def hit(self, caller: str) -> tuple[bool, int]:
        """返回 (是否放行, 窗口内已计数)。"""
        window_id = int(time.time()) // self.window
        key = f"rl:{caller}:{window_id}"
        count = int(self.client.incr(key))          # 原子自增：多进程/多实例共享同一计数
        if count == 1:
            self.client.expire(key, self.window + 1)  # 首次计数才设过期，窗口结束自动清零
        return count <= self.limit, count
```

真实运行输出：

```text
  第 1 发：放行（窗口计数 1/5）
  第 2 发：放行（窗口计数 2/5）
  第 3 发：放行（窗口计数 3/5）
  第 4 发：放行（窗口计数 4/5）
  第 5 发：放行（窗口计数 5/5）
  第 6 发：拒绝(429)（窗口计数 6/5）
  第 7 发：拒绝(429)（窗口计数 7/5）
  第 8 发：拒绝(429)（窗口计数 8/5）
[窗口内] 放行 5 / 拒绝 3——阈值 5 之外的请求全部 429
…等待窗口翻页（1.1s）…
[新窗口] 第 1 发：放行（计数重新从 1 开始——固定窗口自动复位）
[隔离] bob 的首次请求：放行（计数 1，与 alice 无关）
```

四个设计点：①`window_id` 把"时间"编进 key——窗口翻页自然形成新 key，EXPIRE 负责清理旧 key（`window+1` 秒留余量防边界残留）；②`INCR` 是**原子的**——多实例/多进程打同一个 key 也不会数错，这就是"限流放 Redis"的答案；③`count == 1` 才 EXPIRE——每次都设会把过期时间不断顺延，窗口永不清零（经典 bug）；④key 按 caller 隔离。算法与 ch17 app.py 的 `FixedWindowLimiter` 一致——那边返回 dict（含 retry-after 给 429 响应头），这边返回 tuple（纯算法演示），测试/test_ch19.py 验证了放行序列、窗口翻页与 caller 隔离。对照 Resilience4j RateLimiter：算法一致，差异在**计数共享范围**——Resilience4j 默认单机，Redis 方案天然跨实例。

### 19.5.5 缓存模式速查与缓存键设计

本书实现的是 cache-aside，但工程师要知道全套模式的取舍：

| 模式 | 读路径 | 写路径 | 一致性 | 适用场景 |
|---|---|---|---|---|
| cache-aside（旁路缓存） | 先查缓存，未命中回源并写回 | 应用写 DB 后**删**缓存 | 弱（窗口内陈旧） | 读多写少；本书 EX-19-03 |
| read-through | 缓存层代理回源 | 同上 | 弱 | 有成熟缓存库/中间件时 |
| write-through | 同上 | 同步写缓存+DB | 强 | 写也不少、要求强一致 |
| write-behind | 同上 | 先写缓存、异步刷 DB | 更弱（有丢数风险） | 高写吞吐、可容忍丢失 |

对应 Java：Spring Cache 的 `@Cacheable` 就是 cache-aside 的声明式封装，`@CacheEvict` 对应"写后删缓存"——注解背后跑的还是同一套逻辑，Java 经验在概念层完全平移。

缓存键设计四条军规：①**命名空间分层**（`order:{order_id}`、`rl:{caller}:{window_id}`）——可读、可按前缀清理（`KEYS order:*` 仅调试用，生产用 SCAN 防阻塞）；②**键里不放敏感信息**（手机号、token——键会出现在监控、导出、日志里）；③**带版本号便于整体失效**（`v2:embedding:{doc_id}`——算法升级切版本号，避免新旧混杂）；④**TTL 与业务语义对齐**（订单状态 30s~5min、限流窗口 window+1s、幂等账本 24h+），"所有键默认 5 分钟"式的统一 TTL 是设计偷懒，后患是陈旧度与内存占用两头不可控。

## 19.6 安装 / 文件位置 / 运行命令

- 依赖：fakeredis 2.40.0（默认离线）；真实 Redis 可选（本沙箱 apt 安装 redis-server，实测 7.0.15，`redis-cli ping` → PONG）。
- 文件位置：`示例代码/ch19_data_cache/`（4 个示例）；测试 `测试/test_ch19.py`（4 个）。
- 运行命令：

```bash
python3 示例代码/ch19_data_cache/ex_19_01_sql_injection.py
python3 示例代码/ch19_data_cache/ex_19_02_readonly_connection.py
python3 示例代码/ch19_data_cache/ex_19_03_redis_cache.py                    # fakeredis
REDIS_URL=redis://127.0.0.1:6379/5 python3 示例代码/ch19_data_cache/ex_19_03_redis_cache.py  # 真实 Redis
python3 示例代码/ch19_data_cache/ex_19_04_rate_limit_fixed_window.py
python3 -m pytest 测试/test_ch19.py -v
```

## 19.7 常见错误与排查（真实踩坑记录）

**错误一：扫描器报告"注入失败"就认为代码安全（AND 优先级误判）**

见 19.5.1——朴素 payload 因 AND 优先级返回 0 行，被误判为"已防护"。run log 第 4 节第 10 条记录了这一真实过程：作者复现时也先被朴素 payload 骗过。修复：**代码层立即改参数化**（不看扫描结果），并把"朴素 payload 失败"保留为教学案例。评审口令：看到 f-string/字符串拼接进 SQL，无论有没有 payload 证明可注入，一律按漏洞处理。

**错误二：限流阈值在多实例部署后"翻倍"**

每个实例各数各的（进程内存计数），N 个实例 = N 倍配额。修复：计数放 Redis（INCR 原子跨实例）——ch17 收束演练用 Redis/fakeredis 而非内存字典正是这个原因（EX-20-02 的输出提示也点明了这一点）。这也与 ch20 的 `--workers 2` 直接相关：**同一台机器的两个 worker 也算两个实例**。

**错误三：每次请求都 EXPIRE 导致窗口永不过期**

`incr` 后无条件 `expire(key, window)`——每次请求都重置 TTL，只要流量不断，旧窗口的 key 永不清零（内存泄漏 + 计数混乱）。修复：`if count == 1: expire(...)`（EX-19-04 现在的写法）。诊断特征：Redis 里 `rl:*` 的 key 数量持续增长、TTL 始终等于满窗口值。

**错误四：缓存了"不该缓存"的错误响应**

回源调用抛异常时，若把错误信息也 `set` 进缓存（或回源函数内部吞错返回空对象），后续 TTL 内所有请求都拿到错误快照。修复：**只缓存成功响应**——异常路径不写缓存（EX-19-03 的写法：`expensive_query` 抛错则根本走不到 set）。对模型 API 的缓存还有一层：温度>0 的生成结果每次不同，缓存的是"该输入的代表性输出"，产品上要确认可接受（ch59 语义缓存的边界）。

## 19.8 企业场景中的使用方式

- **Python AI 服务的数据访问边界**：与 Java 服务共享数据库时，Python 侧遵循同一套军规——参数化（PreparedStatement 语义全平台一致）、只读账户（按服务分账户）、无 DDL 权限。text-to-SQL 场景（若做）：模型生成 SQL → 白名单校验（只允许 SELECT + 指定表）→ 只读账户执行 → 结果上限（LIMIT 强制）。
- **缓存与限流的配对**：模型 API 的配额保护是"缓存先行、限流兜底"——命中缓存不消耗配额，未命中请求过限流闸门再出网。ch17 收束演练的依赖链（鉴权→限流）+ 本章缓存，组合起来就是 syllabus 指定的"订单查询 + 风控限流"完整形态。
- **Resilience4j 对照速查**：Redis INCR 固定窗口 ↔ RateLimiter（单机）；`expire` 自动复位 ↔ 周期刷新；key 按 caller 隔离 ↔ `limitForFunction` 按调用方命名；缺口：熔断/降级（ch59 的 CircuitBreaker 对应物）。

## 19.9 练习

1. **基础**：写出参数化查询防注入的机制级解释（预编译/语法树/数据通道），并说明为什么"先把输入里的单引号转义再拼接"不是等价方案。
2. **基础**：固定窗口在窗口边界可能放过 2 倍突发（19.2 类比边界）。算一个具体例子：limit=60/min，窗口从整秒对齐，攻击者如何利用？一句话给出滑窗/令牌桶如何缓解。
3. **代码**：给 `get_order_cached` 加"空值不缓存"与"回源失败重试一次"（复用 ch15 思想），并写两个 pytest 分别验证（用 fakeredis + 一个可控制的回源函数）。
4. **代码**：实现滑动窗口限流器 `SlidingWindowLimiter`：用 Redis ZSET（`zadd`/`zcount`/`zremrangebyscore`），成员=请求唯一 id、score=时间戳，窗口内计数超阈值拒绝。写测试对比它与固定窗口在边界处的行为差异。
5. **调试题**：线上 Redis 缓存命中率从 85% 骤降到 5%，接口变慢但没有报错。给出三个可能原因与各自的验证命令/方法（提示：从 TTL 设置、key 设计、实例变更三个方向想）。

<details>
<summary>点开查看参考答案</summary>

1. 机制：参数化把 SQL 文本与参数值**分通道**传输——连接层先发送预编译语句（语法树定型），参数值通过独立协议通道传入，只参与"比较/赋值"的求值，不进入 SQL 解析器，因此任何输入字符都改变不了语法树。转义再拼接是"黑名单/规则对抗"：引号转义规则随数据库、字符集（如 GBK 宽字节绕过）、上下文（字符串/标识符/LIMIT 子句）变化，总有覆盖不到的路径——正确性靠"机制上不可能"，不靠"规则上没漏"。
2. 例子：窗口 0~60s 与 60~120s；攻击者在 59.9s 打 60 发（上一窗口配额内）+ 61.0s 再打 60 发（新窗口重新计数）——2 秒内 120 发，相当于瞬时 3600/min。缓解：滑动窗口（ZSET 按时间戳精确计数）或令牌桶（按速率匀速补充令牌，瞬时突发受桶容量约束）——两者都把"窗口边界"这个硬切面抹平。
3. 骨架：`def get_order_cached(client, order_id, source, ttl=60):` 内 `data = source(order_id)` 若 `data is None: return None`（不写缓存）；`try: data = source(order_id) except TransientError: data = source(order_id)`（重试一次，仍失败则抛出、不缓存）。测试一：source 返回 None 的 key 二次调用仍回源（source 被调 2 次）；测试二：source 记录调用序列 [fail, ok]，最终返回 ok 且缓存生效（第 3 次调用命中）。
4. 骨架：`key = f"rsw:{caller}"`；`now = time.time()`；`pipeline: zremrangebyscore(key, 0, now-window); zadd(key, {uuid4().hex: now}); zcount(key, now-window, now)`；`allowed = count <= limit; expire(key, window)`。行为差异测试：固定窗口在边界放 2×突发，滑动窗口同一场景第二发被拒（计数包含前窗口末尾请求）。
5. ①TTL 被调小或写缓存的 `ex=` 参数丢失（键永不过期变成立即过期）：`redis-cli --bigkeys`、抽查 `TTL order:ORD-10001`；②key 设计变更导致同一业务键分裂（如 order_id 格式变化、加了时间戳进 key）：`KEYS order:* | head` 看键形态、对比回源日志；③Redis 实例被重启/替换（内存实例无持久化、或连错了库号 db 0 vs db 5）：`redis-cli INFO keyspace` 看各库键数、`INFO stats` 的 keyspace_hits/misses 比值随时间变化。
</details>

## 19.10 自测检查表

- 我能画出朴素 payload 与带注释 payload 拼接后的 SQL 语法树，解释 AND 优先级为什么"救了"坏代码。
- 我能说清参数化查询的机制级防御原理，并反驳"转义就够了"。
- 我能复述只读防线的定位（纵深防御第二道墙）与 SQLite/生产数据库的等价物。
- 我能实现 cache-aside 三步并说出"只缓存成功响应"与"命中率是唯一裁判"两条军规。
- 我能实现固定窗口限流并解释 `count == 1` 才 EXPIRE 的原因与窗口边界毛刺。
- 我能解释限流计数为什么必须跨实例共享（Redis）以及它与 Resilience4j 的差异。
- 我在本沙箱用真实 Redis 7.0.15 跑通过 EX-19-03 并用 redis-cli 看到缓存键（或能复现该验证路径）。

## 19.11 面试追问[模拟题]

1. **[模拟题]** "缓存穿透/击穿/雪崩分别是什么？你的 cache-aside 里各有什么对策？"——穿透（查不存在的 key 每次都回源）：空值短 TTL 缓存或布隆过滤器；击穿（热 key 过期瞬间并发回源）：SETNX 单飞/逻辑过期；雪崩（大量 key 同时过期）：TTL 加随机抖动。本题的三件事本章只覆盖了基础形态，回答时说明"生产实现还会补"。
2. **[模拟题]** "为什么用 INCR+EXPIRE 而不是 GET 后在应用里 +1 再 SET？"——GET-then-SET 非原子：两个实例同时 GET 到 59、各自 SET 60，限流被击穿；INCR 在 Redis 单线程模型下原子执行。追问：INCR 和 EXPIRE 是两条命令，中间崩溃怎么办？（count==1 时才 EXPIRE + 窗口 key 自带时间片，最坏浪费一个窗口的 key；更强方案用 Lua 脚本合并两步。）
3. **[模拟题]** "text-to-SQL 让模型生成 SQL，你的安全设计是什么？"——分层：模型输出先过静态校验（只允许 SELECT、表白名单、强制 LIMIT）→ 只读账户执行 → 结果行数/列数上限 → 审计日志记录完整 SQL 与 trace_id（ch17 的 trace 串联）。明确边界：模型输出等同用户输入，不做"模型说的就信"的假设（衔接 ch28 提示注入与 ch58 纵深防御）。

### 待核实

- 真实 Redis 仅验证 7.0.15 单机 GET/SET/INCR/EXPIRE/TTL/ping 路径（run log 第 6 节）；哨兵/集群/持久化行为未验证，生产部署以对应拓扑的官方文档为准。
- fakeredis 对 Redis 事务/Lua 脚本的支持完整度以其官方文档为准，本书仅使用了字符串计数与 TTL 子集。

---

# 第 20 章 部署基础：Dockerfile、uvicorn 生产参数与健康检查

> **本章目标**：读懂并逐条核对生产级 Dockerfile（多阶段构建/非 root/HEALTHCHECK/层缓存）；掌握 uvicorn 生产参数的真实语义；把健康检查端点纳入部署契约；理解"requirements 锁定"的工程意义。
> **前置知识**：ch17（收束演练服务——本章的部署对象）、ch14（--workers 的进程模型）。
> **学完你能做什么**：为 ch17 服务写出可交给运维的 Dockerfile 并说出每行的理由；给出 uvicorn 生产启动命令并解释每个参数；说清"存活探针 vs 就绪探针"的分工。

## 20.1 真实问题引入

Java 世界里部署被 Spring Boot jar + 内嵌 Tomcat + K8s 探针"惯坏"了——Dockerfile 十行搞定。Python 这边你会遇到一串新问题：**uvicorn 裸跑用什么参数？**（`--workers` 是什么）；**镜像里为什么装了 gcc？**（某些 Python 包安装时现场编译）；**容器里进程是谁在跑？**（默认 root，被打穿就是 root 权限）；**健康检查打哪个端点？**（ch17 的 /healthz 正是为此准备的）。

本章的特殊之处必须先说清楚：**本沙箱没有 Docker**（FACTS 环境事实）。所以 ch20 的验证方式是"静态检查"——把生产 Dockerfile 的 11 项关键特征写成自动检查器（EX-20-01），逐条核对通过；uvicorn 参数用 `--help` 实测存在性（EX-20-02）。这是诚实的验证边界：**文本特征全对 ≠ 镜像可构建**，真实的 `docker build` 需要你在自己的环境执行。这个"用可执行的检查替代不可执行的操作"的思路本身，也是部署工程的一部分（CI 里大量 lint/dry-run 都是这个思路）。

## 20.2 一句话解释 + 生活类比 + 类比边界

**一句话解释**：生产部署 = 一个只含运行时产物的镜像（多阶段构建）+ 明确的服务器参数（uvicorn workers/超时/并发上限）+ 机器可读的健康信号（/healthz + HEALTHCHECK/探针）+ 可复现的依赖清单（requirements 锁定）。

**生活类比**：多阶段构建像**展会布展**——搭建阶段（builder）全是工具梯、包装箱、脚手架（gcc、pip 缓存），正式开展前全部撤走，观众看到的展厅里只有展品和展架（解释器 + 依赖 + 应用代码）。非 root 用户像**场馆规定工作人员不带万能钥匙**——就算有人冒充工作人员进了后台，也没有每个房间的钥匙。HEALTHCHECK 像**巡更打卡**——场馆按固定间隔检查各岗位有人应答，不应答的岗位自动补人（编排器重启容器）。

**Java 对照**：多阶段构建 ↔ Maven 多阶段（构建镜像装 JDK+maven、运行镜像只要 JRE）——Spring Boot 的 Layered Jar 思想与"先 COPY requirements 再装依赖"的层缓存技巧同源（依赖不变就不重装）。uvicorn ↔ Tomcat/Netty 内嵌服务器，但 **uvicorn --workers 是多进程模型**（每 worker 一个 OS 进程，各带 GIL——ch14 的进程池思想），而 Tomcat 是单进程多线程（线程池）。HEALTHCHECK ↔ K8s liveness/readiness probe 的 Docker 原生前身。

> 💡 类比边界：三处容易带 Java 偏见的边界。①**"多 worker ≠ 线程池"**：uvicorn 的 worker 是进程，进程间零共享——Spring 单例里的进程内缓存/计数器思维在这里失效（ch19 限流必须放 Redis 的部署层原因）；②**Dockerfile 的 HEALTHCHECK 与 K8s 探针不同时用**：K8s 会忽略 HEALTHCHECK 而用自己的 liveness/readiness——写 HEALTHCHECK 是给"裸 docker run/docker-compose"场景，进 K8s 就换成探针配置；③**应用内限流计数、进程内缓存、内存 Session 在 --workers>1 下全部失真**——部署形态反推架构决策，这是本章与 ch19 的联动考点。

## 20.3 正式原理与准确术语

- **多阶段构建（multi-stage build）**：`FROM … AS builder` 编译/安装依赖，`COPY --from=builder` 只搬运行时产物到干净镜像——最终镜像不含工具链与缓存。
- **层缓存（layer cache）**：Docker 每条指令一层、内容不变即命中缓存；**先 COPY requirements.txt 再 pip install、最后 COPY 代码**——改代码不触发重装依赖。
- **slim 基础镜像**：`python:3.12-slim` 精简 Debian；**固定版本号**避免"下次构建基础镜像漂移"。
- **非 root 运行**：`RUN useradd …` + `USER appuser`——容器被攻破时攻击者不是 root。
- **HEALTHCHECK**：容器内健康自检（interval/timeout/retries），失败超过阈值编排器标记 unhealthy。
- **uvicorn 生产参数**（EX-20-02 用 `--help` 实测存在）：`--workers`（进程数）、`--host 0.0.0.0`（容器内必须，否则端口映射不进来）、`--port`、`--timeout-keep-alive`（小于 LB 空闲超时，避免半开连接堆积）、`--limit-concurrency`（并发上限，保护下游）、`--timeout-graceful-shutdown`（优雅停机宽限期）、`--access-log`（排障期开，稳定后关）。
- **健康检查端点**：`/healthz` 存活（进程活着即可 200）；"就绪"（依赖可用）与"存活"分离的思想（ch17 的 healthz 返回 backend 信息就是为排查留的钩子）。
- **requirements 锁定**：`requirements-lock.txt`（pip freeze 产物）固定全量传递依赖版本——构建可复现的最低保障；更严格的 lock 工具链（pip-构建工具/uv 等）本书不展开。
- **.dockerignore**：`.git/`、测试、示例不进镜像（镜像更小、构建上下文更快、少泄密面）。

## 20.4 最小完整示例：生产 Dockerfile 逐行解读

EX-20-01 | 示例代码/ch20_deploy/Dockerfile（完整版见该文件，共两阶段）

```dockerfile
# ── 阶段一：构建阶段（builder）——装全量工具链，编译/下载依赖 ──
FROM python:3.12-slim AS builder
WORKDIR /build
# 先只 COPY 依赖清单再安装：代码改动时命中 Docker 缓存，不必重装依赖（层缓存关键技巧）
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── 阶段二：运行阶段——只带解释器 + 已装好的依赖 + 应用代码 ──
FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /install /usr/local
COPY app.py .
RUN useradd --create-home appuser
USER appuser
EXPOSE 8917
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8917/healthz', timeout=2)" || exit 1
CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8917", \
     "--workers", "2", "--timeout-keep-alive", "5"]
```

逐行理由已在注释与 20.3 术语里，挑三条最值钱的展开：①**依赖层与代码层分离**是 Python 镜像构建速度的命门——pip install 一层几十秒到几分钟，代码 COPY 一层毫秒级，顺序反了则每次改一行代码都要重装全部依赖；②**`--prefix=/install` 把依赖装进独立目录**供第二阶段整体搬走——这是多阶段构建搬"装好的包"而不是"搬源码重装"的关键技巧；③**HEALTHCHECK 打的是 127.0.0.1**（容器内自检自己的 /healthz），不是外部地址——探针的语义是"我这个进程还活着吗"。

**配套检查器**（本沙箱的真实验证方式）：

EX-20-01 | 示例代码/ch20_deploy/ex_20_01_dockerfile_static.py（节选，完整版见该文件）

```python
CHECKS: list[tuple[str, str]] = [
    ("多阶段构建（至少两个 FROM）", r"(?mi)^FROM\s+\S+\s+AS\s+\S+"),
    ("构建阶段先 COPY requirements 再安装（层缓存）", r"(?s)COPY\s+requirements\.txt.*?pip install"),
    ("存在非 root 用户切换", r"(?mi)^USER\s+appuser$"),
    ("HEALTHCHECK 指向 /healthz", r"(?ims)^HEALTHCHECK.*?/healthz"),
    ("CMD 明确 --workers（多进程并行）", r"(?ims)^CMD.*?--workers"),
    # …共 11 项，完整清单见该文件…
]

def main() -> int:
    text = DOCKERFILE.read_text(encoding="utf-8")
    for name, pattern in CHECKS:
        ok = re.search(pattern, text) is not None
        print(f"  [{'✓' if ok else '✗'}] {name}")
```

真实运行输出（本沙箱实测）：

```text
静态检查目标：/workspace/ai_application_course/示例代码/ch20_deploy/Dockerfile

  [✓] 多阶段构建（至少两个 FROM）
  [✓] 基础镜像用 slim 变体
  [✓] 构建阶段先 COPY requirements 再安装（层缓存）
  [✓] pip 安装带 --no-cache-dir（不留缓存层）
  [✓] 从 builder 阶段拷贝安装产物（--from=builder）
  [✓] 存在非 root 用户切换
  [✓] 存在 HEALTHCHECK
  [✓] HEALTHCHECK 指向 /healthz
  [✓] CMD 明确 --workers（多进程并行）
  [✓] CMD 明确 --timeout-keep-alive
  [✓] CMD 绑定 0.0.0.0（容器外可访问）

结果：11/11 项通过
说明：本检查仅验证 Dockerfile 文本特征，不等价于镜像可构建（沙箱无 Docker，
构建验证需读者在有 Docker 的环境执行，以官方构建输出为准）。
```

## 20.5 逐段解释：uvicorn 生产参数实测与启动验证

### 20.5.1 uvicorn 参数的存在性验证——不凭记忆写文档

EX-20-02 | 示例代码/ch20_deploy/ex_20_02_uvicorn_prod_params.py（节选，完整版见该文件）

```python
PARAMS: list[tuple[str, str]] = [
    ("--workers", "进程数：绕过 GIL 的多进程并行；容器内常设 1~2×vCPU，交给编排器水平扩"),
    ("--host", "监听地址：容器内必须 0.0.0.0，否则端口映射不进来"),
    ("--timeout-keep-alive", "keep-alive 空闲超时（秒）：小于 LB 的空闲超时，避免半开连接堆积"),
    ("--limit-concurrency", "并发上限：超过即拒绝，保护下游（配合 ch19 限流思想）"),
    ("--timeout-graceful-shutdown", "优雅停机宽限期：给在途请求留出收尾时间"),
    # …共 7 项…
]

def main() -> None:
    help_text = subprocess.run(
        [sys.executable, "-m", "uvicorn", "--help"],
        capture_output=True, text=True, check=True).stdout
    for flag, meaning in PARAMS:
        present = flag in help_text   # 用 --help 实测参数存在，不凭记忆写文档
```

真实运行输出（本沙箱实测）：

```text
uvicorn 版本：0.54.0

  [✓] --workers                  进程数：绕过 GIL 的多进程并行；容器内常设 1~2×vCPU，交给编排器水平扩
  [✓] --host                     监听地址：容器内必须 0.0.0.0，否则端口映射不进来
  [✓] --port                     监听端口：与 EXPOSE/Service 对齐
  [✓] --timeout-keep-alive       keep-alive 空闲超时（秒）：小于 LB 的空闲超时，避免半开连接堆积
  [✓] --limit-concurrency        并发上限：超过即拒绝，保护下游（配合 ch19 限流思想）
  [✓] --timeout-graceful-shutdown 优雅停机宽限期：给在途请求留出收尾时间
  [✓] --access-log               访问日志：排障期开启，稳定后可关（高频日志的成本）

7/7 个参数在本机 uvicorn --help 中实际存在。
提示：--workers>1 时应用必须可多进程安全运行（无进程内共享可变状态，
限流计数要放 Redis——这正是 ch17 收束演练用 Redis 而非内存字典的原因）。
```

这个"用 --help 验证参数存在再写进教材"的做法值得当成习惯——它防的是"教程说有这个参数，你的版本其实没有"的经典翻车。参数语义三强调：`--workers 2` 就是 ch14 讲的两个进程（各带 GIL、零共享）；`--timeout-keep-alive` 必须**小于**负载均衡的空闲超时，方向反了会出现"uvicorn 已断开、LB 仍往半开连接发请求"的幽灵错误；`--limit-concurrency` 是服务端的"背压总闸"，与应用内限流（ch19）分工不同——它保护本服务，ch19 的 Redis 限流保护下游与配额。

顺带回答 20.1 留下的问题——**gunicorn 和 uvicorn 什么关系**：gunicorn 是传统 WSGI 服务器（Flask/Django 时代的主力），不认识 ASGI 协议；生产跑 FastAPI 有两种形态——直接 `uvicorn --workers N`（uvicorn 自带多 worker 进程管理，本书采用），或 `gunicorn -k uvicorn.workers.UvicornWorker app:app -w N`（gunicorn 做进程守护，每个子进程内跑一个 uvicorn 事件循环）。后者换来 gunicorn 成熟的进程监控与热重启能力，代价是多一层间接；workers 数、优雅停机等参数语义两者同构，选型看团队已有运维栈——没有历史包袱就用 uvicorn 直接跑。

### 20.5.2 部署前的服务验证闭环

部署不是"镜像 build 成功"就结束，而是"启动→健康→业务→停止"的闭环。ch17.6 的真实启动证据（本沙箱实测：uvicorn + curl 验证 /healthz 200、订单查询 200、SSE 全流、限流 429 头、后台任务落盘）正是部署验收的最小剧本。把它写成命令模板：

```bash
# 单条命令完成"启动→验证→停止"（CI 环境后台进程会被回收，必须串在一条命令里）
python3 -m uvicorn app:app --host 127.0.0.1 --port 8933 & sleep 2 \
  && curl -sf http://127.0.0.1:8933/healthz \
  && curl -sf -H "X-API-Key: demo-key-123" http://127.0.0.1:8933/orders/ORD-10001 \
  && kill %1
```

> ⚠️ 常见坑：容器内 `--host` 若写成 127.0.0.1，端口映射（-p 8917:8917）完全不生效——映射的是容器网络命名空间的 0.0.0.0 端口，进程只听 loopback 时外面永远连不进来。这是 Python 服务容器化的第一高频错误（Java 内嵌 Tomcat 默认绑 0.0.0.0，所以你没踩过）。

## 20.6 安装 / 文件位置 / 运行命令

- 依赖：无新增（uvicorn 0.54.0 已在 requirements.txt）；Docker 本沙箱不可用——Dockerfile 仅静态检查。
- 文件位置：`示例代码/ch20_deploy/`（Dockerfile + 2 个示例）；本章无 pytest（按 syllabus 以"静态检查记录"替代，EX-20-01 的 11 项检查即检查记录，退出码 0）。
- 运行命令：

```bash
python3 示例代码/ch20_deploy/ex_20_01_dockerfile_static.py    # 11/11 通过，退出码 0
python3 示例代码/ch20_deploy/ex_20_02_uvicorn_prod_params.py  # 7/7 参数存在
# 读者环境（有 Docker）的真实构建与运行：
docker build -t order-service:latest 示例代码/ch20_deploy/
docker run -p 8917:8917 --read-only --tmpfs /tmp order-service:latest
```

## 20.7 常见错误与排查（真实踩坑记录）

**错误一：静态检查 4 项"明明写了却判不通过"——正则标志位 bug**

EX-20-01 初版 11 项检查里有 4 项误报未通过（CMD/HEALTHCHECK 行存在却匹配不到）。定位：正则用了 `(?is)` 标志组却缺 `m`——`^CMD` 里的 `^` 没有多行模式加持，只匹配整个文本的开头，而 CMD 在文件末尾当然匹配不到。修复为 `(?ims)` 后 11/11。这条的元教训：**验证工具自身也要被验证**——"4 项失败"的第一反应应当是怀疑检查器，因为被检查物是人工逐行写过的。

**错误二：容器内 curl 不通——`--host` 绑了 127.0.0.1**

见 20.5.2 的⚠️。修复：`--host 0.0.0.0`（EXPOSE 与 -p 只声明/映射，不改变监听地址）。

**错误三：改一行代码，镜像重建要 5 分钟（层缓存失效）**

把 `COPY app.py .` 写在 `pip install` 之前——代码一变，后续所有层（含重型依赖安装）全部重建。修复：恢复"requirements 先行、代码最后"的层序（20.4 第一条展开的理由）。

**错误四：`--workers 2` 后限流阈值变相翻倍 / 进程内缓存不一致**

worker 是独立进程（ch14），进程内存的计数器/缓存互不可见。修复：跨进程状态全部外置——限流计数进 Redis（ch19），共享缓存进 Redis，配置每进程独立读。这呼应 ch17 面试追问与 EX-20-02 输出的提示行。

**错误五：CI 里验证服务的后台进程"消失"**

ch17 run log 的真实教训：先启动、下一条命令再 curl，全部 000——命令结束后台进程被回收。修复：启动/验证/停止在同一条 shell 命令内串联。K8s Job/GitHub Actions 里都有同款生命周期语义。

## 20.8 企业场景中的使用方式

- **交付物清单**：给 Java 团队/运维交付一个 Python AI 服务，本章定义的最小交付集是——Dockerfile（多阶段+非 root+HEALTHCHECK）、requirements-lock.txt、`/healthz` 端点、生产启动参数清单（uvicorn flags 及理由）、一份"单条命令冒烟验证"脚本（ch17 的启动证据模板）。
- **与 Spring Boot 部署的对位**：Boot jar ↔ 镜像内 app.py；`management/health` ↔ `/healthz`；JVM 内存参数 ↔ `--workers`×每进程内存预算；Tomcat maxThreads ↔ `--limit-concurrency`。对位表能帮 Java 团队快速建立心智模型。
- **K8s 迁移钩子**：HEALTHCHECK → liveness probe（`httpGet: /healthz`）；"就绪"应另建 `/readyz`（检查 Redis/模型端点连通）——ch17 的 healthz 返回 backend 字段就是为这个演进预留的；`--workers` 在 K8s 下常配 1（水平扩 Pod 代替纵向加 worker），这是与虚拟机时代的部署哲学差异。
- **上线最小检查清单**（ch61 有 15 项完整版，此处是本章范围的子集）：①镜像构建通过——本地真实 `docker build`，不止静态检查；②单容器冒烟——/healthz 200 + 一条业务路径 200 + 一条 4xx 语义正确；③生产参数核对——`--host 0.0.0.0`、workers、`--timeout-keep-alive` 小于 LB 空闲超时；④探针接入——存活与就绪分离；⑤日志与 trace_id 可被集中收集（ch17 的格式即为此设计）；⑥密钥经环境注入且启动校验拒绝空值（EX-16-03 模式）；⑦依赖锁定（requirements-lock.txt）保证镜像可复现；⑧回滚方案——上一版镜像可立即拉起。

## 20.9 练习

1. **基础**：说出多阶段构建解决什么问题，以及"先 COPY requirements 再 COPY 代码"的层缓存原理。
2. **基础**：`--timeout-keep-alive 5` 与"LB 空闲超时 60s"搭配对吗？方向应该怎么调？
3. **代码**：给 Dockerfile 增加 `.dockerignore` 文件（至少排除 .git/、测试/、示例代码/、__pycache__），并在 ex_20_01 的 CHECKS 里加一条对应检查项（提示：`.dockerignore` 不在 Dockerfile 文本里，需要让检查器读第二个文件）。
4. **代码**：写一个 `/readyz` 端点（仿 ch17 healthz）：检查 Redis ping（fakeredis 也 ping），成功返回 200 `{"status":"ready"}`，失败返回 503；写 TestClient 测试覆盖两态。
5. **调试题**：同事的容器日志显示"uvicorn 启动正常、/healthz 返回 200"，但 K8s 探针仍然报 unhealthy 并不断重启 Pod。给出三个可能原因（提示：探针配置路径/端口、监听地址、就绪与存活混淆）。

<details>
<summary>点开查看参考答案</summary>

1. 多阶段构建把"编译/安装依赖所需的工具链"留在 builder 阶段，运行镜像只拷贝产物——镜像更小、攻击面更小、构建缓存与源码不泄露。层缓存：Docker 逐层构建且内容不变即复用——requirements 先行时，依赖版本不变则该层及之后（在代码 COPY 之前的所有层）命中缓存，改代码只重建毫秒级的代码层。
2. 不对，方向反了。uvicorn 的 keep-alive 空闲超时应**小于** LB 的空闲超时（如 uvicorn 5s < LB 60s）：让服务端先于 LB 主动断开空闲连接，LB 才不会把新请求发往已死的半开连接（表现为偶发连接重置）。
3. `.dockerignore` 内容示例：`.git`、`测试/`、`示例代码/`、`__pycache__/`、`*.pyc`、`_audit.log`。检查器改造：`ignore = (DOCKERFILE.parent / ".dockerignore").read_text()`，加检查项 `(".dockerignore 排除 .git", r"(?m)^\.git\s*$")` 等，对 ignore 文本逐条匹配——注意这扩展了"静态检查"的检查面，思路不变。
4. 骨架：`@app.get("/readyz")` / `def readyz() -> JSONResponse:` 内 `try: limiter.client.ping(); return JSONResponse({"status": "ready"}) except Exception: return JSONResponse(status_code=503, content={"status": "not ready"})`。测试：`make_client()` 默认 fakeredis ping 可用 → 200；`monkeypatch.setattr(limiter.client, "ping", raise_conn_error)` 或注入一个 ping 抛异常的 fake client → 503（fake 方式更稳，参照 ch18 monkeypatch 思想）。
5. ①探针配置的 path/port 与实际不符（探针打 /healthz 但写成了 /health，或 Service 端口与容器端口错位）；②容器内 uvicorn 绑了 127.0.0.1——容器内自检（curl localhost）能通、K8s 从 Pod IP 探测不通（探针走的是容器网络接口）；③把 liveness probe 误配成了重依赖检查（如 ping 模型端点）而模型偶发慢 → 存活检查超时重启风暴——重依赖检查应放 readiness（摘流量）而不是 liveness（重启进程）。
</details>

## 20.10 自测检查表

- 我能逐行说出生产 Dockerfile 的 11 项特征及各自防的事故。
- 我能解释多阶段构建 + `--prefix` 搬运 + 层缓存顺序三件事如何共同决定构建速度与镜像大小。
- 我能给出 uvicorn 生产启动命令，并解释 --workers/--host/--timeout-keep-alive/--limit-concurrency 各自保护什么。
- 我知道 --workers 与 ch14 进程模型、ch19 Redis 限流之间的因果链。
- 我能区分存活（liveness/healthz）与就绪（readyz）的职责，并说出 K8s 下 HEALTHCHECK 的替代品。
- 我复现过"单条命令内启动→curl 验证→停止"的服务验证闭环（或能在自己环境执行）。
- 我知道本沙箱 Docker 不可用，本书 Dockerfile 的验证边界是 11 项静态检查 + 读者环境真实构建。

## 20.11 面试追问[模拟题]

1. **[模拟题]** "为什么 Python 的 ASGI 服务要开多个 worker？和 Node 的单进程多路复用差在哪？"——Python 有 GIL：单 worker 的 asyncio 能吃满 IO 并发但 CPU 计算只有一个核；多 worker 用进程绕开 GIL（ch14）。Node/V8 单线程事件循环 + 无 GIL，扩展靠 cluster 模块多进程——殊途同归都到"多进程"，但动机不同。回答边界：free-threading 实验构建正在改变这个格局，以官方发布说明为准。
2. **[模拟题]** "滚动发布时怎么保证不丢请求？"——分层答：优雅停机（`--timeout-graceful-shutdown` 给在途请求收尾）+ 就绪探针（新 Pod ready 才进 LB、旧 Pod 先摘流量再 SIGTERM）+ 客户端重试兜底（ch15，配合幂等键防重复）。Java 对照：Spring Boot graceful shutdown + K8s preStop。
3. **[模拟题]** "你的镜像构建慢，怎么定位与优化？"——按层看构建日志（Docker 的 step 输出即耗时分布）：依赖安装层慢 → 确认 requirements 先行/换更精简的基础镜像/挂 pip 缓存（builder 阶段）；传输层慢 → .dockerignore 减小构建上下文；每次全重建 → 检查层序是否被代码 COPY 打断。

### 待核实

- Dockerfile 未经过真实 `docker build`（沙箱无 Docker）：11 项静态特征检查全通过，镜像可构建性以读者环境实际构建为准（run log 第 6 节第 1 条）。
- uvicorn 多 worker 的进程模型与优雅停机未做长时压测，参数存在性已用 `--help` 核实；`--workers` 的推荐值区间（1~2×vCPU）是常见工程经验而非本书实测结论。

---

# 第三部分小结与衔接

学完 ch13~ch20，你已经具备 Java 工程师视角下完整的"Python 服务侧"能力栈：

| 能力 | 章 | 对 Java 心智模型 | 全书后续用到的地方 |
|---|---|---|---|
| asyncio 并发与超时取消 | ch13 | 虚拟线程/CompletableFuture（不等价处已标明） | ch23 流式、ch36 RAG 服务、ch43+ LangGraph |
| 线程/进程/GIL 选型 | ch14 | ExecutorService（GIL 修正直觉） | ch25 embedding 计算、本地推理 |
| HTTP 客户端工程化 | ch15 | Apache HttpClient + Resilience4j Retry | ch24 模型 API 重试/超时、ch59 稳定性参数 |
| Pydantic 校验与配置 | ch16 | Bean Validation + Jackson + @ConfigurationProperties | ch24 结构化输出、全书模型层 |
| FastAPI 服务 | ch17 | Spring MVC/SseEmitter（Depends≠@Autowired 已辨析） | ch36 RAG 项目、P1~P3 项目 |
| pytest 测试体系 | ch18 | JUnit 5 + Mockito + WireMock | 各项目测试、ch51 LangGraph 测试 |
| 数据与缓存 | ch19 | PreparedStatement + Redis/Resilience4j | P1 缓存、ch58 只读账户、ch59 限流熔断 |
| 部署基础 | ch20 | Boot jar + K8s 探针 | P3 Docker 化、ch61 上线检查清单 |

**验证存档**：本部分 30 个示例（EX-13-01~EX-20-02）全部真实执行并产出文中输出；测试/test_ch13~19.py 共 40 个测试全绿；ch17 收束演练与 ch19 真实 Redis 有"本沙箱实测"启动证据；Dockerfile 因沙箱无 Docker 仅完成 11 项静态检查（诚实边界写入 ch20）。完整运行记录与修复过程见 `验证报告/运行日志/part03.md`。

**下一部分衔接**：卷二 ch21 起进入模型与框架——ch24 的 openai SDK 全流程直接复用 ch15（超时/重试/幂等）与 ch16（Pydantic 结构化输出）成果；ch36 的 RAG 服务与第八部分 LangGraph 的流式输出建立在 ch13/ch17 的 asyncio + SSE 地基上。Python 服务侧的"地基"到此完成。

<!-- PART3-END -->
