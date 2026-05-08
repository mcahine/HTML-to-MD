#!/usr/bin/env python3
"""虎嗅 (huxiu.com) HTML 转 Markdown 转换器"""
import sys
import os
import re
import base64
from pathlib import Path
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from html_converter_base import HTMLConverterBase, safe_print


class HuxiuConverter(HTMLConverterBase):
    def __init__(self):
        super().__init__(
            domain='huxiu.com',
            name='虎嗅',
            content_selector=None,
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
    
    def extract_metadata(self, html_content, html_path):
        """提取虎嗅文章的元数据"""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, 'lxml')
        
        metadata = {
            'title': '',
            'author': '',
            'date': '',
            'source': '虎嗅',
            'url': '',
            'converted_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # 提取标题 - 尝试多种选择器
        for sel in ['h1', '.article-title', '.title']:
            title_elem = soup.select_one(sel)
            if title_elem:
                metadata['title'] = title_elem.get_text(strip=True)
                break
        
        # 从文件名提取日期
        filename = os.path.basename(html_path)
        date_match = re.search(r'(\d{4})(\d{2})(\d{2})', filename)
        if date_match:
            metadata['date'] = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
        
        # 提取作者 - 尝试多种选择器
        for sel in ['.author-name', '.article-author', '.author', '[class*="author"]']:
            author_elem = soup.select_one(sel)
            if author_elem:
                metadata['author'] = author_elem.get_text(strip=True)
                if metadata['author']:
                    break
        
        # 从 meta 标签提取 URL
        og_url = soup.find('meta', property='og:url')
        if og_url:
            metadata['url'] = og_url.get('content', '')
        
        return metadata, soup
    
    def extract_content(self, soup):
        """提取文章内容区域"""
        # 尝试多种选择器
        selectors = [
            '.article__content',  # 虎嗅新版
            '.article-detail',    # 虎嗅旧版
            '.article-content',
            '.article-wrap',
            'article',
        ]
        
        for selector in selectors:
            content = soup.select_one(selector)
            if content:
                # 确保有足够的内容
                text_len = len(content.get_text(strip=True))
                if text_len > 500:
                    return content
        
        return None
    
    def element_to_markdown(self, elem, level=0, visited=None):
        """将单个元素转换为Markdown"""
        from bs4 import NavigableString
        
        if visited is None:
            visited = set()
        
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
        if elem.name in ['script', 'style', 'nav', 'aside']:
            return ''
        
        # 处理标题
        if elem.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            text = elem.get_text(strip=True)
            if text:
                level_marker = '#' * int(elem.name[1])
                return f"\n{level_marker} {text}\n\n"
            return ''
        
        # 处理图片
        if elem.name == 'img':
            src = elem.get('src', '')
            alt = elem.get('alt', '')
            if self.is_valid_image_src(src):
                return f"\n![{alt}]({src})\n\n"
            return ''
        
        # 处理链接
        if elem.name == 'a':
            href = elem.get('href', '')
            text = elem.get_text(strip=True)
            if href and text:
                return f"[{text}]({href})"
            return text
        
        # 处理加粗
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
            if text:
                return f"\n{text}\n\n"
            return ''
        
        # 处理列表
        if elem.name == 'ul':
            items = []
            for li in elem.find_all('li', recursive=False):
                text = self.element_to_markdown(li, level + 1, visited)
                if text:
                    items.append(f"- {text.strip()}")
            return '\n' + '\n'.join(items) + '\n\n' if items else ''
        
        if elem.name == 'ol':
            items = []
            for i, li in enumerate(elem.find_all('li', recursive=False), 1):
                text = self.element_to_markdown(li, level + 1, visited)
                if text:
                    items.append(f"{i}. {text.strip()}")
            return '\n' + '\n'.join(items) + '\n\n' if items else ''
        
        # 处理表格
        if elem.name == 'table':
            return self._convert_table_to_markdown(elem)
        
        if elem.name == 'tr':
            # 表格行在表格处理中直接处理，这里返回空
            return ''
        
        if elem.name in ['td', 'th']:
            text = elem.get_text(strip=True)
            return text
        
        if elem.name == 'li':
            parts = []
            for child in elem.children:
                part = self.element_to_markdown(child, level + 1, visited)
                if part:
                    parts.append(part)
            return ''.join(parts).strip()
        
        # 处理 div/section/article
        if elem.name in ['div', 'section', 'article']:
            parts = []
            for child in elem.children:
                part = self.element_to_markdown(child, level + 1, visited)
                if part:
                    parts.append(part)
            return ''.join(parts)
        
        # 默认递归处理
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
            # 跳过表头行（如果已经在headers中）
            if tr.find('th') and headers:
                continue
            
            tds = tr.find_all(['td', 'th'])
            row = [td.get_text(strip=True) for td in tds]
            if row:
                rows.append(row)
        
        if not rows and not headers:
            return ''
        
        # 构建Markdown表格
        md_lines = []
        
        # 表头
        if headers:
            md_lines.append('| ' + ' | '.join(headers) + ' |')
            md_lines.append('| ' + ' | '.join(['---'] * len(headers)) + ' |')
        elif rows:
            # 使用第一行作为表头
            md_lines.append('| ' + ' | '.join(rows[0]) + ' |')
            md_lines.append('| ' + ' | '.join(['---'] * len(rows[0])) + ' |')
            rows = rows[1:]
        
        # 数据行
        for row in rows:
            md_lines.append('| ' + ' | '.join(row) + ' |')
        
        return '\n' + '\n'.join(md_lines) + '\n\n'
    
    def convert(self, html_path, output_dir=None):
        """转换单个HTML文件"""
        if not os.path.exists(html_path):
            safe_print(f"File not found: {html_path}")
            return False
        
        if output_dir is None:
            output_dir = os.path.dirname(html_path) or '.'
        
        # 固定输出目录
        domain_dir = os.path.join(output_dir, '虎嗅')
        os.makedirs(domain_dir, exist_ok=True)
        
        # 读取HTML
        with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
            html_content = f.read()
        
        # 提取元数据
        metadata, soup = self.extract_metadata(html_content, html_path)
        
        # 提取内容
        content_elem = self.extract_content(soup)
        if not content_elem:
            safe_print(f"Content not found: {html_path}")
            return False
        
        # 移除不需要的元素
        for selector in ['.ad-container', '.share-box', '.related-news',
                         '.comment-section', '.article__bottom-content',
                         '.js-article-wrap', 'script', 'style']:
            for elem in content_elem.select(selector):
                elem.decompose()
        
        # 提取图片（在转换内容之前，更新 img src）
        self.extract_images(content_elem, html_path, domain_dir)
        
        # 转换内容
        md_content = self.element_to_markdown(content_elem)
        
        # 清理多余空行
        md_content = re.sub(r'\n{3,}', '\n\n', md_content.strip())
        
        # 清理 data URI
        md_content = re.sub(r'!\[([^\]]*)\]\(data:[^)]+\)\n*', '', md_content)
        
        # 清理文末推广内容（文章标题、文章链接、阅读原文等）
        # 匹配 "文章标题：" 开始到文末的推广内容
        md_content = re.sub(r'\n+文章标题：.*$', '', md_content, flags=re.DOTALL)
        # 清理 "阅读原文：" 相关行
        md_content = re.sub(r'\n+阅读原文：.*$', '', md_content, flags=re.DOTALL)
        # 清理 "文章链接：" 相关行
        md_content = re.sub(r'\n+文章链接：.*$', '', md_content, flags=re.DOTALL)
        
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
    converter = HuxiuConverter()
    if len(sys.argv) > 1:
        if sys.argv[1].endswith('.html'):
            converter.convert(sys.argv[1])
        else:
            import glob
            files = glob.glob(os.path.join(sys.argv[1], "*虎嗅*.html"))
            print(f"Found {len(files)} files")
            for f in files:
                converter.convert(f)
    else:
        import glob
        files = glob.glob("*虎嗅*.html")
        print(f"Found {len(files)} files")
        for f in files:
            converter.convert(f)
