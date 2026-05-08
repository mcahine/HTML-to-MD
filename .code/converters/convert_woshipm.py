#!/usr/bin/env python3
"""
人人都是产品经理 HTML 文件转换脚本
将 woshipm.com 的网页转换为 Markdown，并提取 Base64 图片到 assets 文件夹
"""

import os
import re
import base64
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup
import html2text


class WoshipmHtmlToMarkdownConverter:
    """人人都是产品经理 HTML 转 Markdown 转换器"""
    
    def __init__(self):
        self.html2text = html2text.HTML2Text()
        self.html2text.ignore_links = False
        self.html2text.ignore_images = False
        self.html2text.body_width = 0
        self.html2text.wrap_links = False
        self.html2text.wrap_list_items = False
    
    def is_woshipm_site(self, soup):
        """检查是否是人人都是产品经理网站"""
        # 检查 URL
        url_meta = soup.find('meta', {'property': 'og:url'})
        if url_meta and url_meta.get('content'):
            if 'woshipm.com' in url_meta['content']:
                return True
        
        # 检查 canonical
        canonical = soup.find('link', {'rel': 'canonical'})
        if canonical and canonical.get('href'):
            if 'woshipm.com' in canonical['href']:
                return True
        
        return False
    
    def extract_metadata(self, soup):
        """提取文章元数据"""
        metadata = {}
        
        # 标题
        title_tag = soup.find('meta', {'property': 'og:title'})
        if title_tag and title_tag.get('content'):
            metadata['title'] = title_tag['content']
        else:
            # 尝试从页面标题获取
            title_elem = soup.select_one('.article--title, .post-title, h1.title, h2.title')
            if title_elem:
                metadata['title'] = title_elem.get_text(strip=True)
            elif soup.title:
                metadata['title'] = soup.title.string.strip() if soup.title.string else 'Untitled'
            else:
                metadata['title'] = 'Untitled'
        
        # 作者
        author_tag = soup.find('meta', {'name': 'author'})
        if author_tag:
            metadata['author'] = author_tag.get('content', '')
        else:
            # 尝试从 meta 信息获取
            author_elem = soup.select_one('.artilce--meta, .article-meta, .author-name')
            if author_elem:
                meta_text = author_elem.get_text(strip=True)
                # 通常是 "作者 · 发布时间 · 浏览量" 格式
                parts = meta_text.split('·')
                if parts:
                    metadata['author'] = parts[0].strip()
                else:
                    metadata['author'] = meta_text
            else:
                metadata['author'] = ''
        
        # URL
        url_tag = soup.find('meta', {'property': 'og:url'})
        metadata['url'] = url_tag['content'] if url_tag else ''
        
        # 发布时间
        date_tag = soup.find('meta', {'property': 'article:published_time'})
        if date_tag:
            metadata['date'] = date_tag['content']
        else:
            metadata['date'] = ''
        
        return metadata
    
    def extract_content(self, soup):
        """提取正文内容 - 人人都是产品经理专用"""
        # 人人都是产品经理的选择器
        selectors = [
            '.article--content',      # 主要正文容器
            '.grap',                  # 旧版正文容器
            '.article-content',       # 备选
            '.post-content',          # 备选
            'article.post',           # 文章容器
            '.entry-content',         # 通用备选
        ]
        
        for selector in selectors:
            content = soup.select_one(selector)
            if content:
                return content, selector
        
        # 通用策略
        generic_selectors = ['article', '.article', 'main', '.content', '#content']
        for selector in generic_selectors:
            content = soup.select_one(selector)
            if content:
                return content, selector
        
        return None, None
    
    def clean_content(self, content):
        """清理内容中的不必要元素"""
        # 移除脚本、样式、导航等
        for element in content.find_all(['script', 'style', 'nav', 'header', 'footer', 'aside']):
            element.decompose()
        
        # 移除广告相关元素
        ad_patterns = re.compile(r'ad|banner|popup|commercial|promotion', re.I)
        for element in content.find_all(class_=ad_patterns):
            element.decompose()
        
        # 移除人人都是产品经理特定的无关元素
        woshipm_remove_selectors = [
            '.article--meta',         # 元信息栏
            '.article-footer',        # 文章底部
            '.article-tags',          # 标签
            '.related-posts',         # 相关文章
            '.comments-area',         # 评论区
            '.comment-list',          # 评论列表
            '.post-navigation',       # 文章导航
            '.author-box',            # 作者信息框
            '.social-share',          # 分享按钮
            '.sidebar',               # 侧边栏
            '.site-header',           # 网站头部
            '.site-footer',           # 网站底部
        ]
        
        for selector in woshipm_remove_selectors:
            for element in content.select(selector):
                element.decompose()
        
        return content
    
    def extract_and_save_images(self, soup, assets_dir, file_stem):
        """提取 Base64 图片并保存到 assets 文件夹"""
        assets_dir.mkdir(parents=True, exist_ok=True)
        image_map = {}
        
        img_tags = soup.find_all('img')
        
        for idx, img in enumerate(img_tags, 1):
            src = img.get('src', '')
            
            if src.startswith('data:image'):
                try:
                    match = re.match(r'data:image/(\w+);base64,(.+)', src)
                    if match:
                        ext = match.group(1)
                        base64_data = match.group(2).strip()
                        
                        ext_map = {
                            'jpeg': 'jpg',
                            'jpg': 'jpg',
                            'png': 'png',
                            'gif': 'gif',
                            'webp': 'webp',
                            'svg': 'svg'
                        }
                        file_ext = ext_map.get(ext.lower(), ext.lower())
                        
                        filename = f"image_{idx:03d}.{file_ext}"
                        filepath = assets_dir / filename
                        
                        try:
                            image_data = base64.b64decode(base64_data)
                            with open(filepath, 'wb') as f:
                                f.write(image_data)
                            
                            relative_path = f"assets/{file_stem}_assets/{filename}"
                            image_map[src] = relative_path
                            print(f"    [图片] 已保存: {filename} ({len(image_data)} bytes)")
                        except Exception as e:
                            print(f"    [警告] 保存图片失败 {filename}: {e}")
                            continue
                except Exception as e:
                    print(f"    [警告] 解析 Base64 图片失败: {e}")
                    continue
        
        return image_map
    
    def replace_image_links_in_markdown(self, markdown, image_map):
        """在 Markdown 中替换图片链接"""
        for old_src, new_path in image_map.items():
            old_src_escaped = re.escape(old_src)
            pattern = r'!\[([^\]]*)\]\(' + old_src_escaped + r'\)'
            replacement = f'![\\1]({new_path})'
            markdown = re.sub(pattern, replacement, markdown)
        
        return markdown
    
    def format_special_blocks(self, markdown):
        """将特定内容转换为代码块格式，连续内容合并到一个代码块"""
        lines = markdown.split('\n')
        result = []
        
        def is_special_line(stripped):
            """判断是否是特殊内容行"""
            if not stripped:
                return False
            if '本文由人人都是产品经理作者' in stripped:
                return True
            if '原创/授权 发布于人人都是产品经理' in stripped:
                return True
            if '原创发布于人人都是产品经理' in stripped:
                return True
            if '题图来自' in stripped and ('协议' in stripped or 'CC0' in stripped):
                return True
            if stripped == '赞赏':
                return True
            if '已赞' in stripped and '赞赏' in stripped:
                return True
            if '该文观点仅代表作者本人' in stripped:
                return True
            if '人人产品经理平台仅提供信息存储空间服务' in stripped:
                return True
            return False
        
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            
            # 文章摘要（通常是正文第一段，以">"开头）
            if i == 0 and stripped.startswith('>'):
                content = stripped.lstrip('>').strip()
                result.append(f"```\n{content}\n```")
                i += 1
                continue
            
            # 检查是否是特殊内容行
            if is_special_line(stripped):
                # 收集连续的特殊内容（包括中间的空行）
                special_lines = [stripped]
                j = i + 1
                while j < len(lines):
                    next_stripped = lines[j].strip()
                    if is_special_line(next_stripped):
                        special_lines.append(next_stripped)
                        j += 1
                    elif next_stripped == '':
                        # 空行，检查下一行是否还是特殊内容
                        if j + 1 < len(lines) and is_special_line(lines[j + 1].strip()):
                            j += 1
                            continue
                        else:
                            break
                    else:
                        break
                
                # 输出合并的代码块
                result.append('```')
                result.extend(special_lines)
                result.append('```')
                
                i = j
            else:
                result.append(line)
                i += 1
        
        return '\n'.join(result)
    
    def clean_markdown(self, markdown):
        """清理 Markdown 内容"""
        # 移除过多的空行
        markdown = re.sub(r'\n{3,}', '\n\n', markdown)
        
        # 清理人人都是产品经理特定的文本
        markdown = re.sub(r'编辑于\s*\d{4}[-/]\d{2}[-/]\d{2}\s*\d{2}:\d{2}', '', markdown)
        markdown = re.sub(r'浏览量\s*\d+', '', markdown)
        markdown = re.sub(r'点赞', '', markdown)
        markdown = re.sub(r'收藏', '', markdown)
        markdown = re.sub(r'分享', '', markdown)
        
        # 移除评论区相关内容
        markdown = re.sub(r'\d+ 条评论', '', markdown)
        markdown = re.sub(r'发表评论', '', markdown)
        markdown = re.sub(r'相关推荐[\s\S]*$', '', markdown)
        markdown = re.sub(r'相关文章[\s\S]*$', '', markdown)
        
        # 清理SVG占位图片（透明1x1像素图片）
        markdown = re.sub(r'!\[([^\]]*)\]\(data:image/svg[^)]+\)', '', markdown)
        
        # 清理课程推广卡片（如起点课堂 ke.qidianla.com 等）
        # 格式: [![](image) 标题 描述 查看详情 > ](链接)
        markdown = re.sub(r'\[!\[.*?\]\(.*?\)\s+.*?查看详情\s*[>》].*?\]\([^)]+\)', '', markdown)
        
        # 将特定内容转为代码块
        markdown = self.format_special_blocks(markdown)
        
        # 清理开头和结尾的空白
        markdown = markdown.strip()
        
        return markdown
    
    def convert_file(self, input_path, output_dir='人人都是产品经理'):
        """转换单个文件"""
        print(f"\n处理: {input_path.name}")
        
        # 创建输出目录结构
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        file_stem = input_path.stem
        assets_dir = output_dir / "assets" / f"{file_stem}_assets"
        
        output_path = output_dir / (file_stem + '.md')
        
        with open(input_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
            soup = BeautifulSoup(html_content, 'html.parser')
        
        # 检查是否是人人都产品经理网站
        if not self.is_woshipm_site(soup):
            print(f"  [跳过] 不是人人都是产品经理网站的网页")
            return False
        
        # 提取元数据
        metadata = self.extract_metadata(soup)
        print(f"  [标题] {metadata.get('title', 'N/A')}")
        print(f"  [作者] {metadata.get('author', 'N/A')}")
        
        # 提取并清理内容
        content, selector = self.extract_content(soup)
        if not content:
            print(f"  [错误] 无法提取内容")
            return False
        
        print(f"  [选择器] {selector}")
        
        # 提取并保存图片
        print(f"  [提取] 正在处理图片...")
        image_map = self.extract_and_save_images(content, assets_dir, file_stem)
        print(f"  [完成] 共提取 {len(image_map)} 张图片到 assets/{file_stem}_assets/")
        
        # 清理内容
        content = self.clean_content(content)
        
        # 转换为 Markdown
        markdown = self.html2text.handle(str(content))
        
        # 替换图片链接
        markdown = self.replace_image_links_in_markdown(markdown, image_map)
        
        # 清理 Markdown
        markdown = self.clean_markdown(markdown)
        
        # 添加 YAML Front Matter
        front_matter = f'''---
title: {metadata.get('title', 'Untitled')}
author: {metadata.get('author', '')}
source: 人人都是产品经理
url: {metadata.get('url', '')}
date: {metadata.get('date', '')}
converted_at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
---

'''
        
        # 保存
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(front_matter + markdown)
        
        print(f"  [成功] 已保存: {output_path.name}")
        return True
    
    def batch_convert(self, input_dir='.', output_dir='人人都是产品经理'):
        """批量转换目录中的 HTML 文件"""
        input_path = Path(input_dir)
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        html_files = list(input_path.glob('*.html'))
        print(f"找到 {len(html_files)} 个 HTML 文件")
        print(f"输出目录: {output_path.absolute()}")
        
        success_count = 0
        skip_count = 0
        
        for html_file in html_files:
            try:
                result = self.convert_file(html_file, output_dir)
                if result:
                    success_count += 1
                else:
                    skip_count += 1
            except Exception as e:
                print(f"  [异常] {html_file.name}: {e}")
        
        print(f"\n转换完成: {success_count} 个成功, {skip_count} 个跳过")


if __name__ == '__main__':
    converter = WoshipmHtmlToMarkdownConverter()
    converter.batch_convert()
