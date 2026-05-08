# CLAUDE.md — 网页结构分析与 Markdown 转换项目

## 项目概述

将 SingleFile 保存的 HTML 网页批量转换为结构化 Markdown，附带 YAML 元数据，Base64 图片提取到本地 assets 目录。覆盖 30+ 中文网站，每个网站有专用转换器。

## 目录结构

```
Project-20260303-网页结构分析/
├── CLAUDE.md              ← 本文件（Claude Code 自动读取）
├── README.md              ← 项目说明（给其他 AI 工具/人看）
├── .code/                 ← 所有脚本和转换器
│   ├── converters/        ← 网站转换器（25+个）
│   ├── 配置与导航/        ← 域名配置和导航程序
│   ├── batch_convert_all.py  ← 批量转换入口
│   ├── polish_markdown.py    ← 后处理/格式化
│   ├── html_converter_base.py ← 基础转换器类
│   ├── rename_interactive.py ← 交互式重命名
│   ├── cleanup_unused_images.py ← 清理未引用图片
│   ├── archive_html.py    ← 归档 HTML 到副本目录
│   └── safe_delete.py     ← 回收站安全删除
├── 财联社/                 ← 各网站目录（HTML→MD+assets）
├── IT之家/
├── 掘金/
├── ...（30+ 网站目录）
└── .docx/                 ← 技术文档

## 常用命令

```bash
# 分类新网页（根目录 HTML → 对应网站目录）
python .code/classify_html.py

# 重新整理所有文件
python .code/reclassify_by_domain.py

# 批量转换所有网站
python .code/batch_convert_all.py

# 后处理格式化所有 MD
python .code/polish_markdown.py

# 清理未引用图片（先 dry-run）
python .code/cleanup_unused_images.py
python .code/cleanup_unused_images.py --do

# 归档 HTML 到副本目录
python .code/archive_html.py

# 交互式重命名不合规文件
python .code/rename_interactive.py
python .code/rename_interactive.py --list

# 存档导航（浏览器浏览）
python .code/配置与导航/导航.py --all
```

## 核心流程

1. **分类** — 根目录 HTML 按域名分到对应网站目录
2. **转换** — 各网站转换器将 HTML → MD + 提取 Base64 图片
3. **后处理** — `polish_markdown.py` 统一格式化、清理杂信息
4. **清理** — `cleanup_unused_images.py` 删除未被 MD 引用的图片
5. **归档** — `archive_html.py` 将 HTML 移至副本目录

## 关键约定

- **删除文件**：一律用回收站（`send2trash`），禁止 `rm -rf`
- **图片路径**：`assets/{文章名}_assets/image_N.ext`
- **MD 格式**：YAML front matter（title/author/date/source/url/converted_at）+ Markdown 正文
- **文件命名**：`关键词1_关键词2_关键词3_YYYYMMDD_来源.html`
- **新转换器**：放在 `.code/converters/`，继承 `HTMLConverterBase`，添加到 `batch_convert_all.py`
- **域名配置**：编辑 `.code/配置与导航/domain_config.json`，不要在代码中硬编码

## 转换器架构

三层架构：
- **`html_converter_base.py`** — 基类，提供 `convert()`、`_extract_base64_images()`、`_build_yaml_front_matter()`、`_protect_code_blocks()`
- **Config 型**（如 `convert_juejin.py`）— 只设置 CSS 选择器，20-50 行
- **Custom 型**（如 `convert_cailianshe.py`）— 覆盖 `convert()`，自定义图片/编码处理
