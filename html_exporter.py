"""ThreatHunter 文章 HTML 生成。"""

import html
import re
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

from config import (
    HTML_OUTPUT_DIR,
    REPORT_URL,
)


REQUEST_TIMEOUT_SECONDS = 30


def export_article_html(
    article: dict[str, str],
    period_start: date,
    period_end: date,
    output_dir: Path = HTML_OUTPUT_DIR,
    enforce_period: bool = True,
) -> tuple[Path, str, list[dict[str, str]]] | None:
    """保存日期范围内的文章，范围外返回 None。"""
    title = article["title"].strip()
    url = article["url"].strip()

    output_dir.mkdir(parents=True, exist_ok=True)
    html_path = output_dir / f"{sanitize_filename(title)}.html"

    article_data = extract_article_data(url)
    published_date = date.fromisoformat(article_data["date"])
    if enforce_period and not period_start <= published_date <= period_end:
        print(f"跳过日期范围外文章：{published_date} · {title}")
        return None

    article_data["bodyHtml"] = clean_article_html(article_data["bodyHtml"])
    document = build_standard_html(article_data)
    html_path.write_text(document, encoding="utf-8")
    return html_path, article_data["date"], article_data["relatedLinks"]


def extract_article_data(url: str) -> dict[str, object]:
    """读取新版研究详情页正文数据。"""
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError as error:
        raise RuntimeError("缺少 requests 或 beautifulsoup4，请先运行：bash setup.sh") from error

    print(f"正在读取文章原始数据：{url}")
    try:
        response = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        raise RuntimeError(f"文章页面请求失败：{error}") from error

    soup = BeautifulSoup(response.text, "html.parser")
    article_node = soup.select_one(".report-rich-content")
    if not article_node:
        raise RuntimeError("页面中没有找到新版研究正文区域。")

    normalize_resource_urls(article_node, response.url)
    data = {
        "title": extract_title(soup),
        "date": extract_date(soup),
        "category": extract_category(soup),
        "bodyHtml": str(article_node),
        "relatedLinks": extract_related_links(article_node, response.url),
    }
    if not data["title"] or not data["date"] or not data["bodyHtml"]:
        raise RuntimeError("页面正文数据不完整。")

    print(f"正文原始 HTML：{len(data['bodyHtml'])} 字符")
    print(f"正文关联链接：{len(data['relatedLinks'])} 个")
    return data


def extract_title(soup) -> str:
    """提取文章标题。"""
    title_node = soup.select_one("h1")
    if title_node:
        return title_node.get_text(" ", strip=True)
    meta_title = soup.select_one('meta[property="og:title"]')
    return (meta_title.get("content") or "").split("｜", 1)[0].strip()


def extract_date(soup) -> str:
    """提取文章发布时间。"""
    meta_date = soup.select_one('meta[property="article:published_time"]')
    if meta_date and meta_date.get("content"):
        return meta_date["content"][:10]
    text = soup.get_text(" ", strip=True)
    match = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", text)
    if match:
        year, month, day = match.groups()
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
    raise RuntimeError("无法识别文章发布时间。")


def extract_category(soup) -> str:
    """提取文章分类。"""
    category_node = soup.select_one(".report-detail-heading .eyebrow")
    if not category_node:
        return ""
    parts = [
        part.strip()
        for part in category_node.get_text(" ", strip=True).split("/")
        if part.strip()
    ]
    return parts[-1] if parts else ""


def normalize_resource_urls(article_node, base_url: str) -> None:
    """把正文内相对链接和图片地址改为绝对地址。"""
    for link in article_node.find_all("a"):
        href = link.get("href")
        if href:
            link["href"] = urljoin(base_url, href)
    for image in article_node.find_all("img"):
        src = image.get("src")
        if src:
            image["src"] = urljoin(base_url, src)


def extract_related_links(article_node, base_url: str) -> list[dict[str, str]]:
    """提取正文区域中的站内研究文章链接。"""
    links = []
    seen_urls = set()
    for link in article_node.find_all("a"):
        link_text = link.get_text(" ", strip=True)
        link_url = urljoin(base_url, link.get("href", "").strip())
        if not link_text or not is_research_article_url(link_url):
            continue
        if link_url in seen_urls:
            continue
        seen_urls.add(link_url)
        links.append({"link_text": link_text, "link_url": link_url})
    return links


def is_research_article_url(url: str) -> bool:
    """判断链接是否像 ThreatHunter 研究文章详情页。"""
    from urllib.parse import urlparse

    parsed = urlparse(url)
    if parsed.netloc and parsed.netloc != "www.threathunter.cn":
        return False
    if not parsed.path.startswith("/research/"):
        return False
    blocked_prefixes = (
        "/research/topics/",
        "/research/archive/",
    )
    if any(parsed.path.startswith(prefix) for prefix in blocked_prefixes):
        return False
    if re.search(r"\.(pdf|zip|png|jpe?g|webp|gif)$", parsed.path, re.I):
        return False
    return parsed.path.rstrip("/") != "/research"


def clean_article_html(body_html: str) -> str:
    """把正文转成只保留文字和图片的 HTML。"""
    parser = ArticleHtmlCleaner()
    parser.feed(body_html)
    parser.close()

    clean_html = parser.to_html()
    text_length = len(parser.text_content.strip())
    print(f"清洗后正文文字：{text_length} 字符，图片：{parser.image_count} 张")
    if text_length < 300:
        raise RuntimeError("清洗后的正文文字过少，暂不生成 HTML。")
    return clean_html


class ArticleHtmlCleaner(HTMLParser):
    """保留正文段落和图片地址。"""

    BLOCK_TAGS = {"p", "div", "section", "li", "h1", "h2", "h3", "h4"}
    SKIP_TAGS = {"script", "style", "iframe"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[str] = []
        self.current_text: list[str] = []
        self.text_content = ""
        self.image_count = 0
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in self.SKIP_TAGS:
            self.skip_depth += 1
            return
        if self.skip_depth:
            return
        if tag in self.BLOCK_TAGS or tag == "br":
            self._flush_text()
        if tag == "img":
            self._flush_text()
            self._append_image(dict(attrs))

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self.SKIP_TAGS and self.skip_depth:
            self.skip_depth -= 1
            return
        if not self.skip_depth and tag in self.BLOCK_TAGS:
            self._flush_text()

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return
        normalized = re.sub(r"\s+", " ", data).strip()
        if normalized:
            self.current_text.append(normalized)
            self.text_content += normalized

    def close(self) -> None:
        self._flush_text()
        super().close()

    def to_html(self) -> str:
        return "\n".join(self.blocks)

    def _flush_text(self) -> None:
        text = "".join(self.current_text).strip()
        self.current_text = []
        if text:
            self.blocks.append(f"<p>{html.escape(text)}</p>")

    def _append_image(self, attrs: dict[str, str | None]) -> None:
        src = next(
            (
                attrs.get(name)
                for name in ("data-original", "data-src", "data-url", "src")
                if attrs.get(name)
            ),
            None,
        )
        if not src or src.startswith("data:image"):
            return
        if src.startswith("//"):
            src = f"https:{src}"
        alt = attrs.get("alt") or "文章图片"
        self.blocks.append(
            f'<img src="{html.escape(src, quote=True)}" '
            f'alt="{html.escape(alt, quote=True)}" loading="lazy">'
        )
        self.image_count += 1


def build_standard_html(article: dict[str, str]) -> str:
    """生成便于阅读和后续处理的 HTML 文档。"""
    title = html.escape(article["title"])
    category = html.escape(article["category"])
    published_date = html.escape(article["date"])
    return f"""
    <!doctype html>
    <html lang="zh-CN">
    <head>
      <meta charset="utf-8">
      <title>{title}</title>
      <style>
        body {{
          margin: 0 auto; padding: 32px; max-width: 820px;
          color: #222; font-family: -apple-system, "PingFang SC",
          "Microsoft YaHei", sans-serif; line-height: 1.8;
        }}
        h1 {{ font-size: 30px; line-height: 1.4; margin-bottom: 12px; }}
        .meta {{ color: #777; margin-bottom: 28px; }}
        article {{ font-size: 16px; line-height: 1.9; }}
        article p {{ margin: 12px 0; }}
        article img {{ display: block; max-width: 100%; height: auto; margin: 18px auto; }}
        * {{ box-sizing: border-box; }}
      </style>
    </head>
    <body>
      <h1>{title}</h1>
      <div class="meta">{published_date} · {category}</div>
      <article>{article["bodyHtml"]}</article>
    </body>
    </html>
    """


def sanitize_filename(filename: str, max_length: int = 100) -> str:
    """生成安全的本地文件名。"""
    cleaned_name = re.sub(r'[\\/:*?"<>|]', "_", filename)
    cleaned_name = re.sub(r"\s+", " ", cleaned_name).strip(" .")
    if not cleaned_name:
        return "未命名文章"
    return cleaned_name[:max_length].rstrip(" .")
