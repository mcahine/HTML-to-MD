#!/usr/bin/env python3
"""国家发改委信息公开 (zfxxgk.ndrc.gov.cn) HTML 转 Markdown 转换器"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from html_converter_base import HTMLConverterBase

class NDRCZfxxgkConverter(HTMLConverterBase):
    def __init__(self):
        super().__init__(
            domain='zfxxgk.ndrc.gov.cn',
            name='国家发改委信息公开',
            content_selector='.article, .zwgkdetail, .gk-content, .xxgkcontent, .content-detail, .detail-content, .content',
            title_selector='h1, .title, .article-title, .detail-title, .gk-title',
            author_selector='.author, .source, .ly, .gk-ly',
            date_selector='.publish-date, .time, .date, .sj, .gk-date',
            remove_selectors=[
                '.header', '.footer', '.sidebar', '.nav',
                '.breadcrumb', '.share-box', '.related-links',
                '.toolbar', '.pages', '.next-page',
                '.gk-form', '.gk-table',
                'script', 'style'
            ]
        )

if __name__ == '__main__':
    import sys
    converter = NdrcZfxxgkConverter()
    if len(sys.argv) > 1:
        if sys.argv[1].endswith('.html'):
            converter.convert(sys.argv[1])
        else:
            converter.batch_convert(sys.argv[1])
    else:
        converter.batch_convert(r'C:/Users/D-001/Downloads/HTML')
