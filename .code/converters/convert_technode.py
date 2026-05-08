#!/usr/bin/env python3
"""动点科技 (cn.technode.com) HTML 转 Markdown 转换器"""
import sys, os, re
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from html_converter_base import HTMLConverterBase, safe_print


class TechnodeConverter(HTMLConverterBase):
    """动点科技文章转换器 — 去掉标签区、相关文章、寻求报道等尾部杂项"""

    def __init__(self):
        super().__init__(
            domain='cn.technode.com',
            name='动点科技',
            content_selector='article',
            remove_selectors=[
                'script', 'style', 'nav', 'footer', 'header',
                '.sidebar', '.comment', '.comments',
                '.share-buttons', '.social-share',
                '.post-tag-share-container',     # 标签行
                '.post-tag-container',            # 标签容器
                '.tagcloud',                      # 标签云
                '.owl-stage-outer',               # 近期文章轮播
                '.owl-stage',                     # 近期文章内层
                '.related-posts',                 # 相关文章
                '.related-articles',
                '.entry-meta',                    # 元数据行（日期/作者）
                '.author-box',                    # 作者信息
                '.post-navigation',               # 上下篇导航
                '.breadcrumb',                    # 面包屑
                '#jp-relatedposts',               # Jetpack 相关文章
                '.sharedaddy',                    # 分享按钮
            ],
        )


if __name__ == '__main__':
    conv = TechnodeConverter()
    if len(sys.argv) > 1:
        conv.convert(sys.argv[1])
    else:
        conv.batch_convert('.')
