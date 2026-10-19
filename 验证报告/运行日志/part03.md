# Part03 运行日志（ch13~ch20 工程化与服务开发）

- 执行环境：沙箱 Linux，Python 3.14.7（pyenv），CI=true 非交互。
- 核实日期：2026-10-19。依赖版本见 requirements.txt（fastapi 0.146.0 / uvicorn 0.54.0 / httpx 0.28.1 / pydantic 2.14.1 / pydantic-settings 2.16.0 / pytest 9.1.1 / pytest-asyncio 1.4.0 / respx 0.23.1 / fakeredis 2.40.0）。
- 额外环境动作：`apt-get install -y redis-server` 成功（Redis 7.0.15，redis-cli ping=True），用于 ch19 真实 Redis 演示；ruff 0.16.0 / mypy 1.19.1 已在环境中，用于 ch18 ○选修演示。Docker 不可用（ch20 仅静态检查）。

## 1. 示例运行记录（全部真实执行，退出码 0）

| EX | 文件 | 命令 | 关键输出摘要 |
|---|---|---|---|
| EX-13-01 | examples/ch13_asyncio/ex_13_01_hello_coroutine.py | python3 …/ex_13_01_hello_coroutine.py | 两个 await 顺序执行，总耗时 0.60s |
| EX-13-02 | examples/ch13_asyncio/ex_13_02_sleep_compare.py | python3 …/ex_13_02_sleep_compare.py | [A] time.sleep×5=1.00s；[B] asyncio.sleep 并发=0.20s；[C] 阻塞 0.5s 使 0.1s 任务 0.60s 才返回 |
| EX-13-03 | examples/ch13_asyncio/ex_13_03_create_task_gather.py | python3 … | gather 按提交顺序返回；总耗时 0.40s（取最慢） |
| EX-13-04 | examples/ch13_asyncio/ex_13_04_timeout_cancel.py | python3 … | wait_for 超时→CancelledError 清理→re-raise；手动 cancel 生效 |
| EX-13-05 | examples/ch13_asyncio/ex_13_05_exception_propagation.py | python3 … | 默认策略：ValueError 抛出且兄弟任务未被取消；return_exceptions=True 异常入列表 |
| EX-13-06 | examples/ch13_asyncio/ex_13_06_semaphore.py | python3 … | 最大并发=3（未被突破）；总耗时 0.80s=ceil(10/3)×0.2 |
| EX-13-07 | examples/ch13_asyncio/ex_13_07_async_context.py | python3 … | __aenter__/__aexit__ 与 asynccontextmanager 两种写法，异常路径清理生效 |
| EX-13-08 | examples/ch13_asyncio/ex_13_08_concurrent_fetch.py | python3 … | 真实 HTTP：顺序 2.08s vs 并发 0.13s，加速比 16.2×（backlog 修复后） |
| EX-14-01 | examples/ch14_threads_processes/ex_14_01_thread_pool.py | python3 … | 20 个 200ms IO 任务：单线程 4.00s vs 线程池(10) 0.40s，10.0× |
| EX-14-02 | examples/ch14_threads_processes/ex_14_02_cpu_bound_experiment.py | python3 … | 纯 Python 素数计数：串行 1.05s；线程 1.08s（0.97×，无加速）；进程 0.72s（1.47×，3 核+启动开销封顶） |
| EX-14-03 | examples/ch14_threads_processes/ex_14_03_process_pool.py | python3 … | 默认启动方式 forkserver（3.14 起 Linux 默认改变）；池启动 174ms；100 个 submit 65ms |
| EX-15-01 | examples/ch15_http_client/ex_15_01_client_pool_timeout.py | python3 … | 复用连接 402ms vs 每次新建 536ms；ReadTimeout 301ms；PoolTimeout 808ms |
| EX-15-02 | examples/ch15_http_client/ex_15_02_retry_backoff.py | python3 … | 503→退避 68ms→503→退避 86ms→200（attempt 3，总 198ms）；404 不重试 |
| EX-15-03 | examples/ch15_http_client/ex_15_03_idempotency_key.py | python3 … | 无幂等键两笔订单号不同；带 Idempotency-Key 同单号 + X-Idempotent-Replay: true |
| EX-16-01 | examples/ch16_pydantic/ex_16_01_basics.py | python3 …（cwd=ch16_pydantic） | 2 个校验错误（string_pattern_mismatch / greater_than）；"3"→int 宽松转换 |
| EX-16-02 | examples/ch16_pydantic/ex_16_02_validators.py | python3 … | strip+upper 生效；跨字段规则拦截；字段规则拦截 |
| EX-16-03 | examples/ch16_pydantic/ex_16_03_settings.py | python3 … | .env 加载 staging；环境变量覆盖为 production（env > .env > 默认） |
| EX-16-04 | examples/ch16_pydantic/ex_16_04_json_schema.py | python3 … | model_dump_json 往返；缺失/越界字段被拦截；JSON Schema 含 required/maximum |
| EX-17-01 | examples/ch17_fastapi_service/ex_17_01_params_models.py | python3 … | 201 创建（response_model 过滤 cost_price）；422 定位 body 字段；路径参数 pattern 422 |
| EX-17-02 | examples/ch17_fastapi_service/ex_17_02_depends_auth.py | python3 … | 200/422(缺头)/401/403/200 鉴权链全通过 |
| EX-17-03 | examples/ch17_fastapi_service/ex_17_03_exception_middleware.py | python3 … | 日志与响应头同 trace_id；透传 X-Trace-Id 被沿用 |
| EX-17-04 | examples/ch17_fastapi_service/ex_17_04_sse_stream.py | python3 … | 6 条 data 事件；提前断连无异常，finally 清理日志出现 |
| EX-17-05 | examples/ch17_fastapi_service/ex_17_05_background_tasks.py | python3 … | 响应 201；后台审计任务确实落盘（TestClient 等整个 ASGI 生命周期，故测得耗时含 0.3s） |
| EX-17-06 | examples/ch17_fastapi_service/app.py | uvicorn app:app --port 8917/8918/8919/8920 + curl | 见第 3 节"真实启动验证" |
| EX-18-01 | examples/ch18_testing/ex_18_01_fixture_parametrize.py | pytest …/ex_18_01_fixture_parametrize.py -v | 5 passed |
| EX-18-02 | examples/ch18_testing/ex_18_02_monkeypatch_tmp_path.py | pytest … -v | 4 passed |
| EX-18-03 | examples/ch18_testing/ex_18_03_async_tests.py | pytest … -v | 3 passed（asyncio mode=AUTO） |
| EX-18-04 | examples/ch18_testing/ex_18_04_respx_mock.py | python3 … | 固定响应/失败序列/ConnectTimeout/调用次数断言全部符合预期 |
| EX-19-01 | examples/ch19_data_cache/ex_19_01_sql_injection.py | python3 … | 拼接查询泄露 2 行（-- 注释 payload）；朴素永真 payload 因 AND 优先级失败（0 行）；参数化 0 行；executescript 夹带 DELETE 清空表 |
| EX-19-02 | examples/ch19_data_cache/ex_19_02_readonly_connection.py | python3 … | PRAGMA query_only=ON：读正常，写/删被 OperationalError 拒绝 |
| EX-19-03 | examples/ch19_data_cache/ex_19_03_redis_cache.py | python3 …（fakeredis）；REDIS_URL=redis://127.0.0.1:6379/5 python3 …（真实 Redis 7.0.15） | 两种后端行为一致：首次 db 105ms→命中 cache→TTL 过期后回源；真实 Redis 中 keys order:* 可见 |
| EX-19-04 | examples/ch19_data_cache/ex_19_04_rate_limit_fixed_window.py | python3 … | 8 发：5 放行/3 拒绝；窗口翻页后复位；bob 与 alice 隔离 |
| EX-20-01 | examples/ch20_deploy/ex_20_01_dockerfile_static.py | python3 … | 11/11 项静态检查通过（Dockerfile 文本特征） |
| EX-20-02 | examples/ch20_deploy/ex_20_02_uvicorn_prod_params.py | python3 … | uvicorn 0.54.0 --help 实测 7/7 生产参数存在 |

## 2. pytest 汇总

命令：`cd /workspace/ai_application_course && python3 -m pytest tests/test_ch13.py tests/test_ch14.py tests/test_ch15.py tests/test_ch16.py tests/test_ch17.py tests/test_ch18.py tests/test_ch19.py`

最终结果摘要行：

```
40 passed in 12.90s
```

分布：ch13 6 个、ch14 3 个、ch15 6 个、ch16 6 个、ch17 9 个、ch18 6 个、ch19 4 个。
ch20 按大纲用"静态检查记录"替代 pytest（EX-20-01 的 11 项检查即检查记录，退出码 0）。

## 3. ch17 收束演练真实启动验证（uvicorn + curl 证据）

1. 启动：`cd examples/ch17_fastapi_service && python3 -m uvicorn app:app --host 127.0.0.1 --port 8918`（后台）。
2. `curl -s -i http://127.0.0.1:8918/healthz` → `HTTP/1.1 200 OK`，响应头含 `x-trace-id: 01e9abc939ac45e1`，body `{"status":"ok","backend":"fakeredis","rate_limit_per_minute":60}`。
3. `curl -s -i -H "X-API-Key: demo-key-123" http://127.0.0.1:8918/orders/ORD-10001` → 200 + `{"order_id":"ORD-10001","user":"alice","amount":129.0,"status":"paid"}`。
4. `curl -s -N -m 2 …/orders/ORD-10001/stream` → SSE 片段：5 条 `event: progress`（percent 20→100，stage 已支付→已签收）+ `event: done`。
5. 限流实测：连打 70 发（前序已用部分配额）→ `58 个 200 + 12 个 429`；429 响应头 `retry-after: 59`、`x-ratelimit-limit: 60`、`x-ratelimit-remaining: 0`。
6. SSE 客户端断连：`curl -N -m 0.15 …/stream` 提前关闭 → 应用日志出现 `SSE 生成器退出（完成/断连/异常统一清理）`（uvicorn 直接取消生成器走 finally；`is_disconnected` 为另一条兜底路径，本次未触发，两路径都在代码中）。
7. POST + 后台任务（端口 8920 复验）：`curl -X POST …/orders` → `201 Created` + `{"accepted":true,"order_id":"ORD-30001"}`；约 0.8s 后 `_audit.log` 出现 `{"ts": 1792374512.15, "order_id": "ORD-30001", "trace_id": "601cefcd3e41467f"}`——trace_id 与响应头一致。
8. 全部验证结束后服务进程已 kill（`uvicorn 已停止`）。

注：第一次尝试用"后台启动、下一条命令再 curl"的方式失败——沙箱中命令结束后台进程会被回收（curl 全部返回 000）。改为单条命令内完成"启动→验证→停止"后全部成功。这也是 CI 环境跑长驻服务的常见坑，记录备查。

## 4. 失败与修复过程（真实踩坑记录）

1. **EX-13-05**：`asyncio.create_task(asyncio.gather(...))` 抛 `TypeError: a coroutine was expected, got <_GatheringFuture pending>`——gather 返回 Future 不是协程。修复：外包一层 async 函数再 create_task。已写进教材排错节。
2. **EX-13-08**：并发加速比只有 1.8×。插桩定位到 `socketserver.request_queue_size` 默认 backlog=5，20 个瞬时连接溢出触发 1s SYN 重传。修复：自定义服务器 `request_queue_size = 128` 后加速比 16.2×。教材作为排障案例。
3. **EX-15-01/02**：`ValueError: httpx.Timeout must either include a default, or set all four parameters explicitly`——httpx.Timeout 少传 write。修复：四参数显式齐全。教材排错节素材。
4. **EX-15-02**：`TypeError: request_with_retry() got an unexpected keyword argument 'params'`。修复：签名增加 `**kwargs` 透传。
5. **app.py（EX-17-06）**：所有带 Depends 的端点 422 "Field required"，`loc=['query','_verdict']`。最小复现逐步定位：与 Annotated、下划线参数名无关，真凶是 `from __future__ import annotations` + 工厂函数闭包内定义依赖——字符串化注解在模块全局找不到闭包名，FastAPI 静默把依赖参数当 query 参数。修复：移除 future 导入（代码兼容 3.10+ 的运行时 `X | None`）。教材排错节重点案例。
6. **app.py**：fastapi 的 `Path` 遮蔽 `pathlib.Path`。修复：`import pathlib` 模块引用。
7. **app.py**：`get_order` 漏配 `Path(pattern=...)` 导致非法格式返回 404 而非 422。修复：补约束，测试转绿。
8. **ex_17_03**：中间件日志 trace=-。原因：先 reset 再打日志。修复：调整时序（日志→finally reset）。
9. **ex_17_05**：断言"响应先于后台任务返回"在 TestClient 下失败——TestClient 会等整个 ASGI 生命周期（含后台任务）。修复：改为诚实注释 + 真实 uvicorn 复验时序。
10. **ex_19_01**：朴素永真 payload `' OR '1'='1` 因 AND 优先级实际返回 0 行（防住了）。改用 `' OR '1'='1' --`（注释密码条件）复现泄露，并把"朴素 payload 失败"作为教学点保留。
11. **ex_20_01**：4 项检查误报未通过——正则 `(?is)` 缺 `m` 标志导致 `^CMD` 匹配不到行首。修复为 `(?ims)` 后 11/11。
12. **tests/test_ch15.py**：初版把退避次数数错（fail=3、max_attempts=5 应为 3 次退避而非 4 次）。修正断言。
13. **tests/test_ch16.py**：写测试时 env 前缀误写为 `ORDER_SVC_`（示例 Settings 前缀是 `ORDER_`）。修正。
14. **tests/test_ch18.py**：限流计数器在用例间累计导致非法参数用例拿到 429。修复：用例开头清零计数。
15. **探测脚本**：多进程代码缺 `if __name__ == "__main__"` 守卫 + forkserver（3.14 起 Linux 默认）→ `RuntimeError: ...bootstrapping phase`。真实示例文件均有守卫不受影响；该报错写进 ch14 排错节。

## 5. ch18 ○选修：ruff / mypy 一条龙实测记录

- `ruff check examples/ch15_http_client examples/ch17_fastapi_service`：首跑 10 errors（导入排序、未用变量等 7 项可自动修复 + 3 项 B008）。
- `ruff check --fix …`：7 fixed, 3 remaining——剩余 3 项均为 B008 "Depends 出现在参数默认值"，这是 FastAPI 官方文档的标准写法；改用 `Annotated` 风格可消除（正文讨论）。修复后全部示例与测试复跑通过（无回归）。
- `mypy examples/ch16_pydantic examples/ch19_data_cache`：4 errors——均为"动态行为误报"教学素材：Pydantic 宽松转换（str→int）、`_env_file` 魔法参数、`except Exception` 上的 `.errors()`。结论：lint/类型检查要配 per-project 规则并保留人的判断。

## 6. 未验证项（诚实清单）

1. Dockerfile 未经过真实 `docker build`（沙箱无 Docker）：仅完成 11 项静态特征检查，镜像可构建性以读者环境实际构建为准。
2. 真实 Redis 仅验证 7.0.15 单机 GET/SET/INCR/EXPIRE/TTL/ping 路径；未验证哨兵/集群/持久化。
3. uvicorn 多 worker 生产行为（--workers 2 的进程模型、优雅停机参数）未在本沙箱做长时间压测，参数存在性已用 `--help` 核实。
4. 本沙箱 Python 为 3.14.7；教材声明基准 3.12+、兼容 3.10+，但 3.10/3.11 解释器上的回归未逐条执行。
5. GIL/free-threading 的版本演进按"以官方发布说明为准"处理（FACTS 约束），未在 3.13 free-threading 构建上实测。
