#!/usr/bin/env python3
"""极客公园 (geekpark.net) HTML 转 Markdown 转换器"""
import sys, os, re
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from html_converter_base import HTMLConverterBase, safe_print


class GeekparkConverter(HTMLConverterBase):
    """极客公园 — 去掉标签栏和分享栏"""

    def __init__(self):
        super().__init__(
            domain='geekpark.net',
            name='极客公园',
            content_selector='article',
            title_selector='h1, .post-title, .article-title',
            remove_selectors=[
                'script', 'style', 'nav', 'footer', 'header',
                '.sidebar', '.comment', '.comments',
                '.tags',              # 标签栏
                '.article-tag',       # 单个标签
                '.share-wrap',        # 分享栏
                '.post-actions',      # 互动按钮
                '.recommend', '.related',
                '.post-header',       # 摘要/作者头
            ],
        )

    def _extract_metadata(self, soup, html_path):
        """Extract title, date, URL."""
        import re, os
        metadata = {
            'title': '', 'author': '', 'date': '',
            'source': '极客公园', 'url': '',
        }

        # URL from SingleFile
        html_str = str(soup)
        url_match = re.search(r'url:\s*(https?://[^\s\]\"]+)', html_str)
        if url_match:
            metadata['url'] = url_match.group(1).rstrip('/')

        # Title from og:title or h1
        og = soup.find('meta', {'property': 'og:title'})
        if og:
            metadata['title'] = og.get('content', '').strip()
        if not metadata['title']:
            h1 = soup.select_one('h1, .post-title')
            if h1:
                metadata['title'] = h1.get_text(strip=True)

        # Date from filename or meta
        dm = re.search(r'(\d{4})(\d{2})(\d{2})', os.path.basename(str(html_path)))
        if dm:
            metadata['date'] = f"{dm.group(1)}-{dm.group(2)}-{dm.group(3)}"

        return metadata


if __name__ == '__main__':
    conv = GeekparkConverter()
    if len(sys.argv) > 1:
        conv.convert(sys.argv[1])
    else:
        conv.batch_convert('.')
