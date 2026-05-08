#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
界面新闻(www.jiemian.com) HTML 转 Markdown 脚本

功能：
1. 提取文章正文、标题、作者、发布时间
2. 保存 Base64 图片到 assets 文件夹
3. 清理广告和推广内容
4. 处理文章标签和分类
5. 支持批量转换

使用方法：
    python convert_jiemian.py [文件或目录路径]
    
如果不指定路径，则处理当前目录下的所有 HTML 文件
"""

import os
import re
import sys
import base64
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup


class JiemianConverter:
    """界面新闻 HTML 转 Markdown 转换器"""
    
    # 目标域名
    DOMAIN = 'www.jiemian.com'
    
    # 输出目录
    OUTPUT_DIR = '界面新闻'
    
    def __init__(self):
        self.stats = {'success': 0, 'skipped': 0}
    
    def is_jiemian_site(self, soup):
        """检查是否是界面新闻网站"""
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
        
        # 检查 title 是否包含界面新闻
        title_tag = soup.find('title')
        if title_tag:
            title_text = title_tag.get_text()
            if '界面新闻' in title_text or '|界面' in title_text:
                return True
        
        # 检查 SingleFile 保存的 URL
        comments = soup.find_all(string=lambda text: isinstance(text, str))
        for comment in comments:
            if 'url:' in comment and 'jiemian.com' in comment:
                return True
        
        return False
    
    def extract_metadata(self, soup):
        """提取文章元数据"""
        metadata = {}
        
        # 标题 - 从 title 标签提取，去掉后缀
        title_tag = soup.find('title')
        if title_tag:
            title_text = title_tag.get_text(strip=True)
            # 去掉 |界面新闻 或 |界面 后缀
            title_text = re.sub(r'\s*[|｜]\s*界面新闻?$', '', title_text)
            metadata['title'] = title_text
        else:
            metadata['title'] = ''
        
        # 作者 - 从 .article-author 中的 .author-name
        author_tag = soup.select_one('.article-author .author-name')
        if author_tag:
            metadata['author'] = author_tag.get_text(strip=True)
        else:
            # 备选：从 meta 标签
            author_meta = soup.find('meta', attrs={'name': 'author'})
            if author_meta:
                metadata['author'] = author_meta.get('content', '')
            else:
                metadata['author'] = ''
        
        # 作者职位/描述
        author_mate = soup.select_one('.article-author .author-mate')
        if author_mate:
            metadata['author_title'] = author_mate.get_text(strip=True)
        else:
            metadata['author_title'] = ''
        
        # URL - 从 SingleFile 注释或 canonical
        url_found = False
        comments = soup.find_all(string=lambda text: isinstance(text, str))
        for comment in comments:
            if 'url:' in comment:
                match = re.search(r'url:\s*(https?://\S+)', comment)
                if match:
                    metadata['url'] = match.group(1)
                    url_found = True
                    break
        
        if not url_found:
            canonical = soup.find('link', rel='canonical')
            if canonical and canonical.get('href'):
                metadata['url'] = canonical['href']
            else:
                metadata['url'] = ''
        
        # 时间 - 从文件名或 SingleFile 注释提取
        date_found = False
        for comment in comments:
            if 'saved date:' in comment:
                # 格式: Wed Sep 24 2025 14:29:31 GMT+0800
                match = re.search(r'saved date:\s*([A-Za-z]+\s+\w+\s+\d{4})', comment)
                if match:
                    try:
                        date_str = match.group(1)
                        date_obj = datetime.strptime(date_str, '%a %b %d %Y')
                        metadata['date'] = date_obj.strftime('%Y-%m-%d')
                        date_found = True
                    except:
                        pass
                break
        
        if not date_found:
            metadata['date'] = ''
        
        # 关键词/标签
        # keywords_meta = soup.find('meta', attrs={'name': 'keywords'})
        # if keywords_meta:
        #     keywords = keywords_meta.get('content', '')
        #     if keywords:
        #         metadata['tags'] = [k.strip() for k in keywords.split(',') if k.strip()]
        
        # 摘要
        description_meta = soup.find('meta', attrs={'name': 'description'})
        if description_meta:
            metadata['description'] = description_meta.get('content', '')
        
        # 来源
        metadata['source'] = '界面新闻'
        
        return metadata
    
    def extract_content(self, soup):
        """提取文章正文内容"""
        # 界面新闻正文在 .content div 中
        content = soup.select_one('.content')
        
        if not content:
            # 备选选择器
            content = soup.select_one('.article-content')
        
        if not content:
            return None
        
        # 处理CSS背景图片：对于带有 background-image:var(--sf-img-X) 的img标签
        # 将src从SVG占位图替换为CSS变量引用
        css_img_count = 0
        for elem in content.find_all('img', style=re.compile(r'background-image:\s*var\(--sf-img-\d+\)')):
            style = elem.get('style', '')
            match = re.search(r'background-image:\s*var\((--sf-img-\d+)\)', style)
            if match:
                var_name = match.group(1)
                # 替换src为CSS变量引用
                elem['src'] = f'var({var_name})'
                # 移除style属性（不再需要）
                del elem['style']
                css_img_count += 1
        if css_img_count > 0:
            print(f"    [Info] Processed {css_img_count} CSS background images")
        
        # 清理不需要的元素
        remove_selectors = [
            '.article-author',      # 作者信息（已提取）
            '.meta-container',      # 元数据容器
            '.navbar-container',    # 导航栏
            '.comment-view',        # 评论区域
            '.comment-container',   # 评论容器
            '.side-column-container', # 侧边栏
            '.ad-view',             # 广告
            '#ad_content',          # 广告内容
            '#related-company-stocks', # 相关股票
            '.buy-column-container', # 购买专栏
            '.top3-keywords',       # 关键词推荐
            '.return-top',          # 返回顶部
            'footer',               # 页脚
            '.next-article-container', # 下一篇文章
            '.jm-comment',          # 评论
            '.jm-comments',         # 评论列表
            '.new-box',             # 推荐阅读
            '.header-fixed__title', # 固定头部标题（与h1重复）
            '.article-info',        # 文章信息（作者、时间等已在metadata中）
            '.limited-free',        # 限时免费提示
            '.article-header',      # 文章头部（标题、摘要已在YAML中）
            '.article-img',         # 文章头图（第一张图片，通常与标题重复）
            '.jm-app-view',         # APP推广区块
            'script',
            'style',
        ]
        
        for selector in remove_selectors:
            for element in content.select(selector):
                element.decompose()
        
        # 同时清理 content 之外的元素（如作者区域在 content 外）
        for selector in ['.article-author', '.meta-container', '.navbar-container', 
                         '.comment-view', '.side-column-container']:
            for element in soup.select(selector):
                element.decompose()
        
        return content
    
    def extract_css_variable_images(self, soup, assets_dir, file_stem, start_idx=1):
        """提取CSS变量中的Base64图片"""
        image_map = {}
        idx = start_idx
        
        # 查找所有style标签
        style_tags = soup.find_all('style')
        for style_tag in style_tags:
            style_content = str(style_tag.string) if style_tag.string else ''
            
            # 查找CSS变量定义: --sf-img-X: /* original URL: ... */ url("data:image/...")
            pattern = r'--(sf-img-\d+):\s*/\*\s*original URL:\s*([^\s*]+)\s*\*/\s*url\("(data:image/[^"]+)"\)'
            matches = re.finditer(pattern, style_content)
            
            for match in matches:
                var_name = match.group(1)
                original_url = match.group(2)
                data_url = match.group(3)
                
                if data_url.startswith('data:image'):
                    try:
                        data_match = re.match(r'data:image/(\w+);base64,(.+)', data_url)
                        if data_match:
                            ext = data_match.group(1)
                            base64_data = data_match.group(2).strip()
                            
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
                                # 使用CSS变量名作为映射键
                                image_map[f'var(--{var_name})'] = relative_path
                                print(f"    [Image] Saved CSS var {var_name}: {filename} ({len(image_data)} bytes)")
                                idx += 1
                            except Exception as e:
                                print(f"    [Warn] Save failed {filename}: {e}")
                    except Exception as e:
                        print(f"    [Warn] Base64 parse failed for {var_name}: {e}")
        
        return image_map, idx
    
    def extract_and_save_images(self, soup, assets_dir, file_stem):
        """提取 Base64 图片并保存到 assets 文件夹，同时更新HTML中的src属性"""
        assets_dir.mkdir(parents=True, exist_ok=True)
        saved_images = []  # 列表保存 (原src, 新路径)
        
        # 首先提取普通img标签的图片
        img_tags = soup.find_all('img')
        idx = 1
        
        for img in img_tags:
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
                            saved_images.append((src, relative_path))
                            print(f"    [Image] Saved: {filename} ({len(image_data)} bytes)")
                            idx += 1
                        except Exception as e:
                            print(f"    [Warn] Save failed {filename}: {e}")
                            continue
                except Exception as e:
                    print(f"    [Warn] Base64 parse failed: {e}")
                    continue
        
        # 然后提取CSS变量中的图片
        css_image_map, idx = self.extract_css_variable_images(soup, assets_dir, file_stem, idx)
        
        # 更新HTML中的src属性（将Base64替换为本地路径）
        for old_src, new_path in saved_images:
            for img in soup.find_all('img', src=old_src):
                img['src'] = new_path
        
        # 更新CSS变量引用（将var(--sf-img-X)替换为本地路径）
        for var_name, new_path in css_image_map.items():
            # var_name格式为 'var(--sf-img-45)'
            for img in soup.find_all('img', src=var_name):
                img['src'] = new_path
        
        # 返回所有保存的图片信息
        return saved_images + list(css_image_map.items())
    
    def replace_image_links_in_markdown(self, markdown, image_map):
        """在 Markdown 中替换图片链接"""
        # image_map可以是字典或(原src, 新路径)元组的列表
        items = image_map.items() if isinstance(image_map, dict) else image_map
        
        for old_src, new_path in items:
            old_src_escaped = re.escape(old_src)
            # 替换标准Markdown图片格式
            pattern = r'!\[([^\]]*)\]\(' + old_src_escaped + r'\)'
            replacement = f'![\\1]({new_path})'
            markdown = re.sub(pattern, replacement, markdown)
            
            # 替换CSS变量引用（如 var(--sf-img-45)）
            if 'var(--' in old_src:
                # 直接替换变量名
                pattern = re.escape(old_src)
                markdown = re.sub(pattern, new_path, markdown)
        
        return markdown
    
    def html_to_markdown(self, html_content):
        """将 HTML 转换为 Markdown（简化版）"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 处理标题 h3
        for h3 in soup.find_all('h3'):
            text = h3.get_text(strip=True)
            h3.replace_with(f'\n\n### {text}\n\n')
        
        # 先处理图片（防止被空的p标签删除）
        for img in soup.find_all('img'):
            src = img.get('src', '')
            alt = img.get('alt', '')
            img.replace_with(f'\n\n![{alt}]({src})\n\n')
        
        # 处理段落
        for p in soup.find_all('p'):
            # 跳过空段落
            text = p.get_text(strip=True)
            if text:
                p.insert_before('\n\n')
                p.insert_after('\n\n')
            else:
                p.decompose()
        
        # 处理 strong/b 标签
        for strong in soup.find_all(['strong', 'b']):
            text = strong.get_text(strip=True)
            strong.replace_with(f'**{text}**')
        
        # 处理 em/i 标签
        for em in soup.find_all(['em', 'i']):
            text = em.get_text(strip=True)
            em.replace_with(f'*{text}*')
        
        # 处理 a 标签
        for a in soup.find_all('a'):
            href = a.get('href', '')
            text = a.get_text(strip=True)
            if href and text:
                a.replace_with(f'[{text}]({href})')
        
        # 处理 span（主要是包裹股票代码的）
        for span in soup.find_all('span'):
            text = span.get_text(strip=True)
            span.replace_with(text)
        
        # 获取文本
        text = soup.get_text(separator='', strip=False)
        
        # 清理多余空行
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        return text.strip()
    
    def clean_markdown(self, markdown):
        """清理 Markdown 内容"""
        # 首先统一换行符为 \n (处理 Windows \r\n)
        has_cr = '\r' in markdown
        markdown = markdown.replace('\r\n', '\n')
        markdown = markdown.replace('\r', '\n')
        # print(f"  [DEBUG] Has CR: {has_cr}")
        
        # 移除过多的空行
        markdown = re.sub(r'\n{3,}', '\n\n', markdown)
        
        # 清理可能残留的广告/推广内容
        # 界面新闻底部的版权声明
        markdown = re.sub(r'未经正式授权严禁转载本文，侵权必究。', '', markdown)
        
        # 清理作者信息行中的浏览量、来源等（保留作者和日期）
        # 格式: [作者](链接)*·*日期 浏览 XXw来源：界面新闻
        markdown = re.sub(r'浏览\s*\d+\.?\d*w?', '', markdown)
        
        # 清理HTML标签残留
        markdown = re.sub(r'<[^>]+>', '', markdown)
        
        # 清理特定的界面新闻广告标记
        markdown = re.sub(r'\[下载界面新闻.*?\]\(.*?\)', '', markdown)
        
        # 清理SVG占位图片和空图片标记
        markdown = re.sub(r'!\[([^\]]*)\]\(data:image/svg[^)]*\)', '', markdown)
        markdown = re.sub(r'!\[\]\(data:image/svg[^)]*\)', '', markdown)
        markdown = re.sub(r'!\[\]\(\)', '', markdown)
        # 清理data:,开头的空图片（SVG占位图的一种形式）
        markdown = re.sub(r'!\[([^\]]*)\]\(data:,\)', '', markdown)
        
        # 清理孤立的 ! (可能是图片链接残留)
        # 匹配被空行包围的孤立 !
        markdown = re.sub(r'\n+\s*!\s*\n+', '\n\n', markdown)
        # 匹配行首行尾只有 ! 的情况
        markdown = re.sub(r'^[\s!]+$', '', markdown, flags=re.MULTILINE)
        # 匹配只有 ! 的行
        markdown = re.sub(r'^!$', '', markdown, flags=re.MULTILINE)
        
        # 强制清理任何孤立的 ! (包括带换行符的)
        lines = markdown.split('\n')
        lines = [line for line in lines if line.strip() != '!']
        markdown = '\n'.join(lines)
        
        # 清理图片周围的多余空行
        # 将图片前后的3个以上空行替换为2个
        markdown = re.sub(r'\n\n\n+', '\n\n', markdown)
        
        # 清理界面新闻的导航栏残留
        # 注意：这个正则会匹配 ![](assets/...) 后面跟着链接到界面新闻的情况
        # 但这也可能误删文章中的图片，所以只删除那些明确是导航栏的（后面跟着特定文本的）
        markdown = re.sub(r'\[!\[\]\(assets/[^)]+\)\]\(https://www\.jiemian\.com/\)正在阅读:', '', markdown)
        markdown = re.sub(r'正在阅读:', '', markdown)
        
        # 清理评论数标记
        markdown = re.sub(r'\[\d+\]\(#pll\)', '', markdown)
        markdown = re.sub(r'\[\d+\]\(javascript:void\(0\)\)', '', markdown)
        
        # 清理APP推广
        markdown = re.sub(r'扫一扫下载界面新闻APP', '', markdown)
        markdown = re.sub(r'\[其他途径关注界面.*?\]\(.*?\)', '', markdown)
        
        # 清理空链接（如：[](https://www.jiemian.com/) 导航栏链接）
        # 使用负向先行断言确保前面不是 !（避免误删图片）
        markdown = re.sub(r'(?<!!)\[\]\([^)]+\)', '', markdown)
        
        # 清理底部推荐文章（界面新闻底部的相关推荐）
        markdown = re.sub(r'\[查看其余\d+篇文章.*?\]\(.*?\)', '', markdown)
        
        # 清理可能残留的界面新闻底部链接和孤立的 !
        lines = markdown.split('\n')
        cleaned_lines = []
        for line in lines:
            # 跳过连续的文章推荐链接行（以[开头以)结尾的长行）
            if len(line) > 100 and line.startswith('[') and line.count('](') > 1:
                continue
            # 跳过孤立的 !
            if line.strip() == '!':
                continue
            cleaned_lines.append(line)
        markdown = '\n'.join(cleaned_lines)
        
        # 最终清理：将3个及以上连续空行替换为2个
        markdown = re.sub(r'\n\n\n+', '\n\n', markdown)
        
        return markdown.strip()
    
    def convert_file(self, input_path):
        """转换单个文件"""
        print(f"\n[Process] {input_path.name}")
        
        # 创建输出目录结构
        output_dir = Path(self.OUTPUT_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        file_stem = input_path.stem
        assets_dir = output_dir / "assets" / f"{file_stem}_assets"
        
        output_path = output_dir / (file_stem + '.md')
        
        with open(input_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
            soup = BeautifulSoup(html_content, 'html.parser')
        
        # 检查是否是界面新闻
        if not self.is_jiemian_site(soup):
            print(f"  [Skip] Not jiemian.com")
            self.stats['skipped'] += 1
            return False
        
        # 提取元数据
        metadata = self.extract_metadata(soup)
        print(f"  [Title] {metadata.get('title', 'N/A')}")
        print(f"  [Author] {metadata.get('author', 'N/A')}")
        print(f"  [Date] {metadata.get('date', 'N/A')}")
        
        # 提取内容（先在soup中处理CSS背景图片标记）
        content = self.extract_content(soup)
        if not content:
            print(f"  [Error] Cannot extract content")
            return False
        
        # 提取并保存图片（在整个soup中，并更新src属性）
        image_map = self.extract_and_save_images(soup, assets_dir, file_stem)
        print(f"  [Extract] {len(image_map)} images to assets/{file_stem}_assets/")
        
        # 转换为 Markdown
        content_str = str(content)
        # Debug: 检查content中是否有img标签
        img_count = content_str.count('<img')

        
        markdown_content = self.html_to_markdown(content_str)
        
        # Debug: 检查markdown中是否有图片
        md_img_count = markdown_content.count('![](')
        print(f"    [Info] Markdown has {md_img_count} images after html_to_markdown")
        # 替换图片链接（以防万一有遗漏）
        markdown_content = self.replace_image_links_in_markdown(markdown_content, image_map)
        

        
        # Debug: 检查 image_map
        # print(f"  [DEBUG] Image map: {image_map}")
        
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
        
        print(f"  [Success] Saved: {output_path}")
        self.stats['success'] += 1
        return True
    
    def convert_directory(self, directory='.'):
        """批量转换目录下的 HTML 文件"""
        directory = Path(directory)
        html_files = list(directory.glob('*.html')) + list(directory.glob('*.htm'))
        
        print(f"Found {len(html_files)} HTML files")
        
        for html_file in html_files:
            try:
                self.convert_file(html_file)
            except Exception as e:
                print(f"  [Error] Processing failed: {e}")
                import traceback
                traceback.print_exc()
                self.stats['skipped'] += 1
        
        print(f"\nDone: {self.stats['success']} success, {self.stats['skipped']} skipped")


def main():
    # 处理 Windows 控制台编码问题
    import sys
    import io
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    
    converter = JiemianConverter()
    
    if len(sys.argv) > 1:
        input_path = Path(sys.argv[1])
        if input_path.is_file():
            converter.convert_file(input_path)
        elif input_path.is_dir():
            converter.convert_directory(input_path)
        else:
            print(f"Error: Path not found - {input_path}")
    else:
        # 处理当前目录
        converter.convert_directory('.')


if __name__ == '__main__':
    main()
