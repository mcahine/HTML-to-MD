#!/usr/bin/env python3
"""
知乎专栏 (zhuanlan.zhihu.com) HTML 转 Markdown 转换器

功能：
- 提取知乎文章正文内容
- 处理 Base64 图片并保存到 assets 目录
- 清理知乎特有的元素（侧边栏、推荐阅读等）
- 生成带有 YAML 前置元数据的 Markdown 文件
"""
import sys
import os
from pathlib import Path
import re
import base64

# 尝试导入基础模块（如果存在）
try:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from html_converter_base import HTMLConverterBase, safe_print
    HAS_BASE = True
except ImportError:
    HAS_BASE = False
    import html2text
    
    def safe_print(msg):
        """安全打印函数，处理编码问题"""
        try:
            print(msg)
        except:
            pass

from bs4 import BeautifulSoup
from datetime import datetime


class ZhihuConverter(HTMLConverterBase if HAS_BASE else object):
    """知乎专栏 HTML 转 Markdown 转换器"""
    
    def __init__(self):
        """初始化转换器"""
        if HAS_BASE:
            super().__init__(
                domain='zhihu.com',
                name='知乎专栏',
                content_selector='.Post-RichTextContainer, .RichContent-inner, .Post-content, .ArticleContent, article',
                title_selector='h1.Post-Title, h1.Title, h1',
                author_selector='.AuthorInfo-name, .UserLink, meta[name="author"]',
                date_selector='.ContentItem-time, .PublishTime, time',
                remove_selectors=[
                    '.Post-SideActions', '.ContentItem-actions', '.Topbar',
                    '.Post-topicsAndReviewer', '.RelatedReadings',
                    '.Comments-container', '.Reward', '.Post-Sub', '.ColumnPostDetail',
                    'script', 'style', '.Modal-wrapper'
                ]
            )
        else:
            self.html2text = html2text.HTML2Text()
            self.html2text.ignore_links = False
            self.html2text.ignore_images = False
            self.html2text.body_width = 0
    
    def extract_metadata(self, soup, html_path):
        """
        提取文章元数据
        
        Args:
            soup: BeautifulSoup 对象
            html_path: HTML 文件路径
            
        Returns:
            dict: 包含标题、作者、日期、URL 等元数据
        """
        metadata = {
            'title': '',
            'author': '',
            'date': '',
            'source': '知乎专栏',
            'url': ''
        }
        
        # 从 title 标签提取标题
        title_tag = soup.find('title')
        if title_tag:
            title_text = title_tag.get_text(strip=True)
            # 移除 "- 知乎" 后缀
            metadata['title'] = re.sub(r'\s*-\s*知乎$', '', title_text)
        
        # 从 h1 提取标题（备用）
        if not metadata['title']:
            h1 = soup.select_one('h1.Post-Title, h1.Title, h1')
            if h1:
                metadata['title'] = h1.get_text(strip=True)
        
        # 从 HTML 注释提取 URL (SingleFile 格式)
        html_content = str(soup)
        match = re.search(r'url:\s*(https?://\S+)', html_content)
        if match:
            metadata['url'] = match.group(1).strip()
        
        # 从 canonical link 提取 URL（备用）
        if not metadata['url']:
            canonical = soup.find('link', {'rel': 'canonical'})
            if canonical and canonical.get('href'):
                metadata['url'] = canonical['href']
        
        # 提取作者
        author_elem = soup.select_one('.AuthorInfo-name, .UserLink, meta[name="author"]')
        if author_elem:
            if author_elem.name == 'meta':
                metadata['author'] = author_elem.get('content', '')
            else:
                metadata['author'] = author_elem.get_text(strip=True)
        
        # 提取日期
        date_elem = soup.select_one('.ContentItem-time, .PublishTime, time')
        if date_elem:
            date_text = date_elem.get_text(strip=True) or date_elem.get('datetime', '')
            # 尝试解析日期（知乎格式：2023-01-01 或 发布于 2023-01-01）
            date_match = re.search(r'(\d{4})[\-年](\d{1,2})[\-月](\d{1,2})', date_text)
            if date_match:
                metadata['date'] = f"{date_match.group(1)}-{date_match.group(2):0>2}-{date_match.group(3):0>2}"
        
        # 从 URL 提取日期（备用）
        if not metadata['date'] and metadata['url']:
            # 知乎 URL 格式：https://zhuanlan.zhihu.com/p/441223546
            # 尝试从文件名提取日期
            filename_match = re.search(r'(\d{4})(\d{2})(\d{2})', os.path.basename(html_path))
            if filename_match:
                metadata['date'] = f"{filename_match.group(1)}-{filename_match.group(2)}-{filename_match.group(3)}"
        
        return metadata
    
    def clean_content(self, soup):
        """
        清理并提取正文内容
        
        1. 找到 .Post-RichTextContainer 或其他内容区域
        2. 移除知乎特有的元素（侧边栏、推荐阅读等）
        3. 处理图片链接
        """
        from copy import deepcopy
        
        # 找到内容区域（知乎专栏）
        content = soup.select_one('.Post-RichTextContainer')
        if not content:
            content = soup.select_one('.RichContent-inner')
        if not content:
            content = soup.select_one('.Post-content')
        if not content:
            content = soup.select_one('article')
        
        if not content:
            return None
        
        content = deepcopy(content)
        
        # 移除不需要的元素（只移除特定的UI元素，不移除包含css-类的所有元素）
        remove_selectors = [
            '.Post-SideActions',          # 侧边操作栏（赞同、评论等）
            '.ContentItem-actions',        # 内容操作栏
            '.Topbar',                     # 顶部导航
            '.Post-topicsAndReviewer',     # 话题和审稿人
            '.RelatedReadings',            # 推荐阅读
            '.Comments-container',         # 评论区
            '.Reward',                     # 赞赏
            '.Post-Sub',                   # 订阅相关
            '.ColumnPostDetail',           # 专栏文章详情
            '.Modal-wrapper',              # 弹窗
            'script', 'style',             # 脚本和样式
            # 只移除交互元素（按钮、图标等），不删除包含css-的所有元素
            'svg[class*="css-"]',          # SVG图标（通常带有css-类）
            'a.RichContent-EntityWord',    # 实体词链接
            '.RichContent-EntityWord',     # 实体词链接（备用）
            '.ContentItem-more',           # "查看更多"按钮
        ]
        
        for selector in remove_selectors:
            try:
                for elem in content.select(selector):
                    elem.decompose()
            except:
                pass
        
        # 处理图片链接（知乎图片通常是 data-src 或 src）
        for img in content.find_all('img'):
            # 优先使用 data-src（知乎的懒加载）
            data_src = img.get('data-src', '')
            if data_src and not data_src.startswith('data:'):
                img['src'] = data_src
            src = img.get('src', '')
            # 处理知乎图片链接（去掉查询参数）
            if 'zhimg.com' in src:
                # 移除 ?source=xxx 等查询参数
                clean_src = src.split('?')[0]
                img['src'] = clean_src
        
        return content
    
    def process_images(self, content, output_dir, stem=''):
        """
        处理图片 - 将 Base64 图片保存到文件
        
        Args:
            content: BeautifulSoup 元素
            output_dir: 输出目录
            
        Returns:
            tuple: (图片数量, 处理后的 content)
        """
        assets_dir = os.path.join(output_dir, 'assets', f'{stem}_assets') if stem else os.path.join(output_dir, 'assets')
        os.makedirs(assets_dir, exist_ok=True)
        
        img_count = 0
        replacements = []
        
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
                        
                        replacements.append((src, f'assets/{stem}_assets/{img_name}'))
                    else:
                        img.decompose()
                except:
                    img.decompose()
            # 跳过 SVG 图标类图片
            elif 'svg' in src.lower():
                img.decompose()
        
        # 使用字符串替换来更新 src
        if replacements:
            content_str = str(content)
            for old_src, new_src in replacements:
                content_str = content_str.replace(old_src, new_src)
            new_soup = BeautifulSoup(content_str, 'html.parser')
            if new_soup.find():
                return img_count, new_soup.find()
            return img_count, new_soup
        
        return img_count, content
    
    def post_process_markdown(self, md_content, metadata):
        """
        后处理 Markdown 内容
        
        移除知乎特有的无关内容
        """
        # 移除 "首发于" 等标识
        md_content = re.sub(r'\n*首发于.*?(?=\n|$)', '', md_content)
        
        # 移除 "赞同" "喜欢" 等按钮文字
        md_content = re.sub(r'\n*\d+\s*赞同.*?(?=\n|$)', '', md_content)
        md_content = re.sub(r'\n*\d+\s*喜欢.*?(?=\n|$)', '', md_content)
        
        # 移除 "推荐阅读" 部分
        md_content = re.sub(r'\n*推荐阅读.*?(?=\n{2,}|$)', '', md_content, flags=re.DOTALL)
        
        # 移除 "编辑于" 等信息
        md_content = re.sub(r'\n*编辑于.*?(?=\n|$)', '', md_content)
        
        # 移除版权声明（知乎专栏通常有）
        md_content = re.sub(r'\n*本文来自.*?(?=\n{2,}|$)', '', md_content, flags=re.DOTALL)
        
        # 清理多余空行
        md_content = re.sub(r'\n{3,}', '\n\n', md_content)
        
        # 修复图片路径
        def fix_image_path(match):
            alt = match.group(1)
            path = match.group(2).replace('\\', '/')
            return f'![{alt}]({path})'
        md_content = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', fix_image_path, md_content)
        
        # 移除重复的标题
        title = metadata.get('title', '')
        if title:
            md_content = re.sub(f'^#+\s*{re.escape(title)}\s*\n', '', md_content, count=1, flags=re.IGNORECASE)
        
        return md_content.strip()
    
    def convert(self, html_path, output_dir=None):
        """
        转换单个 HTML 文件
        
        Args:
            html_path: HTML 文件路径
            output_dir: 输出目录（可选）
            
        Returns:
            bool: 是否成功
        """
        if not os.path.exists(html_path):
            print(f"文件不存在: {html_path}")
            return False
        
        if output_dir is None:
            output_dir = os.path.dirname(html_path) or '.'
        
        domain_dir = os.path.join(output_dir, 'zhihu_com')
        os.makedirs(domain_dir, exist_ok=True)
        
        try:
            with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
                soup = BeautifulSoup(f.read(), 'html.parser')
        except Exception as e:
            print(f"解析 HTML 失败: {e}")
            return False
        
        # 提取元数据
        metadata = self.extract_metadata(soup, html_path)

        # 链接卡片处理：提取标题和链接，去除缩略图和多余文本
        for card in soup.find_all(attrs={'data-draft-type': 'link-card'}):
            from bs4 import NavigableString
            # Remove images inside link cards so they don't get extracted/counted
            for img in card.find_all('img'):
                img.decompose()
            title = card.get('data-text', '') or card.get_text(strip=True)
            href = card.get('href', '')
            if title and href:
                import re as _re
                title = _re.sub(r'(?:https?://)?[\w.-]+\.[a-z]{2,}(?:/[\w./\-?=&%]*)?$', '', title).strip()
                card.replace_with(NavigableString(f'[{title}]({href})'))
            else:
                card.decompose()

        # LaTeX 处理：从 data-tex 提取公式，$ 包裹
        for span in soup.find_all('span', class_='ztext-math'):
            tex = span.get('data-tex', '').strip()
            if not tex:
                continue
            # Single character inline
            if len(tex) <= 1:
                span.replace_with(NavigableString(f'${tex}$'))
            # Long display formula (>60 chars)
            elif len(tex) > 60:
                span.replace_with(NavigableString(f'\n$$\n{tex}\n$$\n'))
            # Inline formula
            else:
                span.replace_with(NavigableString(f'${tex}$'))

        # 处理图片（必须在 clean_content 之前，因为 clean_content 会 deepcopy）
        stem = Path(html_path).stem
        img_count = self._extract_base64_images(soup, str(html_path), domain_dir)

        # 清理内容
        content = self.clean_content(soup)
        if not content:
            print(f"未找到正文内容: {html_path}")
            return False
        if img_count > 0:
            print(f"  提取了 {img_count} 张图片")
        
        # Protect code blocks
        code_blocks = self._protect_code_blocks(content)

        # 转换为 Markdown
        if HAS_BASE:
            md_content = self.html_to_markdown(content)
        else:
            md_content = self.html2text.handle(str(content))

        # Restore code blocks
        md_content = self._restore_code_blocks(md_content, code_blocks)

        # 后处理
        md_content = self.post_process_markdown(md_content, metadata)
        
        # 构建 YAML 前置元数据
        yaml_front = f"""---
title: "{metadata['title']}"
author: {metadata['author'] or '知乎用户'}
date: {metadata['date'] or ''}
source: {metadata['source']}
url: {metadata['url']}
converted_at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
---

"""
        
        # 保存文件
        base_name = os.path.splitext(os.path.basename(html_path))[0]
        md_path = os.path.join(domain_dir, f"{base_name}.md")
        
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(yaml_front + md_content)
        
        print(f"已转换: {md_path}")
        return True
    
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
    converter = ZhihuConverter()
    
    if len(sys.argv) > 1:
        if sys.argv[1].endswith('.html'):
            converter.convert(sys.argv[1])
        else:
            converter.batch_convert(sys.argv[1])
    else:
        import glob
        files_to_convert = []
        
        for pattern in ['*知乎*.html', '*zhihu*.html']:
            files_to_convert.extend(glob.glob(pattern))
        
        files_to_convert = list(set(files_to_convert))
        
        if not files_to_convert:
            print("未发现知乎专栏的 HTML 文件")
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
