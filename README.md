# ThreatHunter 文章 HTML 采集工具

使用 Python 3.10 和 Playwright，每月 25 日检查 ThreatHunter 报告列表。
标题命中关键词的文章会保存为包含文字和远程图片的 HTML，历史记录用于避免重复处理。

## 当前流程

1. 每月 25 日读取文章列表。
2. 仅处理上月25日至本月25日发布的文章（包含首尾日期）。
3. 边界日可能再次出现，由 `history.json` 阻止重复处理。
4. 根据 `config.py` 中的标题关键词筛选文章。
5. 保存便于人工阅读和提交给 GPT 的 HTML。
6. 更新 `history.json`。

本项目不再自动生成 TXT、JSON 或 PDF。

## 文件结构

```text
threat_hunter_auto/
├── config.py          # 配置：网址、关键词、日期、输出目录
├── crawler.py         # 抓取 ThreatHunter 报告列表
├── html_exporter.py   # 读取文章正文，清洗 HTML，保存本地 HTML
├── run.py             # 主入口：月度窗口、筛选、history 记录
├── requirements.txt   # Python 依赖
└── README.md          # 使用说明
```

运行后会自动生成：

```text
output/html/          # 文章 HTML
history.json          # 已处理文章记录
.browser_profile/     # Playwright 浏览器缓存
```

这些运行产物不建议上传到 GitHub。

## 安装

```bash
python3 -m pip install -r requirements.txt
playwright install chromium
```

## 运行

每月 25 日正式运行：

```bash
python3 run.py
```

非 25 日手动测试：

```bash
python3 run.py --force
```

生成文件位于：`output/html/<文章标题>.html`。
