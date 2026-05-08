#!/usr/bin/env python3
"""中国日报网 (chinadaily.com.cn) HTML 转 Markdown 转换器"""
import sys
import os
import re
import base64
from pathlib import Path
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from html_converter_base import HTMLConverterBase, safe_print


class ChinaDailyConverter(HTMLConverterBase):
    def __init__(self):
        super().__init__(
            domain='chinadaily.com.cn',
            name='中国日报网',
            content_selector='.article, #Content, .article-content',
            title_selector='.dabiaoti, h1',
            author_selector=None,
            date_selector='.fenx',
            remove_selectors=['script', 'style', 'nav', '.fenx', '.dabiaoti', 
                           '.related-news', '.comment-box', '.ad', 
                           '.share-box', '.editor']
        )
    
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
        """提取中国日报网文章的元数据"""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, 'lxml')
        
        metadata = {
            'title': '',
            'author': '中国日报网',
            'date': '',
            'source': '中国日报网',
            'url': self.extract_url_from_html(html_content),
            'converted_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # 提取标题
        title_elem = soup.select_one('.dabiaoti')
        if not title_elem:
            title_elem = soup.find('h1')
        if title_elem:
            metadata['title'] = title_elem.get_text(strip=True)
        
        # 从文件名提取日期作为备选
        filename = os.path.basename(html_path)
        date_match = re.search(r'(\d{4})(\d{2})(\d{2})', filename)
        if date_match:
            metadata['date'] = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
        
        # 尝试从 .fenx 中提取日期
        fenx = soup.select_one('.fenx')
        if fenx:
            text = fenx.get_text(strip=True)
            # 匹配 2026年01月22日 格式
            date_match = re.search(r'(\d{4})[年/-](\d{1,2})[月/-](\d{1,2})', text)
            if date_match:
                metadata['date'] = f"{date_match.group(1)}-{date_match.group(2):0>2}-{date_match.group(3):0>2}"
        
        return metadata, soup
    
    def is_valid_image_src(self, src):
        """检查图片 src 是否有效"""
        if not src:
            return False
        if src in ['data:,', 'data:image/png,', 'data:image/jpeg,', '#']:
            return False
        if src.strip() == '':
            return False
        return True
    
    def element_to_markdown(self, elem, level=0):
        """将单个元素转换为Markdown"""
        from bs4 import NavigableString
        
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
        
        # 处理代码块
        if elem.name == 'pre':
            code_elem = elem.find('code')
            if code_elem:
                code = code_elem.get_text()
                lang = ''
                if code_elem.get('class'):
                    for cls in code_elem.get('class'):
                        if 'language-' in cls:
                            lang = cls.replace('language-', '')
                            break
                if code.strip():
                    return f"```{lang}\n{code.strip()}\n```\n\n"
            text = elem.get_text()
            if text.strip():
                return f"```\n{text.strip()}\n```\n\n"
            return ''
        
        # 处理内联代码
        if elem.name == 'code':
            code = elem.get_text(strip=True)
            return f"`{code}`" if code else ''
        
        # 处理强调
        if elem.name in ['strong', 'b']:
            text = elem.get_text(strip=True)
            return f"**{text}**" if text else ''
        
        if elem.name in ['em', 'i']:
            text = elem.get_text(strip=True)
            return f"*{text}*" if text else ''
        
        # 处理段落
        if elem.name == 'p':
            parts = []
            for child in elem.children:
                part = self.element_to_markdown(child, level + 1)
                if part:
                    parts.append(part)
            text = ''.join(parts).strip()
            text = re.sub(r'[ \t]+', ' ', text)
            return f"{text}\n\n" if text else ''
        
        # 处理列表项
        if elem.name == 'li':
            parts = []
            for child in elem.children:
                part = self.element_to_markdown(child, level + 1)
                if part:
                    parts.append(part)
            return ''.join(parts).strip()
        
        # 处理无序列表
        if elem.name == 'ul':
            items = []
            for li in elem.find_all('li', recursive=False):
                text = self.element_to_markdown(li, level + 1)
                if text:
                    items.append(f"- {text}")
            return '\n'.join(items) + '\n\n' if items else ''
        
        # 处理有序列表
        if elem.name == 'ol':
            items = []
            for i, li in enumerate(elem.find_all('li', recursive=False), 1):
                text = self.element_to_markdown(li, level + 1)
                if text:
                    items.append(f"{i}. {text}")
            return '\n'.join(items) + '\n\n' if items else ''
        
        # 处理引用块
        if elem.name == 'blockquote':
            parts = []
            for child in elem.children:
                part = self.element_to_markdown(child, level + 1)
                if part:
                    parts.append(part)
            text = ''.join(parts).strip()
            if text:
                lines = text.split('\n')
                quoted = '\n'.join([f"> {line}" for line in lines if line.strip()])
                return f"{quoted}\n\n"
            return ''
        
        # 处理水平线
        if elem.name == 'hr':
            return '---\n\n'
        
        # 处理换行
        if elem.name == 'br':
            return '\n'
        
        # 处理 div/span/section（递归处理子元素）
        if elem.name in ['div', 'span', 'section']:
            parts = []
            for child in elem.children:
                part = self.element_to_markdown(child, level + 1)
                if part:
                    parts.append(part)
            return ''.join(parts)
        
        # 默认递归处理子元素
        parts = []
        for child in elem.children:
            part = self.element_to_markdown(child, level + 1)
            if part:
                parts.append(part)
        return ''.join(parts)
    
    def extract_images(self, soup, html_path, output_dir):
        """提取图片"""
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
    
    def convert(self, html_path, output_dir=None):
        """转换单个HTML文件"""
        if not os.path.exists(html_path):
            safe_print(f"File not found: {html_path}")
            return False
        
        if output_dir is None:
            output_dir = os.path.dirname(html_path) or '.'
        
        # 固定输出目录为"中国日报网"
        domain_dir = os.path.join(output_dir, '中国日报网')
        os.makedirs(domain_dir, exist_ok=True)
        
        # 读取HTML
        html_content = self.read_html(html_path)
        
        # 提取元数据
        metadata, soup = self.extract_metadata(html_content, html_path)
        
        # 找到主要内容区域
        content_elem = None
        selectors = [
            '.article',
            '#Content', 
            '.article-content',
            '.zhun-art',
        ]
        
        for selector in selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                break
        
        if not content_elem:
            safe_print(f"Content not found: {html_path}")
            return False
        
        # 先移除不需要的元素
        for selector in ['script', 'style', 'nav', '.fenx', '.dabiaoti',
                         '.related-news', '.comment-box', '.ad',
                         '.share-box', '.editor', '.detail-option-box']:
            for elem in content_elem.select(selector):
                elem.decompose()
        
        # 提取图片（在转换内容之前）
        self.extract_images(soup, html_path, domain_dir)
        
        # 转换内容
        md_content = self.element_to_markdown(content_elem)
        
        # 清理多余空行
        md_content = re.sub(r'\n{3,}', '\n\n', md_content.strip())
        
        # 清理 data URI 图片
        md_content = re.sub(r'!\[([^\]]*)\]\(data:[^)]+\)\n*', '', md_content)
        
        # 构建 YAML Front Matter
        yaml_lines = ["---"]
        yaml_lines.append(f"title: {metadata['title']}")
        yaml_lines.append(f"author: {metadata['author']}")
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
    converter = ChinaDailyConverter()
    if len(sys.argv) > 1:
        if sys.argv[1].endswith('.html'):
            converter.convert(sys.argv[1])
        else:
            # 批量转换
            import glob
            files = glob.glob(os.path.join(sys.argv[1], "*中国日报网*.html"))
            print(f"Found {len(files)} files")
            for f in files:
                converter.convert(f)
    else:
        # 默认：转换当前目录
        import glob
        files = glob.glob("*中国日报网*.html")
        print(f"Found {len(files)} files")
        for f in files:
            converter.convert(f)
