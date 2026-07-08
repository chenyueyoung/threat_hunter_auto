"""ThreatHunter 文章 HTML 生成。"""

import html
import re
from datetime import date
from pathlib import Path
from html.parser import HTMLParser

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from config import (
    BROWSER_CHANNEL,
    BROWSER_PROFILE_DIR,
    HEADLESS,
    HTML_OUTPUT_DIR,
    PAGE_TIMEOUT_MS,
)


def export_article_html(
    article: dict[str, str],
    period_start: date,
    period_end: date,
    output_dir: Path = HTML_OUTPUT_DIR,
) -> tuple[Path, str] | None:
    """保存日期范围内的文章，范围外返回 None。"""
    title = article["title"].strip()
    url = article["url"].strip()

    output_dir.mkdir(parents=True, exist_ok=True)
    BROWSER_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    html_path = output_dir / f"{sanitize_filename(title)}.html"

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(BROWSER_PROFILE_DIR),
            channel=BROWSER_CHANNEL,
            headless=HEADLESS,
        )
        page = context.pages[0] if context.pages else context.new_page()

        try:
            article_data = extract_article_data(page, url)
            published_date = date.fromisoformat(article_data["date"])
            if not period_start <= published_date <= period_end:
                print(f"跳过日期范围外文章：{published_date} · {title}")
                return None

            article_data["bodyHtml"] = clean_article_html(
                html.unescape(article_data["bodyHtml"])
            )
            document = build_standard_html(article_data)
            page.set_content(
                document,
                wait_until="domcontentloaded",
                timeout=PAGE_TIMEOUT_MS,
            )
            html_path.write_text(page.content(), encoding="utf-8")
        except PlaywrightTimeoutError as error:
            raise RuntimeError("文章页面或正文图片加载超时。") from error
        finally:
            context.close()

    return html_path, article_data["date"]


def extract_article_data(page, url: str) -> dict[str, str]:
    """读取页面内嵌的文章数据。"""
    print(f"正在读取文章原始数据：{url}")
    page.goto(url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)
    page.wait_for_function(
        "() => window.$S && window.$S.blogPostData",
        timeout=PAGE_TIMEOUT_MS,
    )

    data = page.evaluate(
        """
        () => {
            const data = window.$S.blogPostData;
            const meta = data.blogPostMeta;
            const section = data.content.sections.find(
                item => item.component?.type === "HtmlComponent"
            );
            return {
                title: meta.socialMediaConfig.title,
                date: meta.publishedAt.slice(0, 10),
                category: meta.categories?.[0]?.name || "",
                bodyHtml: section?.component?.value || ""
            };
        }
        """
    )
    if not data["bodyHtml"]:
        raise RuntimeError("页面原始数据中没有找到文章正文。")

    print(f"正文原始 HTML：{len(data['bodyHtml'])} 字符")
    return data


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
