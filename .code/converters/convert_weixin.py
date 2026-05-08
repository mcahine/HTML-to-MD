#!/usr/bin/env python3
"""微信公众号 (mp.weixin.qq.com) HTML 转 Markdown 转换器"""
import sys
import os
import re
import base64
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from html_converter_base import HTMLConverterBase, safe_print


class WeixinConverter(HTMLConverterBase):
    def __init__(self):
        super().__init__(
            domain='mp.weixin.qq.com',
            name='微信公众号',
            content_selector=None,
            title_selector=None,
            author_selector=None,
            date_selector=None,
            remove_selectors=[]
        )
    
    def extract_metadata(self, html_content, html_path):
        """提取微信公众号文章元数据"""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, 'lxml')
        
        metadata = {
            'title': '',
            'author': '',
            'date': '',
            'source': '微信公众号',
            'url': '',
            'converted_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # 提取标题
        title_elem = soup.select_one('#activity_name') or soup.select_one('.rich_media_title') or soup.find('h1')
        if title_elem:
            metadata['title'] = title_elem.get_text(strip=True)
        
        # 提取作者
        author_elem = soup.select_one('#js_name') or soup.select_one('.profile_nickname')
        if author_elem:
            metadata['author'] = author_elem.get_text(strip=True)
        
        # 提取日期
        date_elem = soup.select_one('#publish_time') or soup.select_one('.publish_time')
        if date_elem:
            date_text = date_elem.get_text(strip=True)
            # 匹配中文日期格式：2026年1月9日
            cn_match = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日', date_text)
            if cn_match:
                year = cn_match.group(1)
                month = cn_match.group(2).zfill(2)
                day = cn_match.group(3).zfill(2)
                metadata['date'] = f"{year}-{month}-{day}"
            else:
                metadata['date'] = date_text[:20]
        
        # 从文件名提取日期作为备选
        if not metadata['date']:
            filename = os.path.basename(html_path)
            date_match = re.search(r'(\d{4})(\d{2})(\d{2})', filename)
            if date_match:
                metadata['date'] = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
        
        # 提取URL
        og_url = soup.find('meta', property='og:url')
        if og_url:
            metadata['url'] = og_url.get('content', '')
        
        return metadata, soup
    
    def extract_content(self, soup):
        """提取文章内容"""
        content = soup.select_one('#js_content') or soup.select_one('.rich_media_content')
        return content
    
    def extract_images(self, soup, html_path, output_dir):
        """提取图片"""
        base_name = Path(html_path).stem
        assets_dir = os.path.join(output_dir, 'assets', f"{base_name}_assets")
        os.makedirs(assets_dir, exist_ok=True)
        
        img_count = 0
        for img in soup.find_all('img'):
            src = img.get('src', '')
            if not src:
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
                        
                        rel_path = f"assets/{base_name}_assets/{img_name}"
                        img['src'] = rel_path
                        safe_print(f"  Saved: {rel_path}")
                except Exception as e:
                    safe_print(f"  Error saving image: {e}")
        
        return img_count
    
    def is_title_like(self, text, prev_text='', next_text=''):
        """判断文本是否像小标题"""
        text = text.strip()
        if not text:
            return False
        
        # 长度检查：标题通常较短（4-20个字符）
        if len(text) < 4 or len(text) > 25:
            return False
        
        # 不包含标点符号（除了书名号和引号）
        if any(c in text for c in ['。', '，', '！', '？', '；', '：']):
            return False
        
        # 不以常见的段落开头词开头
        if text.startswith(('如果', '近日', '有的人', '围绕', '最近', '1月', '2月', '3月', '4月', '5月', '6月', 
                           '7月', '8月', '9月', '10月', '11月', '12月', '百炼', '阿里云', '通过', '依托', 
                           '为了满足', '另外', '据介绍', '随着', '此外')):
            return False
        
        # 标题通常包含关键词
        title_keywords = ['解决', '挑战', '方案', '架构', '原理', '介绍', '实现', '优化', '升级', 
                         '能力', '功能', '特性', '优势', '场景', '应用', '实践', '案例', '总结',
                         '核心', '关键', '重要', '主要', '基础', '底层', '上层', '中间层']
        
        return any(kw in text for kw in title_keywords)
    
    def convert_content_to_markdown(self, content_elem):
        """将内容转换为Markdown"""
        from bs4 import NavigableString
        
        md_lines = []
        # 只获取p元素（微信文章内容主要在p标签中）
        paragraphs = list(content_elem.find_all('p'))
        
        # 过滤出有内容的元素
        elements = []
        seen_texts = set()  # 用于去重
        for p in paragraphs:
            text = p.get_text(strip=True)
            img = p.find('img')
            
            # 跳过重复内容
            if text and text in seen_texts:
                continue
            if text:
                seen_texts.add(text)
            
            if text or img:
                elements.append(p)
        
        i = 0
        while i < len(elements):
            elem = elements[i]
            text = elem.get_text(strip=True)
            
            # 检查是否是图片
            img = elem.find('img')
            if img:
                src = img.get('src', '') or img.get('data-src', '')
                alt = img.get('alt', '图片')
                # 过滤掉数据URI的SVG占位图
                if src and not src.startswith('data:'):
                    md_lines.append(f"\n![{alt}]({src})\n")
                i += 1
                continue
            
            if not text:
                i += 1
                continue
            
            # 检查是否是连续的小标题（多个短段落组成一个标题）
            title_parts = [text]
            j = i + 1
            while j < len(elements):
                next_text = elements[j].get_text(strip=True)
                if not next_text:
                    j += 1
                    continue
                # 如果下一个也是短文本，可能是标题的一部分
                if len(next_text) <= 20 and not any(c in next_text for c in ['。', '，']):
                    title_parts.append(next_text)
                    j += 1
                else:
                    break
            
            combined_text = ''.join(title_parts)
            
            # 判断是否是标题
            if len(title_parts) > 1 or self.is_title_like(combined_text):
                # 合并为一个加粗标题
                md_lines.append(f"\n**{combined_text}**\n")
                i = j
            else:
                # 普通段落
                # 处理内联元素
                processed_text = self.process_inline_elements(elem)
                if processed_text:
                    md_lines.append(f"{processed_text}")
                i += 1
        
        return '\n\n'.join(md_lines)
    
    def process_inline_elements(self, elem):
        """处理内联元素"""
        from bs4 import NavigableString
        
        result = []
        for child in elem.descendants:
            if isinstance(child, NavigableString):
                result.append(str(child))
            elif child.name == 'br':
                result.append('\n')
            elif child.name in ['strong', 'b']:
                text = child.get_text()
                result.append(f'**{text}**')
            elif child.name in ['em', 'i']:
                text = child.get_text()
                result.append(f'*{text}*')
            elif child.name == 'a':
                href = child.get('href', '')
                text = child.get_text()
                result.append(f'[{text}]({href})')
        
        return ''.join(result)
    
    def convert(self, html_path, output_dir=None):
        """转换单个HTML文件"""
        if not os.path.exists(html_path):
            safe_print(f"File not found: {html_path}")
            return False
        
        if output_dir is None:
            output_dir = os.path.dirname(html_path) or '.'
        
        domain_dir = os.path.join(output_dir, 'mp_weixin_qq_com')
        os.makedirs(domain_dir, exist_ok=True)
        
        with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
            html_content = f.read()
        
        metadata, soup = self.extract_metadata(html_content, html_path)
        content_elem = self.extract_content(soup)
        
        if not content_elem:
            safe_print(f"Content not found: {html_path}")
            return False
        
        # 移除不需要的元素
        for selector in ['.rich_media_tool', '.rich_media_area_extra', '#js_pc_qr_code', 
                         '.qr_code_pc', '.reward_area', 'script', 'style']:
            for elem in content_elem.select(selector):
                elem.decompose()
        
        # 提取图片
        self.extract_images(content_elem, html_path, domain_dir)
        
        # 转换内容
        md_content = self.convert_content_to_markdown(content_elem)
        
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
        
        # 写入文件
        base_name = Path(html_path).stem
        md_path = os.path.join(domain_dir, f"{base_name}.md")
        
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(yaml_lines) + '\n' + md_content)
        
        safe_print(f"Converted: {md_path}")
        return True


if __name__ == '__main__':
    converter = WeixinConverter()
    if len(sys.argv) > 1:
        if sys.argv[1].endswith('.html'):
            converter.convert(sys.argv[1])
        else:
            import glob
            files = glob.glob(os.path.join(sys.argv[1], "*.html"))
            print(f"Found {len(files)} files")
            for f in files:
                # 检查是否是微信公众号文章
                with open(f, 'r', encoding='utf-8', errors='ignore') as file:
                    content = file.read(5000)
                    if 'mp.weixin.qq.com' in content:
                        converter.convert(f)
    else:
        converter.batch_convert(r'C:/Users/D-001/Downloads/HTML')
