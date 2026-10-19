# EX-12-02 | pathlib 与 datetime 时区：naive vs aware 的坑
# 运行：python3 examples/ch12_stdlib_project/ex_12_02_pathlib_timezone.py
"""完整可运行：路径即对象；时间必须"带时区"——naive/aware 混用会当场报错。"""
from __future__ import annotations

import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent


def shanghai_tz() -> ZoneInfo | timezone:
    """优先 zoneinfo（IANA 时区库），Windows 缺 tzdata 时退回固定偏移。"""
    try:
        return ZoneInfo("Asia/Shanghai")
    except Exception:  # ZoneInfoNotFoundError 等：教学环境兜底
        return timezone(timedelta(hours=8))


def main() -> None:
    print("[1] pathlib：路径是对象，不是字符串拼接（告别 \\ 和 / 的地狱）")
    demo_dir = HERE / "_demo_files" / "logs"
    demo_dir.mkdir(parents=True, exist_ok=True)  # 一次建多层目录，已存在不报错
    log_file = demo_dir / "app-2026-10-19.log"
    log_file.write_text("INFO 启动完成\n", encoding="utf-8")
    print("    创建:", log_file)
    print("    name =", log_file.name, "| stem =", log_file.stem,
          "| suffix =", log_file.suffix, "| parent.name =", log_file.parent.name)
    for p in sorted(demo_dir.parent.glob("*.log")):
        print("    glob 命中:", p.relative_to(HERE))

    print("\n[2] datetime：naive（天真）vs aware（带时区）")
    naive = datetime(2026, 10, 19, 9, 30, 0)                     # 没有时区信息
    aware_utc = datetime(2026, 10, 19, 9, 30, 0, tzinfo=timezone.utc)  # 明确是 UTC
    print("    naive     =", naive.isoformat(), "| tzinfo =", naive.tzinfo)
    print("    aware_utc =", aware_utc.isoformat())
    try:
        _ = naive < aware_utc  # 混比：Python 直接拒绝，防止你悄悄算错 8 小时
    except TypeError as exc:
        print("    naive < aware → TypeError:", exc)

    print("\n[3] 时区转换：同一时刻，不同钟面")
    sh = aware_utc.astimezone(shanghai_tz())
    print(f"    {aware_utc.isoformat()}  ==  {sh.isoformat()}（同一时刻！）")

    print("\n[4] 解析 ISO 8601 字符串（GitHub API 返回的时间长这样）")
    parsed = datetime.fromisoformat("2026-10-19T01:23:45Z")  # 3.11+ 直接支持 Z
    print("    fromisoformat('...Z') →", parsed.isoformat())
    # Python 3.10 及更早不认 'Z'，要先替换：datetime.fromisoformat(s.replace('Z', '+00:00'))

    print("\n[5] 历史坑：utcnow() 已废弃（3.12 起警告），它返回的是 naive 对象")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        legacy = datetime.utcnow()
    for w in caught:
        print(f"    触发警告 {w.category.__name__}: {w.message}")
    print(f"    datetime.utcnow() → {legacy.isoformat()}  tzinfo={legacy.tzinfo} ← 没有时区！")
    now_aware = datetime.now(timezone.utc)  # 正确姿势
    print(f"    datetime.now(timezone.utc) → {now_aware.isoformat()} ← aware，放心用")

    # 清理演示文件
    log_file.unlink()
    demo_dir.rmdir()
    demo_dir.parent.rmdir()


if __name__ == "__main__":
    main()
