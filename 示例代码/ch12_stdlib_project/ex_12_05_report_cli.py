# EX-12-05 | 收束项目：接口数据清洗报告 CLI（GitHub 仓库洞察）
# 运行（在仓库根目录 ai_application_course/ 下）：
#   python3 示例代码/ch12_stdlib_project/ex_12_05_report_cli.py                      # auto：先联网，失败自动回退本地样本
#   python3 示例代码/ch12_stdlib_project/ex_12_05_report_cli.py --source local       # 纯离线
#   python3 示例代码/ch12_stdlib_project/ex_12_05_report_cli.py --output report.json # 报告落盘
#   python3 示例代码/ch12_stdlib_project/ex_12_05_report_cli.py --dump-json sample_data.json  # 重新抓取并更新本地样本
"""完整可运行：json + pathlib + datetime 时区 + re + argparse 的一次综合演练。

数据流：GitHub REST API（或本地兜底样本）→ 字段提取/时间格式化/正则提版本 → JSON 报告。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

REPO_SLUG = "langchain-ai/langgraph"
API_URL = f"https://api.github.com/repos/{REPO_SLUG}"
HERE = Path(__file__).resolve().parent
SAMPLE_PATH = HERE / "sample_data.json"
TAG_PATTERN = re.compile(r"^v(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)$")
REQUEST_HEADERS = {"User-Agent": "textbook-stdlib-demo", "Accept": "application/vnd.github+json"}


# ---------- 数据获取层 ----------

def fetch_online() -> dict[str, Any]:
    """真实联网抓取。httpx 在 requirements.txt 中（ch15 会专门讲工程化 HTTP 客户端）。"""
    import httpx  # 按需导入：离线路径完全不依赖第三方库

    with httpx.Client(timeout=10.0, headers=REQUEST_HEADERS) as client:
        repo_resp = client.get(API_URL)
        repo_resp.raise_for_status()  # 非 2xx 抛 HTTPStatusError（ch08 异常链思想）
        tags_resp = client.get(f"{API_URL}/tags", params={"per_page": 5})
        tags_resp.raise_for_status()
    return {"repo": repo_resp.json(), "tags": tags_resp.json()}


def load_local() -> dict[str, Any]:
    """回退路径：读取打包的真实样本（抓取记录见 验证报告/运行日志/part02b.md）。"""
    if not SAMPLE_PATH.exists():
        raise FileNotFoundError(f"本地样本不存在：{SAMPLE_PATH}")
    return json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))


# ---------- 清洗与统计层 ----------

def to_shanghai(iso_text: str) -> str:
    """'2024-01-30T17:33:42Z' → 北京时间可读字符串（naive/aware 见 ex_12_02）。"""
    dt = datetime.fromisoformat(iso_text.replace("Z", "+00:00"))  # 3.10 兼容写法，3.11+ 可省 replace
    try:
        target = ZoneInfo("Asia/Shanghai")
    except Exception:
        target = timezone(timedelta(hours=8))
    return dt.astimezone(target).strftime("%Y-%m-%d %H:%M:%S") + " (UTC+8)"


def parse_versions(tags: list[dict[str, Any]]) -> dict[str, Any]:
    """正则提取版本号 + semver 排序（字符串排序会闹 '0.10.2' < '0.9.1' 的笑话）。"""
    versions: list[dict[str, Any]] = []
    skipped: list[str] = []
    for tag in tags:
        name = tag.get("name", "")
        m = TAG_PATTERN.match(name)
        if m is None:
            skipped.append(name)
            continue
        versions.append({"tag": name, "version": m.group(0)[1:],
                         "semver": (int(m["major"]), int(m["minor"]), int(m["patch"]))})
    versions.sort(key=lambda v: v["semver"])
    return {
        "count": len(versions),
        "versions": [{"tag": v["tag"], "version": v["version"]} for v in versions],
        "max_in_batch": versions[-1]["version"] if versions else None,
        "skipped_non_semver": skipped,
    }


def build_report(payload: dict[str, Any], data_source: str) -> dict[str, Any]:
    """把原始 payload 清洗成结构化报告（全部字段带缺省兜底，接口字段不可全信）。"""
    repo = payload.get("repo", {}) or {}
    tags = payload.get("tags", []) or []
    license_info = repo.get("license") or {}
    created_at: str = repo.get("created_at") or ""
    pushed_at: str = repo.get("pushed_at") or ""
    return {
        "meta": {
            "data_source": data_source,          # online | local-fallback | local
            "generated_at": datetime.now(timezone.utc)
                              .astimezone(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
            "upstream_api": API_URL,
        },
        "repo": {
            "full_name": repo.get("full_name", "未知"),
            "description": repo.get("description", ""),
            "language": repo.get("language", "未知"),
            "stars": repo.get("stargazers_count", 0),
            "forks": repo.get("forks_count", 0),
            "open_issues": repo.get("open_issues_count", 0),
            "default_branch": repo.get("default_branch", ""),
            "license": license_info.get("spdx_id", "无"),
            "created_at_utc": created_at,
            "created_at_cn": to_shanghai(created_at) if created_at else "",
            "pushed_at_cn": to_shanghai(pushed_at) if pushed_at else "",
        },
        "versions": parse_versions(tags),
    }


# ---------- CLI 层 ----------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="report-cli",
        description="拉取 GitHub 公开仓库数据做清洗统计，输出 JSON 报告（教材 ch12 收束项目）",
    )
    parser.add_argument("--source", choices=["auto", "online", "local"], default="auto",
                        help="auto=先联网失败回退本地（默认）；online=只联网；local=只本地")
    parser.add_argument("--output", type=Path, default=None, help="报告写入的 JSON 文件路径")
    parser.add_argument("--dump-json", type=Path, default=None, metavar="PATH",
                        help="（联网成功时）把原始抓取结果存成新的本地样本")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload: dict[str, Any] | None = None
    data_source = ""

    if args.source in ("auto", "online"):
        try:
            payload = fetch_online()
            data_source = "online"
            if args.dump_json is not None:
                args.dump_json.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                print(f"[样本更新] 原始抓取结果已写入 {args.dump_json}", file=sys.stderr)
        except Exception as exc:  # 网络/HTTP 一切失败都走这里
            if args.source == "online":
                print(f"[错误] 在线获取失败且指定 --source online，不回退：{exc}", file=sys.stderr)
                return 1
            print(f"[模式提示] 网络不可用（{type(exc).__name__}: {exc}）", file=sys.stderr)
            print(f"[模式提示] 已自动回退到打包的本地样本 sample_data.json"
                  f"（真实抓取于 2026-10-19，数字为抓取时点快照）", file=sys.stderr)
            data_source = "local-fallback"

    if payload is None:
        try:
            payload = load_local()
            data_source = data_source or "local"
        except Exception as exc:
            print(f"[错误] 本地样本也无法加载：{exc}", file=sys.stderr)
            return 1

    report = build_report(payload, data_source)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.output is not None:
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                               encoding="utf-8")
        print(f"[报告落盘] {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
