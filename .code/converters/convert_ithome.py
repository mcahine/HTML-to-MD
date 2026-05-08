#!/usr/bin/env python3
"""IT之家 (ithome.com) HTML 转 Markdown 转换器"""
import sys
import os
import re
import base64
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from html_converter_base import HTMLConverterBase, safe_print


class ITHomeConverter(HTMLConverterBase):
    def __init__(self):
        super().__init__(
            domain='ithome.com',
            name='IT之家',
            content_selector=None,  # 自定义提取
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
                    match = re.match(r'data:image/([^;]+);base64,(.+)', src)
                    if match:
                        ext = match.group(1)
                        data = match.group(2)
                        if not data or data.strip() == '':
                            continue
                        
                        # 清理扩展名中的特殊字符
                        ext = ext.replace('+xml', '').replace('/', '_').replace('+', '_')
                        
                        img_data = base64.b64decode(data)
                        if len(img_data) < 100:
                            continue
                        
                        img_count += 1
                        img_name = f"image_{img_count:03d}.{ext}"
                        img_path = os.path.join(assets_dir, img_name)
                        
                        with open(img_path, 'wb') as f:
                            f.write(img_data)
                        
                        # 如果是 AVIF 格式，转换为 JPEG 以提高兼容性
                        final_ext = ext
                        final_name = img_name
                        if ext.lower() == 'avif':
                            try:
                                import pillow_avif
                                from PIL import Image
                                
                                jpeg_name = f"image_{img_count:03d}.jpg"
                                jpeg_path = os.path.join(assets_dir, jpeg_name)
                                
                                # 打开 AVIF 并转换为 JPEG
                                pil_img = Image.open(img_path)
                                if pil_img.mode in ('RGBA', 'P'):
                                    pil_img = pil_img.convert('RGB')
                                pil_img.save(jpeg_path, 'JPEG', quality=90)
                                
                                # 删除原 AVIF 文件，使用 JPEG
                                os.remove(img_path)
                                final_ext = 'jpg'
                                final_name = jpeg_name
                                safe_print(f"  Converted AVIF to JPEG: {jpeg_name}")
                            except Exception as e:
                                safe_print(f"  Warning: AVIF conversion failed, keeping original: {e}")
                        
                        rel_path = f"assets/{base_name}_assets/{final_name}"
                        img['src'] = rel_path
                        safe_print(f"  Saved: {rel_path}")
                except Exception as e:
                    safe_print(f"  Error saving image: {e}")
        
        return img_count
    
    def extract_metadata(self, html_content, html_path):
        """提取IT之家文章的元数据"""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, 'lxml')
        
        metadata = {
            'title': '',
            'author': '',
            'date': '',
            'source': 'IT之家',
            'url': '',
            'converted_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # 提取标题 - 从 h1 标签
        h1 = soup.find('h1')
        if h1:
            metadata['title'] = h1.get_text(strip=True)
        
        # 如果h1没有，尝试从title标签提取（去掉" - IT之家"后缀）
        if not metadata['title']:
            title_tag = soup.find('title')
            if title_tag:
                title_text = title_tag.get_text(strip=True)
                metadata['title'] = re.sub(r'\s*-\s*IT之家$', '', title_text)
        
        # 从 #dt .fl .info 提取日期和作者
        dt = soup.select_one('#dt')
        if dt:
            fl = dt.select_one('.fl')
            if fl:
                info = fl.select_one('.info')
                if info:
                    spans = info.find_all('span')
                    # 第一个span是时间
                    if len(spans) > 0:
                        time_text = spans[0].get_text(strip=True)
                        # 转换时间格式 2025/12/23 22:26:52 -> 2025-12-23
                        time_match = re.match(r'(\d{4})/(\d{2})/(\d{2})', time_text)
                        if time_match:
                            metadata['date'] = f"{time_match.group(1)}-{time_match.group(2)}-{time_match.group(3)}"
                    
                    # 找作者（包含"作者："的span）
                    for span in spans:
                        text = span.get_text(strip=True)
                        if text.startswith('作者：'):
                            metadata['author'] = text.replace('作者：', '').strip()
                            break
        
        # 从文件名提取日期作为备选
        if not metadata['date']:
            filename = os.path.basename(html_path)
            date_match = re.search(r'(\d{4})(\d{2})(\d{2})', filename)
            if date_match:
                metadata['date'] = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
        
        # 从 meta 标签提取 URL
        og_url = soup.find('meta', property='og:url')
        if og_url:
            metadata['url'] = og_url.get('content', '')
        
        return metadata, soup
    
    def extract_content(self, soup):
        """提取文章内容区域"""
        # IT之家的正文在 .post_content
        content = soup.select_one('.post_content')
        if content:
            return content
        
        # 备选选择器
        for selector in ['.article-content', '#content', '.content']:
            content = soup.select_one(selector)
            if content and len(content.get_text(strip=True)) > 200:
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
        
        # 跳过广告和相关推荐
        if elem.get('class'):
            classes = ' '.join(elem.get('class', []))
            skip_classes = ['ad', 'related', 'share', 'comment', 'toolbar', 'sidebar']
            for skip in skip_classes:
                if skip in classes.lower():
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
        
        # 处理引用块
        if elem.name == 'blockquote':
            text = elem.get_text(strip=True)
            if text:
                lines = text.split('\n')
                quoted = '\n'.join([f"> {line}" for line in lines if line.strip()])
                return f"\n{quoted}\n\n"
            return ''
        
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
        
        # 处理div
        if elem.name == 'div':
            parts = []
            for child in elem.children:
                part = self.element_to_markdown(child, level + 1, visited)
                if part:
                    parts.append(part)
            return ''.join(parts)
        
        # 处理列表
        if elem.name == 'ul':
            items = []
            for li in elem.find_all('li', recursive=False):
                text = li.get_text(strip=True)
                if text:
                    items.append(f"- {text}")
            if items:
                return '\n' + '\n'.join(items) + '\n\n'
            return ''
        
        if elem.name == 'ol':
            items = []
            for i, li in enumerate(elem.find_all('li', recursive=False), 1):
                text = li.get_text(strip=True)
                if text:
                    items.append(f"{i}. {text}")
            if items:
                return '\n' + '\n'.join(items) + '\n\n'
            return ''
        
        # 处理其他元素
        parts = []
        for child in elem.children:
            part = self.element_to_markdown(child, level + 1, visited)
            if part:
                parts.append(part)
        return ''.join(parts)
    
    def convert(self, html_path, output_dir=None):
        """转换单个HTML文件"""
        if not os.path.exists(html_path):
            safe_print(f"File not found: {html_path}")
            return False
        
        if output_dir is None:
            output_dir = os.path.dirname(html_path) or '.'
        
        # 固定输出目录
        domain_dir = os.path.join(output_dir, 'IT之家')
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
                         '.comment-section', '.bottom-bar', '.top-bar',
                         '.breadcrumb', '.article-tags', '.app-download',
                         'script', 'style']:
            for elem in content_elem.select(selector):
                elem.decompose()
        
        # 提取图片
        self.extract_images(content_elem, html_path, domain_dir)
        
        # 转换内容
        md_content = self.element_to_markdown(content_elem)
        
        # 清理多余空行
        md_content = re.sub(r'\n{3,}', '\n\n', md_content.strip())
        
        # 清理 data URI
        md_content = re.sub(r'!\[[^\]]*\]\(data:[^)]+\)\n*', '', md_content)
        
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
    converter = ITHomeConverter()
    if len(sys.argv) > 1:
        if sys.argv[1].endswith('.html'):
            converter.convert(sys.argv[1])
        else:
            # 批量转换
            import glob
            files = glob.glob(os.path.join(sys.argv[1], "*IT之家*.html"))
            print(f"Found {len(files)} files")
            for f in files:
                converter.convert(f)
    else:
        # 批量转换当前目录
        import glob
        files = glob.glob("*IT之家*.html")
        print(f"Found {len(files)} files")
        for f in files:
            converter.convert(f)
