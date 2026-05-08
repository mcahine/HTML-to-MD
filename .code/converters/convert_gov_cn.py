#!/usr/bin/env python3
"""中国政府网站 (gov.cn) HTML 转 Markdown 转换器

说明：
- 中国政府网的政策文件附件（如PDF、Excel表格）通常是独立文件
- 本转换器只提取主文章页面的内容
- TODO: 后续添加附件自动下载功能（通过解析页面中的附件链接并下载）
"""
import sys
import os
import re
import base64
from pathlib import Path
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from html_converter_base import HTMLConverterBase, safe_print


class GovCnConverter(HTMLConverterBase):
    def __init__(self):
        super().__init__(
            domain='gov.cn',
            name='中国政府网',
            content_selector=None,  # 将自定义提取逻辑
            title_selector=None,
            author_selector=None,
            date_selector=None,
            remove_selectors=[]
        )
    
    def is_valid_image_src(self, src):
        """检查图片 src 是否有效"""
        if not src:
            return False
        if src in ['data:,', 'data:image/png,', 'data:image/jpeg,', '#']:
            return False
        if src.strip() == '':
            return False
        return True
    
    def read_html(self, html_path):
        """读取HTML文件，自动检测编码"""
        encodings = ['utf-8', 'utf-8-sig', 'gbk', 'gb2312', 'latin1']
        
        for encoding in encodings:
            try:
                with open(html_path, 'r', encoding=encoding) as f:
                    content = f.read()
                if '����' not in content[:5000]:
                    return content
            except:
                continue
        
        with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    
    def extract_url_from_html(self, html_content):
        """从 HTML 注释中提取原始 URL"""
        match = re.search(r'url:\s*(https?://[^\s\n]+)', html_content)
        if match:
            return match.group(1).strip()
        return ''
    
    def extract_metadata(self, html_content, html_path):
        """提取中国政府网文章的元数据"""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, 'lxml')
        
        metadata = {
            'title': '',
            'author': '',
            'date': '',
            'source': '中国政府网',
            'url': self.extract_url_from_html(html_content),
            'converted_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # 1. 从 <title> 标签提取标题（优先）
        title_tag = soup.find('title')
        if title_tag:
            title_text = title_tag.get_text(strip=True)
            # 中国政府网 title 格式通常为：标题_栏目_网站名
            # 例如：商事调解条例_国务院公报_中国政府网
            # 提取第一个下划线前的内容作为标题
            if '_' in title_text:
                metadata['title'] = title_text.split('_')[0]
            else:
                metadata['title'] = title_text
        
        # 2. 备选：尝试从 pages_title 提取标题
        if not metadata['title']:
            title_elem = soup.select_one('.pages_title')
            if title_elem:
                metadata['title'] = title_elem.get_text(strip=True)
        
        # 3. 备选：尝试从 #UCAP-CONTENT 的第一段提取标题
        if not metadata['title']:
            ucap = soup.select_one('#UCAP-CONTENT')
            if ucap:
                # 找到第一个有文字的段落
                for p in ucap.find_all(['p', 'div']):
                    text = p.get_text(strip=True)
                    if text and len(text) > 5:
                        metadata['title'] = text[:100]  # 取前100字符作为标题
                        break
        
        # 3. 从文件名提取日期
        filename = os.path.basename(html_path)
        date_match = re.search(r'(\d{4})(\d{2})(\d{2})', filename)
        if date_match:
            metadata['date'] = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
        
        # 4. 尝试从内容中提取日期（常见格式：2025年12月31日）
        if not metadata['date']:
            date_pattern = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日', html_content)
            if date_pattern:
                metadata['date'] = f"{date_pattern.group(1)}-{date_pattern.group(2):0>2}-{date_pattern.group(3):0>2}"
        
        return metadata, soup
    
    def extract_images(self, soup, html_path, output_dir):
        """提取图片，包括 base64 图片"""
        base_name = Path(html_path).stem
        assets_dir = os.path.join(output_dir, 'assets', f"{base_name}_assets")
        os.makedirs(assets_dir, exist_ok=True)
        
        img_count = 0
        for img in soup.find_all('img'):
            src = img.get('src', '')
            if not self.is_valid_image_src(src):
                continue
            
            # 处理 base64 图片
            if src.startswith('data:image'):
                try:
                    match = re.match(r'data:image/(\w+);base64,(.+)', src)
                    if match:
                        ext = match.group(1)
                        data = match.group(2)
                        if not data or data.strip() == '':
                            continue
                        img_data = base64.b64decode(data)
                        if len(img_data) < 100:
                            continue
                        
                        img_count += 1
                        img_name = f"image_{img_count:03d}.{ext}"
                        img_path = os.path.join(assets_dir, img_name)
                        
                        with open(img_path, 'wb') as f:
                            f.write(img_data)
                        
                        rel_path = f"assets/{base_name}_assets/{img_name}"
                        img['src'] = rel_path
                        safe_print(f"  Saved: {rel_path}")
                except Exception as e:
                    safe_print(f"  Error saving image: {e}")
        
        return img_count
    
    def element_to_markdown(self, elem, level=0, visited=None):
        """将单个元素转换为Markdown，处理行内格式"""
        from bs4 import NavigableString
        
        if visited is None:
            visited = set()
        
        # 防止循环引用
        elem_id = id(elem)
        if elem_id in visited:
            return ''
        visited.add(elem_id)
        
        if isinstance(elem, NavigableString):
            text = str(elem)
            return text if text.strip() else ''
        
        if elem.name is None:
            return ''
        
        # 跳过这些元素
        if elem.name in ['script', 'style', 'nav']:
            return ''
        
        # 处理标题
        if elem.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            text = elem.get_text(strip=True)
            if text:
                level_marker = '#' * int(elem.name[1])
                return f"{level_marker} {text}\n\n"
            return ''
        
        # 处理图片
        if elem.name == 'img':
            src = elem.get('src', '')
            alt = elem.get('alt', '')
            if self.is_valid_image_src(src):
                return f"![{alt}]({src})\n\n"
            return ''
        
        # 处理链接
        if elem.name == 'a':
            href = elem.get('href', '')
            text = elem.get_text(strip=True)
            if href and text:
                return f"[{text}]({href})"
            return text
        
        # 处理强调（加粗）
        if elem.name in ['strong', 'b']:
            text = elem.get_text(strip=True)
            return f"**{text}**" if text else ''
        
        # 处理斜体
        if elem.name in ['em', 'i']:
            text = elem.get_text(strip=True)
            return f"*{text}*" if text else ''
        
        # 处理段落
        if elem.name == 'p':
            parts = []
            for child in elem.children:
                part = self.element_to_markdown(child, level + 1, visited)
                if part:
                    parts.append(part)
            text = ''.join(parts).strip()
            text = re.sub(r'[ \t]+', ' ', text)
            return f"{text}\n\n" if text else ''
        
        # 处理列表项
        if elem.name == 'li':
            parts = []
            for child in elem.children:
                part = self.element_to_markdown(child, level + 1, visited)
                if part:
                    parts.append(part)
            return ''.join(parts).strip()
        
        # 处理无序列表
        if elem.name == 'ul':
            items = []
            for li in elem.find_all('li', recursive=False):
                text = self.element_to_markdown(li, level + 1, visited)
                if text:
                    items.append(f"- {text}")
            return '\n'.join(items) + '\n\n' if items else ''
        
        # 处理有序列表
        if elem.name == 'ol':
            items = []
            for i, li in enumerate(elem.find_all('li', recursive=False), 1):
                text = self.element_to_markdown(li, level + 1, visited)
                if text:
                    items.append(f"{i}. {text}")
            return '\n'.join(items) + '\n\n' if items else ''
        
        # 处理表格
        if elem.name == 'table':
            return self._convert_table_to_markdown(elem)
        
        # 处理换行
        if elem.name == 'br':
            return '\n'
        
        # 处理 div/section/article（递归处理子元素）
        if elem.name in ['div', 'section', 'article']:
            parts = []
            for child in elem.children:
                part = self.element_to_markdown(child, level + 1, visited)
                if part:
                    parts.append(part)
            return ''.join(parts)
        
        # 默认递归处理子元素
        parts = []
        for child in elem.children:
            part = self.element_to_markdown(child, level + 1, visited)
            if part:
                parts.append(part)
        return ''.join(parts)
    
    def _convert_table_to_markdown(self, table):
        """将HTML表格转换为Markdown表格"""
        rows = []
        headers = []
        
        # 提取表头
        thead = table.find('thead')
        if thead:
            ths = thead.find_all('th')
            if ths:
                headers = [th.get_text(strip=True) for th in ths]
        
        # 如果没有thead，检查第一行
        if not headers:
            first_row = table.find('tr')
            if first_row:
                ths = first_row.find_all('th')
                if ths:
                    headers = [th.get_text(strip=True) for th in ths]
        
        # 提取数据行
        tbody = table.find('tbody')
        if tbody:
            trs = tbody.find_all('tr')
        else:
            trs = table.find_all('tr')
        
        for tr in trs:
            if tr.find('th') and headers:
                continue
            
            tds = tr.find_all(['td', 'th'])
            row = [td.get_text(strip=True) for td in tds]
            if row:
                rows.append(row)
        
        if not rows and not headers:
            return ''
        
        md_lines = []
        
        if headers:
            md_lines.append('| ' + ' | '.join(headers) + ' |')
            md_lines.append('| ' + ' | '.join(['---'] * len(headers)) + ' |')
        elif rows:
            md_lines.append('| ' + ' | '.join(rows[0]) + ' |')
            md_lines.append('| ' + ' | '.join(['---'] * len(rows[0])) + ' |')
            rows = rows[1:]
        
        for row in rows:
            md_lines.append('| ' + ' | '.join(row) + ' |')
        
        return '\n'.join(md_lines) + '\n\n'
    
    def convert(self, html_path, output_dir=None):
        """转换单个HTML文件"""
        if not os.path.exists(html_path):
            safe_print(f"File not found: {html_path}")
            return False
        
        if output_dir is None:
            output_dir = os.path.dirname(html_path) or '.'
        
        # 固定输出目录为"中国政府网"
        domain_dir = os.path.join(output_dir, '中国政府网')
        os.makedirs(domain_dir, exist_ok=True)
        
        # 读取HTML
        html_content = self.read_html(html_path)
        
        # 提取元数据
        metadata, soup = self.extract_metadata(html_content, html_path)
        
        # 找到主要内容区域
        content_elem = None
        
        # 策略1：尝试 #UCAP-CONTENT > div（常规布局）
        ucap = soup.select_one('#UCAP-CONTENT')
        if ucap:
            # 获取第一个子div
            for child in ucap.children:
                if hasattr(child, 'name') and child.name == 'div':
                    content_elem = child
                    break
            if not content_elem:
                content_elem = ucap
        
        # 策略2：找到包含最多文本内容的 .pages_content（某些文件使用表格布局）
        if not content_elem:
            pages_contents = soup.find_all(class_='pages_content')
            if pages_contents:
                # 选择文本长度最长的
                content_elem = max(pages_contents, key=lambda x: len(x.get_text(strip=True)))
                
                # 如果 .pages_content 是 table，提取其中的内容单元格
                if content_elem.name == 'table':
                    # 找到包含最多内容的 td 单元格
                    tds = content_elem.find_all(['td', 'th'])
                    if tds:
                        content_elem = max(tds, key=lambda x: len(x.get_text(strip=True)))
        
        # 策略3：其他备选选择器
        if not content_elem:
            selectors = ['.content', '#content', 'article']
            for selector in selectors:
                content_elem = soup.select_one(selector)
                if content_elem:
                    break

        # 策略4：政务公开模板 (.zwgkbg) 或其他长文本容器
        if not content_elem:
            for cls in ['zwgkbg', 'pages_content', 'TRS_Editor', 'TRS_PreAppend']:
                cand = soup.find(class_=cls)
                if cand:
                    # If it's a table, extract the best td
                    if cand.name == 'table':
                        tds = cand.find_all(['td', 'th'])
                        if tds:
                            cand = max(tds, key=lambda x: len(x.get_text(strip=True)))
                    content_elem = cand
                    break

        # 策略5：最后兜底 — 找正文最多的容器元素
        if not content_elem:
            best, best_len = None, 0
            for tag in soup.find_all(['div', 'td', 'section', 'table']):
                t = tag.get_text(strip=True)
                if len(t) > best_len and len(t) > 300:
                    best_len = len(t)
                    best = tag
            content_elem = best
        
        if not content_elem:
            safe_print(f"Content not found: {html_path}")
            return False
        
        # 移除不需要的元素
        for selector in ['script', 'style', 'nav', '.header', '.footer',
                         '.sidebar', '.breadcrumb', '.share-box',
                         '.related-links', '.pages_date',
                         '.detailtop',       # 下载链接+文档分类头部
                         '.downloadbtn',     # 下载按钮
                         '.xg',              # 相关信息
                         ]:
            for elem in content_elem.select(selector):
                elem.decompose()

        # 提取图片（在转换内容之前，更新 img src）
        self.extract_images(soup, html_path, domain_dir)

        # 转换内容
        md_content = self.element_to_markdown(content_elem)

        # ── Post-processing ────────────────────────────────────
        # 清理多余空行
        md_content = re.sub(r'\n{3,}', '\n\n', md_content.strip())

        # 清理 data URI 图片（已被提取并替换为本地路径）
        md_content = re.sub(r'!\[([^\]]*)\]\(data:[^)]+\)\n*', '', md_content)

        # 移除文档分类标签行（国家发展改革委行政规范性文件/规章等）
        md_content = re.sub(
            r'^\s*(?:国家发展和改革委员会|国家发展改革委)\s*(?:行政规范性文件|规章|令|公告|通告|通知)\s*',
            '', md_content, flags=re.MULTILINE)

        # 移除下载链接残留：[下载文字版](url) [下载图片版](url) [下载OFD版](url)
        md_content = re.sub(r'\[下载[^\]]*\]\([^)]+\)', '', md_content)

        # 修复被下载链接打断的标题：# 标题（原本和下载链接粘在一起）
        md_content = re.sub(r'(?:[^#\n])(#[^#\n]{5,80})', r'\n\n\1', md_content)

        # 移除政府信息公开元数据表格行（含全角冒号等字符）
        md_content = re.sub(
            r'^\s*(?:政府信息公开\s*)?\|?\s*(?:公开事项名称|索引号|制发日期|主办单位)[^|]*\|.*$',
            '', md_content, flags=re.MULTILINE)
        # 移除表格分隔线残留
        md_content = re.sub(r'^\s*\|[\s\-:|]+\|\s*$', '', md_content, flags=re.MULTILINE)
        # 移除空表格行
        md_content = re.sub(r'^\s*\|\s*\|\s*$', '', md_content, flags=re.MULTILINE)
        # 移除政府信息公开表头行
        md_content = re.sub(r'^\s*政府信息公开.*$', '', md_content, flags=re.MULTILINE)

        # 修复 **** → 无（合并相邻加粗标记的间隙）
        md_content = re.sub(r'\*\*\*\*', '', md_content)

        # 修复被空行打断的加粗块：**text**\n\n**more** → **textmore**
        md_content = re.sub(r'\*\*([^*\n]+)\*\*\n\n\*\*([^*]+)\*\*', r'**\1\2**', md_content)

        # 先确保章节标题前有空行（在移除加粗之前）
        md_content = re.sub(r'([^\n])\*\*([一二三四五六七八九十]+[、，。])', r'\1\n\n**\2', md_content)
        md_content = re.sub(r'([^\n])\*\*([（(][一二三四五六七八九十]+[）)])', r'\1\n\n**\2', md_content)
        md_content = re.sub(r'([^\n])\*\*([第][^**]+[条款节章])', r'\1\n\n**\2', md_content)

        # 再移除编号/条目前的加粗标记
        # **一、总体目标** → 一、总体目标
        md_content = re.sub(r'\*\*([一二三四五六七八九十]+[、，。][^*]+)\*\*', r'\1', md_content)
        # **（一）深入开展...** → （一）深入开展...
        md_content = re.sub(r'\*\*([（(][一二三四五六七八九十]+[）)][^*]*?)\*\*', r'\1', md_content)
        # Remove bold from article/chapter numbering
        # **标题第一条** → **标题**\n\n第一条  (split heading from article)
        md_content = re.sub(
            r'\*\*(.+?)(第[一二三四五六七八九十百千\d]+条)\*\*',
            r'**\1**\n\n\2 ', md_content)
        # **第一条** → 第一条
        md_content = re.sub(r'\*\*(第[一二三四五六七八九十百千\d]+条)\*\*', r'\1 ', md_content)
        md_content = re.sub(r'\*\*(第[一二三四五六七八九十百千\d]+[章节款])\*\*', r'\1 ', md_content)

        # Use EM SPACE paragraphs as boundary: ensure blank line before each    paragraph
        md_content = re.sub(r'([^\n])\n(  )', r'\1\n\n\2', md_content)

        # Insert blank line before document title headings
        md_content = re.sub(r'([^\n])\n(\*\*[^*。，、；：！？\n]{4,40}\*\*)', r'\1\n\n\2', md_content)
        
        # TODO: 附件下载功能
        # 中国政府网的附件（如PDF、Excel表格）通常是独立文件，通过页面中的链接引用
        # 后续可以通过查找包含 "附件" 关键词的 <a> 标签，提取 href 并下载
        # 示例实现：
        #   attachment_links = soup.find_all('a', string=re.compile('附件'))
        #   for link in attachment_links:
        #       href = link.get('href')
        #       if href:
        #           download_attachment(href, domain_dir)
        
        # 构建 YAML Front Matter
        yaml_lines = ["---"]
        yaml_lines.append(f"title: {metadata['title']}")
        if metadata['author']:
            yaml_lines.append(f"author: {metadata['author']}")
        if metadata['date']:
            yaml_lines.append(f"date: {metadata['date']}")
        yaml_lines.append(f"source: {metadata['source']}")
        if metadata['url']:
            yaml_lines.append(f"url: {metadata['url']}")
        yaml_lines.append(f"converted_at: {metadata['converted_at']}")
        yaml_lines.append("---")
        yaml_lines.append("")
        
        # 写入文件
        base_name = Path(html_path).stem
        md_path = os.path.join(domain_dir, f"{base_name}.md")
        
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(yaml_lines) + '\n' + md_content)
        
        safe_print(f"Converted: {md_path}")
        return True


if __name__ == '__main__':
    converter = GovCnConverter()
    if len(sys.argv) > 1:
        if sys.argv[1].endswith('.html'):
            converter.convert(sys.argv[1])
        else:
            # 批量转换
            import glob
            files = glob.glob(os.path.join(sys.argv[1], "*中国政府网*.html"))
            print(f"Found {len(files)} files")
            for f in files:
                converter.convert(f)
    else:
        # 默认：转换当前目录
        import glob
        files = glob.glob("*中国政府网*.html")
        print(f"Found {len(files)} files")
        for f in files:
            converter.convert(f)
