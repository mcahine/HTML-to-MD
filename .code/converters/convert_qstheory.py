#!/usr/bin/env python3
"""求是网 (qstheory.cn) HTML 转 Markdown 转换器"""
import sys
import os
import re
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from html_converter_base import safe_print


class QstheoryConverter:
    """求是网 HTML 转 Markdown 转换器"""
    
    def __init__(self):
        self.domain = 'qstheory.cn'
        self.name = '求是网'
    
    def extract_metadata(self, soup, html_path):
        """提取文章元数据"""
        metadata = {
            'title': '',
            'author': '',
            'date': '',
            'source': '求是网',
            'url': '',
            'converted_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # 提取标题 - h1 是主标题，h2 是副标题
        h1_elem = soup.find('h1')
        h2_elem = soup.find('h2')
        if h1_elem and h2_elem:
            metadata['title'] = f"{h1_elem.get_text(strip=True)} | {h2_elem.get_text(strip=True)}"
        elif h1_elem:
            metadata['title'] = h1_elem.get_text(strip=True)
        elif h2_elem:
            metadata['title'] = h2_elem.get_text(strip=True)
        
        # 提取日期 - 优先从 meta 标签
        meta_date = soup.find('meta', attrs={'name': 'publishdate'})
        if meta_date:
            date_content = meta_date.get('content', '').strip()
            # 处理格式: 2026-01-16 或 2026-01-16 09:00:00
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', date_content)
            if date_match:
                metadata['date'] = date_match.group(1)
        
        # 从文件名提取日期作为备选
        if not metadata['date']:
            filename = os.path.basename(html_path)
            date_match = re.search(r'(\d{4})(\d{2})(\d{2})', filename)
            if date_match:
                metadata['date'] = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
        
        # 提取作者
        meta_author = soup.find('meta', attrs={'name': 'author'})
        if meta_author:
            metadata['author'] = meta_author.get('content', '').strip()
        
        # 如果meta没有作者，尝试从正文提取（通常在开头有"作者：xxx"）
        if not metadata['author']:
            content_elem = self.extract_content(soup)
            if content_elem:
                first_p = content_elem.find('p')
                if first_p:
                    text = first_p.get_text(strip=True)
                    author_match = re.search(r'作者[：:](\S+)', text)
                    if author_match:
                        metadata['author'] = author_match.group(1)
        
        # 提取URL
        og_url = soup.find('meta', property='og:url')
        if og_url:
            metadata['url'] = og_url.get('content', '')
        
        return metadata
    
    def extract_content(self, soup):
        """提取文章正文"""
        content = soup.select_one('.content') or soup.select_one('#content') or soup.select_one('.article-content')
        return content
    
    def process_content(self, content_elem, base_path=None):
        """处理内容，清理重复标题和元数据，保留图片"""
        paragraphs = []
        seen_texts = set()
        
        # 获取所有子元素（包括图片和段落）
        for elem in content_elem.find_all(['p', 'img', 'h2', 'h3', 'h4', 'figure']):
            # 处理图片
            if elem.name == 'img':
                img_markdown = self.process_image(elem, base_path)
                if img_markdown:
                    paragraphs.append(img_markdown)
                continue
            
            # 处理 figure 标签（通常包含图片和说明）
            if elem.name == 'figure':
                img = elem.find('img')
                if img:
                    img_markdown = self.process_image(img, base_path)
                    if img_markdown:
                        paragraphs.append(img_markdown)
                # 提取图片说明
                figcaption = elem.find('figcaption')
                if figcaption:
                    caption_text = figcaption.get_text(strip=True)
                    if caption_text:
                        paragraphs.append(f"*{caption_text}*")
                continue
            
            # 跳过包含小图标的 span（通常是日期、来源等元数据图标）
            if elem.name == 'span':
                # 检查是否是图片容器
                img = elem.find('img')
                if img:
                    continue  # 跳过，让小图标不显示
                # 获取文本
                text = elem.get_text(strip=True)
                # 过滤元数据文本
                if re.match(r'^\d{4}-\d{2}-\d{2}', text):
                    continue
                if text.startswith('来源') or text.startswith('作者'):
                    continue
                if text in seen_texts:
                    continue
                if text:
                    seen_texts.add(text)
                    paragraphs.append(text)
                continue
            
            # 处理文本元素
            text = elem.get_text(strip=True)
            
            # 过滤空文本
            if not text:
                continue
            
            # 过滤标题重复（已经在 YAML front matter 中）
            if text.startswith('体系化学理化') or text.startswith('——学习'):
                continue
            
            # 过滤来源和作者行（如"来源：《求是》2026/02"、"作者：xxx"）
            if re.match(r'^来源[：:]《', text) or re.match(r'^作者[：:]', text):
                continue
            
            # 过滤日期行
            if re.match(r'^\d{4}-\d{2}-\d{2}', text):
                continue
            
            # 过滤版权信息
            if any(keyword in text for keyword in ['Copyright', '版权所有', '免责声明']):
                continue
            
            # 清理文本
            text = re.sub(r'\s+', ' ', text)
            
            # 去重
            if text in seen_texts:
                continue
            seen_texts.add(text)
            
            paragraphs.append(text)
        
        return paragraphs
    
    def process_image(self, img_elem, base_path=None):
        """处理图片元素，转换为 Markdown 格式"""
        src = img_elem.get('src', '')
        alt = img_elem.get('alt', '')
        
        if not src:
            return None
        
        # 处理 base64 图片
        if src.startswith('data:image'):
            # 保存 base64 图片为文件
            return self.save_base64_image(src, alt, base_path)
        
        # 处理相对路径
        if src.startswith('//'):
            src = 'https:' + src
        elif src.startswith('/'):
            src = 'https://www.qstheory.cn' + src
        
        # 普通图片链接
        return f"![{alt}]({src})"
    
    def save_base64_image(self, src, alt, base_path=None):
        """保存 base64 图片到文件，过滤小图标"""
        import base64
        import hashlib
        
        # 解析 base64 数据
        match = re.match(r'data:image/(\w+);base64,(.+)', src)
        if not match:
            return None
        
        img_ext = match.group(1)
        img_data = match.group(2)
        
        # 检查数据大小（过滤小于 3KB 的小图标）
        data_size = len(img_data) * 3 // 4  # base64 解码后的近似大小
        if data_size < 3072:  # 小于 3KB 的图片认为是图标，跳过
            return None
        
        # 生成文件名（使用数据哈希）
        img_hash = hashlib.md5(img_data.encode()).hexdigest()[:8]
        img_filename = f"image_{img_hash}.{img_ext}"
        
        # 确定输出目录（使用 assets 文件夹）
        if base_path:
            stem = Path(base_path).stem
            img_dir = os.path.join(os.path.dirname(base_path), 'assets', f'{stem}_assets')
            os.makedirs(img_dir, exist_ok=True)
            img_path = os.path.join(img_dir, img_filename)
            
            # 保存图片
            try:
                with open(img_path, 'wb') as f:
                    f.write(base64.b64decode(img_data))
                # 返回相对路径的 Markdown
                rel_path = os.path.join('assets', img_filename).replace('\\', '/')
                return f"![{alt}]({rel_path})"
            except Exception as e:
                safe_print(f"Save image failed: {e}")
                return None
        else:
            # 如果没有 base_path，保留原始 base64
            return f"![{alt}]({src})"
    
    
    def convert(self, html_path, output_dir=None):
        """转换单个HTML文件"""
        if not os.path.exists(html_path):
            safe_print(f"File not found: {html_path}")
            return False
        
        if output_dir is None:
            output_dir = os.path.dirname(html_path) or '.'
        
        # 使用'求是网'作为输出目录名
        domain_dir = os.path.join(output_dir, '求是网')
        os.makedirs(domain_dir, exist_ok=True)
        
        try:
            from bs4 import BeautifulSoup
            with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
                soup = BeautifulSoup(f.read(), 'lxml')
        except Exception as e:
            safe_print(f"Parse HTML failed: {e}")
            return False
        
        metadata = self.extract_metadata(soup, html_path)
        content_elem = self.extract_content(soup)
        
        if not content_elem:
            safe_print(f"Content not found: {html_path}")
            return False
        
        # 先确定输出路径（图片保存需要）
        base_name = Path(html_path).stem
        md_path = os.path.join(domain_dir, f"{base_name}.md")
        
        # 处理内容（传递 md_path 用于保存图片）
        paragraphs = self.process_content(content_elem, md_path)
        
        # 合并为Markdown
        md_content = '\n\n'.join(paragraphs)
        
        # 清理多余空行
        md_content = re.sub(r'\n{3,}', '\n\n', md_content.strip())
        
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
        
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(yaml_lines) + '\n' + md_content)
        
        safe_print(f"Converted: {md_path}")
        return True
    
    def batch_convert(self, input_dir, output_dir=None):
        """批量转换"""
        if output_dir is None:
            output_dir = input_dir
        
        import glob
        html_files = glob.glob(os.path.join(input_dir, "*求是网*.html"))
        success_count = 0
        
        safe_print(f"\n=== 求是网 ({self.domain}) ===")
        safe_print(f"Found {len(html_files)} HTML files")
        
        for html_file in html_files:
            if self.convert(html_file, output_dir):
                success_count += 1
        
        safe_print(f"\nCompleted: {success_count}/{len(html_files)}")
        return success_count


if __name__ == '__main__':
    converter = QstheoryConverter()
    if len(sys.argv) > 1:
        if sys.argv[1].endswith('.html'):
            converter.convert(sys.argv[1])
        else:
            converter.batch_convert(sys.argv[1])
    else:
        converter.batch_convert(r'C:/Users/D-001/Downloads/HTML')
