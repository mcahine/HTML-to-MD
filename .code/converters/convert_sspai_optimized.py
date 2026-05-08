#!/usr/bin/env python3
"""少数派 (sspai.com) HTML 转 Markdown 转换器 - 优化版"""
import os
import re
import base64
import json
from pathlib import Path
from bs4 import BeautifulSoup
import html2text

class SspaiConverterOptimized:
    """少数派 HTML 转 Markdown 优化版转换器"""
    
    def __init__(self):
        self.html2text = html2text.HTML2Text()
        self.html2text.ignore_links = False
        self.html2text.ignore_images = False
        self.html2text.body_width = 0
        self.html2text.wrap_links = False
        self.html2text.wrap_list_items = False
        # 保护代码块
        self.html2text.code_preserve = True
    
    def extract_metadata(self, soup, html_path):
        """提取文章元数据"""
        metadata = {
            'title': '',
            'author': '',
            'date': '',
            'source': 'https://sspai.com'
        }
        
        # 1. 尝试从 JSON-LD 提取
        json_ld = soup.find('script', {'type': 'application/ld+json'})
        if json_ld and json_ld.string:
            try:
                data = json.loads(json_ld.string)
                if isinstance(data, dict):
                    # 标题
                    headline = data.get('headline', '')
                    if headline:
                        metadata['title'] = headline.replace(' - 少数派', '')
                    
                    # 作者
                    author_data = data.get('author', {})
                    if isinstance(author_data, dict):
                        metadata['author'] = author_data.get('name', '')
                    
                    # 日期
                    date_published = data.get('datePublished', '')
                    if date_published and date_published != '1970-01-01T00:00:00.000Z':
                        metadata['date'] = date_published[:10]
                    
                    # 来源 URL
                    url = data.get('url', '')
                    if url:
                        metadata['source'] = url
            except json.JSONDecodeError:
                pass
        
        # 2. 如果 JSON-LD 没提取到，从 meta 标签提取
        if not metadata['title']:
            og_title = soup.find('meta', {'property': 'og:title'})
            if og_title and og_title.get('content'):
                metadata['title'] = og_title['content'].replace(' - 少数派', '')
        
        if not metadata['title']:
            title_tag = soup.find('title')
            if title_tag:
                metadata['title'] = title_tag.get_text().replace(' - 少数派', '')
        
        # 从页面内容中提取作者（如果还没找到）
        if not metadata['author']:
            # 尝试从作者卡片获取
            author_elem = soup.select_one('.ss__user__nickname span, .author-name, .username')
            if author_elem:
                metadata['author'] = author_elem.get_text(strip=True)
        
        # 提取日期
        if not metadata['date']:
            # 尝试从 .timer 获取
            timer = soup.select_one('.timer')
            if timer:
                date_text = timer.get_text(strip=True)
                # 格式: 2025/12/16 16:32
                match = re.search(r'(\d{4}/\d{2}/\d{2})', date_text)
                if match:
                    metadata['date'] = match.group(1).replace('/', '-')
        
        # 从 URL meta 提取来源
        og_url = soup.find('meta', {'property': 'og:url'})
        if og_url and og_url.get('content'):
            metadata['source'] = og_url['content']
        
        return metadata
    
    def clean_content(self, soup):
        """清理并提取正文内容"""
        # 找到内容区域 - 少数派的主要内容是 .article__main__content
        content = None
        
        # 尝试多种选择器
        selectors = [
            '.article__main__content',  # 主要选择器
            'article .article-body',      # 备用选择器
            'article',                    # 通用选择器
            '.content',                   # 通用选择器
            '.post-content',              # 备用
        ]
        
        for selector in selectors:
            content = soup.select_one(selector)
            if content:
                break
        
        if not content:
            print("警告: 未找到正文内容区域")
            return None
        
        # 创建内容的深拷贝
        from copy import deepcopy
        content_copy = deepcopy(content)
        
        # 移除不需要的元素
        remove_selectors = [
            # 头部导航
            'header', 
            '.ss__custom__header',
            '.ss__custom__header__wrapper',
            '#app-head',
            
            # 作者相关信息
            '.author-card',
            '.article-author',
            '.author-box', 
            '.article-header-author',
            '.author-popover',
            '.el-popover',
            '.el-popper',
            '.el-tooltip',
            '.author-item',
            '.follow-btn',
            '.author-profile',
            '.ss__user__card',
            '.ss__user__card__wrapper',
            '[class*="user__card"]',
            
            # 评论区
            '.comment-section',
            '.comments__feed',
            '.comment-list',
            '.comment-form',
            '.comment-area',
            '.comments-section',
            '.common__comment__dialog',
            '.common__comment__handlers',
            
            # 推荐文章
            '.related-articles',
            '.related-read-box',
            '.recommend_container',
            '.articleCard',
            
            # 广告和推广
            '.ads',
            '.advertisement',
            '.advertisement-box',
            '.adv-box',
            '.app-download-banner',
            '.matrix-recommend',
            '.article-sponsor',
            
            # 底部信息
            '.article-footer',
            '.article-copyright',
            '.article-recommend',
            '.article-actionBar',
            '.article-copyrights',
            
            # 工具栏和按钮
            '.article-actions',
            '.article-share',
            '.article-toolbar',
            '.read-more',
            '.post-navigation',
            '.ss__button',
            
            # 目录和导航
            '.toc',
            '.catalog',
            '.outline',
            '.table-of-contents',
            
            # 标签
            '.tag-list',
            '.article-tag',
            
            # 编辑信息
            '.editor-info',
            '.article-editor',
            '.responsible-editor',
            
            # 脚本和样式
            'script',
            'style',
            'noscript',
            
            # SVG 图标
            'svg',
        ]
        
        for selector in remove_selectors:
            for elem in content_copy.select(selector):
                elem.decompose()
        
        # 清理特定文本节点
        for elem in content_copy.find_all(['span', 'div', 'p']):
            text = elem.get_text(strip=True)
            # 移除包含特定模式的文本
            if any(pattern in text for pattern in [
                '关注少数派公众号',
                '解锁全新阅读体验',
                '实用、好用的正版软件',
                '少数派为你呈现',
                '我来说一句',
                '发布发表评论',
                '本文责编',
                '本文编辑',
                'Less is more',
                '公众号同为',
                '主作者',
                '联合作者',
                '没有更多评论了',
                '全部评论',
                '推荐阅读',
            ]):
                if len(text) < 100:  # 确保是短文本
                    elem.decompose()
                    continue
        
        # 清理空标签和无用属性
        for elem in content_copy.find_all():
            # 移除 data-v- 开头的属性
            attrs_to_remove = [attr for attr in elem.attrs if attr.startswith('data-v-') or attr.startswith('data-sf-')]
            for attr in attrs_to_remove:
                del elem[attr]
            
            # 移除 Vue 相关属性
            vue_attrs = ['data-v-', 'class*="el-popover"', 'aria-describedby', 'tabindex']
            
        # 移除小尺寸图片（可能是头像或图标）
        for img in content_copy.find_all('img'):
            src = img.get('src', '')
            width = img.get('width', '')
            height = img.get('height', '')
            
            # 跳过 Base64 内容图片，只处理小图标
            if width and height:
                try:
                    w, h = int(width), int(height)
                    if w <= 72 and h <= 72:
                        img.decompose()
                        continue
                except:
                    pass
            
            # 检查是否是头像 URL
            if any(pattern in src.lower() for pattern in ['avatar', 'thumbnail/!32x32', 'thumbnail/!48x48', 'thumbnail/!72x72']):
                img.decompose()
                continue
        
        return content_copy
    
    def convert_images(self, content, output_dir):
        """处理图片：将 Base64 图片保存到本地"""
        img_dir = os.path.join(output_dir, 'images')
        os.makedirs(img_dir, exist_ok=True)
        
        img_count = 0
        for img in content.find_all('img'):
            src = img.get('src', '')
            
            # 处理 Base64 图片
            if src.startswith('data:image'):
                try:
                    # 解析 Base64
                    match = re.match(r'data:image/(\w+);base64,(.+)', src)
                    if match:
                        img_type, img_data = match.groups()
                        img_type = img_type.lower()
                        
                        # 修正图片类型
                        if img_type == 'svg+xml':
                            img_type = 'svg'
                        elif img_type not in ['png', 'jpg', 'jpeg', 'gif', 'webp']:
                            img_type = 'png'
                        
                        # 生成文件名
                        img_count += 1
                        img_name = f'image_{img_count:03d}.{img_type}'
                        img_path = os.path.join(img_dir, img_name)
                        
                        # 保存图片
                        try:
                            with open(img_path, 'wb') as f:
                                f.write(base64.b64decode(img_data))
                            
                            # 更新 img 标签的 src
                            rel_path = os.path.join('images', img_name)
                            img['src'] = rel_path
                        except Exception as e:
                            print(f"保存图片失败: {e}")
                            img.decompose()
                    else:
                        img.decompose()
                except Exception as e:
                    print(f"处理图片失败: {e}")
                    img.decompose()
            else:
                # 保留原始 URL
                pass
        
        return img_count
    
    def convert(self, html_path, output_dir=None):
        """转换单个 HTML 文件"""
        if not os.path.exists(html_path):
            print(f"文件不存在: {html_path}")
            return False
        
        if output_dir is None:
            output_dir = os.path.dirname(html_path) or '.'
        
        # 创建输出目录
        domain_dir = os.path.join(output_dir, 'sspai_com')
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
        img_count = self.convert_images(content, domain_dir)
        if img_count > 0:
            print(f"  提取了 {img_count} 张图片")
        
        # 转换为 Markdown
        md_content = self.html2text.handle(str(content))
        
        # 后处理 Markdown
        md_content = self.post_process_markdown(md_content, metadata)
        
        # 构建 YAML 前置元数据
        yaml_front = f"---\n"
        yaml_front += f"title: {metadata['title']}\n"
        yaml_front += f"author: {metadata['author']}\n"
        yaml_front += f"date: {metadata['date']}\n"
        yaml_front += f"source: {metadata['source']}\n"
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
        
        # 修复标题格式
        md_content = re.sub(r'([^\n])\n(#{1,6} )', r'\1\n\n\2', md_content)
        
        # 修复图片前后格式
        md_content = re.sub(r'(!\[.*?\]\(.*?\))\n([^\n])', r'\1\n\n\2', md_content)
        md_content = re.sub(r'([^\n])\n(!\[.*?\]\(.*?\))', r'\1\n\n\2', md_content)
        
        # 移除空图片引用
        md_content = re.sub(r'!\[\]\(\)', '', md_content)
        md_content = re.sub(r'!\[\]\(data:image/svg[^\)]+\)', '', md_content)
        
        # 移除标题中可能的 HTML 标签
        md_content = re.sub(r'<[^>]+>', '', md_content)
        
        # 修复链接格式
        md_content = re.sub(r'\[([^\]]+)\]\s*\n\s*\(([^\)]+)\)', r'[\1](\2)', md_content)
        
        # 移除 "# 讨论" 等无用标题
        md_content = re.sub(r'\n#{1,6}\s*(讨论|评论|相关文章|推荐文章|作者简介).*\n', '\n', md_content, flags=re.IGNORECASE)
        
        # 移除重复的标题（如果正文开头重复了文章标题）
        title = metadata.get('title', '')
        if title:
            md_content = re.sub(f'^#+\\s*{re.escape(title)}\\s*\\n', '', md_content, count=1, flags=re.IGNORECASE)
        
        # 清理行首行尾空白
        lines = [line.rstrip() for line in md_content.split('\n')]
        md_content = '\n'.join(lines)
        
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
    import sys
    converter = SspaiConverterOptimized()
    
    if len(sys.argv) > 1:
        if sys.argv[1].endswith('.html'):
            converter.convert(sys.argv[1])
        else:
            converter.batch_convert(sys.argv[1])
    else:
        # 转换少数派文件
        files_to_convert = [
            "Gemini_律师_AI工作流_20251216_少数派.html",
            "H_pylori_胃_健康_20240109_少数派.html",
            "Windows_Vista_视觉史_20260125_少数派.html"
        ]
        
        success_count = 0
        for html_file in files_to_convert:
            if os.path.exists(html_file):
                if converter.convert(html_file):
                    success_count += 1
            else:
                print(f"文件不存在: {html_file}")
        
        print(f"\n转换完成: {success_count}/{len(files_to_convert)} 个文件成功")
