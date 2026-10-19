# EX-05-04 | 推导式全家 | 运行: python3 examples/ch05_datastructures/ex_05_04_comprehensions.py
def main() -> None:
    scores: dict[str, int] = {"alice": 92, "bob": 58, "carol": 77}

    # 列表推导式：[表达式 for 变量 in 可迭代 if 条件]
    names = [name for name in scores if scores[name] >= 60]
    print(f"及格名单: {names}")

    # if-else 写在表达式位置（三元）：注意与"过滤用的 if"位置不同
    marks = [f"{s}分" if s >= 60 else f"{s}分(补考)" for s in scores.values()]
    print(f"成绩标注: {marks}")

    # 字典推导式
    passed = {name: s for name, s in scores.items() if s >= 60}
    print(f"及格成绩表: {passed}")

    # 集合推导式
    initials = {name[0].upper() for name in scores}
    print(f"首字母集合: {sorted(initials)}")

    # 生成器表达式：不立即构建列表，惰性求值（ch09 展开）
    total = sum(s for s in scores.values())
    print(f"总分: {total}")

    # 嵌套推导式：按"先外后内"的阅读顺序展平矩阵
    matrix = [[1, 2, 3], [4, 5, 6]]
    flat = [cell for row in matrix for cell in row]
    print(f"展平: {flat}")

    # 与传统写法对照（两者等价）
    flat_loop: list[int] = []
    for row in matrix:
        for cell in row:
            flat_loop.append(cell)
    print(f"传统循环: {flat_loop}")


if __name__ == "__main__":
    main()
