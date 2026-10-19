# ch14 测试 | 线程池 IO 加速、CPU 密集的线程无加速/进程有加速（真实计时）
# 运行：cd /workspace/ai_application_course && python3 -m pytest 测试/test_ch14.py -v
import time
from concurrent.futures import ThreadPoolExecutor

from 示例代码.ch14_threads_processes.ex_14_02_cpu_bound_experiment import (
    CHUNKS,
    count_primes_in_range,
)


def test_thread_pool_io_speedup():
    """IO 密集：等待期释放 GIL，线程池显著加速。"""
    def io_task() -> None:
        time.sleep(0.1)  # time.sleep 释放 GIL

    n = 10
    started = time.perf_counter()
    for _ in range(n):
        io_task()
    sequential = time.perf_counter() - started

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=5) as pool:
        list(pool.map(lambda _: io_task(), range(n)))
    parallel = time.perf_counter() - started

    assert parallel < sequential * 0.6  # 5 线程应快 2 倍以上（实测 ~5 倍）


def test_cpu_bound_threads_no_real_speedup():
    """CPU 密集：纯 Python 计算独占 GIL，多线程不提速（甚至更慢）。"""
    started = time.perf_counter()
    expected = [count_primes_in_range(lo, hi) for lo, hi in CHUNKS]
    serial = time.perf_counter() - started

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=4) as pool:
        got = list(pool.map(count_primes_in_range,
                            [c[0] for c in CHUNKS], [c[1] for c in CHUNKS]))
    threaded = time.perf_counter() - started

    assert got == expected  # 正确性先行
    assert threaded > serial * 0.85  # 若多线程真能并行，应远小于串行；实测 ≈ 1.0x


def test_cpu_bound_processes_speedup():
    """CPU 密集：每进程独立 GIL，多进程显著快于多线程（本机 3 核，约 1.4~1.5x）。"""
    import time as t
    from concurrent.futures import ProcessPoolExecutor

    started = t.perf_counter()
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(count_primes_in_range,
                      [c[0] for c in CHUNKS], [c[1] for c in CHUNKS]))
    threaded = t.perf_counter() - started

    started = t.perf_counter()
    with ProcessPoolExecutor(max_workers=4) as pool:
        got = list(pool.map(count_primes_in_range,
                            [c[0] for c in CHUNKS], [c[1] for c in CHUNKS]))
    processes = t.perf_counter() - started

    assert got == [count_primes_in_range(lo, hi) for lo, hi in CHUNKS]
    assert processes < threaded  # 进程方案真实更快（含启动开销仍如此）
