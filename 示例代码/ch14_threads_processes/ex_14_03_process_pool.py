# EX-14-03 | ProcessPoolExecutor：map/submit 用法与多进程的代价（启动开销、可序列化限制）
# 运行：python3 示例代码/ch14_threads_processes/ex_14_03_process_pool.py
import time
from concurrent.futures import ProcessPoolExecutor


def square(x: int) -> int:
    # 注意：这个函数必须定义在模块顶层——子进程要按名字"找回"它（可 pickle），嵌套函数不行
    return x * x


def main() -> None:
    # 代价一：进程池启动开销。fork/forkserver/spawn 三种启动方式的开销不同，
    # Python 3.14 起 Linux 默认 start method 从 fork 改为 forkserver（以官方发布说明为准）。
    from multiprocessing import get_start_method
    print(f"当前平台默认启动方式：{get_start_method()}")

    started = time.perf_counter()
    with ProcessPoolExecutor(max_workers=4) as pool:
        # map：与内置 map 同形，按顺序返回结果
        results = list(pool.map(square, range(8)))
    elapsed = time.perf_counter() - started
    print(f"pool.map(square, 0..7) = {results}，含池启动共耗时 {elapsed * 1000:.0f}ms")

    # 代价二：参数与返回值都要跨进程序列化（pickle）。
    # 小任务 + 大数据的传输会让"加速"被传输成本吃掉——适合粗粒度任务。
    started = time.perf_counter()
    with ProcessPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(square, i) for i in range(100)]
        total = sum(f.result() for f in futures)
    print(f"100 个 submit+result：total={total}，耗时 {(time.perf_counter() - started) * 1000:.0f}ms")

    # 代价三：函数体里再起进程/线程的组合陷阱（演示经典报错写法，不真实运行）
    print("若把 lambda / 嵌套函数交给进程池：pickle 无法序列化 → PicklingError / AttributeError")


if __name__ == "__main__":
    main()
