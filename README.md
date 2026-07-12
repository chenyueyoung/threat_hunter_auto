# ThreatHunter Intelligence Pipeline

本项目用于自动采集 ThreatHunter 文章，并将每篇文章转换为独立的标准化 Article Package ZIP。

项目最终输出是标准化 Article Package，可作为后续 LLM 分析的输入。

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

## 标准输出

项目会为每篇文章生成一个独立 ZIP 文件：

```text
output/
└── package/
    ├── <文章标题A>.zip
    ├── <文章标题B>.zip
    └── ...
```

每个 ZIP 内部包含：

```text
content.txt
metadata.json
images/
```

ZIP 内部不会再额外嵌套文章标题文件夹。

## 环境要求

用户电脑需要提前安装：

- Python 3.10+
- Git

## 首次使用

下载项目：

```bash
git clone https://github.com/chenyueyoung/threat_hunter_auto.git
cd threat_hunter_auto
```

安装依赖：

```bash
bash setup.sh
```

## 运行方式

正式运行：

```bash
bash start.sh
```

手动测试：

```bash
bash start.sh --force
```

## 输出位置

运行完成后，结果保存在：

```text
output/package/
```

每篇文章对应一个 ZIP 文件，例如：

```text
output/package/今天结婚，明天骗贷：揭秘黑产“配婚”骗贷欺诈产业链.zip
```

## 结果用途

生成的 Article Package ZIP 可以直接上传至支持文件输入的 LLM 工具，用于后续摘要、结构化分析或风险情报整理。
