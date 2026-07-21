"""ThreatHunter 公开研究列表抓取。"""

from __future__ import annotations

import html
import re
from urllib.parse import urljoin

from config import REPORT_URL


REQUEST_TIMEOUT_SECONDS = 30


def fetch_articles() -> list[dict[str, str]]:
    """返回公开研究列表中的标题、日期、链接、分类和标签。"""
    try:
        import requests
    except ImportError as error:
        raise RuntimeError("缺少 requests，请先运行：bash setup.sh") from error

    print(f"请求的初始 URL：{REPORT_URL}")
    try:
        response = requests.get(
            REPORT_URL,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        raise RuntimeError(f"公开研究列表请求失败：{error}") from error

    print(f"重定向后的最终 URL：{response.url}")
    articles = parse_research_articles(response.text)
    print(f"是否找到文章列表：{'是' if articles else '否'}")
    print(f"共发现 {len(articles)} 篇公开研究")
    return articles


def parse_research_articles(page_html: str) -> list[dict[str, str]]:
    """从新版研究页提取所有公开研究。"""
    articles = parse_embedded_research_data(page_html)
    if articles:
        return articles
    return parse_dom_research_cards(page_html)


def parse_embedded_research_data(page_html: str) -> list[dict[str, str]]:
    """从 Next.js 页面内嵌数据中提取完整研究列表。"""
    decoded_html = html.unescape(page_html).replace('\\"', '"')
    pattern = re.compile(
        r'"slug":"(?P<slug>[^"]+)".*?'
        r'"title":"(?P<title>[^"]+)".*?'
        r'"category":"(?P<category>[^"]*)".*?'
        r'"publishedAt":"(?P<date>\d{4}-\d{2}-\d{2})".*?'
        r'"tags":\[(?P<tags>[^\]]*)\]',
        re.DOTALL,
    )

    raw_articles = []
    for match in pattern.finditer(decoded_html):
        raw_articles.append(
            {
                "title": clean_text(match.group("title")),
                "date": match.group("date"),
                "url": urljoin(REPORT_URL, f"/research/{match.group('slug')}"),
                "category": clean_text(match.group("category")),
                "tags": ", ".join(parse_tags(match.group("tags"))),
            }
        )
    return clean_articles(raw_articles)


def parse_dom_research_cards(page_html: str) -> list[dict[str, str]]:
    """从页面卡片 DOM 中提取研究列表，作为内嵌数据解析失败时的兜底。"""
    try:
        from bs4 import BeautifulSoup
    except ImportError as error:
        raise RuntimeError("缺少 beautifulsoup4，请先运行：bash setup.sh") from error

    soup = BeautifulSoup(page_html, "html.parser")
    raw_articles = []
    for card in soup.select(".featured-report-panel, article.report-card"):
        title_node = card.select_one("h2 a[href]")
        if not title_node:
            continue
        time_node = card.select_one("time")
        tag_nodes = card.select(".report-card-tags span")
        tags = [
            clean_text(tag.get_text(" ", strip=True))
            for tag in tag_nodes
            if "report-edition-tag" not in tag.get("class", [])
        ]

        raw_articles.append(
            {
                "title": clean_text(title_node.get_text(" ", strip=True)),
                "date": (time_node.get("datetime") or "")[:10] if time_node else "",
                "url": urljoin(REPORT_URL, title_node.get("href", "")),
                "category": clean_text(get_card_category(card)),
                "tags": ", ".join(tag for tag in tags if tag),
            }
        )
    return clean_articles(raw_articles)


def get_card_category(card) -> str:
    """提取研究卡片分类。"""
    category_node = card.select_one(".card-kicker")
    return category_node.get_text(" ", strip=True) if category_node else ""


def parse_tags(raw_tags: str) -> list[str]:
    """解析内嵌数据中的标签数组。"""
    return [clean_text(tag) for tag in re.findall(r'"([^"]+)"', raw_tags)]


def clean_articles(raw_articles: list[dict[str, str]]) -> list[dict[str, str]]:
    """清理重复和无效研究。"""
    articles: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    for article in raw_articles:
        title = article.get("title", "").strip()
        url = article.get("url", "").strip()
        if not title or not url or url in seen_urls:
            continue

        seen_urls.add(url)
        articles.append(
            {
                "title": title,
                "date": article.get("date", "").strip(),
                "url": url,
                "category": article.get("category", "").strip(),
                "tags": article.get("tags", "").strip(),
            }
        )

    return articles


def clean_text(text: str) -> str:
    """清理页面文本中的多余空白。"""
    return re.sub(r"\s+", " ", text).strip()
