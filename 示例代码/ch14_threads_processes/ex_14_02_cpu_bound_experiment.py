# EX-14-02 | CPU 密集实验：纯 Python 循环在 串行 / 线程 / 多进程 下的真实耗时对比
# 运行：python3 示例代码/ch14_threads_processes/ex_14_02_cpu_bound_experiment.py
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor


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


def run_serial() -> tuple[float, int]:
    started = time.perf_counter()
    results = [count_primes_in_range(lo, hi) for lo, hi in CHUNKS]
    return time.perf_counter() - started, sum(results)


def run_threads() -> tuple[float, int]:
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(count_primes_in_range, [c[0] for c in CHUNKS], [c[1] for c in CHUNKS]))
    return time.perf_counter() - started, sum(results)


def run_processes() -> tuple[float, int]:
    started = time.perf_counter()
    with ProcessPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(count_primes_in_range, [c[0] for c in CHUNKS], [c[1] for c in CHUNKS]))
    return time.perf_counter() - started, sum(results)


if __name__ == "__main__":
    t_seq, n1 = run_serial()
    t_thr, n2 = run_threads()
    t_prc, n3 = run_processes()
    assert n1 == n2 == n3, "三种方式算出的素数总数必须一致（正确性先行）"
    print(f"纯 Python 素数计数（4 片等成本工作，总素数 {n1} 个）：")
    print(f"  串行           {t_seq:.2f}s  （基准 1.00x）")
    print(f"  线程池 4 线程  {t_thr:.2f}s  （{t_seq / t_thr:.2f}x —— 几乎无加速：CPU 计算独占 GIL，甚至更慢）")
    print(f"  进程池 4 进程  {t_prc:.2f}s  （{t_seq / t_prc:.2f}x —— 接近核数加速：每个进程有独立 GIL）")
    import os
    print(f"（本机 CPU 核数 os.cpu_count() = {os.cpu_count()}，加速比上界受核数限制）")
