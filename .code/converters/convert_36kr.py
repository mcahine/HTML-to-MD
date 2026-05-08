#!/usr/bin/env python3
"""36氪 (36kr.com) HTML 转 Markdown 转换器"""
import sys, os, re
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from html_converter_base import HTMLConverterBase, safe_print

from bs4 import BeautifulSoup


class Kr36Converter(HTMLConverterBase):
    """36氪文章转换器"""

    def __init__(self):
        super().__init__(
            domain='36kr.com',
            name='36氪',
            content_selector='.article-content',
            remove_selectors=[
                'script', 'style', 'nav', 'footer', 'header',
                '.kr-header', '.kr-header-main', '.kr-header-content',
                '.kr-header-search-entry',
                '.sidebar', '.comment', '.comments', '.recommend',
                '.share', '.social', '.ads',
                '.related-posts', '.related-articles',
                '.navigation', '.pagination',
                '.qr-code', '.app-download',
                '.seek-report-wrap',          # 寻求报道
                '.seek-report-link-btn',      # 寻求报道按钮
                '.article-title-icon',        # 作者/日期行（时代财经·2024年...）
                '.article-footer-txt',        # 文章底部版权声明
                '.editor-note',               # 编辑注（本文来自...）
                '.summary',                   # 文章摘要
            ],
        )

    def _extract_metadata(self, soup, html_path):
        """Extract metadata, title cleaned of -36氪 suffix."""
        metadata = {
            'title': '',
            'author': '',
            'date': '',
            'source': '36氪',
            'url': '',
        }

        html_str = str(soup)

        # URL
        url_match = re.search(r'url:\s*(https?://[^\s\]\"]+)', html_str)
        if url_match:
            metadata['url'] = url_match.group(1).rstrip('/')
        if not metadata['url']:
            canonical = soup.find('link', {'rel': 'canonical'})
            if canonical and canonical.get('href'):
                metadata['url'] = canonical['href']

        # Title — from og:title or h1, strip trailing -36氪
        og_title = soup.find('meta', {'property': 'og:title'})
        if og_title:
            metadata['title'] = og_title.get('content', '').strip()

        if not metadata['title']:
            h1 = soup.select_one('h1, .article-title')
            if h1:
                metadata['title'] = h1.get_text(strip=True)

        # Clean common title suffixes
        for suffix in ['-36氪', '- 36氪', '| 36氪', '36氪首发', '｜36氪', '|36氪']:
            if metadata['title'].endswith(suffix):
                metadata['title'] = metadata['title'][:-len(suffix)].strip()

        # Strip title prefixes like "科氪 | ", "36氪融资｜"
        for prefix in ['科氪 | ', '科氪| ', '36氪融资｜', '36氪首发 | ', '36氪首发｜']:
            if metadata['title'].startswith(prefix):
                metadata['title'] = metadata['title'][len(prefix):]

        # Date — from og:article:published_time or meta
        pub_time = soup.find('meta', {'property': 'article:published_time'})
        if pub_time:
            d = pub_time.get('content', '')
            m = re.search(r'(\d{4})-(\d{2})-(\d{2})', d)
            if m:
                metadata['date'] = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"

        if not metadata['date'] and metadata['url']:
            m = re.search(r'/p/(\d+)', metadata['url'])
            if m:
                pass  # URL doesn't encode date

        if not metadata['date']:
            m = re.search(r'(\d{4})(\d{2})(\d{2})', os.path.basename(str(html_path)))
            if m:
                metadata['date'] = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"

        return metadata

    def _extract_content(self, soup):
        """Extract the actual article body (skip title/author/date wrapper)."""
        # The real article body is inside this specific class chain
        body = soup.select_one('.content.articleDetailContent.kr-rich-text-wrapper')
        if not body:
            # Fallback: try .article-content and clean manually
            content = super()._extract_content(soup)
            if content:
                for h1 in content.find_all('h1'):
                    h1.decompose()
                for el in content.select('.article-title-icon, .article-footer-txt, .editor-note, .seek-report-link-btn, .seek-report-wrap, .summary'):
                    el.decompose()
                return content
            return None

        from copy import deepcopy
        body = deepcopy(body)

        # Remove author/editor meta lines within the body
        for el in list(body.find_all(['p', 'span', 'em', 'small'])):
            txt = el.get_text(strip=True)
            if re.match(r'^(作者|编辑|撰文|记者|文|责编|责任编?辑?)\s*[|｜:：]', txt):
                el.decompose()

        return body


if __name__ == '__main__':
    conv = Kr36Converter()
    if len(sys.argv) > 1:
        conv.convert(sys.argv[1])
    else:
        conv.batch_convert('.')
