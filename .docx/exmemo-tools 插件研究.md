# ExMemo Tools 插件研究与本地调制分析

> 本文档基于官方源码（v1.2.0）与本地 `.obsidian/plugins/exmemo-tools/data.json` 调制配置对比撰写，面向项目维护者与 AI 编码助手。

---

## 1. 插件概述

**ExMemo Tools** 是一款基于大语言模型（LLM）的 Obsidian 插件，核心定位是**智能文档管理与内容优化**。它并非简单的"AI 写作助手"，而是一套围绕笔记生命周期设计的自动化工具链：从文件归档、元数据生成、内容编辑到知识卡片提取和目录索引，覆盖了笔记从采集到组织的完整流程。

### 1.1 官方功能清单

| 功能模块 | 命令/入口 | 说明 |
|---------|----------|------|
| 生成元数据 | `Ctrl+P` → ExMemo Tools: 生成元数据 | 自动为当前文件生成/补全 YAML front matter |
| 智能归档 | `Ctrl+P` → ExMemo Tools: 为当前文件选择合适的目录 | 基于内容推荐最适合的存放目录 |
| AI 辅助编辑 | `Ctrl+P` → ExMemo Tools: 将选中的文本插入/智能编辑/续写 | 多提示词管理，支持替换/追加/前置 |
| 生成卢曼卡片 | `Ctrl+P` → ExMemo Tools: 生成卢曼卡片 | 为文件或选中段落提取知识卡片 |
| 生成目录索引 | 右键目录 → ExMemo 生成目录索引 | 为目录生成 MOC（Map of Content） |
| 搜索结果索引 | 搜索结果右键 → 创建索引 | 将搜索结果集生成临时索引文件 |

### 1.2 与本项目的关系

本项目中的《全自动知识卡片元数据生成规范 (v1.0)》以及大量 Markdown 文件中出现的 `aliases`、`description`、`summary`、`problem`、`related_concept` 等字段，**本质上就是 ExMemo Tools 自定义元数据功能的深度应用**。理解这个插件的设计思路，就等于理解了本项目元数据体系的工程底座。

---

## 2. 核心架构分析

### 2.1 模块职责划分

```
src/
├── main.ts              ← 插件入口：命令注册、事件绑定、设置加载
├── settings.ts          ← 配置接口与默认值定义
├── settings_tab.ts      ← Obsidian 设置面板 UI（最复杂的 UI 文件）
├── meta.ts              ← 元数据生成主控：调度 FeatureExtractor、更新 front matter
├── feature_extractor.ts ← LLM 请求构建与响应解析核心
├── llm_utils.ts         ← LLM API 调用封装
├── index_generator.ts   ← 目录索引 / 搜索索引 / 批量元数据更新
├── select_folder.ts     ← 智能归档：目录推荐与文件移动
├── zettelkasten.ts      ← 卢曼卡片：提取、格式化、读写管理
├── edit_md.ts           ← 文本编辑与插入定位
├── llm_assistant.ts     ← AI 辅助编辑（多提示词管理）
├── prompts.ts           ← 提示词管理弹窗
├── utils.ts             ← 工具函数：front matter 更新、内容分块、标签加载等
└── lang/                ← 国际化（en / zh）
```

### 2.2 关键技术决策

#### 单请求多字段提取（FeatureExtractor）

插件最精妙的设计在于 `FeatureExtractor` 类。它不是为每个元数据字段分别调用一次 LLM，而是：

1. 将每个字段抽象为 `FeatureDefinition`（key + prompt + options + required + multiple）
2. 一次性构建一个复合 LLM 请求，要求返回统一 JSON 格式
3. 从响应中解析所有字段，支持多值字段自动拆分为数组

**优势**：大幅节省 API Token 消耗；字段间可以共享上下文理解。

**请求模板结构**：
```
I need to generate metadata for the following article. Requirements:

1. tags: [prompt]
   Available tags: xxx,yyy,zzz. Feel free to choose multiple...
2. category: [prompt]
   Available category: A,B,C. Must choose ONE...
3. description: [prompt]
...

Please return in the following JSON format:
{
    "tags": "value1,value2,value3",
    "category": "value for category",
    "description": "value for description"
}

File path: {path}
The article content is as follows:
{content}
```

#### 增量更新策略

`meta.ts` 中的 `addFeaturesForExtraction` 函数实现了**智能增量**：
- 检查 front matter 中是否已有该字段且非空
- 若已有则跳过，不重复调用 LLM
- 支持 `force` 模式强制覆盖
- 支持 `no-llm` 模式只更新时间戳和静态字段

#### 内容截断机制

为避免长文档耗尽 Token，插件提供三种截断策略：
- `head_only`：只取文档前 N 个 Token
- `head_tail`：取前段 + 后段（中间省略）
- `heading`：提取所有标题层级结构（最智能，保留文档骨架）

---

## 3. 六大功能模块深度解析

### 3.1 元数据生成（Meta）

**流程**：
1. `adjustCurrentFileMeta` 获取当前文件
2. `addFeaturesForExtraction` 检查哪些字段缺失
3. `FeatureExtractor.buildRequest()` 构建复合请求
4. `callLLM()` 调用大模型
5. 解析 JSON 结果，按字段写入 front matter
6. 额外处理：封面图、编辑时间、自定义元数据

**默认生成字段**：
- `tags` — 主题标签（多值）
- `category` — 归档分类（单值，必须在预设列表中）
- `description` — 概念摘要
- `title` — 机器可读标题/别名
- `updated` / `created` — 编辑时间（可选）
- `cover` — 封面图（可选）

**自定义元数据机制**：
通过 `customMetadata` 数组，用户可无限扩展字段。每个自定义字段支持两种类型：
- `static`：固定值，直接写入 front matter
- `prompt`：通过 LLM 动态生成

### 3.2 智能归档（Select Folder）

**并非简单的关键词匹配**，而是真正的 LLM 决策：

1. 获取当前文件标题和 description（优先）
2. 扫描整个 Vault 的目录结构
3. 若目录数 > 3，构造 Prompt 让 LLM 推荐最适合的 **3 个目录**
4. 用户从推荐结果中选择，插件执行 `vault.rename()` 移动文件

**Prompt 模板**：
```
The current file name is: '{basename}'. The description is: '{description}'.
Please help me find the three most suitable directories for storing this file,
and return only the directory paths, separated by line breaks.

Below is the list of directory paths:
{all_folder_paths}
```

### 3.3 AI 辅助编辑（LLM Assistant）

这是一个**通用 LLM 对话框**，核心能力：
- 多提示词管理：用户可保存、编辑、删除常用提示词
- 使用计数与最近访问时间排序
- 三种结果模式：追加到选中内容前 / 后，或直接替换
- 支持对话式编辑（`llmDialogEdit` 开关）

**本地高频提示词**（来自 data.json）：
1. "将短文修正为适合 Obsidian 阅读的格式"（使用 188 次）— 表情转文本、链接转脚注、去除外链图片
2. "精炼为干净流畅的自然段"（使用 31 次）— 剔除冗余，箭头连接段落
3. "录音转写文字规整成通畅文章"（使用 3 次）— 口语转书面，保留上下文

### 3.4 卢曼卡片（Zettelkasten）

**核心设计**：
- 卡片格式：`> [!zk {timestamp}-{flag}] {title}`，后续行以 `>` 开头
- `flag=0`：全文提取的卡片；`flag=1`：选中段落提取的卡片
- 选中提取优先于全文提取
- 支持批量去重：全文卡片可覆盖重写，选中卡片永久保留

**卡片管理器（CardManager）**：
- `readExistingCards()`：正则解析文档中所有卡片
- `removeNonSelectionCards()`：清理旧的全文卡片（避免重复）
- `writeCards()`：在文档顶部（front matter 后）或尾部插入卡片

### 3.5 目录索引生成（Index Generator）

**这是插件最强大的知识组织功能之一**。

为任意目录生成 `index_{dirname}.md` 文件，结构包含：
- **Front Matter**：聚合该目录下所有文件的 tags（按频次排序），标记为 `MOC`
- **文件列表（File List）**：简洁的文件链接列表
- **文件详情（File Detail）**：文件链接 + description
- **卡片汇总（Cards）**：如果文件包含卢曼卡片，一并摘录到索引中

**索引更新机制**：
- 增量更新：只重新生成内容块，不破坏手动添加的内容
- 使用 `updateContentBlock()` 按标题区块替换
- 索引文件本身也会调用 `adjustFileMeta` 生成元数据

**搜索索引**：
对 Obsidian 全局搜索结果右键，可将结果集生成为一个临时索引文件，自动以搜索 query 命名。

### 3.6 批量元数据更新

通过搜索右键菜单或目录右键，可对**一批文件**批量执行元数据提取：
- 自动过滤已有完整元数据的文件
- 预估 Token 消耗，弹窗让用户确认
- 提供取消按钮（`CancellableNotice`），支持中断
- 处理完成后自动刷新 Obsidian 元数据缓存

---

## 4. 本地调制深度分析

对比官方 `DEFAULT_SETTINGS` 与本地 `data.json`，可清晰看到用户围绕自身知识管理需求做的一系列深度定制。

### 4.1 LLM 后端切换

| 配置项 | 官方默认 | 本地调制 |
|-------|---------|---------|
| `llmBaseUrl` | `https://api.openai.com/v1` | `https://api.deepseek.com/` |
| `llmModelName` | `gpt-4o` | `deepseek-v4-flash` |
| `llmToken` | `sk-` | `sk-41e48c52...`（已脱敏） |

**结论**：从 OpenAI 生态迁移到 DeepSeek 国产模型，兼顾成本与中文能力。

### 4.2 字段映射重定义

| 语义角色 | 官方默认字段名 | 本地字段名 |
|---------|--------------|-----------|
| 机器可读标识 | `title` | **`aliases`** |
| 人类可读标题 | — | 新增 **`AI title`**（自定义元数据） |
| 概念摘要 | `description` | `description`（保持一致） |
| 主题标签 | `tags` | `tags`（保持一致） |
| 归档分类 | `category` | `category`（保持一致） |

**关键洞察**：用户将 `metaTitleFieldName` 从 `title` 改为 `aliases`，意味着插件生成的"标题"实际上对应本项目的 `aliases` 字段。而真正的文章原始标题由转换器基类生成，存放在 `title` 字段中。

### 4.3 自定义元数据扩展（8 个新增字段）

本地配置在 `customMetadata` 中新增了 8 个 prompt 类型字段，几乎完整复刻了《全自动知识卡片元数据生成规范》的字段体系：

| 字段 | 类型 | 与规范的对应关系 |
|------|------|----------------|
| `related concept` | prompt | `related_concept` — 关联概念 |
| `problem` | prompt | `problem` — 核心问题 |
| `summary` | prompt | `summary` — 精华要点 |
| `next step` | prompt | `next_step` — 后续行动建议 |
| `suggestion` | prompt | `suggestion` — 完善建议 |
| `audience` | prompt | `audience` — 目标读者画像 |
| `difficulty` | prompt | `difficulty` — 阅读难度 |
| `rating` | prompt | `rating` — 价值评分 |
| `AI title` | prompt | `AI title` — 人类可读标题 |

**每个字段的 prompt 都经过精心编写**，包含：
- 明确的输出格式要求（字数限制、分隔符、是否加引号）
- 具体的评分/分级标准（如 difficulty 的 5 级定义与 rating 的 1-5 分标准）
- 反例与禁忌（如禁止出现"本文""这篇文章"等指代词）

### 4.4 标签体系与分类体系的固化

**标签体系（25 个根标签）**：
编程与架构、算法与模型、工具与实践、数学与逻辑、人工智能、产品与设计、项目管理、商业与管理、职业发展、领域知识、阅读与写作、学习方法、教育、信息管理、健康、情绪与心理、运动与饮食、自我管理、旅行与自然、创作与设计、影视与音乐、财务与经济、人文与社科、哲学与思维、自然科学、其他

**分类体系（16 个类别）**：
生活记录、健康、情绪与思考、阅读笔记、待读清单、学习笔记、创意与创作、专业技术、产品与设计、项目与会议、求职面试、演讲与分享、财务、任务管理、个人信息、其他

这些体系被硬编码在 `metaTagsPrompt` 和 `metaCategoryPrompt` 中，作为 LLM 的约束条件。这意味着：**本项目的元数据不是自由生成的，而是在严格受控的语义空间内产生的**，这是保证后续聚合、导航、检索准确性的关键。

### 4.5 功能开关与性能调优

| 配置项 | 官方默认 | 本地调制 | 说明 |
|-------|---------|---------|------|
| `metaMaxTokens` | 1000 | **150000** | 大幅放宽，允许处理超长文档 |
| `metaTruncateMethod` | `head_only` | **`heading`** | 改用标题骨架提取，保留结构 |
| `metaEditTimeEnabled` | true | **false** | 关闭自动时间戳，减少 front matter 变动 |
| `insertCardsAt` | `before` | **`after`** | 卡片插入到文档末尾 |
| `llmResultMode` | `UNKNOWN` | **`replace`** | 编辑结果直接替换原文 |

---

## 5. 对本项目的启发与可借鉴点

### 5.1 元数据补全自动化的工程路径

ExMemo Tools 已经证明：**基于 LLM 的批量元数据补全是可行且成本可控的**。本项目可以借鉴其技术路径：

1. **使用 FeatureExtractor 的批量请求模式**：将多个字段合并为一次 LLM 调用，而非每个字段单独调用
2. **增量更新机制**：只处理缺失字段的文件，避免重复消耗 Token
3. **内容截断策略**：对超长网页使用 `heading` 模式提取骨架，而非全文送入

### 5.2 索引生成可直接复用

ExMemo Tools 的 `index_generator.ts` 已经实现了：
- 按目录聚合子文件和子目录的元数据
- 生成包含 `tags`、`description`、卡片汇总的 MOC 文件
- 支持搜索结果生成临时索引

**建议**：本项目可直接 fork 或改编 `index_generator.ts` 的逻辑，替换 Obsidian API 调用为文件系统操作，生成静态的 `语义导航.md`。

### 5.3 智能归档的启发

虽然本项目的归档已经通过 `classify_html.py` 按域名完成了第一层分类，但 ExMemo Tools 的归档思路提示了**第二层语义归档**的可能性：
- 同一网站（如掘金）的文章可能跨越多个 `category`（专业技术、产品与设计）
- 未来可开发脚本，基于 `category` 字段将文件从"网站目录"软链接或重新组织到"知识目录"

### 5.4 卢曼卡片与知识卡片的差异

ExMemo Tools 的卢曼卡片是**片段级**的（从文中提取一个核心观点），而本项目的知识卡片是**文档级**的（整篇文章的元数据描述）。两者互补：
- 文档级元数据用于**检索和导航**
- 片段级卡片用于**深度阅读和知识连接**

**建议**：可在 Obsidian 中使用 ExMemo Tools 为关键文章生成卢曼卡片，作为文档级元数据的补充。

---

## 6. 附录：关键源码文件速查

| 文件 | 行数 | 核心关注点 |
|------|------|-----------|
| `feature_extractor.ts` | ~186 | 单请求多字段提取的 JSON 构建与解析 |
| `meta.ts` | ~279 | 字段缺失检测、增量更新、front matter 写入 |
| `index_generator.ts` | ~538 | 目录索引结构、批量处理、Token 预估 |
| `zettelkasten.ts` | ~263 | 卡片格式定义、正则解析、去重策略 |
| `select_folder.ts` | ~198 | 目录推荐 Prompt、文件移动 |
| `settings_tab.ts` | ~840 | UI 面板结构（了解配置项全貌） |
| `data.json`（本地） | ~121 | 用户实际运行的配置快照 |

---

## 7. 参考资料

- 官方仓库：https://github.com/exmemo-ai/obsidian-exmemo-tools
- 本地安装路径：`C:\Users\D-001\Desktop\Project-20260303-网页结构分析\.obsidian\plugins\exmemo-tools`
- 本地配置文件：`.obsidian/plugins/exmemo-tools/data.json`
- 关联文档：`全自动知识卡片元数据生成规范 (v1.0).md`
