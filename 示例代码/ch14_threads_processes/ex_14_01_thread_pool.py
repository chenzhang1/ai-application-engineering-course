# EX-14-01 | ThreadPoolExecutor：IO 密集任务的线程池并发（对照 asyncio 的时间收益）
# 运行：python3 示例代码/ch14_threads_processes/ex_14_01_thread_pool.py
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
