# EX-05-03 | dict 与 set | 运行: python3 examples/ch05_datastructures/ex_05_03_dict_set.py
def main() -> None:
    # dict：键值对。3.7+ 语言规范保证按插入顺序遍历
    user: dict[str, str] = {"name": "alice", "role": "admin"}
    user["email"] = "a@example.com"           # 新增；对已有 key 则覆盖
    print(f"user['name'] = {user['name']}")
    print(f"get 不抛异常: user.get('phone') = {user.get('phone')!r}")
    print(f"get 带默认值: {user.get('phone', '未绑定')}")
    print(f"插入顺序遍历 keys: {list(user.keys())}")

    removed: str = user.pop("role")
    print(f"pop('role') = {removed}，剩余 keys = {list(user)}")

    defaults: dict[str, str] = {"role": "guest", "theme": "light"}
    merged: dict[str, str] = defaults | user  # 3.9+ 合并运算符：右侧优先
    print(f"| 合并 = {merged}")
    defaults.update(user)
    print(f"update 后 defaults = {defaults}")

    # set：元素唯一且必须可哈希；遍历顺序不保证（下面用 sorted 展示）
    tags1: set[str] = {"java", "python", "sql"}
    tags2: set[str] = {"python", "docker"}
    print(f"并集 |: {sorted(tags1 | tags2)}")
    print(f"交集 &: {sorted(tags1 & tags2)}")
    print(f"差集 -: {sorted(tags1 - tags2)}")
    print(f"对称差 ^: {sorted(tags1 ^ tags2)}")
    print(f"list 去重: {sorted({1, 2, 2, 3, 3, 3})}")
    probe: set[str] = {"python", "docker"}
    print(f"子集判断: probe <= tags2 = {probe <= tags2}")


if __name__ == "__main__":
    main()
