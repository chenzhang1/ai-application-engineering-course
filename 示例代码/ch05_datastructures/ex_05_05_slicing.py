# EX-05-05 | 切片 | 运行: python3 示例代码/ch05_datastructures/ex_05_05_slicing.py
def main() -> None:
    data: list[int] = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]

    print(f"data[2:5]    = {data[2:5]}     # 下标 2 到 4（不含 5）")
    print(f"data[:3]     = {data[:3]}      # 省略起点 = 从头开始")
    print(f"data[7:]     = {data[7:]}      # 省略终点 = 一直到尾")
    print(f"data[-3:]    = {data[-3:]}     # 负下标：最后三个")
    print(f"data[::2]    = {data[::2]}     # 步长 2")
    print(f"data[::-1]   = {data[::-1]}    # 步长 -1：反转")
    print(f"data[5:2:-1] = {data[5:2:-1]}  # 逆序切片")

    # 越界不报错（这与下标访问不同）
    print(f"data[5:100]  = {data[5:100]}")

    # 切片是浅拷贝：得到新列表（对照 ch04）
    copy_via_slice: list[int] = data[:]
    print(f"data[:] is data: {copy_via_slice is data}")

    # 切片赋值：一次替换一段，甚至改变列表长度
    nums = [1, 2, 3, 4, 5]
    nums[1:3] = [20, 30, 99]
    print(f"切片赋值后 nums = {nums}")

    text: str = "Hello,Python"
    print(f"字符串同样支持切片: {text[7:]} / {text[::-1]}")


if __name__ == "__main__":
    main()
