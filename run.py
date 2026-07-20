"""每月抓取 ThreatHunter 目标文章并生成 Article Package ZIP。"""

from __future__ import annotations

import argparse
import getpass
import importlib.util
import json
import re
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from config import BASE_DIR, HISTORY_FILE, RUN_DAY, TITLE_KEYWORDS


KEYWORD_PATTERN = re.compile("|".join(map(re.escape, TITLE_KEYWORDS)))
REQUIRED_MODULES = {
    "playwright": "playwright",
    "beautifulsoup4": "bs4",
    "requests": "requests",
}


@dataclass
class RunContext:
    report_topic: str
    report_website: str
    report_date: str
    report_vendor: str
    run_by: str
    run_at: str
    run_timezone: str
    push_github: bool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="抓取 ThreatHunter 文章并生成 Article Package ZIP。"
    )
    parser.add_argument("--force", action="store_true", help="非 25 日也允许手动运行")
    parser.add_argument("--push-github", action="store_true", help="处理完成后提交并推送 ZIP")
    parser.add_argument("--report-topic", default="", help="报告主题")
    parser.add_argument("--report-website", default="", help="报告网站或文章来源网址")
    parser.add_argument("--report-date", default="", help="报告发布时间，格式 YYYY-MM-DD")
    parser.add_argument("--report-vendor", default="", help="报告厂商或来源机构")
    parser.add_argument("--run-by", default="", help="运行人")
    args = parser.parse_args()

    if args.report_date:
        validate_report_date(args.report_date)
    return args


def validate_report_date(report_date: str) -> None:
    try:
        datetime.strptime(report_date, "%Y-%m-%d")
    except ValueError:
        print("report-date 格式错误，请使用 YYYY-MM-DD，例如：2026-05-28")
        raise SystemExit(2)


def ensure_dependencies() -> None:
    missing_packages = [
        package
        for package, module in REQUIRED_MODULES.items()
        if importlib.util.find_spec(module) is None
    ]
    if not missing_packages:
        return

    print("当前 Python 环境缺少项目依赖。")
    print(f"当前解释器：{sys.executable}")
    print(f"缺少依赖：{', '.join(missing_packages)}")
    print("请先执行：")
    print("python3 -m pip install -r requirements.txt")
    print("python3 -m playwright install chromium")
    raise SystemExit(1)


def build_run_context(args: argparse.Namespace) -> RunContext:
    now = datetime.now().astimezone()
    return RunContext(
        report_topic=args.report_topic.strip(),
        report_website=args.report_website.strip(),
        report_date=args.report_date.strip(),
        report_vendor=args.report_vendor.strip() or "ThreatHunter",
        run_by=args.run_by.strip() or get_current_user(),
        run_at=now.strftime("%Y-%m-%d %H:%M:%S"),
        run_timezone=now.strftime("%Z%z"),
        push_github=args.push_github,
    )


def get_current_user() -> str:
    try:
        return getpass.getuser() or "未提及"
    except Exception:
        return "未提及"


def get_monthly_period(reference_date: date) -> tuple[date, date]:
    """返回最近完成的月度采集窗口。"""
    if reference_date.day >= RUN_DAY:
        end_year = reference_date.year
        end_month = reference_date.month
    elif reference_date.month == 1:
        end_year = reference_date.year - 1
        end_month = 12
    else:
        end_year = reference_date.year
        end_month = reference_date.month - 1

    period_end = date(end_year, end_month, RUN_DAY)
    if end_month == 1:
        period_start = date(end_year - 1, 12, RUN_DAY)
    else:
        period_start = date(end_year, end_month - 1, RUN_DAY)
    return period_start, period_end


def filter_articles(articles: list[dict[str, str]]) -> list[dict[str, str]]:
    """筛选标题命中关键词的文章。"""
    return [
        article
        for article in articles
        if KEYWORD_PATTERN.search(article.get("title", "").strip())
    ]


def load_history(history_file: Path = HISTORY_FILE) -> list[dict[str, object]]:
    """读取历史记录；文件不存在时返回空列表。"""
    if not history_file.exists():
        return []

    try:
        with history_file.open("r", encoding="utf-8") as file:
            records = json.load(file)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"历史记录文件格式错误：{history_file}") from error

    if not isinstance(records, list):
        raise RuntimeError("历史记录的最外层必须是 JSON 列表。")
    return records


def find_history_record(
    article_url: str,
    history_file: Path = HISTORY_FILE,
) -> dict[str, object] | None:
    """查找指定文章的历史记录。"""
    records = load_history(history_file)
    return next(
        (record for record in records if record.get("url") == article_url),
        None,
    )


def add_history(
    article: dict[str, str],
    outputs: dict[str, str],
    history_file: Path = HISTORY_FILE,
) -> None:
    """记录已成功处理的文章。"""
    article_url = article["url"].strip()
    records = load_history(history_file)
    for record in records:
        if record.get("url") == article_url:
            record["outputs"] = outputs
            record["processed_at"] = datetime.now().astimezone().isoformat(
                timespec="seconds"
            )
            save_history(records, history_file)
            return

    records.append(
        {
            "title": article.get("title", "").strip(),
            "url": article_url,
            "outputs": outputs,
            "processed_at": datetime.now().astimezone().isoformat(
                timespec="seconds"
            ),
        }
    )
    save_history(records, history_file)


def package_exists(history_record: dict[str, object]) -> bool:
    outputs = history_record.get("outputs", {})
    if not isinstance(outputs, dict):
        return False

    package_path = outputs.get("package_path")
    if not isinstance(package_path, str):
        return False

    package_file = BASE_DIR / package_path
    if not package_file.exists() or package_file.suffix != ".zip":
        return False

    try:
        with zipfile.ZipFile(package_file) as zip_file:
            metadata = json.loads(zip_file.read("metadata.json").decode("utf-8"))
    except (KeyError, OSError, json.JSONDecodeError, zipfile.BadZipFile):
        return False

    return metadata.get("generator") == "threat_hunter_auto"


def save_history(records: list[dict[str, object]], history_file: Path) -> None:
    """保存历史记录。"""
    history_file.parent.mkdir(parents=True, exist_ok=True)
    with history_file.open("w", encoding="utf-8") as file:
        json.dump(records, file, ensure_ascii=False, indent=2)
        file.write("\n")


def process_article(
    article: dict[str, str],
    period_start: date,
    period_end: date,
    run_context: RunContext,
    export_article_html,
    process_html,
) -> dict[str, object]:
    """处理单篇文章并返回状态。"""
    title = article["title"]
    url = article["url"]

    history_record = find_history_record(url)
    if history_record:
        published_value = history_record.get("outputs", {}).get("published_date")
        if published_value:
            published_date = date.fromisoformat(str(published_value))
            if not period_start <= published_date <= period_end:
                print(f"跳过日期范围外文章：{published_date} · {title}")
                return {"status": "outside", "package_path": None}
        if package_exists(history_record) and not has_report_overrides(run_context):
            print(f"跳过 history 已有文章：{title}")
            return {"status": "skipped", "package_path": None}
        print(f"需要生成或更新文章包：{title}")

    html_path = None
    try:
        result = export_article_html(article, period_start, period_end)
        if result is None:
            return {"status": "outside", "package_path": None}
        html_path, published_date = result
        report_options = build_article_report_options(
            run_context=run_context,
            article_url=url,
            published_date=published_date,
        )
        process_result = process_html(
            html_path,
            source_url=url,
            report_options=report_options,
        )
        relative_package_path = process_result.package_path.relative_to(BASE_DIR)
        add_history(
            article,
            {
                "package_path": str(relative_package_path),
                "published_date": published_date,
            },
        )
    except (RuntimeError, OSError) as error:
        print(f"处理失败：{title}")
        print(f"失败原因：{error}")
        return {"status": "failed", "package_path": None}
    finally:
        if html_path:
            html_path.unlink(missing_ok=True)

    print(f"文章打包成功：{relative_package_path}")
    return {
        "status": "processed",
        "package_saved": 1,
        "image_success": process_result.image_success_count,
        "image_failed": process_result.image_failed_count,
        "package_path": process_result.package_path,
    }


def has_report_overrides(run_context: RunContext) -> bool:
    return any(
        (
            run_context.report_topic,
            run_context.report_website,
            run_context.report_date,
            run_context.report_vendor != "ThreatHunter",
            run_context.run_by != get_current_user(),
        )
    )


def build_article_report_options(
    run_context: RunContext,
    article_url: str,
    published_date: str,
) -> dict[str, str]:
    return {
        "report_topic": run_context.report_topic,
        "report_website": run_context.report_website or article_url,
        "report_date": run_context.report_date or published_date,
        "report_vendor": run_context.report_vendor,
        "run_by": run_context.run_by,
        "run_at": run_context.run_at,
        "run_timezone": run_context.run_timezone,
    }


def upload_packages_to_github(package_paths: list[Path]) -> str:
    if not package_paths:
        print("没有需要上传的新文件")
        return "没有需要上传的新文件"

    try:
        ensure_git_remote()
        relative_paths = [str(path.relative_to(BASE_DIR)) for path in package_paths]
        run_git(["git", "add", "--", *relative_paths])
        diff_result = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", *relative_paths],
            cwd=BASE_DIR,
            check=False,
        )
        if diff_result.returncode == 0:
            print("没有需要上传的新文件")
            return "没有需要上传的新文件"

        message = f"Add ThreatHunter packages: {datetime.now():%Y-%m-%d %H:%M}"
        run_git(["git", "commit", "-m", message])
        run_git(["git", "push", "origin", "main"])
    except RuntimeError as error:
        print(f"GitHub 上传失败：{error}")
        return "失败，本地文件已保留"

    return "成功"


def ensure_git_remote() -> None:
    result = subprocess.run(
        ["git", "remote", "-v"],
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0 or "origin" not in result.stdout:
        raise RuntimeError("当前仓库未配置 origin 远程地址。")


def run_git(command: list[str]) -> None:
    result = subprocess.run(
        command,
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(detail or "Git 命令执行失败。")


def main() -> None:
    """运行月度采集任务。"""
    args = parse_args()
    ensure_dependencies()

    from crawler import fetch_articles
    from html_exporter import export_article_html
    from processor import process_html

    run_context = build_run_context(args)
    today = date.today()
    if today.day != RUN_DAY and not args.force:
        print(f"今天是 {today:%Y-%m-%d}，正式任务仅在每月 {RUN_DAY} 日运行。")
        print("如需手动测试，请运行：python3 run.py --force")
        return

    period_start, period_end = get_monthly_period(today)
    print("开始检查 ThreatHunter 文章并生成 Article Package ZIP。")
    print(f"本期范围：{period_start} 至 {period_end}（含首尾日期）\n")

    try:
        articles = fetch_articles()
    except RuntimeError as error:
        print(f"程序结束：{error}")
        return

    target_articles = filter_articles(articles)

    print(
        f"\n共抓取 {len(articles)} 篇文章，"
        f"其中 {len(target_articles)} 篇符合筛选条件。\n"
    )

    result_counts = {
        "processed": 0,
        "skipped": 0,
        "outside": 0,
        "failed": 0,
        "package_saved": 0,
        "image_success": 0,
        "image_failed": 0,
    }
    package_paths: list[Path] = []

    for article in target_articles:
        result = process_article(
            article,
            period_start,
            period_end,
            run_context,
            export_article_html,
            process_html,
        )
        result_counts[str(result["status"])] += 1
        result_counts["package_saved"] += int(result.get("package_saved", 0))
        result_counts["image_success"] += int(result.get("image_success", 0))
        result_counts["image_failed"] += int(result.get("image_failed", 0))
        package_path = result.get("package_path")
        if isinstance(package_path, Path):
            package_paths.append(package_path)
        print()

    github_status = "未启用"
    if run_context.push_github:
        github_status = upload_packages_to_github(package_paths)

    print_summary(run_context, result_counts, github_status)


def print_summary(
    run_context: RunContext,
    result_counts: dict[str, int],
    github_status: str,
) -> None:
    print("本次运行完成：")
    print(f"运行人：{run_context.run_by}")
    print(f"运行时间：{run_context.run_at}")
    print(f"报告主题：{run_context.report_topic or '按文章标题自动生成'}")
    print(f"报告厂商：{run_context.report_vendor}")
    print(f"报告时间：{run_context.report_date or '按文章发布时间自动生成'}")
    print(f"报告网站：{run_context.report_website or '按文章实际 URL 自动生成'}")
    print(f"文章打包数量：{result_counts['package_saved']}")
    print(f"图片下载成功数量：{result_counts['image_success']}")
    print(f"图片下载失败数量：{result_counts['image_failed']}")
    print(f"GitHub上传状态：{github_status}")


if __name__ == "__main__":
    main()
