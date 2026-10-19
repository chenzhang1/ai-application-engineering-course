# EX-05-07 | defaultdict 与 Counter | 运行: python3 示例代码/ch05_datastructures/ex_05_07_defaultdict_counter.py
from collections import Counter, defaultdict


def main() -> None:
    words: list[str] = ["java", "python", "java", "go", "python", "java"]

    # 手写计数（对照 Java: map.merge(k, 1, Integer::sum)）
    counts: dict[str, int] = {}
    for w in words:
        counts[w] = counts.get(w, 0) + 1
    print(f"手写计数: {counts}")

    # defaultdict：访问缺失 key 时按工厂函数自动创建默认值
    grouped: defaultdict[int, list[str]] = defaultdict(list)
    for w in words:
        grouped[len(w)].append(w)
    print(f"按长度分组: {dict(grouped)}")
    print(f"访问缺失 key: grouped[99] = {grouped[99]}（自动创建空列表并写入）")
    print(f"访问之后 keys: {sorted(grouped)}")

    # Counter：计数器专用工具，缺失 key 返回 0 且不写入
    counter: Counter[str] = Counter(words)
    print(f"Counter: {dict(counter)}")
    print(f"最常见的 2 个: {counter.most_common(2)}")
    print(f"缺失 key 计数: counter['rust'] = {counter['rust']}（不写入 key）")
    print(f"访问之后 keys: {sorted(counter)}")


if __name__ == "__main__":
    main()
