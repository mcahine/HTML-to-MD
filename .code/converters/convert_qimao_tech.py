#!/usr/bin/env python3
"""七猫技术团队 (tech.qimao.com) HTML 转 Markdown 转换器 - 优化版"""
import sys
import os
from pathlib import Path
import re

# 尝试导入基础模块
try:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from html_converter_base import HTMLConverterBase, safe_print
    HAS_BASE = True
except ImportError:
    HAS_BASE = False
    import html2text
    
    def safe_print(msg):
        try:
            print(msg)
        except:
            pass

from bs4 import BeautifulSoup
from datetime import datetime

class QimaoTechConverter(HTMLConverterBase if HAS_BASE else object):
    """七猫技术团队 HTML 转 Markdown 优化版转换器"""
    
    def __init__(self):
        if HAS_BASE:
            super().__init__(
                domain='tech.qimao.com',
                name='七猫技术团队',
                content_selector='.article-content, .content, article',
                title_selector='h1, .article-title, .title',
                author_selector='.author-name, .author, .article-author',
                date_selector='.publish-time, .article-date, .date, time',
                remove_selectors=[
                    '.sidebar', '.article-meta', '.author-card',
                    '.comments', '.related-posts', '.tags', '.tag-list',
                    '.post-tags', '.article-tags',
                    'script', 'style', '.ads', '.share-bar', '.qr-code',
                    '.post-views', '.entry-tags', '.navigation'
                ]
            )
        else:
            self.html2text = html2text.HTML2Text()
            self.html2text.ignore_links = False
            self.html2text.ignore_images = False
            self.html2text.body_width = 0
    
    def extract_metadata(self, soup, html_path):
        """提取文章元数据"""
        metadata = {
            'title': '',
            'author': '',
            'date': '',
            'source': '七猫技术团队',
            'url': ''
        }
        
        # 从 title 标签提取
        title_tag = soup.find('title')
        if title_tag:
            title_text = title_tag.get_text(strip=True)
            # 移除可能的站点后缀
            metadata['title'] = re.sub(r'\s*[-|]\s*七猫技术团队$', '', title_text)
        
        # 从 h1 提取（备用）
        if not metadata['title']:
            h1 = soup.select_one('h1, .article-title')
            if h1:
                metadata['title'] = h1.get_text(strip=True)
        
        # 从 HTML 注释提取 URL (SingleFile 格式)
        html_content = str(soup)
        match = re.search(r'url:\s*(https?://\S+)', html_content)
        if match:
            metadata['url'] = match.group(1).strip()
        
        # 从 canonical link 提取
        if not metadata['url']:
            canonical = soup.find('link', {'rel': 'canonical'})
            if canonical and canonical.get('href'):
                metadata['url'] = canonical['href']
        
        # 提取日期
        date_elem = soup.select_one('.publish-time, .article-date, .date, time')
        if date_elem:
            date_text = date_elem.get_text(strip=True) or date_elem.get('datetime', '')
            # 尝试解析日期
            date_match = re.search(r'(\d{4})[/-](\d{2})[/-](\d{2})', date_text)
            if date_match:
                metadata['date'] = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
        
        # 如果 HTML 中没有找到日期，从 URL 提取
        if not metadata['date'] and metadata['url']:
            date_match = re.search(r'/(\d{4})(\d{2})(\d{2})/', metadata['url'])
            if date_match:
                metadata['date'] = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
        
        # 备用：从文件名提取日期
        if not metadata['date']:
            filename_match = re.search(r'(\d{4})(\d{2})(\d{2})', os.path.basename(html_path))
            if filename_match:
                metadata['date'] = f"{filename_match.group(1)}-{filename_match.group(2)}-{filename_match.group(3)}"
        
        # 提取作者
        author_elem = soup.select_one('.author-name, .author, .article-author')
        if author_elem:
            metadata['author'] = author_elem.get_text(strip=True)
        
        return metadata
    
    def fix_code_blocks(self, soup):
        """修复代码块"""
        from copy import deepcopy
        from bs4 import BeautifulSoup
        
        soup = deepcopy(soup)
        
        # 查找 pre > code 结构
        for pre in soup.find_all('pre'):
            code = pre.find('code')
            if code:
                # 获取语言类
                lang = 'text'
                for cls in code.get('class', []):
                    if cls.startswith('language-') or cls in ['python', 'java', 'javascript', 'bash', 'shell', 'go', 'cpp']:
                        lang = cls.replace('language-', '')
                        break
                
                # 创建新的 pre > code 结构
                code_text = code.get_text()
                new_html = f'<pre><code class="language-{lang}">{code_text}</code></pre>'
                new_soup = BeautifulSoup(new_html, 'html.parser')
                new_pre = new_soup.find('pre')
                pre.replace_with(new_pre)
        
        return soup
    
    def clean_content(self, soup):
        """清理并提取正文内容"""
        # 找到内容区域
        content = soup.select_one('.article-content')
        if not content:
            content = soup.select_one('.content')
        if not content:
            content = soup.find('article')
        
        if not content:
            return None
        
        # 修复代码块
        content = self.fix_code_blocks(content)
        
        # 创建内容的深拷贝
        from copy import deepcopy
        content_copy = deepcopy(content)
        
        # 移除不需要的元素
        remove_selectors = [
            '.sidebar', '.article-meta', '.author-card',
            '.comments', '.related-posts', '.tags', '.tag-list',
            '.post-tags', '.article-tags',
            'script', 'style', '.ads', '.share-bar', '.qr-code',
            '.post-views', '.entry-tags', '.navigation', '.author-info'
        ]
        
        for selector in remove_selectors:
            for elem in content_copy.select(selector):
                elem.decompose()
        
        return content_copy
    
    def process_images(self, content, output_dir, stem=''):
        """处理图片"""
        assets_dir = os.path.join(output_dir, 'assets', f'{stem}_assets') if stem else os.path.join(output_dir, 'assets')
        os.makedirs(assets_dir, exist_ok=True)

        img_count = 0
        for img in content.find_all('img'):
            src = img.get('src', '')

            if src.startswith('data:image'):
                try:
                    match = re.match(r'data:image/(\w+);base64,(.+)', src)
                    if match:
                        img_type, img_data = match.groups()
                        img_type = img_type.lower()

                        if img_type == 'svg+xml':
                            img_type = 'svg'
                        elif img_type not in ['png', 'jpg', 'jpeg', 'gif', 'webp']:
                            img_type = 'png'

                        img_count += 1
                        img_name = f'image_{img_count:03d}.{img_type}'
                        img_path = os.path.join(assets_dir, img_name)

                        with open(img_path, 'wb') as f:
                            f.write(__import__('base64').b64decode(img_data))

                        img['src'] = f'assets/{stem}_assets/{img_name}' if stem else f'assets/{img_name}'
                    else:
                        img.decompose()
                except:
                    img.decompose()

        return img_count
    
    def convert(self, html_path, output_dir=None):
        """转换单个 HTML 文件"""
        if not os.path.exists(html_path):
            print(f"文件不存在: {html_path}")
            return False
        
        if output_dir is None:
            output_dir = os.path.dirname(html_path) or '.'
        
        # 创建输出目录
        domain_dir = os.path.join(output_dir, 'tech_qimao_com')
        os.makedirs(domain_dir, exist_ok=True)
        
        try:
            with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
                soup = BeautifulSoup(f.read(), 'html.parser')
        except Exception as e:
            print(f"解析 HTML 失败: {e}")
            return False
        
        # 提取元数据
        metadata = self.extract_metadata(soup, html_path)
        
        # 清理并提取内容
        content = self.clean_content(soup)
        if not content:
            print(f"未找到正文内容: {html_path}")
            return False
        
        # 处理图片
        img_count = self._extract_base64_images(content, str(html_path), domain_dir)
        if img_count > 0:
            print(f"  提取了 {img_count} 张图片")
        
        # Protect code blocks before conversion
        code_blocks = self._protect_code_blocks(content)

        # 转换为 Markdown
        if HAS_BASE:
            md_content = self.html_to_markdown(content)
        else:
            md_content = self.html2text.handle(str(content))

        # Restore code blocks
        md_content = self._restore_code_blocks(md_content, code_blocks)

        # Remove data: URIs that weren't extracted
        md_content = re.sub(r'!\[[^\]]*\]\(data:[^)]*\)\n*', '', md_content)

        # 后处理 Markdown
        md_content = self.post_process_markdown(md_content, metadata)
        
        # 构建 YAML 前置元数据
        yaml_front = f"---\n"
        yaml_front += f"title: \"{metadata['title']}\"\n"
        yaml_front += f"author: {metadata['author'] or '未知'}\n"
        yaml_front += f"date: {metadata['date'] or ''}\n"
        yaml_front += f"source: {metadata['source']}\n"
        yaml_front += f"url: {metadata['url']}\n"
        yaml_front += f"converted_at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        yaml_front += f"---\n\n"
        
        # 保存文件
        base_name = os.path.splitext(os.path.basename(html_path))[0]
        md_path = os.path.join(domain_dir, f"{base_name}.md")
        
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(yaml_front + md_content)
        
        print(f"已转换: {md_path}")
        return True
    
    def post_process_markdown(self, md_content, metadata):
        """后处理 Markdown 内容 - 优化可读性"""
        # 确保标题前后有空行
        md_content = re.sub(r'([^\n])(\n#{1,6}\s)', r'\1\n\2', md_content)
        md_content = re.sub(r'(\n#{1,6}[^\n]+)(\n[^\n#])', r'\1\n\2', md_content)
        
        # 确保图片前后有空行（处理图片紧跟文字的情况）
        md_content = re.sub(r'([^\n])(\n!\[)', r'\1\n\2', md_content)
        md_content = re.sub(r'(\n!\[[^\]]*\]\([^\)]+\))(\n[^\n#])', r'\1\n\2', md_content)
        # 处理图片紧跟在行内文本后的情况（图片在同一行末尾，如：文字![](图片)）
        md_content = re.sub(r'([^\n!])\s*(\n!\[[^\]]*\]\([^\)]+\))', r'\1\n\n\2', md_content)
        md_content = re.sub(r'(\n!\[[^\]]*\]\([^\)]+\))\s*([^\n])', r'\1\n\n\2', md_content)
        # 处理图片紧跟在文本后（同一行，没有换行）
        md_content = re.sub(r'([^\n])\s*(!\[[^\]]*\]\([^\)]+\))', r'\1\n\n\2', md_content)
        
        # 确保代码块前后有空行
        md_content = re.sub(r'([^\n])(\n```)', r'\1\n\2', md_content)
        md_content = re.sub(r'(```\n)([^\n#])', r'\1\n\2', md_content)
        
        # 修复列表格式（确保列表项前有空行，除非是连续列表）
        md_content = re.sub(r'([^\n\*\-\d])(\n([\*\-\+]\s|\d+\.\s))', r'\1\n\2', md_content)
        
        # 移除标题中可能的 HTML 标签
        md_content = re.sub(r'<[^>]+>', '', md_content)
        
        # 修复图片路径（将反斜杠替换为正斜杠）
        def fix_image_path(match):
            alt = match.group(1)
            path = match.group(2)
            path = path.replace('\\', '/')
            return f'![{alt}]({path})'
        md_content = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', fix_image_path, md_content)
        
        # 移除重复的标题
        title = metadata.get('title', '')
        if title:
            md_content = re.sub(f'^#+\s*{re.escape(title)}\s*\n', '', md_content, count=1, flags=re.IGNORECASE)
        
        # 清理末尾的标签行
        md_content = re.sub(r'\n-\s+[\w\s]+$', '', md_content.strip())
        
        # 清理末尾的文章标题链接
        md_content = re.sub(r'\n\*\*文章标题：\*\*.*?\n\n', '\n\n', md_content, flags=re.DOTALL)
        
        # 清理固定链接部分
        md_content = re.sub(r'\n\*\*固定链接：\*\*\n+', '\n', md_content)
        
        # 清理末尾的链接图片
        md_content = re.sub(r'\n+\[\s*!\[.*?\]\(.*?\)\s*\]\(.*?\)\s*$', '', md_content)
        
        # 移除标签、主题、专题等元数据行
        md_content = re.sub(r'\n\s*(主题|标签|分类|专题)\s*[：:]\s*.*\n', '\n', md_content, flags=re.IGNORECASE)
        
        # 移除 "展示评论" 等交互元素
        md_content = re.sub(r'\n\s*展示评论\s*\n', '\n', md_content, flags=re.IGNORECASE)
        
        # 移除推荐文章卡片
        md_content = re.sub(r'\n\s*__\s*\n*\[.*?\d{4}/\d{1,2}/\d{1,2}.*\n', '\n', md_content, flags=re.DOTALL)
        
        # 移除多余空行（最多保留两个）
        md_content = re.sub(r'\n{3,}', '\n\n', md_content)
        
        # 清理行内代码后的多余空行
        md_content = re.sub(r'`([^`]+)`\n\n(?=[^`])', r'`\1`\n', md_content)
        
        # Cut at footer section (tags + related articles)
        for pattern in [
            r'\n主题\s*\[',       # 主题 [AI](url)
            r'\n标签\s*\[',       # 标签 [xx](url)
            r'\n\s*展示评论',     # 展示评论
            r'\n\[ __[^\]]+',     # [ __article title
        ]:
            m = re.search(pattern, md_content)
            if m:
                # Find the start of this block (go back to previous blank line)
                nl = md_content.rfind('\n', 0, m.start())
                prev_nl = md_content.rfind('\n', 0, nl)
                cutoff = prev_nl if prev_nl > 0 else nl
                md_content = md_content[:cutoff]
                break

        return md_content.strip()
    
    def batch_convert(self, directory):
        """批量转换目录中的所有 HTML 文件"""
        if not os.path.isdir(directory):
            print(f"目录不存在: {directory}")
            return
        
        html_files = [f for f in os.listdir(directory) if f.endswith('.html')]
        if not html_files:
            print(f"目录中没有 HTML 文件: {directory}")
            return
        
        success_count = 0
        for html_file in html_files:
            html_path = os.path.join(directory, html_file)
            if self.convert(html_path):
                success_count += 1
        
        print(f"\n转换完成: {success_count}/{len(html_files)} 个文件成功")

if __name__ == '__main__':
    converter = QimaoTechConverter()
    
    if len(sys.argv) > 1:
        if sys.argv[1].endswith('.html'):
            converter.convert(sys.argv[1])
        else:
            converter.batch_convert(sys.argv[1])
    else:
        # 转换当前目录下包含七猫的文件
        import glob
        files_to_convert = []
        
        # 搜索当前目录
        for pattern in ['*七猫*.html', '*qimao*.html']:
            files_to_convert.extend(glob.glob(pattern))
        
        # 去重
        files_to_convert = list(set(files_to_convert))
        
        if not files_to_convert:
            print("未发现七猫技术团队的 HTML 文件")
            sys.exit(0)
        
        print(f"发现 {len(files_to_convert)} 个待转换文件")
        
        success_count = 0
        for html_file in files_to_convert:
            if os.path.exists(html_file):
                if converter.convert(html_file):
                    success_count += 1
            else:
                print(f"文件不存在: {html_file}")
        
        print(f"\n转换完成: {success_count}/{len(files_to_convert)} 个文件成功")
