#!/usr/bin/env python3
"""阮一峰 (ruanyifeng.com) HTML 转 Markdown 转换器"""
import sys, os, re
from pathlib import Path
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from html_converter_base import HTMLConverterBase, safe_print


class RuanyifengConverter(HTMLConverterBase):
    def __init__(self):
        super().__init__(
            domain='ruanyifeng.com',
            name='阮一峰',
            content_selector='#main-content',
            title_selector='h1',
            author_selector=None,
            date_selector=None,
            remove_selectors=['script', 'style', '.entry-meta', '.post-meta']
        )

    def convert(self, html_path, output_dir=None):
        if not os.path.exists(html_path):
            safe_print(f"File not found: {html_path}")
            return False

        html_path = Path(html_path)
        if output_dir is None:
            output_dir = html_path.parent
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_path.read_text(encoding='utf-8', errors='ignore'), 'lxml')

        metadata = {'title': '', 'author': '阮一峰', 'date': '', 'source': '阮一峰的网络日志', 'url': ''}

        h1 = soup.find('h1')
        if h1:
            metadata['title'] = h1.get_text(strip=True)
        else:
            t = soup.find('title')
            if t:
                metadata['title'] = re.sub(r'\s*[-|]\s*阮一峰.*$', '', t.get_text(strip=True))

        for meta in soup.find_all('meta'):
            if meta.get('property') == 'og:url':
                metadata['url'] = meta.get('content', '')

        filename = os.path.basename(html_path)
        dm = re.search(r'(\d{4})(\d{2})(\d{2})', filename)
        if dm:
            metadata['date'] = f"{dm.group(1)}-{dm.group(2)}-{dm.group(3)}"

        content = soup.select_one('#main-content')
        if not content:
            safe_print(f"Content not found: {html_path}")
            return False

        for sel in self.remove_selectors:
            for elem in content.select(sel):
                elem.decompose()

        img_count = self._extract_base64_images(soup, html_path, out)

        md_body = self._html_to_markdown(content)
        md_body = re.sub(r'!\[([^\]]*)\]\(data:[^)]+\)\n*', '', md_body)
        md_body = re.sub(r'\n{3,}', '\n\n', md_body).strip()

        yaml_block = self._build_yaml_front_matter(metadata)
        output_path = out / f"{html_path.stem}.md"
        output_path.write_text(yaml_block + '\n' + md_body + '\n', encoding='utf-8')
        safe_print(f"Converted: {output_path}")
        return True


if __name__ == '__main__':
    converter = RuanyifengConverter()
    if len(sys.argv) > 1:
        if sys.argv[1].endswith('.html'):
            converter.convert(sys.argv[1])
        else:
            converter.batch_convert(sys.argv[1])
    else:
        converter.batch_convert('阮一峰')
