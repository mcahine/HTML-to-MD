#!/usr/bin/env python3
"""宝玉的博客 (baoyu.io) HTML 转 Markdown 转换器 - 完全重写版"""
import sys
import os
import re
import base64
from pathlib import Path
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from html_converter_base import HTMLConverterBase, safe_print


class BaoyuConverter(HTMLConverterBase):
    def __init__(self):
        super().__init__(
            domain='baoyu.io',
            name='宝玉的分享',
            content_selector='article',
            title_selector='h1',
            author_selector=None,
            date_selector=None,
            remove_selectors=['script', 'style', 'nav']
        )
    
    def read_html(self, html_path):
        """读取HTML文件，自动检测编码"""
        # 尝试多种编码
        encodings = ['utf-8', 'utf-8-sig', 'gbk', 'gb2312', 'latin1']
        
        for encoding in encodings:
            try:
                with open(html_path, 'r', encoding=encoding) as f:
                    content = f.read()
                # 验证是否包含乱码特征
                if '����' not in content[:5000]:
                    return content
            except:
                continue
        
        # 回退：使用utf-8并忽略错误
        with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    
    def extract_url_from_html(self, html_content):
        """从 HTML 注释中提取原始 URL"""
        # SingleFile 格式: url: https://baoyu.io/...
        match = re.search(r'url:\s*(https?://[^\s\n]+)', html_content)
        if match:
            return match.group(1).strip()
        return ''
    
    def extract_metadata(self, html_content, html_path):
        """提取元数据"""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, 'lxml')
        
        metadata = {
            'title': '',
            'author': '宝玉',
            'date': '',
            'source': '宝玉的分享',
            'url': self.extract_url_from_html(html_content),
            'converted_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'original_title': '',
            'original_author': '',
            'original_url': '',
            'original_date': ''
        }
        
        # 提取标题
        h1 = soup.find('h1')
        if h1:
            metadata['title'] = h1.get_text(strip=True)
        
        # 从文件名提取日期
        filename = os.path.basename(html_path)
        date_match = re.search(r'(\d{4})(\d{2})(\d{2})', filename)
        if date_match:
            metadata['date'] = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
        
        # 提取原文信息（从blockquote）
        blockquote = soup.find('blockquote')
        if blockquote:
            bq_text = blockquote.get_text()
            
            # 原文标题
            title_match = re.search(r'原文标题[：:]\s*(.+?)(?:\n|作者|$)', bq_text)
            if title_match:
                metadata['original_title'] = title_match.group(1).strip()
            
            # 作者
            author_match = re.search(r'作者[：:]\s*(.+?)(?:\n|原文链接|$)', bq_text)
            if author_match:
                metadata['original_author'] = author_match.group(1).strip()
            
            # 原文链接
            link_match = re.search(r'原文链接[：:]\s*(https?://\S+)', bq_text)
            if link_match:
                metadata['original_url'] = link_match.group(1).strip()
            
            # 发布时间
            date_match = re.search(r'发布时间[：:]\s*(\d{4}-\d{2}-\d{2})', bq_text)
            if date_match:
                metadata['original_date'] = date_match.group(1)
        
        return metadata, soup
    
    def is_valid_image_src(self, src):
        """检查图片 src 是否有效"""
        if not src:
            return False
        # 过滤空 data URI
        if src in ['data:,', 'data:image/png,', 'data:image/jpeg,']:
            return False
        # 过滤纯占位符
        if src.strip() == '' or src.strip() == '#':
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
        if elem.name in ['script', 'style', 'nav', 'iframe', 'ins']:
            return ''
        
        # 跳过导航链接
        if elem.name == 'a':
            text = elem.get_text(strip=True).lower()
            if text in ['see all posts', 'view all', 'all posts']:
                return ''
        
        # 处理标题
        if elem.name == 'h1':
            text = elem.get_text(strip=True)
            return f"# {text}\n\n" if text else ''
        if elem.name == 'h2':
            text = elem.get_text(strip=True)
            return f"## {text}\n\n" if text else ''
        if elem.name == 'h3':
            text = elem.get_text(strip=True)
            return f"### {text}\n\n" if text else ''
        if elem.name == 'h4':
            text = elem.get_text(strip=True)
            return f"#### {text}\n\n" if text else ''
        
        # 处理图片 - 过滤无效 src
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
            # 没有 code 标签的 pre
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
            # 递归处理子元素
            parts = []
            for child in elem.children:
                part = self.element_to_markdown(child, level + 1)
                if part:
                    parts.append(part)
            text = ''.join(parts).strip()
            # 清理多余空白
            text = re.sub(r'\s+', ' ', text)
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
            # 递归处理子元素
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
        
        # 处理div和span（递归处理子元素）
        if elem.name in ['div', 'span', 'section', 'article', 'main', 'header', 'footer']:
            # 跳过包含特定类名的导航元素
            classes = elem.get('class', [])
            if any(c in ['navigation', 'nav', 'footer', 'header'] for c in classes):
                return ''
            
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
        from pathlib import Path
        
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
                        # 检查是否有实际数据
                        if not data or data.strip() == '':
                            continue
                        img_data = base64.b64decode(data)
                        
                        # 检查图片数据是否有效（至少几个字节）
                        if len(img_data) < 100:
                            continue
                        
                        img_count += 1
                        img_name = f"image_{img_count:03d}.{ext}"
                        img_path = os.path.join(assets_dir, img_name)
                        
                        with open(img_path, 'wb') as f:
                            f.write(img_data)
                        
                        # 更新 src
                        rel_path = f"assets/{base_name}_assets/{img_name}"
                        img['src'] = rel_path
                        print(f"  Saved: {rel_path}")
                except Exception as e:
                    print(f"  Error saving image: {e}")
        
        return img_count
    
    def convert(self, html_path, output_dir=None):
        """转换单个HTML文件"""
        if not os.path.exists(html_path):
            print(f"File not found: {html_path}")
            return False
        
        if output_dir is None:
            output_dir = os.path.dirname(html_path) or '.'
        
        # 固定输出目录
        domain_dir = os.path.join(output_dir, '宝玉的分享')
        os.makedirs(domain_dir, exist_ok=True)
        
        # 读取HTML
        html_content = self.read_html(html_path)
        
        # 提取元数据
        metadata, soup = self.extract_metadata(html_content, html_path)
        
        # 提取图片
        self.extract_images(soup, html_path, domain_dir)
        
        # 找到主要内容区域
        article = soup.find('article')
        if not article:
            print(f"Article not found: {html_path}")
            return False
        
        # 移除不需要的元素
        for elem in article.find_all(['script', 'style', 'nav', 'iframe', 'ins']):
            elem.decompose()
        
        # 移除导航链接
        for elem in article.find_all('a'):
            text = elem.get_text(strip=True).lower()
            if text in ['see all posts', 'view all', 'all posts']:
                elem.decompose()
        
        # 移除 blockquote（原文信息已提取）
        blockquote = article.find('blockquote')
        if blockquote:
            blockquote.decompose()
        
        # 移除 header div（包含标题、日期的部分，因为我们已经在 YAML 中有了）
        # 保留内容div
        content_div = None
        for div in article.find_all('div', recursive=False):
            # 找到包含最多段落的 div
            if len(div.find_all('p')) > 3:
                content_div = div
                break
        
        if not content_div:
            content_div = article
        
        # 转换内容
        md_content = self.element_to_markdown(content_div)
        
        # 清理多余空行
        md_content = re.sub(r'\n{3,}', '\n\n', md_content.strip())
        
        # 清理可能的空图片引用（保险起见）
        md_content = re.sub(r'!\[\]\(data:,\)\n*', '', md_content)
        md_content = re.sub(r'!\[([^\]]*)\]\(data:,\)\n*', '', md_content)
        
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
        
        # 添加原文引用块
        if metadata['original_title']:
            yaml_lines.append(f"> **原文标题：**{metadata['original_title']}")
            if metadata['original_author']:
                author_clean = re.sub(r'\s*https?://\S+\s*', '', metadata['original_author']).strip()
                author_clean = re.sub(r'[（(]\s*[）)]', '', author_clean).strip()
                yaml_lines.append(f"> **作者：**{author_clean}")
            if metadata['original_url']:
                yaml_lines.append(f"> **原文链接：**[{metadata['original_url']}]({metadata['original_url']})")
            if metadata['original_date']:
                yaml_lines.append(f"> **发布时间：**{metadata['original_date']}")
            yaml_lines.append("")
        
        # 写入文件
        base_name = Path(html_path).stem
        md_path = os.path.join(domain_dir, f"{base_name}.md")
        
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(yaml_lines) + '\n' + md_content)
        
        print(f"Converted: {md_path}")
        return True


if __name__ == '__main__':
    converter = BaoyuConverter()
    if len(sys.argv) > 1:
        if sys.argv[1].endswith('.html'):
            converter.convert(sys.argv[1])
        else:
            # 批量转换
            import glob
            files = glob.glob(os.path.join(sys.argv[1], "*宝玉*.html"))
            print(f"Found {len(files)} files")
            for f in files:
                converter.convert(f)
    else:
        # 默认：转换当前目录
        import glob
        files = glob.glob("*宝玉*.html")
        print(f"Found {len(files)} files")
        for f in files:
            converter.convert(f)
