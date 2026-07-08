"""ThreatHunter 文章列表抓取。"""

from urllib.parse import urljoin

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from config import (
    ARTICLE_LINK_SELECTOR,
    BROWSER_CHANNEL,
    HEADLESS,
    PAGE_TIMEOUT_MS,
    REPORT_URL,
)


def fetch_articles() -> list[dict[str, str]]:
    """返回报告页中的文章标题和链接。"""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            channel=BROWSER_CHANNEL,
            headless=HEADLESS,
        )
        page = browser.new_page()
        page.set_default_timeout(PAGE_TIMEOUT_MS)

        try:
            print(f"正在打开：{REPORT_URL}")
            try:
                page.goto(
                    REPORT_URL,
                    wait_until="commit",
                    timeout=15_000,
                )
            except PlaywrightTimeoutError:
                print("页面响应较慢，继续等待文章链接。")

            article_links = page.locator(ARTICLE_LINK_SELECTOR)
            article_links.first.wait_for(
                state="attached",
                timeout=PAGE_TIMEOUT_MS,
            )

            raw_articles = article_links.evaluate_all(
                """
                links => links.map(link => ({
                    title: (link.textContent || "").trim(),
                    url: link.href
                }))
                """
            )
        except PlaywrightTimeoutError as error:
            raise RuntimeError("网页打开超时，请检查网络后重试。") from error
        finally:
            browser.close()

    return _clean_articles(raw_articles)


def _clean_articles(raw_articles: list[dict[str, str]]) -> list[dict[str, str]]:
    """清理列表页中的重复和无效链接。"""
    articles: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    for article in raw_articles:
        title = article.get("title", "").strip()
        url = urljoin(REPORT_URL, article.get("url", "").strip())

        if not title or "查看更多" in title:
            continue
        if url in seen_urls:
            continue

        seen_urls.add(url)
        articles.append({"title": title, "url": url})

    return articles
