#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
观察者网(www.guancha.cn) HTML 转 Markdown 脚本

功能：
1. 提取文章正文、标题、作者、发布时间
2. 保存 Base64 图片到 assets 文件夹
3. 清理广告和推广内容
4. 处理图片说明文字
5. 支持批量转换

使用方法：
    python convert_guancha.py [文件或目录路径]
    
如果不指定路径，则处理当前目录下的所有 HTML 文件
"""

import os
import re
import sys
import base64
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup


class GuanchaConverter:
    """观察者网 HTML 转 Markdown 转换器"""
    
    # 目标域名
    DOMAIN = 'www.guancha.cn'
    
    # 输出目录
    OUTPUT_DIR = '观察者网'
    
    def __init__(self):
        self.stats = {'success': 0, 'skipped': 0}
    
    def is_guancha_site(self, soup):
        """检查是否是观察者网网站"""
        # 检查 canonical link
        canonical = soup.find('link', rel='canonical')
        if canonical and canonical.get('href'):
            if self.DOMAIN in canonical['href']:
                return True
        
        # 检查 og:url
        og_url = soup.find('meta', property='og:url')
        if og_url and og_url.get('content'):
            if self.DOMAIN in og_url['content']:
                return True
        
        # 检查 source 标记
        source_span = soup.find('span', string=re.compile(r'来源.*观察者网'))
        if source_span:
            return True
            
        return False
    
    def extract_metadata(self, soup):
        """提取文章元数据"""
        metadata = {}
        
        # 标题 - 从 h3 标签提取
        title_tag = soup.find('h3')
        if title_tag:
            metadata['title'] = title_tag.get_text(strip=True)
        else:
            # 备选：从 title 标签
            title_tag = soup.find('title')
            if title_tag:
                metadata['title'] = title_tag.get_text(strip=True)
        
        # 作者 - 从 .editor-intro 中的 a 标签
        author_tag = soup.select_one('.editor-intro a')
        if author_tag:
            metadata['author'] = author_tag.get_text(strip=True)
        else:
            metadata['author'] = ''
        
        # 发布时间 - 从 .time span
        time_span = soup.select_one('.time span')
        if time_span:
            time_text = time_span.get_text(strip=True)
            # 匹配时间格式：2024-12-24 08:45:17
            match = re.search(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})', time_text)
            if match:
                metadata['date'] = match.group(1)
            else:
                metadata['date'] = time_text
        else:
            metadata['date'] = ''
        
        # URL - 从 canonical 或 saved date 注释
        canonical = soup.find('link', rel='canonical')
        if canonical and canonical.get('href'):
            metadata['url'] = canonical['href']
        else:
            # 从 SingleFile 注释提取
            comments = soup.find_all(string=lambda text: isinstance(text, str) and 'url:' in text)
            for comment in comments:
                match = re.search(r'url:\s*(\S+)', comment)
                if match:
                    metadata['url'] = match.group(1)
                    break
            else:
                metadata['url'] = ''
        
        # 来源
        metadata['source'] = '观察者网'
        
        return metadata
    
    def extract_content(self, soup):
        """提取文章正文内容"""
        # 主要正文区域
        content = soup.select_one('.content.all-txt')
        
        if not content:
            # 备选选择器
            content = soup.select_one('.content')
        
        if not content:
            return None
        
        # 清理不需要的元素
        remove_selectors = [
            '.share',           # 分享按钮
            '.other-box',       # 收藏/评论按钮
            '.time',            # 时间信息（已提取）
            '.editor',          # 作者信息（已提取）
            'script',
            'style',
        ]
        
        for selector in remove_selectors:
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
    
    def html_to_markdown(self, html_content):
        """将 HTML 转换为 Markdown（简化版）"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 处理段落
        for p in soup.find_all('p'):
            # 处理居中对齐
            style = p.get('style', '')
            if 'text-align:center' in style or 'align=center' in str(p):
                p.insert_before('\n\n')
                p.insert_after('\n\n')
            else:
                p.insert_before('\n\n')
                p.insert_after('\n\n')
        
        # 处理图片
        for img in soup.find_all('img'):
            src = img.get('src', '')
            alt = img.get('alt', '')
            img.replace_with(f'\n\n![{alt}]({src})\n\n')
        
        # 处理图片说明
        for desc in soup.find_all('p', class_='content-pic-desc'):
            text = desc.get_text(strip=True)
            desc.replace_with(f'\n\n*{text}*\n\n')
        
        # 处理 strong 标签
        for strong in soup.find_all(['strong', 'b']):
            text = strong.get_text(strip=True)
            strong.replace_with(f'**{text}**')
        
        # 处理分页标记
        for linebreak in soup.find_all('linebreak'):
            linebreak.replace_with('\n\n---\n\n')
        
        # 获取文本
        text = soup.get_text(separator='', strip=False)
        
        # 清理多余空行
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        return text.strip()
    
    def clean_markdown(self, markdown):
        """清理 Markdown 内容"""
        # 移除过多的空行
        markdown = re.sub(r'\n{3,}', '\n\n', markdown)
        
        # 清理可能残留的广告/推广链接
        # 格式: [![](image) 标题 描述 查看详情 > ](链接)
        markdown = re.sub(r'\[!\[.*?\]\(.*?\)\s+.*?查看详情\s*[>》].*?\]\([^)]+\)', '', markdown)
        
        # 清理HTML标签残留
        markdown = re.sub(r'<[^>]+>', '', markdown)
        
        return markdown.strip()
    
    def convert_file(self, input_path):
        """转换单个文件"""
        print(f"\n处理: {input_path.name}")
        
        # 创建输出目录结构
        output_dir = Path(self.OUTPUT_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        file_stem = input_path.stem
        assets_dir = output_dir / "assets" / f"{file_stem}_assets"
        
        output_path = output_dir / (file_stem + '.md')
        
        with open(input_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
            soup = BeautifulSoup(html_content, 'html.parser')
        
        # 检查是否是观察者网
        if not self.is_guancha_site(soup):
            print(f"  [跳过] 不是观察者网的网页")
            self.stats['skipped'] += 1
            return False
        
        # 提取元数据
        metadata = self.extract_metadata(soup)
        print(f"  [标题] {metadata.get('title', 'N/A')}")
        print(f"  [作者] {metadata.get('author', 'N/A')}")
        print(f"  [时间] {metadata.get('date', 'N/A')}")
        
        # 提取并保存图片
        image_map = self.extract_and_save_images(soup, assets_dir, file_stem)
        print(f"  [提取] 共提取 {len(image_map)} 张图片到 assets/{file_stem}_assets/")
        
        # 提取内容
        content = self.extract_content(soup)
        if not content:
            print(f"  [错误] 无法提取内容")
            return False
        
        # 转换为 Markdown
        markdown_content = self.html_to_markdown(str(content))
        
        # 替换图片链接
        markdown_content = self.replace_image_links_in_markdown(markdown_content, image_map)
        
        # 清理 Markdown
        markdown_content = self.clean_markdown(markdown_content)
        
        # 生成 YAML Front Matter
        yaml_content = "---\n"
        for key, value in metadata.items():
            if value:
                yaml_content += f"{key}: {value}\n"
        yaml_content += f"converted_at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        yaml_content += "---\n\n"
        
        # 组合最终内容
        final_content = yaml_content + markdown_content
        
        # 保存文件
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(final_content)
        
        print(f"  [成功] 已保存: {output_path}")
        self.stats['success'] += 1
        return True
    
    def convert_directory(self, directory='.'):
        """批量转换目录下的 HTML 文件"""
        directory = Path(directory)
        html_files = list(directory.glob('*.html')) + list(directory.glob('*.htm'))
        
        print(f"找到 {len(html_files)} 个 HTML 文件")
        
        for html_file in html_files:
            try:
                self.convert_file(html_file)
            except Exception as e:
                print(f"  [错误] 处理文件时出错: {e}")
                self.stats['skipped'] += 1
        
        print(f"\n转换完成: {self.stats['success']} 个成功, {self.stats['skipped']} 个跳过")


def main():
    converter = GuanchaConverter()
    
    if len(sys.argv) > 1:
        input_path = Path(sys.argv[1])
        if input_path.is_file():
            converter.convert_file(input_path)
        elif input_path.is_dir():
            converter.convert_directory(input_path)
        else:
            print(f"错误: 路径不存在 - {input_path}")
    else:
        # 处理当前目录
        converter.convert_directory('.')


if __name__ == '__main__':
    main()
