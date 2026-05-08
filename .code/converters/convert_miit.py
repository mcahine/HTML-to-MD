#!/usr/bin/env python3
"""工信部 (miit.gov.cn) HTML 转 Markdown 转换器"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from html_converter_base import HTMLConverterBase

class MIITConverter(HTMLConverterBase):
    def __init__(self):
        super().__init__(
            domain='miit.gov.cn',
            name='工信部',
            content_selector='#con_con, .ccontent, .detail-content, .content, .main-content, #content, .content-details, .Custom_UnionStyle',
            title_selector='h1, .title, .article-title, .detail-title, .content-title',
            author_selector='.author, .source, .ly, .article-source',
            date_selector='.publish-date, .time, .date, .sj, .release-date',
            remove_selectors=[
                '.header', '.footer', '.sidebar', '.nav',
                '.breadcrumb', '.share-box', '.related-links',
                '.toolbar', '.pages', '.next-page',
                '.custom-isml', '.article-links',
                'script', 'style'
            ]
        )

if __name__ == '__main__':
    import sys
    converter = MIITConverter()
    if len(sys.argv) > 1:
        if sys.argv[1].endswith('.html'):
            converter.convert(sys.argv[1])
        else:
            converter.batch_convert(sys.argv[1])
    else:
        converter.batch_convert(r'C:/Users/D-001/Downloads/HTML')
