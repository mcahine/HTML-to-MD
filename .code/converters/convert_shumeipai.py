#!/usr/bin/env python3
"""树莓派实验室 (shumeipai.nxez.com) HTML 转 Markdown 转换器 - 优化版"""
import os
from pathlib import Path
import sys
import re
import base64
import json
from datetime import datetime
from bs4 import BeautifulSoup

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

class ShumeipaiConverter(HTMLConverterBase if HAS_BASE else object):
    """树莓派实验室 HTML 转 Markdown 优化版转换器"""
    
    def __init__(self):
        if HAS_BASE:
            super().__init__(
                domain='shumeipai.nxez.com',
                name='树莓派实验室',
                content_selector='.entry-content, .content, article',
                title_selector='h1, .entry-title',
                author_selector='.author, .entry-author, .byline',
                date_selector='.entry-date, .date, time',
                remove_selectors=[
                    '.entry-meta', '.entry-footer', '.comments-area',
                    '.sidebar', '.widget', '.navigation',
                    'script', 'style', 'nav', '.mh-header', '.mh-footer'
                ]
            )
        else:
            self.html2text = html2text.HTML2Text()
            self.html2text.ignore_links = False
            self.html2text.ignore_images = False
            self.html2text.body_width = 0
            self.html2text.wrap_links = False
            self.html2text.wrap_list_items = False
    
    def extract_metadata(self, soup, html_path):
        """提取文章元数据"""
        metadata = {
            'title': '',
            'author': '',
            'date': '',
            'source': '树莓派实验室',
            'url': ''
        }
        
        # 从 title 标签提取
        title_tag = soup.find('title')
        if title_tag:
            title_text = title_tag.get_text(strip=True)
            # 移除 " | 树莓派实验室" 后缀
            metadata['title'] = re.sub(r'\s*\|\s*树莓派实验室$', '', title_text)
        
        # 从 h1/entry-title 提取（备用）
        if not metadata['title']:
            h1 = soup.select_one('h1.entry-title, .entry-title')
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
        date_elem = soup.select_one('.entry-date, .date, time.entry-date')
        if date_elem:
            date_text = date_elem.get_text(strip=True) or date_elem.get('datetime', '')
            # 尝试解析日期
            date_match = re.search(r'(\d{4})[/-](\d{2})[/-](\d{2})', date_text)
            if date_match:
                metadata['date'] = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
        
        # 如果 HTML 中没有找到日期，从 URL 提取 (格式: /2026/01/18/)
        if not metadata['date'] and metadata['url']:
            date_match = re.search(r'/(\d{4})/(\d{2})/(\d{2})(?:/|$)', metadata['url'])
            if date_match:
                metadata['date'] = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
        
        # 备用：从文件名提取日期
        if not metadata['date']:
            filename_match = re.search(r'(\d{4})(\d{2})(\d{2})', os.path.basename(html_path))
            if filename_match:
                metadata['date'] = f"{filename_match.group(1)}-{filename_match.group(2)}-{filename_match.group(3)}"
        
        # 提取作者
        author_elem = soup.select_one('.author, .entry-author, .byline .author')
        if author_elem:
            metadata['author'] = author_elem.get_text(strip=True)
        
        return metadata
    
    def fix_syntaxhighlighter(self, soup):
        """修复 SyntaxHighlighter 代码块 - 替换为 pre/code 结构"""
        from copy import deepcopy
        from bs4 import BeautifulSoup
        
        # 深拷贝避免修改原始 soup
        soup = deepcopy(soup)
        
        # 找到所有 syntaxhighlighter 容器
        for highlighter in soup.find_all(class_=re.compile(r'syntaxhighlighter')):
            # 获取语言类型
            lang = 'bash'  # 默认语言
            for class_name in highlighter.get('class', []):
                if class_name and class_name not in ['syntaxhighlighter', 'nogutter']:
                    lang = class_name
                    break
            
            # 收集所有代码内容 - 从 td.code 的 line div 中获取
            code_lines = []
            code_td = highlighter.find('td', class_='code')
            if code_td:
                for line_div in code_td.find_all(class_='line'):
                    line_text = line_div.get_text()
                    if line_text:
                        code_lines.append(line_text)
            
            # 合并成一个代码块
            if code_lines:
                full_code = '\n'.join(code_lines)
                # 创建标准的 pre > code 结构
                # 添加语言类让 html2text 能识别
                new_html = f'<pre><code class="language-{lang}">{full_code}</code></pre>'
                new_soup = BeautifulSoup(new_html, 'html.parser')
                new_pre = new_soup.find('pre')
                highlighter.replace_with(new_pre)
        
        return soup
    
    def clean_content(self, soup):
        """清理并提取正文内容"""
        # 找到内容区域
        content = soup.select_one('.entry-content, article, .content')
        if not content:
            return None
        
        # 修复代码块
        content = self.fix_syntaxhighlighter(content)
        
        # 创建内容的深拷贝
        from copy import deepcopy
        content_copy = deepcopy(content)
        
        # 移除不需要的元素
        remove_selectors = [
            '.entry-meta', '.entry-footer', '.comments-area',
            '.sidebar', '.widget', '.navigation', '.mh-sidebar',
            'script', 'style', 'nav', '.mh-header', '.mh-footer',
            '.post-views', '.entry-tags', '.share-buttons',
            '#respond', '#comments', '.commentlist',
            '.related-posts', '.author-box'
        ]
        
        for selector in remove_selectors:
            for elem in content_copy.select(selector):
                elem.decompose()
        
        # 清理 HTML 属性
        for elem in content_copy.find_all():
            # 保留部分必要属性
            keep_attrs = ['src', 'alt', 'href', 'class']
            attrs_to_remove = [attr for attr in elem.attrs if attr not in keep_attrs]
            for attr in attrs_to_remove:
                del elem[attr]
        
        return content_copy
    
    def process_images(self, content, output_dir, stem=''):
        """处理图片"""
        stem = Path(html_path).stem
        assets_dir = os.path.join(output_dir, 'assets', f'{stem}_assets')
        os.makedirs(assets_dir, exist_ok=True)

        img_count = 0
        for img in content.find_all('img'):
            src = img.get('src', '')
            
            # 处理 Base64 图片
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
                            f.write(base64.b64decode(img_data))
                        
                        img['src'] = f'assets/{stem}_assets/{img_name}'
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
        domain_dir = os.path.join(output_dir, 'shumeipai_nxez_com')
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
        
        # 提取代码块（在 html2text 处理前）
        code_blocks = []
        for pre in content.find_all('pre'):
            code = pre.find('code')
            if code:
                lang = 'bash'
                for cls in code.get('class', []):
                    if cls.startswith('language-'):
                        lang = cls.replace('language-', '')
                        break
                code_text = code.get_text()
                code_blocks.append({'lang': lang, 'code': code_text, 'elem': pre})
        
        # 用占位符替换代码块
        for i, block in enumerate(code_blocks):
            placeholder = soup.new_tag('p')
            placeholder.string = f"[[CODE_BLOCK_{i}]]"
            block['elem'].replace_with(placeholder)
        
        # 处理图片
        img_count = self._extract_base64_images(content, str(html_path), domain_dir)
        if img_count > 0:
            print(f"  提取了 {img_count} 张图片")
        
        # 转换为 Markdown
        if HAS_BASE:
            md_content = self.html_to_markdown(content)
        else:
            md_content = self.html2text.handle(str(content))
        
        # 恢复代码块
        for i, block in enumerate(code_blocks):
            placeholder = f"[[CODE_BLOCK_{i}]]"
            fence_block = f"```{block['lang']}\n{block['code']}\n```"
            md_content = md_content.replace(placeholder, fence_block)
        
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
        """后处理 Markdown 内容"""
        # 移除重复的空行
        md_content = re.sub(r'\n{3,}', '\n\n', md_content)
        
        # 清理代码块中的非代码内容
        # 那些 lang=none 且包含 Markdown 格式的代码块需要被解包
        
        unwrap_count = [0]
        
        def should_unwrap_codeblock(match):
            lang = match.group(1)
            content = match.group(2)
            # 如果没有语言标记，且内容包含 Markdown 标题或粗体，则解包
            if not lang:
                if re.search(r'^(#{1,6}\s|[\*\-\+]\s)', content, re.MULTILINE):
                    unwrap_count[0] += 1
                    return content.strip()
                if content.count('**') >= 2:
                    unwrap_count[0] += 1
                    return content.strip()
            return match.group(0)
        
        # 匹配代码块并处理（支持 CRLF 和 LF）
        # 使用否定前瞻确保代码块内容不包含 ```
        code_block_pattern = re.compile(r'```(\w*)\r?\n((?:(?!```).)*)\r?\n```', re.DOTALL)
        
        def replace_codeblock(match):
            lang = match.group(1)
            code = match.group(2)
            if not lang:
                has_header = bool(re.search(r'^(#{1,6}\s|[\*\-\+]\s)', code, re.MULTILINE))
                has_bold = code.count('**') >= 2
                if has_header or has_bold:
                    unwrap_count[0] += 1
                    return code.strip()
            return match.group(0)
        
        md_content = code_block_pattern.sub(replace_codeblock, md_content)
        
        # 清理行内代码后的多余空行
        md_content = re.sub(r'`([^`]+)`\n\n(?=[^`])', r'`\1`\n', md_content)
        
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
            md_content = re.sub(f'^#+\\s*{re.escape(title)}\\s*\\n', '', md_content, count=1, flags=re.IGNORECASE)
        
        # 清理末尾的标签行
        md_content = re.sub(r'\n-\s+[\w\s]+$', '', md_content.strip())
        
        # 清理末尾的文章标题链接（**文章标题：**...）
        md_content = re.sub(r'\n\*\*文章标题：\*\*.*?\n\n', '\n\n', md_content, flags=re.DOTALL)
        
        # 清理固定链接部分
        md_content = re.sub(r'\n\*\*固定链接：\*\*\n+', '\n', md_content)
        
        # 清理末尾的链接图片（通常是广告或相关推荐）
        md_content = re.sub(r'\n+\[\s*!\[.*?\]\(.*?\)\s*\]\(.*?\)\s*$', '', md_content)
        
        # 移除标签、主题、专题等元数据行
        md_content = re.sub(r'\n\s*(主题|标签|分类|专题)\s*[：:]\s*.*\n', '\n', md_content, flags=re.IGNORECASE)
        
        # 移除 "展示评论" 等交互元素
        md_content = re.sub(r'\n\s*展示评论\s*\n', '\n', md_content, flags=re.IGNORECASE)
        
        # 移除推荐文章卡片
        md_content = re.sub(r'\n\s*__\s*\n*\[.*?\d{4}/\d{1,2}/\d{1,2}.*\n', '\n', md_content, flags=re.DOTALL)
        
        # 再次移除多余空行
        md_content = re.sub(r'\n{3,}', '\n\n', md_content)
        
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
    converter = ShumeipaiConverter()
    
    if len(sys.argv) > 1:
        if sys.argv[1].endswith('.html'):
            converter.convert(sys.argv[1])
        else:
            converter.batch_convert(sys.argv[1])
    else:
        # 自动发现所有树莓派实验室的文件
        import glob
        files_to_convert = []
        
        # 搜索当前目录
        files_to_convert.extend(glob.glob("*shumeipai*.html"))
        files_to_convert.extend(glob.glob("*树莓派*.html"))
        files_to_convert.extend(glob.glob("*nxez*.html"))
        files_to_convert.extend(glob.glob("*raspberry*.html"))
        
        # 搜索 shumeipai_nxez_com 子目录
        files_to_convert.extend(glob.glob("shumeipai_nxez_com/*.html"))
        
        # 去重
        files_to_convert = list(set(files_to_convert))
        
        if not files_to_convert:
            print("未发现树莓派实验室的 HTML 文件")
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
