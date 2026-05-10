# HTML to MD

将 SingleFile 保存的 HTML 网页批量转换为结构化 Markdown，覆盖 30+ 中文网站。

## 快速开始

```bash
pip install beautifulsoup4 html2text lxml send2trash

# 分类新网页
python .code/classify_html.py

# 批量转换
python .code/batch_convert_all.py

# 后处理
python .code/polish_markdown.py

# 清理未引用图片
python .code/cleanup_unused_images.py --do

# 归档 HTML 到副本目录
python .code/archive_html.py
```

## 文档索引

| 文档 | 路径 | 说明 |
|------|------|------|
| Claude Code 配置 | `CLAUDE.md` | Claude Code 打开项目时自动加载 |
| 流程手册 | `.docx/流程手册.md` | 从分类到归档的完整操作流程 |
| 经验复盘 | `.docx/经验复盘.md` | 踩过的坑和解决方案 |
| 技术文档 | `.docx/技术文档.md` | 各代码模块详细说明 |

## 目录结构

```
├── README.md              ← 本文件
├── CLAUDE.md              ← Claude Code 配置
├── .code/                 ← 所有脚本
│   ├── converters/        ← 网站转换器
│   ├── 配置与导航/        ← 域名配置 + 导航
│   ├── batch_convert_all.py
│   ├── polish_markdown.py
│   └── ...
├── 财联社/                 ← 网站目录（MD + assets）
├── IT之家/
├── 掘金/
├── ...（30+ 网站）
└── .docx/                 ← 详细文档

## 文件命名规范

`关键词1_关键词2_关键词3_YYYYMMDD_来源.html`

## 图片附件规范

`assets/{文章名}_assets/image_N.ext`

## 下一步 (TODO)

- [ ] 将国家统计局的网页转换为 MD 文档（stats.gov.cn，需编写转换器）
- [ ] dx2025.com、dx2035.cn 网页转换（东西智库新域名）


```

## 下一步 (TODO)

- [ ] 将国家统计局的网页转换为 MD 文档（stats.gov.cn，需编写转换器）