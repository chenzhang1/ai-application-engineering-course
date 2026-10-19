# EX-07-02 | 魔术方法 | 运行: python3 示例代码/ch07_classes/ex_07_02_magic_methods.py
from collections.abc import Iterator


class Playlist:
    """一个支持 len、下标、迭代、相等性的播放列表。"""

    def __init__(self, name: str, songs: list[str] | None = None) -> None:
        self.name = name
        # 注意 list(songs) 做了一次拷贝，避免与调用者的列表共享（对照 ch04）
        self._songs: list[str] = list(songs) if songs else []

    def add(self, song: str) -> None:
        self._songs.append(song)

    def __len__(self) -> int:                    # 支持 len(p)
        return len(self._songs)

    def __getitem__(self, index: int) -> str:    # 支持 p[i]，同时让对象可迭代
        return self._songs[index]

    def __iter__(self) -> Iterator[str]:         # 支持 for song in p
        return iter(self._songs)

    def __repr__(self) -> str:                   # 支持 repr(p)，调试显示也用它
        return f"Playlist({self.name!r}, songs={self._songs!r})"

    def __eq__(self, other: object) -> bool:     # 支持 p == q
        if not isinstance(other, Playlist):
            return NotImplemented
        return self.name == other.name and self._songs == other._songs

    def __hash__(self) -> int:                   # 定义了 __eq__ 就必须显式定义 __hash__ 才能进 set/dict
        return hash((self.name, tuple(self._songs)))


def main() -> None:
    p = Playlist("工作歌单", ["Env", "Beyond"])
    p.add("Focus")
    print(f"repr  -> {p!r}")
    print(f"len   -> {len(p)}")
    print(f"p[0]  -> {p[0]}，p[-1] -> {p[-1]}")
    print(f"迭代  -> {[s for s in p]}")

    q = Playlist("工作歌单", ["Env", "Beyond", "Focus"])
    print(f"p == q: {p == q}，p is q: {p is q}")
    print(f"hash(p) == hash(q): {hash(p) == hash(q)}")
    print(f"放进 set 去重后元素个数: {len({p, q})}")


if __name__ == "__main__":
    main()
