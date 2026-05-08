#!/usr/bin/env python3
"""国家发改委 (ndrc.gov.cn) HTML 转 Markdown 转换器"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from html_converter_base import HTMLConverterBase

class NDRCConverter(HTMLConverterBase):
    def __init__(self):
        super().__init__(
            domain='ndrc.gov.cn',
            name='国家发改委',
            content_selector='.detail-content, .content, .main-content, #content, .TRS_Editor',
            title_selector='h1, .title, .article-title, .detail-title',
            author_selector='.author, .source, .ly, .ly2',
            date_selector='.publish-date, .time, .date, .sj, .sj2',
            remove_selectors=[
                '.header', '.footer', '.sidebar', '.nav',
                '.breadcrumb', '.share-box', '.related-links',
                '.toolbar', '.pages', '.next-page',
                'script', 'style'
            ]
        )

if __name__ == '__main__':
    import sys
    converter = NDRCConverter()
    if len(sys.argv) > 1:
        if sys.argv[1].endswith('.html'):
            converter.convert(sys.argv[1])
        else:
            converter.batch_convert(sys.argv[1])
    else:
        converter.batch_convert(r'C:/Users/D-001/Downloads/HTML')
