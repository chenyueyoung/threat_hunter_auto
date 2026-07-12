"""文章打包：从 HTML 提取正文和图片，保存为方便后续分析的文件夹。"""

from __future__ import annotations

import json
import re
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import parse_qs, unquote, urlparse, urlunparse

from config import BASE_DIR, HTML_OUTPUT_DIR


PACKAGE_OUTPUT_DIR = BASE_DIR / "output" / "package"
NOISE_LINES = {
    "返回",
    "首页",
    "发送",
    "复制",
    "更多",
    "上一篇",
    "下一篇",
    "回到主页",
    "产品与服务",
    "关于我们",
    "控制台",
}


@dataclass
class ImageFile:
    original_url: str
    local_file: str


@dataclass
class PackageResult:
    package_path: Path
    image_success_count: int
    image_failed_count: int


def main() -> None:
    html_path = select_html_file(sys.argv[1] if len(sys.argv) > 1 else None)
    result = process_html(html_path)
    print(f"处理完成：{html_path.name}")
    print(f"文章包已保存：{result.package_path}")


def process_html(html_path: Path, source_url: str = "") -> PackageResult:
    """处理单个 HTML 文件，输出独立 Article Package ZIP。"""
    article = extract_article(html_path)
    zip_path = PACKAGE_OUTPUT_DIR / f"{sanitize_filename(article['title'] or html_path.stem)}.zip"
    PACKAGE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with TemporaryDirectory(prefix="article_package_") as temp_dir:
        package_dir = Path(temp_dir)
        images_dir = package_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)

        clean_text = clean_content(article["content_text"])
        (package_dir / "content.txt").write_text(clean_text, encoding="utf-8")

        image_files: list[ImageFile] = []
        failed_count = 0
        for index, image_url in enumerate(article["image_urls"], start=1):
            try:
                image_path = download_image(image_url, images_dir, index)
                image_files.append(
                    ImageFile(
                        original_url=image_url,
                        local_file=str(image_path.relative_to(package_dir)),
                    )
                )
            except Exception as error:
                failed_count += 1
                print(f"图片下载失败，已跳过：{image_url}")
                print(f"失败原因：{error}")

        metadata = {
            "title": article["title"],
            "date": article["date"],
            "source": "ThreatHunter",
            "source_url": source_url,
            "clean_text_file": "content.txt",
            "images": [image.__dict__ for image in image_files],
        }
        save_json(metadata, package_dir / "metadata.json")
        create_zip(package_dir, zip_path)

    return PackageResult(
        package_path=zip_path,
        image_success_count=len(image_files),
        image_failed_count=failed_count,
    )


def select_html_file(path_arg: str | None) -> Path:
    """选择一个 HTML 文件；未指定时默认使用最新文件。"""
    if path_arg:
        html_path = Path(path_arg).expanduser()
        if not html_path.is_absolute():
            html_path = BASE_DIR / html_path
        if not html_path.exists():
            raise FileNotFoundError(f"HTML 文件不存在：{html_path}")
        return html_path

    html_files = sorted(
        HTML_OUTPUT_DIR.glob("*.html"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not html_files:
        raise FileNotFoundError(f"没有找到 HTML 文件：{HTML_OUTPUT_DIR}")
    return html_files[0]


def extract_article(html_path: Path) -> dict[str, object]:
    """从本地 HTML 提取标题、发布时间、正文和正文图片链接。"""
    try:
        from bs4 import BeautifulSoup
    except ImportError as error:
        raise RuntimeError("缺少 beautifulsoup4，请先运行：bash setup.sh") from error

    soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")
    article_node = soup.find("article") or soup
    title = get_text(soup.find("h1")) or get_text(soup.find("title"))
    meta_text = get_text(soup.select_one(".meta"))
    date_match = re.search(r"\d{4}-\d{2}-\d{2}", meta_text)

    return {
        "title": title,
        "date": date_match.group(0) if date_match else "",
        "content_text": article_node.get_text("\n", strip=True),
        "image_urls": [
            image["src"].strip()
            for image in article_node.find_all("img")
            if image.get("src")
        ],
    }


def get_text(node) -> str:
    return node.get_text(" ", strip=True) if node else ""


def download_image(image_url: str, images_dir: Path, index: int) -> Path:
    try:
        import requests
    except ImportError as error:
        raise RuntimeError("缺少 requests，请先运行：bash setup.sh") from error

    response = download_with_fallback(requests, image_url)

    suffix = get_image_suffix(image_url, response.headers.get("content-type", ""))
    image_path = images_dir / f"{index:03d}{suffix}"
    image_path.write_bytes(response.content)
    return image_path


def download_with_fallback(requests_module, image_url: str):
    """每张图片最多尝试 2 次：先代理链接，再微信原图链接。"""
    errors = []
    for candidate_url in get_candidate_image_urls(image_url)[:2]:
        try:
            return download_once(requests_module, candidate_url)
        except Exception as error:
            errors.append(f"{candidate_url} -> {error}")
    raise RuntimeError("; ".join(errors))


def download_once(requests_module, image_url: str):
    response = requests_module.get(
        image_url,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=(10, 20),
    )
    response.raise_for_status()
    return response


def get_candidate_image_urls(image_url: str) -> list[str]:
    fixed_url = fix_threathunter_domain(image_url)
    urls = [fixed_url]
    original_wechat_url = extract_wechat_image_url(fixed_url)
    if original_wechat_url and original_wechat_url not in urls:
        urls.append(original_wechat_url)
    return urls


def fix_threathunter_domain(image_url: str) -> str:
    parsed = urlparse(image_url)
    if parsed.netloc == "ww.threathunter.cn":
        return urlunparse(parsed._replace(netloc="www.threathunter.cn"))
    return image_url


def extract_wechat_image_url(image_url: str) -> str | None:
    parsed = urlparse(image_url)
    query = parse_qs(parsed.query)
    raw_url = query.get("url", [""])[0]
    decoded_url = unquote(raw_url)
    if "mmbiz.qpic.cn" in decoded_url:
        return decoded_url
    return None


def get_image_suffix(image_url: str, content_type: str) -> str:
    parsed_suffix = Path(urlparse(image_url).path).suffix.lower()
    if parsed_suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}:
        return parsed_suffix
    if "png" in content_type:
        return ".png"
    if "webp" in content_type:
        return ".webp"
    return ".jpg"


def clean_content(text: str) -> str:
    lines = []
    seen = set()

    for raw_line in text.splitlines():
        line = normalize_line(raw_line)
        if should_drop_line(line):
            continue
        if line in seen:
            continue
        seen.add(line)
        lines.append(line)

    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def normalize_line(line: str) -> str:
    line = re.sub(r"[ \t\r\f\v]+", " ", line)
    line = re.sub(r"([。！？；：，、])\1+", r"\1", line)
    return line.strip()


def should_drop_line(line: str) -> bool:
    if not line:
        return True
    if line in NOISE_LINES:
        return True
    if "Cookie的使用" in line or "了解更多" == line:
        return True
    if len(line) <= 1:
        return True
    if len(line) <= 3 and not re.search(r"[\u4e00-\u9fffA-Za-z0-9]", line):
        return True
    return False


def save_json(data: dict[str, object], json_path: Path) -> None:
    with json_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        file.write("\n")


def create_zip(package_dir: Path, zip_path: Path) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
        for path in sorted(package_dir.rglob("*")):
            if path.is_file():
                zip_file.write(path, path.relative_to(package_dir))


def sanitize_filename(filename: str, max_length: int = 100) -> str:
    cleaned_name = re.sub(r'[\\/:*?"<>|]', "_", filename)
    cleaned_name = re.sub(r"\s+", " ", cleaned_name).strip(" .")
    if not cleaned_name:
        return "未命名文章"
    return cleaned_name[:max_length].rstrip(" .")


if __name__ == "__main__":
    main()
