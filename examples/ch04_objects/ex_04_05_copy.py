# EX-04-05 | 浅拷贝与深拷贝 | 运行: python3 examples/ch04_objects/ex_04_05_copy.py
import copy


def main() -> None:
    original: dict[str, list[int]] = {"scores": [90, 85], "owner": "alice"}

    alias = original                        # 不是拷贝，只是别名
    shallow = copy.copy(original)           # 浅拷贝：外层新建，内层仍共享
    deep = copy.deepcopy(original)          # 深拷贝：逐层递归复制

    # 外层：alias 是同一个对象；shallow/deep 是新对象
    print(f"alias is original:   {alias is original}")
    print(f"shallow is original: {shallow is original}")
    print(f"deep is original:    {deep is original}")

    # 内层：浅拷贝的 list 与原对象是同一个；深拷贝不是
    print(f"shallow['scores'] is original['scores']: {shallow['scores'] is original['scores']}")
    print(f"deep['scores']    is original['scores']: {deep['scores'] is original['scores']}")

    # 通过浅拷贝改内层，original 跟着变；深拷贝不受影响
    shallow["scores"].append(70)
    print(f"浅拷贝追加后 original = {original}")
    deep["scores"].append(60)
    print(f"深拷贝追加后 original = {original}（不受影响）")
    print(f"deep = {deep}")


if __name__ == "__main__":
    main()
