#!/usr/bin/env python3
"""财联社 (cls.cn) HTML 转 Markdown 转换器"""
import sys
import os
import re
import base64
from pathlib import Path
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from html_converter_base import HTMLConverterBase, safe_print


class CaiLianSheConverter(HTMLConverterBase):
    def __init__(self):
        super().__init__(
            domain='cls.cn',
            name='财联社',
            content_selector='.detail-content, .w-894, .f-l.w-894',
            title_selector='.detail-title, h1',
            author_selector=None,
            date_selector=None,
            remove_selectors=['script', 'style', 'nav', '.detail-header', '.detail-footer']
        )
    
    def read_html(self, html_path):
        """读取HTML文件，自动检测编码"""
        encodings = ['utf-8', 'utf-8-sig', 'gbk', 'gb2312', 'latin1']
        
        for encoding in encodings:
            try:
                with open(html_path, 'r', encoding=encoding) as f:
                    content = f.read()
                if '����' not in content[:5000]:
                    return content
            except:
                continue
        
        with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    
    def extract_url_from_html(self, html_content):
        """从 HTML 注释中提取原始 URL"""
        match = re.search(r'url:\s*(https?://[^\s\n]+)', html_content)
        if match:
            return match.group(1).strip()
        return ''
    
    def extract_metadata(self, html_content, html_path):
        """提取财联社文章的元数据"""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, 'lxml')
        
        metadata = {
            'title': '',
            'author': '财联社',
            'date': '',
            'source': '财联社',
            'url': self.extract_url_from_html(html_content),
            'converted_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # 提取标题 - 财联社标题在 detail-title 类中
        title_elem = soup.find(class_='detail-title')
        if not title_elem:
            title_elem = soup.find('h1')
        if title_elem:
            metadata['title'] = title_elem.get_text(strip=True)
        
        # 从文件名提取日期作为备选
        filename = os.path.basename(html_path)
        date_match = re.search(r'(\d{4})(\d{2})(\d{2})', filename)
        if date_match:
            metadata['date'] = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
        
        # 尝试从内容中提取发布时间
        time_elem = soup.find('time')
        if time_elem:
            time_text = time_elem.get_text(strip=True)
            # 匹配 2025-12-26 06:00 格式
            time_match = re.search(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})', time_text)
            if time_match:
                metadata['date'] = time_match.group(1)
        else:
            # 在页面中查找时间
            for elem in soup.find_all(['span', 'div']):
                text = elem.get_text(strip=True)
                time_match = re.search(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})', text)
                if time_match:
                    metadata['date'] = time_match.group(1)
                    break
        
        return metadata, soup
    
    def is_valid_image_src(self, src):
        """检查图片 src 是否有效"""
        if not src:
            return False
        if src in ['data:,', 'data:image/png,', 'data:image/jpeg,', '#']:
            return False
        if src.strip() == '':
            return False
        return True
    
    def element_to_markdown(self, elem, level=0):
        """将单个元素转换为Markdown，保留圆圈数字引用"""
        from bs4 import NavigableString
        
        if isinstance(elem, NavigableString):
            text = str(elem)
            return text if text.strip() else ''
        
        if elem.name is None:
            return ''
        
        # 跳过这些元素
        if elem.name in ['script', 'style', 'nav', 'iframe']:
            return ''
        
        # 处理标题
        if elem.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            text = elem.get_text(strip=True)
            if text:
                level_marker = '#' * int(elem.name[1])
                return f"{level_marker} {text}\n\n"
            return ''
        
        # 处理图片
        if elem.name == 'img':
            src = elem.get('src', '')
            alt = elem.get('alt', '')
            if self.is_valid_image_src(src):
                return f"![{alt}]({src})\n\n"
            return ''
        
        # 处理链接
        if elem.name == 'a':
            href = elem.get('href', '')
            text = elem.get_text(strip=True)
            if href and text:
                return f"[{text}]({href})"
            return text
        
        # 处理代码块 - 财联社的 detail-brief 是文章摘要，不是代码
        if elem.name == 'pre':
            classes = elem.get('class', [])
            # 如果是财联社的 detail-brief，作为引用块处理
            if 'detail-brief' in classes:
                text = elem.get_text().strip()
                if text:
                    # 保留圆圈数字引用，格式化为引用块
                    lines = text.split('\n')
                    quoted = '\n'.join([f"> {line}" for line in lines if line.strip()])
                    return f"{quoted}\n\n"
                return ''
            
            # 其他 pre 作为代码块处理
            code_elem = elem.find('code')
            if code_elem:
                code = code_elem.get_text()
                lang = ''
                if code_elem.get('class'):
                    for cls in code_elem.get('class'):
                        if 'language-' in cls:
                            lang = cls.replace('language-', '')
                            break
                if code.strip():
                    return f"```{lang}\n{code.strip()}\n```\n\n"
            text = elem.get_text()
            if text.strip():
                return f"```\n{text.strip()}\n```\n\n"
            return ''
        
        # 处理内联代码
        if elem.name == 'code':
            code = elem.get_text(strip=True)
            return f"`{code}`" if code else ''
        
        # 处理强调
        if elem.name in ['strong', 'b']:
            text = elem.get_text(strip=True)
            return f"**{text}**" if text else ''
        
        if elem.name in ['em', 'i']:
            text = elem.get_text(strip=True)
            return f"*{text}*" if text else ''
        
        # 处理段落 - 财联社文章中的圆圈数字①②③等需要保留
        if elem.name == 'p':
            parts = []
            for child in elem.children:
                part = self.element_to_markdown(child, level + 1)
                if part:
                    parts.append(part)
            text = ''.join(parts).strip()
            # 保留圆圈数字，清理多余空白
            text = re.sub(r'[ \t]+', ' ', text)
            return f"{text}\n\n" if text else ''
        
        # 处理列表项
        if elem.name == 'li':
            parts = []
            for child in elem.children:
                part = self.element_to_markdown(child, level + 1)
                if part:
                    parts.append(part)
            return ''.join(parts).strip()
        
        # 处理无序列表
        if elem.name == 'ul':
            items = []
            for li in elem.find_all('li', recursive=False):
                text = self.element_to_markdown(li, level + 1)
                if text:
                    items.append(f"- {text}")
            return '\n'.join(items) + '\n\n' if items else ''
        
        # 处理有序列表
        if elem.name == 'ol':
            items = []
            for i, li in enumerate(elem.find_all('li', recursive=False), 1):
                text = self.element_to_markdown(li, level + 1)
                if text:
                    items.append(f"{i}. {text}")
            return '\n'.join(items) + '\n\n' if items else ''
        
        # 处理引用块
        if elem.name == 'blockquote':
            parts = []
            for child in elem.children:
                part = self.element_to_markdown(child, level + 1)
                if part:
                    parts.append(part)
            text = ''.join(parts).strip()
            if text:
                lines = text.split('\n')
                quoted = '\n'.join([f"> {line}" for line in lines if line.strip()])
                return f"{quoted}\n\n"
            return ''
        
        # 处理水平线
        if elem.name == 'hr':
            return '---\n\n'
        
        # 处理换行
        if elem.name == 'br':
            return '\n'
        
        # 处理 div/span/section（递归处理子元素）
        if elem.name in ['div', 'span', 'section']:
            # 检查是否是文章标题（财联社标题在 detail-title 类中）
            classes = elem.get('class', [])
            is_title = 'detail-title' in classes
            
            parts = []
            for child in elem.children:
                part = self.element_to_markdown(child, level + 1)
                if part:
                    parts.append(part)
            result = ''.join(parts)
            
            # 如果是标题，添加换行
            if is_title and result.strip():
                return result.strip() + '\n\n'
            
            return result
        
        # 默认递归处理子元素
        parts = []
        for child in elem.children:
            part = self.element_to_markdown(child, level + 1)
            if part:
                parts.append(part)
        return ''.join(parts)
    
    def extract_images(self, soup, html_path, output_dir):
        """提取图片"""
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
                    match = re.match(r'data:image/(\w+);base64,(.+)', src)
                    if match:
                        ext = match.group(1)
                        data = match.group(2)
                        if not data or data.strip() == '':
                            continue
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
                        print(f"  Saved: {rel_path}")
                except Exception as e:
                    print(f"  Error saving image: {e}")
        
        return img_count
    
    def convert(self, html_path, output_dir=None):
        """转换单个HTML文件"""
        if not os.path.exists(html_path):
            print(f"File not found: {html_path}")
            return False
        
        if output_dir is None:
            output_dir = os.path.dirname(html_path) or '.'
        
        # 固定输出目录为"财联社"
        domain_dir = os.path.join(output_dir, '财联社')
        os.makedirs(domain_dir, exist_ok=True)
        
        # 读取HTML
        html_content = self.read_html(html_path)
        
        # 提取元数据
        metadata, soup = self.extract_metadata(html_content, html_path)
        
        # 找到主要内容区域 - 先找内容再提取图片，避免修改 soup 影响内容
        # 财联社正文通常在 w-894 或 detail-content 中
        content_elem = None
        
        # 尝试多种选择器
        # .w-894 包含正文和 pre.detail-brief（摘要引用块，含 ①②③）
        # .detail-content 只包含正文
        selectors = [
            '.w-894',           # 优先使用 w-894，它包含摘要引用块
            '.f-l.w-894',
            '.detail-content',
            'article',
        ]
        
        for selector in selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                break
        
        if not content_elem:
            print(f"Content not found: {html_path}")
            return False
        
        # 先移除不需要的元素
        # 注意：.m-b-40 也是 .detail-content 的类，不能移除
        for selector in ['script', 'style', 'nav', '.detail-header', '.detail-footer', 
                         '.share-box', '.related-news', '.comment-box',
                         # 评论区域
                         '.new-comment', '.c-b.p-t-20', '.f-r.p-r.w-824',
                         # 互动按钮（收藏、评论等）
                         '.m-b-10:not(.detail-content *)',  # 只移除非正文内的 m-b-10
                         '.detail-option-box']:
            for elem in content_elem.select(selector):
                elem.decompose()
        
        # 特别处理：移除 .detail-content 内的来源信息 div（通常是第一个子元素）
        detail_content = content_elem.select_one('.detail-content')
        if detail_content:
            for child in list(detail_content.children)[:2]:  # 检查前两个子元素
                if child.name == 'div' and child.get('class'):
                    cls = child.get('class')
                    # 如果是来源信息行（m-b-20 类且包含时间/作者）
                    if 'm-b-20' in cls or 'f-s-14' in cls:
                        child.decompose()
        
        # 移除标题（因为已经在 YAML front matter 中了）
        for title_elem in content_elem.select('.detail-title'):
            title_elem.decompose()
        
        # 移除来源信息（包含 原创、时间、作者 的行）
        # 但要注意不要误删正文内容
        for elem in content_elem.find_all(['div', 'p', 'span', 'a', 'b', 'font']):
            text = elem.get_text(strip=True)
            # 只移除明显是来源信息的短文本
            # 检查是否是底部来源栏（通常是独立的一行，包含作者和时间）
            if len(text) < 300:
                # 检查是否是来源信息模式：原创 + 财联社作者 + 日期 + 星期
                if ('原创' in text and
                    any(day in text for day in ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日'])):
                    elem.decompose()
                    continue
                # 检查是否是互动按钮（收藏、阅、评论、我要评论）
                if (('收藏' in text and '阅' in text) or 
                    ('我要评论' in text) or
                    ('发表评论' in text) or
                    (text.startswith('收藏') and '阅' in text)):
                    elem.decompose()
                    continue
                # 检查是否是评论区域提示
                if ('欢迎您发表' in text and '评论' in text) or \
                   ('发布广告' in text and '删除' in text) or \
                   ('账号将禁止评论' in text) or \
                   ('反馈意见' in text and len(text) < 50):
                    elem.decompose()
                    continue
                # 检查是否是"头条新闻"标签
                if text == '头条新闻' or ('头条新闻' in text and len(text) < 20):
                    elem.decompose()
                    continue
        
        # 先提取图片（修改 soup 中的 img src）
        self.extract_images(soup, html_path, domain_dir)
        
        # 转换内容（在提取图片之后，这样 img src 已经是本地路径）
        md_content = self.element_to_markdown(content_elem)
        
        # 清理多余空行
        md_content = re.sub(r'\n{3,}', '\n\n', md_content.strip())
        
        # 修复引用格式：确保 > 前面有换行
        # 处理 "财联社> " 这种情况
        md_content = re.sub(r'(\S)(>\s+①)', r'\1\n\n\2', md_content)
        md_content = re.sub(r'(\S)(>\s+②)', r'\1\n\n\2', md_content)
        md_content = re.sub(r'(\S)(>\s+③)', r'\1\n\n\2', md_content)
        md_content = re.sub(r'(\S)(>\s+④)', r'\1\n\n\2', md_content)
        md_content = re.sub(r'(\S)(>\s+⑤)', r'\1\n\n\2', md_content)

        # 清理来源/日期杂信息行
        # 模式: 2025-12-22 22:19 星期一 或 2025-12-22 22:19 星期一财联社
        md_content = re.sub(
            r'^\s*\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}\s+星期[一二三四五六日].*$',
            '', md_content, flags=re.MULTILINE)
        # 模式: [话题](链接)2026-01-08...星期X来源>
        md_content = re.sub(
            r'^\s*\[[^\]]+\]\([^)]+\)\s*\d{4}-\d{2}-\d{2}.*$',
            '', md_content, flags=re.MULTILINE)
        # 模式: 单独的 > 结尾的元数据行
        md_content = re.sub(
            r'^\s*.*星期[一二三四五六日].*>\s*$',
            '', md_content, flags=re.MULTILINE)

        # 构建 YAML Front Matter
        yaml_lines = ["---"]
        yaml_lines.append(f"title: {metadata['title']}")
        yaml_lines.append(f"author: {metadata['author']}")
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
        
        print(f"Converted: {md_path}")
        return True


if __name__ == '__main__':
    converter = CaiLianSheConverter()
    if len(sys.argv) > 1:
        if sys.argv[1].endswith('.html'):
            converter.convert(sys.argv[1])
        else:
            # 批量转换
            import glob
            files = glob.glob(os.path.join(sys.argv[1], "*财联社*.html"))
            print(f"Found {len(files)} files")
            for f in files:
                converter.convert(f)
    else:
        # 默认：转换当前目录
        import glob
        files = glob.glob("*财联社*.html")
        print(f"Found {len(files)} files")
        for f in files:
            converter.convert(f)
