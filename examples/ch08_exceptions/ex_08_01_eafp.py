# EX-08-01 | EAFP vs LBYL | 运行: python3 examples/ch08_exceptions/ex_08_01_eafp.py
from pathlib import Path


def lbyl_get(mapping: dict[str, int], key: str) -> int | None:
    """Look Before You Leap：先检查再使用（Java 风格）。"""
    if key in mapping:
        return mapping[key]
    return None


def eafp_get(mapping: dict[str, int], key: str) -> int | None:
    """Easier to Ask Forgiveness than Permission：先做，出错再处理（Python 风格）。"""
    try:
        return mapping[key]
    except KeyError:
        return None


def main() -> None:
    scores: dict[str, int] = {"alice": 90}
    print(f"LBYL 命中: {lbyl_get(scores, 'alice')}，未命中: {lbyl_get(scores, 'bob')}")
    print(f"EAFP 命中: {eafp_get(scores, 'alice')}，未命中: {eafp_get(scores, 'bob')}")

    # EAFP 更顺手的场景：逐条转换"脏数据"，坏的跳过
    raw_values = ["42", "  7 ", "3.5", "abc", ""]
    for raw in raw_values:
        try:
            value: int | str = int(raw)
        except ValueError:
            value = f"失败({type(raw).__name__}无法转int)"
        print(f"int({raw!r}) -> {value}")

    # 对照：LBYL 的"检查"与"使用"之间存在竞态窗口；对文件更推荐直接 EAFP
    p = Path("/definitely/not/exist.txt")
    try:
        text = p.read_text(encoding="utf-8")
        print(f"读到 {len(text)} 字符")
    except FileNotFoundError as exc:
        print(f"直接读 -> FileNotFoundError: {exc.strerror}: {exc.filename}")


if __name__ == "__main__":
    main()
