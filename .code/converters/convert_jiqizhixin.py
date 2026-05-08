#!/usr/bin/env python3
"""机器之心 (jiqizhixin.com) HTML 转 Markdown 转换器"""
import sys, os, re
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from html_converter_base import HTMLConverterBase, safe_print


class JiqizhixinConverter(HTMLConverterBase):
    """机器之心 — 去掉导航栏、进度条、侧边推荐文章、翻译组件"""

    def __init__(self):
        super().__init__(
            domain='jiqizhixin.com',
            name='机器之心',
            content_selector='.detail__info-body',
            remove_selectors=[
                'script', 'style', 'nav', 'footer', 'header',
                '.detail__progress-wrapper',     # 进度条+标题
                '.home__list-wrapper',            # 侧边推荐文章
                '.detail__author-date',           # 作者日期行
                '.translation-widget',            # 翻译组件
                '.sidebar', '.recommend', '.related',
                '.detail__bottom',                # 底部操作栏
            ],
        )

    def _extract_metadata(self, soup, html_path):
        """Extract metadata."""
        metadata = {
            'title': '', 'author': '', 'date': '',
            'source': '机器之心', 'url': '',
        }

        html_str = str(soup)

        # URL
        url_match = re.search(r'url:\s*(https?://[^\s\]\"]+)', html_str)
        if url_match:
            metadata['url'] = url_match.group(1).rstrip('/')

        # Title from progress-wrapper (contains title + "0%"), h1, or og:title
        progress = soup.select_one('.detail__progress-wrapper')
        if progress:
            t = progress.get_text(strip=True)
            t = re.sub(r'0%$', '', t).strip()  # Remove trailing "0%"
            if t:
                metadata['title'] = t

        if not metadata['title']:
            h1 = soup.select_one('h1, .article-title')
            if h1:
                metadata['title'] = h1.get_text(strip=True)

        if not metadata['title']:
            og = soup.find('meta', {'property': 'og:title'})
            if og:
                metadata['title'] = re.sub(r'\s*[|｜]\s*机器之心.*$', '', og.get('content', '').strip())

        # Date from filename
        dm = re.search(r'(\d{4})(\d{2})(\d{2})', os.path.basename(str(html_path)))
        if dm:
            metadata['date'] = f"{dm.group(1)}-{dm.group(2)}-{dm.group(3)}"

        return metadata

    def _extract_content(self, soup):
        content = super()._extract_content(soup)
        if not content:
            return None

        # Remove the "机器之心原创9月3日" banner at top of article
        for el in list(content.find_all(['div', 'p', 'span'])):
            txt = el.get_text(strip=True)
            if re.match(r'^(机器之心|机器之心原创)\s*\d+月\d+日$', txt) and len(txt) < 30:
                el.decompose()
                break

        return content


if __name__ == '__main__':
    conv = JiqizhixinConverter()
    if len(sys.argv) > 1:
        conv.convert(sys.argv[1])
    else:
        conv.batch_convert('.')
