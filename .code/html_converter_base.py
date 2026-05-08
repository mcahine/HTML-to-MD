#!/usr/bin/env python3
"""
HTML转换器基础模块
为各网站转换器提供通用功能
"""
import os
import re
import sys
import base64
from pathlib import Path
from datetime import datetime

def safe_print(msg):
    """安全打印函数，处理编码问题"""
    try:
        print(msg)
    except:
        pass

class HTMLConverterBase:
    """HTML转Markdown转换器基类"""

    def __init__(self, domain='', name='', content_selector='',
                 title_selector='', author_selector='', date_selector='',
                 remove_selectors=None):
        """
        初始化转换器

        Args:
            domain: 网站域名
            name: 网站中文名
            content_selector: 内容区域CSS选择器
            title_selector: 标题CSS选择器
            author_selector: 作者CSS选择器
            date_selector: 日期CSS选择器
            remove_selectors: 需要移除的元素选择器列表
        """
        self.domain = domain
        self.name = name
        self.content_selector = content_selector
        self.title_selector = title_selector
        self.author_selector = author_selector
        self.date_selector = date_selector
        self.remove_selectors = remove_selectors or []
        # Provide html2text instance for converters that use it directly
        import html2text as _h2t
        self.html2text = _h2t.HTML2Text()
        self.html2text.ignore_links = False
        self.html2text.ignore_images = False
        self.html2text.body_width = 0
        self.html2text.wrap_links = False
        self.html2text.wrap_list_items = False
        self.html2text.mark_code = True
        
    def _extract_base64_images(self, soup, html_path, output_dir):
        """Extract Base64 images to assets/{stem}_assets/ and update img src."""
        stem = Path(html_path).stem
        assets_dir = Path(output_dir) / 'assets' / f"{stem}_assets"
        assets_dir.mkdir(parents=True, exist_ok=True)

        count = 0
        for img in soup.find_all('img'):
            src = img.get('src', '')
            if not src or not src.startswith('data:image'):
                continue
            try:
                m = re.match(r'data:image/(\w+);base64,(.+)', src)
                if not m:
                    continue
                ext = m.group(1)
                data = m.group(2).strip()
                if not data:
                    continue
                raw = base64.b64decode(data)
                if len(raw) < 100:
                    continue
                ext = {'jpeg': 'jpg'}.get(ext.lower(), ext.lower())
                count += 1
                fname = f"image_{count:03d}.{ext}"
                fpath = assets_dir / fname
                with open(fpath, 'wb') as f:
                    f.write(raw)
                img['src'] = f"assets/{stem}_assets/{fname}"
            except Exception:
                continue
        return count

    def _build_yaml_front_matter(self, metadata):
        """Build consistent YAML front matter block."""
        lines = ['---']
        for key in ['title', 'author', 'date', 'source', 'url']:
            val = metadata.get(key, '')
            if val:
                lines.append(f"{key}: {val}")
        lines.append(f"converted_at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append('---')
        lines.append('')
        return '\n'.join(lines)

    def convert(self, html_path, output_dir=None):
        """
        转换单个HTML文件

        Args:
            html_path: HTML文件路径
            output_dir: 输出目录

        Returns:
            bool: 是否成功
        """
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            safe_print("错误: 需要安装 beautifulsoup4")
            return False

        html_path = Path(html_path)
        if not html_path.exists():
            safe_print(f"文件不存在: {html_path}")
            return False

        # 读取HTML
        try:
            with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
                html_content = f.read()
        except Exception as e:
            safe_print(f"读取文件失败: {e}")
            return False

        # 解析HTML
        soup = BeautifulSoup(html_content, 'lxml')

        # 提取元数据 (try both old and new signature)
        try:
            metadata = self._extract_metadata(soup, html_path)
        except TypeError:
            metadata = self._extract_metadata(html_content, html_path)
            if isinstance(metadata, tuple):
                metadata, soup = metadata

        # 兜底：如果子类没提取到 URL，从 SingleFile 注释中提取
        if not metadata.get('url'):
            url_match = re.search(r'url:\s*(https?://[^\s\]\"]+)', html_content)
            if url_match:
                metadata['url'] = url_match.group(1).rstrip('/')
        if not metadata.get('url'):
            canonical = soup.find('link', {'rel': 'canonical'})
            if canonical and canonical.get('href'):
                metadata['url'] = canonical['href']

        # 确定输出目录
        if output_dir is None:
            output_dir = html_path.parent
        else:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

        # 提取Base64图片
        img_count = self._extract_base64_images(soup, html_path, output_dir)
        if img_count > 0:
            safe_print(f"  Images: {img_count}")

        # 提取内容
        content = self._extract_content(soup)
        if not content:
            safe_print(f"无法提取内容: {html_path.name}")
            return False

        # 转换为Markdown
        md_body = self._html_to_markdown(content)

        # 清理残留的 data: 图片链接
        md_body = re.sub(r'!\[([^\]]*)\]\(data:[^)]+\)\n*', '', md_body)

        # 构建 YAML front matter + body
        yaml_block = self._build_yaml_front_matter(metadata)
        output_path = output_dir / f"{html_path.stem}.md"

        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(yaml_block + '\n' + md_body)
            safe_print(f"已转换: {output_path}")
            return True
        except Exception as e:
            safe_print(f"写入文件失败: {e}")
            return False
            
    def batch_convert(self, input_dir, output_dir=None):
        """
        批量转换目录中的HTML文件
        
        Args:
            input_dir: 输入目录
            output_dir: 输出目录
            
        Returns:
            tuple: (成功数, 总数)
        """
        input_path = Path(input_dir)
        if not input_path.exists():
            safe_print(f"目录不存在: {input_dir}")
            return 0, 0
            
        html_files = list(input_path.glob('*.html'))
        if not html_files:
            safe_print(f"未找到HTML文件: {input_dir}")
            return 0, 0
            
        safe_print(f"找到 {len(html_files)} 个HTML文件")
        
        success = 0
        for html_file in html_files:
            if self.convert(html_file, output_dir):
                success += 1
                
        safe_print(f"转换完成: {success}/{len(html_files)} 个文件成功")
        return success, len(html_files)
        
    def _extract_metadata(self, soup, html_path):
        """提取元数据（子类可覆盖，super() 可继承 URL 提取）"""
        metadata = {
            'title': '',
            'author': '',
            'date': '',
            'source': self.name,
            'url': ''
        }

        # ── URL (SingleFile comment, canonical, og:url) ──
        html_str = str(soup)
        url_match = re.search(r'url:\s*(https?://[^\s\]\"]+)', html_str)
        if not url_match:
            url_match = re.search(r'original\s+url:\s*(https?://[^\s\]]+)', html_str, re.I)
        if not url_match:
            for meta in soup.find_all('meta'):
                if meta.get('property') in ('og:url',):
                    u = meta.get('content', '').strip()
                    if u:
                        metadata['url'] = u
                        break
            if not metadata['url']:
                canonical = soup.find('link', {'rel': 'canonical'})
                if canonical and canonical.get('href'):
                    metadata['url'] = canonical['href']
        else:
            metadata['url'] = url_match.group(1).rstrip('/')

        # ── Title ──
        if self.title_selector:
            title_elem = soup.select_one(self.title_selector)
            if title_elem:
                metadata['title'] = title_elem.get_text(strip=True)

        # ── Author ──
        if self.author_selector:
            author_elem = soup.select_one(self.author_selector)
            if author_elem:
                metadata['author'] = author_elem.get_text(strip=True)

        # ── Date ──
        if self.date_selector:
            date_elem = soup.select_one(self.date_selector)
            if date_elem:
                metadata['date'] = date_elem.get_text(strip=True)

        return metadata
        
    def _extract_content(self, soup):
        """提取内容区域"""
        if not self.content_selector:
            return soup.body

        # 尝试多个选择器
        selectors = self.content_selector.split(',')
        for selector in selectors:
            selector = selector.strip()
            content = soup.select_one(selector)
            if content:
                # 清理不需要的元素
                for remove_selector in self.remove_selectors:
                    for elem in content.select(remove_selector):
                        elem.decompose()
                # Remove h1 (already in YAML title)
                for h1 in content.find_all('h1'):
                    h1.decompose()
                return content

        return None
        
    def _protect_code_blocks(self, content_elem):
        """Replace each <pre> with a NavigableString placeholder. Returns code_blocks list."""
        from bs4 import NavigableString
        code_blocks = []
        for pre in list(content_elem.find_all('pre')):
            code = pre.find('code')
            text = (code or pre).get_text().strip()
            if not text.strip():
                pre.decompose()
                continue
            lang = ''
            if code:
                for c in code.get('class', []):
                    if c.startswith('language-'):
                        lang = c.replace('language-', '')
                        break
            idx = len(code_blocks)
            code_blocks.append(f'\n```{lang}\n{text}\n```\n')
            placeholder = NavigableString(f'@@CODE_BLOCK_{idx}@@')
            try:
                pre.replace_with(placeholder)
            except ValueError:
                # pre might be detached (deepcopy) — use insert_before + extract
                pre.insert_before(placeholder)
                pre.extract()
        return code_blocks

    def _restore_code_blocks(self, markdown, code_blocks):
        """Replace code block placeholders with actual code blocks."""
        for i, block in enumerate(code_blocks):
            markdown = markdown.replace(f'@@CODE_BLOCK_{i}@@', block)
        # Ensure blank line before fence: text\n``` → text\n\n```
        import re as _re
        markdown = _re.sub(r'([^\n])\n(```)', r'\1\n\n\2', markdown)
        # Text directly followed by ``` (no newline at all) → add \n\n
        markdown = _re.sub(r'([^\n])(```)', r'\1\n\n\2', markdown)
        # Ensure blank line after fence: ```\ntext → ```\n\ntext
        markdown = _re.sub(r'(```)\n([^\n`])', r'\1\n\n\2', markdown)
        return markdown

    def _html_to_markdown(self, content):
        """将HTML内容转换为Markdown"""
        try:
            import html2text
            h = html2text.HTML2Text()
            h.ignore_links = False
            h.ignore_images = False
            h.body_width = 0
            h.wrap_links = False
            h.wrap_list_items = False
            h.mark_code = True
            return h.handle(str(content))
        except ImportError:
            return content.get_text(separator='\n\n', strip=True)

    # Alias for converters that reference the method without underscore prefix
    def html_to_markdown(self, content):
        return self._html_to_markdown(content)


if __name__ == '__main__':
    # 测试基础功能
    if len(sys.argv) > 1:
        converter = HTMLConverterBase()
        converter.batch_convert(sys.argv[1])
    else:
        print("用法: python html_converter_base.py <html文件夹>")
