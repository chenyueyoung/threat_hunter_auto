# ThreatHunter Intelligence Pipeline

This project collects ThreatHunter articles and converts each article into an independent standardized Article Package ZIP.

The output of this project is a standardized Article Package, designed as the standard input for downstream LLM analysis.

## Pipeline

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

## Standard Output

The project generates one ZIP file for each article.

```text
output/
└── package/
    ├── <文章标题A>.zip
    ├── <文章标题B>.zip
    └── ...
```

Each ZIP contains:

```text
content.txt
metadata.json
images/
```

There is no extra article-title folder inside the ZIP.

## Usage

首次使用：

```bash
bash setup.sh
```

以后运行：

```bash
bash start.sh
```

手动测试：

```bash
bash start.sh --force
```
