# EX-08-03 | 异常链 raise ... from ... | 运行: python3 示例代码/ch08_exceptions/ex_08_03_exception_chain.py
import json
import traceback
from pathlib import Path


class DataLoadError(Exception):
    """数据加载失败。"""


def load_records(path: str) -> list[dict[str, str]]:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError as exc:
        # 语义升级：底层细节 -> 业务语言，同时保留原始异常（__cause__）
        raise DataLoadError(f"知识库文件不可用: {path}") from exc


def load_records_quiet(path: str) -> list[dict[str, str]]:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError as exc:
        # from None：抑制内部细节（对外接口可用，但会丢排查线索，慎用）
        raise DataLoadError(f"知识库文件不可用: {path}") from None


def main() -> None:
    try:
        load_records("/definitely/missing.json")
    except DataLoadError:
        print("=== raise ... from exc 的完整堆栈 ===")
        print(traceback.format_exc())

    try:
        load_records_quiet("/definitely/missing.json")
    except DataLoadError as exc:
        print("=== raise ... from None 的堆栈 ===")
        print(f"只抛出 {type(exc).__name__}: {exc}，__cause__ = {exc.__cause__}（内部细节被抑制）")


if __name__ == "__main__":
    main()
