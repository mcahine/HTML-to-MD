#!/usr/bin/env python3
"""掘金 (juejin.cn) HTML 转 Markdown 转换器 — 优化版"""
import sys, os, re
from pathlib import Path
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from html_converter_base import HTMLConverterBase, safe_print


class JuejinConverter(HTMLConverterBase):
    def __init__(self):
        super().__init__(
            domain='juejin.cn',
            name='掘金',
            content_selector='.markdown-body, .article-content, .content, article',
            title_selector='h1, .article-title',
            author_selector='.username, .author-name, .author-info-block .name',
            date_selector='.time, .publish-time, time',
            remove_selectors=[
                '.sidebar', '.article-suspended-panel', '.author-info',
                '.comment-box', '.recommended-area', '.tag-list',
                'script', 'style', '.ads', '.catalog', '.article-banner',
            ]
        )

    def clean_code_blocks(self, soup):
        """Remove 掘金 code block extension headers and junk spans."""
        # Remove code-block-extension-header (contains 体验AI代码助手/代码解读/复制代码)
        for header in soup.find_all(class_='code-block-extension-header'):
            header.decompose()

        # Remove standalone junk spans that survived
        junk_texts = ['体验AI代码助手', '代码解读', '复制代码']
        for span in soup.find_all('span'):
            text = span.get_text(strip=True)
            if any(j in text for j in junk_texts):
                # Only remove if it's a short junk-only span
                if len(text) <= 10:
                    span.decompose()

    def extract_language(self, code_elem):
        """Extract language from code element's class list."""
        if not code_elem:
            return ''
        for cls in code_elem.get('class', []):
            if cls.startswith('language-'):
                lang = cls.replace('language-', '')
                if lang not in ('code-block-extension-codeShowNum', 'hljs'):
                    return lang
            # Handle hljs class with language
            if cls == 'hljs' and code_elem.get('class'):
                for c in code_elem.get('class', []):
                    if c.startswith('language-'):
                        return c.replace('language-', '')
        return ''

    def extract_code_blocks(self, content_elem):
        """Replace each <pre> with a text placeholder directly in the soup tree.
        Returns list_of_code_blocks. content_elem is mutated."""
        from bs4 import NavigableString
        code_blocks = []

        for pre in list(content_elem.find_all('pre')):
            code = pre.find('code')
            if code:
                lang = self.extract_language(code)
                code_text = code.get_text().rstrip('\n')
            else:
                lang = ''
                code_text = pre.get_text().rstrip('\n')

            if not code_text.strip():
                pre.decompose()
                continue

            idx = len(code_blocks)
            code_blocks.append(f'```{lang}\n{code_text}\n```\n')

            # Replace <pre> with a raw text node — html2text passes NavigableString through
            placeholder = NavigableString(f'\n\n@@CODE_BLOCK_{idx}@@\n\n')
            pre.replace_with(placeholder)

        return code_blocks

    def restore_code_blocks(self, markdown, code_blocks):
        """Replace placeholders with formatted code blocks."""
        for i, block in enumerate(code_blocks):
            markdown = markdown.replace(f'@@CODE_BLOCK_{i}@@', block)
        return markdown

    def clean_markdown(self, markdown):
        """Post-process markdown."""
        # Remove leftover junk lines
        markdown = re.sub(r'^\s*(?:体验AI代码助手|代码解读|复制代码)\s*$', '',
                          markdown, flags=re.MULTILINE)
        # Remove code-block-extension related text
        markdown = re.sub(r'\n[ \t]*(?:体验AI代码助手|代码解读|复制代码)[ \t]*\n',
                          '\n', markdown)
        # Normalize blank lines
        markdown = re.sub(r'\n{3,}', '\n\n', markdown)
        return markdown.strip()

    def convert(self, html_path, output_dir=None):
        """转换单个HTML文件"""
        if not os.path.exists(html_path):
            safe_print(f"File not found: {html_path}")
            return False

        if output_dir is None:
            output_dir = os.path.dirname(html_path) or '.'

        html_path = Path(html_path)

        # Read HTML
        try:
            with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
                html_content = f.read()
        except Exception as e:
            safe_print(f"Read failed: {e}")
            return False

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, 'lxml')

        # Extract metadata
        try:
            metadata = self._extract_metadata(soup, html_path)
        except TypeError:
            metadata = {'title': '', 'author': '', 'date': '', 'source': '掘金', 'url': ''}
            title_elem = soup.select_one(self.title_selector)
            if title_elem:
                metadata['title'] = title_elem.get_text(strip=True)
            author_elem = soup.select_one(self.author_selector)
            if author_elem:
                metadata['author'] = author_elem.get_text(strip=True)
            date_elem = soup.select_one(self.date_selector)
            if date_elem:
                metadata['date'] = date_elem.get_text(strip=True)
            filename = os.path.basename(html_path)
            date_match = re.search(r'(\d{4})(\d{2})(\d{2})', filename)
            if date_match and not metadata['date']:
                metadata['date'] = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
        if isinstance(metadata, tuple):
            metadata = metadata[0]

        metadata.setdefault('source', '掘金')
        metadata.setdefault('url', '')
        metadata.setdefault('author', '')
        metadata.setdefault('date', '')

        # Extract content
        content_elem = None
        for sel in ['.markdown-body', '.article-content', 'article', '.content']:
            content_elem = soup.select_one(sel)
            if content_elem and len(content_elem.get_text(strip=True)) > 200:
                break

        if not content_elem:
            safe_print(f"Content not found: {html_path}")
            return False

        # Clean code block extensions
        self.clean_code_blocks(soup)

        # Remove unwanted elements
        for sel in self.remove_selectors:
            for elem in content_elem.select(sel):
                elem.decompose()

        # Determine output directory
        if output_dir is None:
            out = html_path.parent
        else:
            out = Path(output_dir)
            out.mkdir(parents=True, exist_ok=True)

        # Extract and save base64 images
        img_count = self._extract_base64_images(soup, html_path, out)
        if img_count > 0:
            safe_print(f"  Images: {img_count}")

        # Extract code blocks to placeholders (mutates content_elem in place)
        code_blocks = self.extract_code_blocks(content_elem)

        # Convert to markdown — NavigableString placeholders pass through html2text
        md_body = self._html_to_markdown(content_elem)

        # Restore properly formatted code blocks
        md_body = self.restore_code_blocks(md_body, code_blocks)

        # Clean up
        md_body = self.clean_markdown(md_body)
        md_body = re.sub(r'!\[([^\]]*)\]\(data:[^)]+\)\n*', '', md_body)

        # Build YAML front matter
        yaml_block = self._build_yaml_front_matter(metadata)
        output_path = out / f"{html_path.stem}.md"

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(yaml_block + '\n' + md_body + '\n')

        safe_print(f"Converted: {output_path}")
        return True


if __name__ == '__main__':
    converter = JuejinConverter()
    if len(sys.argv) > 1:
        if sys.argv[1].endswith('.html'):
            converter.convert(sys.argv[1])
        else:
            converter.batch_convert(sys.argv[1])
    else:
        converter.batch_convert(r'C:/Users/D-001/Downloads/HTML')
