# AGENTS.md — 网页结构分析与 Markdown 转换项目

> 本文件面向 AI 编码助手。读者应被假设对该项目一无所知。

---

## 项目概述

本项目是一个纯 Python 的本地数据处理工具，用于将 **SingleFile 浏览器扩展**保存的 HTML 网页批量转换为结构化 Markdown 文件，附带 YAML 元数据头部，并将内嵌 Base64 图片提取到本地 assets 目录。

- **覆盖范围**：30+ 个中文网站（IT之家、掘金、财联社、微信公众号、知乎专栏、少数派、观察者网、界面新闻等）
- **输入**：根目录或各网站子目录中的 `.html` 文件（由 SingleFile 保存）
- **输出**：同目录下的 `.md` 文件 + `assets/{文件名}_assets/` 下的图片
- **目标场景**：个人知识库归档，配合 Obsidian 阅读

项目无构建系统、无 Web 服务部署、无正式测试套件。所有脚本直接从源码运行。

---

## 技术栈与依赖

- **语言**：Python 3（无版本锁定，建议在 3.10+ 运行）
- **核心库**：
  - `beautifulsoup4` — HTML 解析
  - `html2text` — HTML → Markdown 转换
  - `lxml` — BeautifulSoup 的解析后端
  - `send2trash` — 安全删除（一律走回收站）
- **可选依赖**：`Pillow` + `pillow-avif`（用于 IT之家 的 AVIF→JPEG 转换）
- **无配置文件**：没有 `pyproject.toml`、`requirements.txt`、`setup.py` 等。依赖通过 `pip install beautifulsoup4 html2text lxml send2trash` 手动安装。

---

## 目录结构

```
Project-20260303-网页结构分析/
├── .code/                          ← 所有脚本（核心代码）
│   ├── converters/                 ← 35+ 个网站专用转换器
│   │   ├── convert_juejin.py       ← Config 型示例
│   │   ├── convert_cailianshe.py   ← Custom 型示例
│   │   ├── convert_generic.py      ← 通用兜底转换器
│   │   └── ...                     ← 其他网站转换器
│   ├── 配置与导航/                  ← 域名映射 + 导航生成
│   │   ├── domain_config.json      ← 域名 → 目录/归档类别 映射
│   │   ├── domain_config.py        ← JSON 加载器 + classify_domain()
│   │   └── 导航.py                  ← 浏览器导航页生成器 / HTTP 服务器
│   ├── html_converter_base.py      ← 转换器基类
│   ├── batch_convert_all.py        ← 批量转换入口
│   ├── classify_html.py            ← 根目录 HTML 按域名分类
│   ├── reclassify_by_domain.py     ← 全项目 HTML 重新按域名整理
│   ├── polish_markdown.py          ← Markdown 后处理/格式化
│   ├── cleanup_unused_images.py    ← 清理未引用图片（dry-run 默认）
│   ├── archive_html.py             ← 归档 HTML 到副本目录
│   ├── rename_interactive.py       ← 交互式/CLI 文件重命名
│   ├── safe_delete.py              ← send2trash 封装
│   └── ...
├── 财联社/                          ← 各网站数据目录（HTML + MD + assets）
├── IT之家/
├── 掘金/
├── ...（30+ 个网站目录）
├── .docx/                          ← 项目文档
│   ├── 流程手册.md                  ← 从分类到归档的完整操作流程
│   ├── 技术文档.md                  ← 各代码模块详细说明
│   └── 经验复盘.md                  ← 踩坑记录与解决方案
├── .obsidian/                      ← Obsidian 知识库配置
├── README.md                       ← 项目说明（给人类/其他 AI 看）
├── CLAUDE.md                       ← Claude Code 专用配置
└── AGENTS.md                       ← 本文件
```

---

## 核心流程（日常操作）

处理新网页的标准五步流程：

1. **分类** — 将 SingleFile 保存的 HTML 放到项目根目录，然后按域名自动分拣到对应网站目录
2. **转换** — 调用各网站专用转换器将 HTML → MD + 提取 Base64 图片
3. **后处理** — 统一格式化 Markdown，清理杂信息
4. **清理** — 删除未被 MD 引用的冗余图片
5. **归档** — 将原始 HTML 移至同级 `-副本` 目录

---

## 常用命令

所有命令均在**项目根目录**执行。

```bash
# ── 分类 ──
python .code/classify_html.py              # 根目录 HTML → 对应网站目录（按域名）
python .code/reclassify_by_domain.py       # 全项目重新按域名整理（会跨目录移动）

# ── 转换 ──
python .code/batch_convert_all.py          # 批量转换所有网站目录中的 HTML

# ── 后处理 ──
python .code/polish_markdown.py            # 格式化所有 MD（YAML 规范化、修复格式问题）

# ── 清理 ──
python .code/cleanup_unused_images.py      # 预览将要删除的未引用图片（dry-run）
python .code/cleanup_unused_images.py --do # 实际删除（走回收站）

# ── 归档 ──
python .code/archive_html.py               # 将各目录中的 HTML 移到 ../项目名-副本/

# ── 重命名 ──
python .code/rename_interactive.py --list  # 列出命名不合规的文件（JSON 输出）
python .code/rename_interactive.py         # 交互式逐文件重命名
python .code/rename_interactive.py --rename "目录名/旧名" "新名"

# ── 导航 ──
python .code/配置与导航/导航.py --all      # 启动本地 HTTP 导航服务（含存档目录）
python .code/配置与导航/导航.py --generate .  # 生成静态 导航.html
```

---

## 转换器架构

三层架构：

### 1. 基类 — `html_converter_base.py`

所有转换器继承自 `HTMLConverterBase`。基类提供：

- `convert(html_path, output_dir)` — 标准转换流程
- `batch_convert(input_dir, output_dir)` — 批量转换
- `_extract_base64_images(soup, html_path, output_dir)` — 提取 Base64 图片到 `assets/{stem}_assets/`
- `_build_yaml_front_matter(metadata)` — 生成统一 YAML 头部
- `_extract_metadata(soup, html_path)` — 提取 title/author/date/source/url
- `_extract_content(soup)` — 按 CSS 选择器提取内容区域
- `_html_to_markdown(content)` — 使用 html2text 转换
- `_protect_code_blocks(content_elem)` / `_restore_code_blocks(markdown, code_blocks)` — 代码块保护机制（防止 html2text 破坏代码格式）

基类构造函数参数：
```python
HTMLConverterBase(
    domain='', name='', content_selector='',
    title_selector='', author_selector='', date_selector='',
    remove_selectors=None
)
```

### 2. Config 型转换器（简单网站）

仅需设置 CSS 选择器，20–50 行。例如 `convert_ruanyifeng.py`：

```python
class RuanyifengConverter(HTMLConverterBase):
    def __init__(self):
        super().__init__(
            domain='ruanyifeng.com',
            name='阮一峰',
            content_selector='#main-content, article, .entry-content',
            title_selector='h1, .article-title',
            author_selector='.author, .byline',
            date_selector='.date, time',
            remove_selectors=['.sidebar', '.comments', 'script', 'style']
        )
```

### 3. Custom 型转换器（复杂网站）

覆盖 `convert()` 方法，自定义编码检测、图片处理、内容提取逻辑。例如 `convert_cailianshe.py`（财联社）有自定义的 `element_to_markdown()` 递归转换器，用于保留圆圈数字引用；`convert_ithome.py` 处理 AVIF 图片转换。

### 注册新转换器

新转换器必须：
1. 放在 `.code/converters/convert_xxx.py`
2. 继承 `HTMLConverterBase`
3. 在 `.code/batch_convert_all.py` 的 `CONVERTERS` 列表中添加条目：
   ```python
   ('目录名', 'convert_xxx', 'ClassName', '输出子目录', 'call_style')
   ```
   `call_style` 有三种：
   - `'convert_simple'` → `converter.convert(str(html_path))`（基类默认，输出到 HTML 同级目录）
   - `'convert_root'` → `converter.convert(str(html_path), output_dir='.')`（转换器自行决定子目录）
   - `'convert_file'` → `converter.convert_file(hf)`（转换器接收 Path 对象，自行处理一切）

---

## 域名配置

域名映射**不硬编码**在 Python 中，而是存放在 `.code/配置与导航/domain_config.json`：

```json
{
  "project": { "domain": "目录名", ... },
  "archive": { "domain": "类别名", ... }
}
```

- `project` 中的域名 → 走完整流程（转换、后处理、归档），留在项目内
- `archive` 中的域名 → 只分类，移动到 `../Project-20260303-分类存档/<类别>/<域名>/`
- 未知域名 → 在项目根目录创建以域名命名的目录，等待人工决定

`domain_config.py` 提供 `classify_domain(domain)` 函数，支持精确匹配、`www.` 前缀剥离、子域名降级匹配。

---

## 文件与目录约定

### 文件命名规范
```
关键词1_关键词2_关键词3_YYYYMMDD_来源.html
```
例如：`苹果发布新款MacBook_20251215_IT之家.html`

### 图片附件规范
- 提取后的图片存放于：`assets/{文章名}_assets/image_N.ext`
- Markdown 中引用为相对路径：`![alt](assets/文章名_assets/image_001.jpg)`

### Markdown 格式规范
- 必须包含 YAML front matter：
  ```yaml
  ---
  title: "文章标题"
  author: 作者名
  date: 2025-12-15
  source: 来源网站
  url: https://...
  converted_at: 2025-12-15 10:30:00
  ---
  ```
- `title` 值必须加双引号（处理内含冒号、特殊字符的情况）
- 正文中标题前后必须有空行
- 图片单独成行，前后有空行
- 代码块使用 ``` 围栏，不使用 4 空格缩进

### 安全删除
- **严禁使用 `rm -rf` 或 `os.remove()` 直接删除文件**
- 所有删除操作必须通过 `send2trash` 走回收站
- `safe_delete.py` 是统一封装
- `cleanup_unused_images.py` 默认 dry-run，必须加 `--do` 才真正删除

---

## 后处理流水线（polish_markdown.py）

`polish_markdown.py` 是覆盖全项目的 Markdown 格式化工具，包含 20+ 个修复函数，主要处理：

| 问题类型 | 修复函数 |
|---------|---------|
| YAML 不规范 | `normalize_yaml` — 移除非标准键、统一字段顺序、title 加引号 |
| Windows 反斜杠路径 | `fix_backslash_paths` |
| 加粗标记含空格 | `fix_spaced_bold` — `** text **` → `**text**` |
| 残留 `data:image` | `fix_data_uri_images` — 尝试映射到本地 assets |
| 泄漏的来源/日期行 | `fix_source_date_junk` — 移除 `2025-12-22 22:19 星期一财联社` 等 |
| 代码块格式 | `fix_indented_code_blocks` — 4 空格缩进 → ``` 围栏 |
| 列表间距 | `fix_list_spacing` — 合并同类型列表项间的空行 |
| HTML 残留标签 | `fix_html_remnants` — 清理 `<br>`、HTML 实体等 |
| 裸 URL | `fix_bare_urls` — 转换为 `<url>` 格式 |
| 图片间距与 alt | `fix_image_spacing`、`fix_image_alt` |
| 标题间距 | `fix_heading_spacing` |
| 数学公式片段 | `fix_latex_inline` — 为 `_{}`、`^{}`、LaTeX 命令加 `$` |
| JS 无效链接 | `fix_javascript_void_links` — 移除 `[text](javascript:void(0))` |
| 中文方括号在链接中 | `fix_chinese_brackets_in_links` — `\[xxx\]` → `【xxx】` |

运行方式：
```bash
python .code/polish_markdown.py              # 处理整个项目
python .code/polish_markdown.py 财联社/       # 处理指定目录
```

---

## 导航与浏览

`.code/配置与导航/导航.py` 提供两种模式：

1. **HTTP 服务器模式**（默认）：扫描项目目录树，启动本地 HTTP 服务，浏览器中可侧栏导航、右侧 iframe 预览 HTML 文件。支持 `--all` 同时挂载分类存档目录。
2. **静态生成模式**（`--generate <目录>`）：为指定目录生成一个独立的 `导航.html` 文件，可在无 Python 环境下用浏览器打开。分类脚本在将文件移入存档后会自动调用此模式更新存档的导航页。

---

## 开发指南

### 添加新网站转换器

1. 分析目标网站的 HTML 结构（用浏览器 DevTools 查看 SingleFile 保存的文件）
2. 在 `.code/converters/` 创建 `convert_xxx.py`：
   - 若结构标准 → 写 Config 型（继承基类，填选择器即可）
   - 若需要特殊处理 → 写 Custom 型（覆盖 `convert()`）
3. 在 `.code/batch_convert_all.py` 的 `CONVERTERS` 列表注册
4. 若为新域名 → 在 `domain_config.json` 的 `project` 段添加映射
5. 测试转换：`python .code/batch_convert_all.py`（只处理有 HTML 的目录）
6. 检查输出后运行 `python .code/polish_markdown.py`

### 修改现有转换器

- Custom 型转换器往往有复杂的 DOM 处理逻辑，修改时注意保持原有的编码检测、图片提取、特殊元素清理逻辑。
- 若发现某类格式问题普遍存在于多个转换器，优先在 `polish_markdown.py` 中添加统一修复，而不是在每个转换器中重复处理。

### 代码风格

- 注释和文档字符串使用**中文**
- 使用 4 空格缩进
- 导入顺序：标准库 → 第三方库 → 本地模块
- Windows 编码问题敏感：涉及中文输出时，脚本通常有 `sys.stdout = io.TextIOWrapper(..., encoding='utf-8')` 处理
- 路径操作统一使用 `pathlib.Path`，必要时用 `.as_posix()` 保证正斜杠

---

## 验证清单（人工检查项）

运行完批量流程后，按此清单检查：

- [ ] 所有 HTML 都有对应的 MD 文件
- [ ] MD 中的图片引用指向实际存在的文件
- [ ] 没有残留的 `data:image` 链接
- [ ] YAML 头包含 `title`/`author`/`date`/`source`/`url`/`converted_at`
- [ ] `title` 值已加双引号
- [ ] 文件命名符合 `关键词_YYYYMMDD_来源` 格式
- [ ] 加粗标记 `**text**` 内外无多余空格
- [ ] 代码块使用 ``` 围栏格式
- [ ] 图片前后有空行

---

## 注意事项

- **不要修改 `.obsidian/` 目录下的配置文件**，除非明确知道 Obsidian 插件/设置的用途。
- **归档操作不可逆**：`archive_html.py` 使用 `shutil.move` 将 HTML 移出项目到 `-副本` 目录，执行前确保转换和后处理已完成且质量合格。
- **分类存档是独立目录**：`../Project-20260303-分类存档/` 与主项目同级，不归 git 管理（项目 `.gitignore` 已忽略分类存档）。
- **基类方法签名兼容性**：部分旧转换器调用 `_extract_metadata` 时传入 `(html_content, html_path)` 而非 `(soup, html_path)`，基类 `convert()` 中已通过 `try/except TypeError` 做了兼容处理。
