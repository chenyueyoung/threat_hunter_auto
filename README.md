# ThreatHunter Intelligence Pipeline

本项目用于自动采集 ThreatHunter 文章，并将每篇文章转换为独立的标准化 Article Package ZIP。

Article Package ZIP 可作为后续 LLM 分析的输入。

## 处理流程

```text
ThreatHunter Website
        ↓
Crawler
        ↓
Temporary HTML
        ↓
Processor
        ↓
Article Package ZIP
        ↓
LLM Analysis
```

## 输出结构

项目会按报告日期自动归档，并为每篇文章生成一个独立 ZIP：

```text
output/
└── package/
    └── YYYY/
        └── YYYY-MM/
            ├── <文章标题A>.zip
            ├── <文章标题B>.zip
            └── ...
```

例如：

```text
output/package/2026/2026-07/配婚骗贷.zip
```

每个 ZIP 内部直接包含：

```text
content.txt
metadata.json
images/
```

## 环境要求

用户电脑需要提前安装：

- Python 3.10+
- Git

## 首次安装

下载项目：

```bash
git clone https://github.com/chenyueyoung/threat_hunter_auto.git
cd threat_hunter_auto
```

安装依赖：

```bash
bash setup.sh
```

## 正式运行

```bash
bash start.sh
```

## 测试运行

```bash
bash start.sh --force
```

## 指定报告参数

```bash
bash start.sh \
  --force \
  --report-topic "配婚骗贷" \
  --report-website "https://www.threathunter.cn/" \
  --report-date "2026-05-28" \
  --report-vendor "威胁猎人" \
  --run-by "陈乐扬"
```

## 运行并上传 GitHub

```bash
bash start.sh \
  --force \
  --report-topic "配婚骗贷" \
  --report-date "2026-05-28" \
  --report-vendor "威胁猎人" \
  --run-by "陈乐扬" \
  --push-github
```

不带 `--push-github` 时，结果只保存在本地。

带 `--push-github` 时，程序会自动将本次生成或更新的 ZIP 提交并上传到 GitHub。

GitHub 上传依赖本机已配置 GitHub 登录权限；没有写入权限时，不影响本地生成结果。

程序不会保存 GitHub 密码、Token、用户名或私钥。

GitHub 仓库会长期保存 `output/package/` 下的 ZIP 情报包。

## 直接使用 Python 运行

推荐使用 `bash setup.sh` 和 `bash start.sh`。

同时也支持：

```bash
python3 run.py
python3 run.py --force
```

如果当前 Python 环境缺少依赖，程序会提示需要执行的安装命令。

## 本地文件说明

`setup.sh` 会在本机生成 `.python_path`，用于让 `start.sh` 复用同一个 Python 环境。

`.python_path`、浏览器缓存、临时文件、history 记录等本地文件不会上传到 GitHub。

每台电脑首次使用都需要执行：

```bash
bash setup.sh
```
