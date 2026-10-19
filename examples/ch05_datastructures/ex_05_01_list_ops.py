# EX-05-01 | list 常用操作 | 运行: python3 examples/ch05_datastructures/ex_05_01_list_ops.py
def main() -> None:
    nums: list[int] = [3, 1, 2]
    nums.append(4)               # 尾部追加
    nums.extend([0, 5])          # 合并另一个可迭代对象
    nums.insert(0, 9)            # 指定位置插入
    print(f"构造后: {nums}")

    last: int = nums.pop()       # 弹出末尾
    first: int = nums.pop(0)     # 弹出指定下标
    nums.remove(2)               # 按值删除第一个匹配
    print(f"pop 得到 {last} 和 {first}，remove(2) 后: {nums}")

    nums.sort()                  # 原地排序，返回 None（注意！）
    print(f"sort 后: {nums}")
    print(f"sorted 副本（倒序）: {sorted(nums, reverse=True)}，原列表仍是 {nums}")

    print(f"index(1) = {nums.index(1)}，count(1) = {nums.count(1)}")
    print(f"len = {len(nums)}，min = {min(nums)}，max = {max(nums)}，sum = {sum(nums)}")

    words: list[str] = ["banana", "apple", "cherry"]
    words.sort(key=len)          # key 函数：按长度排序（稳定排序，同长度保持原顺序）
    print(f"按长度排序: {words}")


if __name__ == "__main__":
    main()
