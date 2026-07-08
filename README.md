# ThreatHunter Article Crawler

Python 自动采集《威胁猎人》网站文章，并根据关键词筛选目标内容，保存为 HTML 文件。

## Features

- 自动采集文章
- 关键词筛选
- 导出 HTML
- 防止重复采集

## Project Structure

```text
threat_hunter_auto/
├── config.py
├── crawler.py
├── html_exporter.py
├── run.py
├── requirements.txt
└── README.md
```

## Installation

```bash
pip install -r requirements.txt
playwright install chromium
```

## Usage

```bash
python3 run.py
```

手动测试：

```bash
python3 run.py --force
```

生成的文件保存在：

```text
output/html/
```
