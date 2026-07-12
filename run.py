"""每月抓取 ThreatHunter 目标文章并生成 HTML。"""

import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

from config import BASE_DIR, HISTORY_FILE, RUN_DAY, TITLE_KEYWORDS
from crawler import fetch_articles
from html_exporter import export_article_html
from processor import process_html


KEYWORD_PATTERN = re.compile("|".join(map(re.escape, TITLE_KEYWORDS)))


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
    return package_file.exists() and package_file.suffix == ".zip"


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
) -> dict[str, int | str]:
    """处理单篇文章并返回状态。"""
    title = article["title"]
    url = article["url"]

    history_record = find_history_record(url)
    if history_record:
        published_value = history_record.get("outputs", {}).get("published_date")
        if published_value:
            published_date = date.fromisoformat(published_value)
            if not period_start <= published_date <= period_end:
                print(f"跳过日期范围外文章：{published_date} · {title}")
                return {"status": "outside"}
        if package_exists(history_record):
            print(f"跳过 history 已有文章：{title}")
            return {"status": "skipped"}
        print(f"history 存在但文章包缺失，重新生成：{title}")

    html_path = None
    try:
        result = export_article_html(article, period_start, period_end)
        if result is None:
            return {"status": "outside"}
        html_path, published_date = result
        process_result = process_html(html_path, source_url=url)
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
        return {"status": "failed"}
    finally:
        if html_path:
            html_path.unlink(missing_ok=True)

    print(f"文章打包成功：{relative_package_path}")
    return {
        "status": "processed",
        "package_saved": 1,
        "image_success": process_result.image_success_count,
        "image_failed": process_result.image_failed_count,
    }


def main() -> None:
    """运行月度采集任务。"""
    force_run = "--force" in sys.argv[1:]
    today = date.today()
    if today.day != RUN_DAY and not force_run:
        print(f"今天是 {today:%Y-%m-%d}，正式任务仅在每月 {RUN_DAY} 日运行。")
        print("如需手动测试，请运行：python3 run.py --force")
        return

    period_start, period_end = get_monthly_period(today)
    print("开始检查 ThreatHunter 文章并生成 HTML。")
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

    if not target_articles:
        print("没有需要处理的目标文章。")
        return

    result_counts = {
        "processed": 0,
        "skipped": 0,
        "outside": 0,
        "failed": 0,
        "package_saved": 0,
        "image_success": 0,
        "image_failed": 0,
    }

    for article in target_articles:
        result = process_article(article, period_start, period_end)
        result_counts[result["status"]] += 1
        result_counts["package_saved"] += result.get("package_saved", 0)
        result_counts["image_success"] += result.get("image_success", 0)
        result_counts["image_failed"] += result.get("image_failed", 0)
        print()

    print("本次运行完成：")
    print(f"- 新处理：{result_counts['processed']} 篇")
    print(f"- 已跳过：{result_counts['skipped']} 篇")
    print(f"- 日期范围外：{result_counts['outside']} 篇")
    print(f"- 失败：{result_counts['failed']} 篇")
    print(f"- 文章打包数量：{result_counts['package_saved']}")
    print(f"- 图片下载成功数量：{result_counts['image_success']}")
    print(f"- 图片下载失败数量：{result_counts['image_failed']}")


if __name__ == "__main__":
    main()
