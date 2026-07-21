# ThreatHunter Intelligence Pipeline

## 项目功能

- 自动采集 ThreatHunter 文章，生成标准化 Article Package ZIP
- 按标题关键词筛选目标文章
- 提取并清洗正文内容
- 下载文章原始图片
- 每篇文章生成独立 Article Package ZIP
- 按 `output/package/YYYY/YYYY-MM/` 自动归档
- 支持可选的 GitHub 上传，便于长期保存和共享
- 输出结果可作为大语言模型（LLM）后续分析输入

## 处理流程

```text
ThreatHunter
        ↓
文章抓取
        ↓
关键词筛选
        ↓
正文提取与清洗
        ↓
图片下载
        ↓
生成 Article Package ZIP
        ↓
LLM 分析
```

## 输出目录

生成结果默认保存在：

```text
output/package/YYYY/YYYY-MM/
```

目录示例：

```text
output/
└── package/
    └── 2026/
        └── 2026-07/
            ├── article-a.zip
            └── article-b.zip
```

每个 ZIP 内部包含：

```text
content.txt
metadata.json
images/
```

文件说明：

- `content.txt`：清洗后的正文内容
- `metadata.json`：文章标题、发布时间、来源、图片列表等元数据
- `images/`：文章中的原始图片

## 首次安装

使用前需安装 Python 3.10+ 和 Git。首次获取项目后执行：

```bash
git clone https://github.com/chenyueyoung/threat_hunter_auto.git
cd threat_hunter_auto
bash setup.sh
```

`setup.sh` 会安装项目依赖、初始化 Playwright 浏览器环境，并创建必要的输出目录。

安装完成后，日常使用只需执行：

```bash
bash start.sh
```

## 使用方法

日常运行：

```bash
bash start.sh
```

强制运行：

```bash
bash start.sh --force
```

带通用参数运行：

```bash
bash start.sh \
  --force \
  --report-topic "示例主题" \
  --report-website "https://www.threathunter.cn/" \
  --report-date "2026-07-01" \
  --report-vendor "示例来源" \
  --run-by "示例用户"
```

带上传参数运行：

```bash
bash start.sh \
  --force \
  --report-topic "示例主题" \
  --report-date "2026-07-01" \
  --report-vendor "示例来源" \
  --run-by "示例用户" \
  --push-github
```

不使用 `--push-github` 时，结果仅保存在本地。

使用 `--push-github` 时，程序会提交并上传本次生成或更新的 ZIP。GitHub 上传依赖本机已有 Git 登录权限。

## 注意事项

- 每台电脑首次使用需要执行 `git clone` 和 `bash setup.sh`。
- 安装完成后，日常运行使用 `bash start.sh`。
- 手动测试使用 `bash start.sh --force`。
- 没有 GitHub 仓库写入权限时，不影响本地生成结果。
- 程序不会保存 GitHub 密码、Token、用户名或私钥。
- 本机配置和临时文件不会上传，包括 `.python_path`、`__pycache__/`、浏览器缓存、临时文件和本地历史记录。
