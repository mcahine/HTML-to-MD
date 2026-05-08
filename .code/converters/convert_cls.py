#!/usr/bin/env python3
"""财联社 (cls.cn) HTML 转 Markdown 转换器"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from html_converter_base import HTMLConverterBase


class CLSConverter(HTMLConverterBase):
    def __init__(self):
        super().__init__(
            domain='cls.cn',
            name='财联社',
            content_selector='.detail-content, .article-content, .content, article',
            title_selector='h1.title, .article-title, h1',
            author_selector='.author-name, .source, .author',
            date_selector='.time, .publish-time, .date',
            remove_selectors=[
                '.ad-container', '.share-box', '.related-news',
                '.comment-section', '.bottom-bar', '.top-bar',
                '.breadcrumb', '.article-tags', '.app-download',
                'script', 'style'
            ]
        )


if __name__ == '__main__':
    import sys
    converter = CLSConverter()
    if len(sys.argv) > 1:
        if sys.argv[1].endswith('.html'):
            converter.convert(sys.argv[1])
        else:
            converter.batch_convert(sys.argv[1])
    else:
        converter.batch_convert(r'C:/Users/D-001/Downloads/HTML')
