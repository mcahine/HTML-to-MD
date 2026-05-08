#!/usr/bin/env python3
"""
张鑫旭博客 (zhangxinxu.com) HTML 转 Markdown 转换器

功能：
- 提取文章正文内容
- 处理 Base64 图片并保存到 assets 目录
- 修复代码块中的 HTML 实体编码
- 移除广告、分享按钮、评论区域等无关内容
- 生成带有 YAML 前置元数据的 Markdown 文件
"""
import sys
import os
from pathlib import Path
import re

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


class ZhangxinxuConverter(HTMLConverterBase if HAS_BASE else object):
    """张鑫旭博客 HTML 转 Markdown 转换器"""
    
    def __init__(self):
        """初始化转换器"""
        if HAS_BASE:
            super().__init__(
                domain='zhangxinxu.com',
                name='张鑫旭博客',
                content_selector='.content, .entry-content, article, #content',
                title_selector='h1, .entry-title, .post-title',
                author_selector='.author, .entry-author',
                date_selector='.entry-date, .post-date, time',
                remove_selectors=[
                    '.sidebar', '.navigation', '.comment-area',
                    '.related-posts', '.tag-cloud', '.ads',
                    'script', 'style', '.share-buttons',
                    '.post-nav', '.post-meta', '.entry-meta'
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
            'author': '张鑫旭',
            'date': '',
            'source': '张鑫旭博客',
            'url': ''
        }
        
        # 从 title 标签提取标题
        title_tag = soup.find('title')
        if title_tag:
            title_text = title_tag.get_text(strip=True)
            # 移除站点后缀 " - 张鑫旭博客"
            metadata['title'] = re.sub(r'\s*[-|]\s*张鑫旭博客$', '', title_text)
        
        # 从 h1 提取标题（备用）
        if not metadata['title']:
            h1 = soup.select_one('h1, .entry-title, .post-title')
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
        
        # 从页面元素提取日期
        date_elem = soup.select_one('.entry-date, .post-date, time')
        if date_elem:
            date_text = date_elem.get_text(strip=True) or date_elem.get('datetime', '')
            date_match = re.search(r'(\d{4})[/-](\d{2})[/-](\d{2})', date_text)
            if date_match:
                metadata['date'] = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
        
        # 从 URL 提取日期（备用）
        if not metadata['date'] and metadata['url']:
            date_match = re.search(r'/(\d{4})(\d{2})(\d{2})/', metadata['url'])
            if date_match:
                metadata['date'] = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
        
        # 从文件名提取日期（最后备用）
        if not metadata['date']:
            filename_match = re.search(r'(\d{4})(\d{2})(\d{2})', os.path.basename(html_path))
            if filename_match:
                metadata['date'] = f"{filename_match.group(1)}-{filename_match.group(2)}-{filename_match.group(3)}"
        
        return metadata
    
    def clean_byline(self, soup):
        """
        清理开头的 byline/版权声明
        
        移除包含 "byzhangxinxu" 或 "本文可全文转载" 的元素
        """
        from copy import deepcopy
        soup = deepcopy(soup)
        
        for elem in soup.find_all(string=re.compile(r'byzhangxinxu|本文可全文转载')):
            try:
                for ancestor in list(elem.parents)[:3]:
                    text = ancestor.get_text()
                    if 'zhangxinxu' in text.lower() and ('本文可全文转载' in text or 'fromhttps' in text.replace(' ', '').lower()):
                        ancestor.decompose()
                        break
            except:
                pass
        return soup
    
    def clean_footer(self, soup):
        """
        清理结尾的表情符号和分享提示
        
        只处理文档后 20% 的内容，避免误删正文
        只删除短文本（<300字符）的匹配项
        """
        from copy import deepcopy
        soup = deepcopy(soup)
        
        # 只处理靠近文档末尾的元素（避免误删正文内容）
        all_texts = list(soup.find_all(string=True))
        start_idx = int(len(all_texts) * 0.8)  # 从 80% 位置开始
        
        emoji_pattern = re.compile(r'[😉😊😇🥰😍😘]|\(本篇完\)|是不是学到了很多|可以分享到微信|有话要说|点击这里')
        
        for elem in all_texts[start_idx:]:
            if emoji_pattern.search(str(elem)):
                try:
                    for ancestor in list(elem.parents)[:3]:
                        text = ancestor.get_text()
                        # 只删除短文本（footer 特征）
                        if (len(text) < 300 and 
                            ('(本篇完)' in text or 
                             '是不是学到了很多' in text or 
                             '可以分享到微信' in text or
                             '有话要说' in text or
                             ('😉' in text and len(text) < 100))):
                                ancestor.decompose()
                                break
                except:
                    pass
        return soup
    
    def remove_copy_links(self, soup):
        """移除代码块中的复制/还原链接"""
        for a in soup.find_all('a'):
            text = a.get_text(strip=True)
            href = a.get('href', '')
            if href == 'javascript:void(0)' and text in ['复制', '还原']:
                a.decompose()
            elif href == 'javascript:void(0)' and a.get('title') in ['复制', '还原']:
                a.decompose()
        return soup
    
    def fix_code_blocks(self, soup):
        """
        修复代码块
        
        使用 NavigableString 避免 BeautifulSoup 对 HTML 实体的二次转义
        确保代码中的 &lt; 显示为 < 而不是被转义
        """
        from copy import deepcopy
        from bs4 import NavigableString
        
        soup = deepcopy(soup)
        soup = self.remove_copy_links(soup)
        
        for pre in soup.find_all('pre'):
            code = pre.find('code')
            
            # 获取语言类型
            lang = 'text'
            for cls in pre.get('class', []):
                if 'js' in cls or 'javascript' in cls:
                    lang = 'javascript'
                    break
                elif 'css' in cls:
                    lang = 'css'
                    break
                elif 'html' in cls:
                    lang = 'html'
                    break
            
            if code:
                # BeautifulSoup 的 get_text() 已经解码了 HTML 实体
                code_text = code.get_text()
                code['class'] = f'language-{lang}'
                code.clear()
                code.append(NavigableString(code_text))
            else:
                code_text = pre.get_text()
                pre.clear()
                pre.append(NavigableString(code_text))
        
        return soup
    
    def clean_content(self, soup):
        """
        清理并提取正文内容
        
        1. 找到 #content 或 article 元素
        2. 清理 byline 和 footer
        3. 修复代码块
        4. 移除评论、侧边栏等不需要的元素
        """
        from copy import deepcopy
        
        # 找到内容区域
        content = soup.select_one('#content')
        if not content:
            content = soup.select_one('.entry-content')
        if not content:
            content = soup.select_one('article')
        
        if not content:
            return None
        
        content = deepcopy(content)
        content = self.clean_byline(content)
        content = self.clean_footer(content)
        content = self.fix_code_blocks(content)
        
        # 移除不需要的元素
        remove_selectors = [
            '.sidebar', '.navigation', '.comment-area',
            '.related-posts', '.tag-cloud', '.ads',
            'script', 'style', '.share-buttons',
            '.post-nav', '.post-meta', '.entry-meta',
            '.post-footer', '.entry-footer',
            '#comments', '.comments', '.comment-list',
            '.comment-form', '#respond', '.comment-respond',
            '.comment-reply-title', '.comment-metadata',
            '.comment-author', '.comment-content',
            '#commentform', '.form-submit', '.comment-form-comment',
            '.comment-form-author', '.comment-form-email',
            '.comment-form-url', '.logged-in-as'
        ]
        
        for selector in remove_selectors:
            for elem in content.select(selector):
                elem.decompose()
        
        # 清理评论标题
        for header in content.find_all(['h2', 'h3', 'h4', 'h5', 'h6']):
            if any(kw in header.get_text(strip=True) for kw in ['评论', '发表评论', '留言', '留言板']):
                header.decompose()
        
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
        import base64
        
        assets_dir = os.path.join(output_dir, 'assets', f'{stem}_assets') if stem else os.path.join(output_dir, 'assets')
        os.makedirs(assets_dir, exist_ok=True)
        
        img_count = 0
        replacements = []
        
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
                            f.write(base64.b64decode(img_data))
                        
                        replacements.append((src, f'assets/{stem}_assets/{img_name}'))
                    else:
                        img.decompose()
                except:
                    img.decompose()
            elif 'svg' in src.lower() and ('share' in src.lower() or 'icon' in src.lower()):
                img.decompose()
        
        # 使用字符串替换来更新 src，避免破坏 BeautifulSoup 结构
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
        # Safe single-line patterns only (no DOTALL to avoid backtracking)
        md_content = re.sub(r'^\s*(主题|标签|分类|专题)\s*[：:].*$', '', md_content, flags=re.MULTILINE | re.IGNORECASE)
        md_content = re.sub(r'^by\s*zhangxinxu.*$', '', md_content, flags=re.MULTILINE | re.IGNORECASE)
        # Remove tag links
        md_content = re.sub(r'^\[([^\]]+)\]\(https?://www\.zhangxinxu\.com/wordpress/tag/[^)]+\)[\s,]*', '', md_content, flags=re.MULTILINE)
        # Remove share links: 分享到[](url)
        md_content = re.sub(r'^分享[到至].*$', '', md_content, flags=re.MULTILINE)
        md_content = re.sub(r'^\[\]\(https?://service\.weibo\.com[^)]+\).*$', '', md_content, flags=re.MULTILINE)
        # Remove ad SVGs and data URI images
        md_content = re.sub(r'!\[[^\]]*\]\(data:image/svg\+xml,[^)]*\)\n*', '', md_content)
        md_content = re.sub(r'!\[[^\]]*\]\(data:[^)]+\)\n*', '', md_content)
        # Remove wwads.cn ad links (inline ad blocks)
        md_content = re.sub(r'\[[^\]]*\][\s\n]*\(https?://wwads\.cn[^)]*\)', '', md_content)
        md_content = re.sub(r'^.*wwads\.cn.*$', '', md_content, flags=re.MULTILINE)
        # Cut at "相关文章" or similar footer sections
        for marker in ['\n相关文章', '\n推荐文章', '\n相关阅读', '\n分享到', '\n分享至']:
            idx = md_content.find(marker)
            if idx > 0:
                md_content = md_content[:idx]
                break
        md_content = re.sub(r'\n{3,}', '\n\n', md_content)
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
        
        domain_dir = os.path.join(output_dir, 'zhangxinxu_com')
        os.makedirs(domain_dir, exist_ok=True)
        
        try:
            with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
                soup = BeautifulSoup(f.read(), 'html.parser')
        except Exception as e:
            print(f"解析 HTML 失败: {e}")
            return False
        
        # 提取元数据
        metadata = self.extract_metadata(soup, html_path)

        # 处理图片（必须在 clean_content 之前，因为 clean_content 会 deepcopy）
        img_count = self._extract_base64_images(soup, str(html_path), domain_dir)
        if img_count > 0:
            print(f"  提取了 {img_count} 张图片")

        # 清理内容
        content = self.clean_content(soup)
        if not content:
            print(f"未找到正文内容: {html_path}")
            return False
        
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
author: {metadata['author']}
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
    converter = ZhangxinxuConverter()
    
    if len(sys.argv) > 1:
        if sys.argv[1].endswith('.html'):
            converter.convert(sys.argv[1])
        else:
            converter.batch_convert(sys.argv[1])
    else:
        import glob
        files_to_convert = []
        
        for pattern in ['*张鑫旭*.html', '*zhangxinxu*.html']:
            files_to_convert.extend(glob.glob(pattern))
        
        files_to_convert = list(set(files_to_convert))
        
        if not files_to_convert:
            print("未发现张鑫旭博客的 HTML 文件")
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
