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
| 元数据应用方案 | `.code/知识卡片元数据应用方案.md` | 知识卡片元数据的结构、场景与实施路线 |

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
```

## 文件命名规范

`关键词1_关键词2_关键词3_YYYYMMDD_来源.html`

## 图片附件规范

`assets/{文章名}_assets/image_N.ext`

## 下一步 (TODO)

### 转换器开发
- [ ] 将国家统计局的网页转换为 MD 文档（stats.gov.cn，需编写转换器）

### 知识卡片元数据补全与应用
- [ ] 为仅有基础型元数据的存量文档批量补全知识卡片型元数据（tags / category / summary / problem 等）
- [ ] 编写 `generate_semantic_nav.py`，按 category / tags / problem 生成静态语义导航页
- [ ] 在 `.obsidian/` 中预设 Dataview 查询模板（精华阅读表、待完善清单、按难度分级表）
- [ ] 抽取 `summary` + `description` + `problem` 构建元数据级语义检索索引
- [ ] 编写 `weekly_review.py`，按周聚合阅读内容自动生成回顾 Markdown
