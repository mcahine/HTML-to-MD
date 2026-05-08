#!/usr/bin/env python3
"""吾爱破解 (52pojie.cn) HTML 转 Markdown 转换器"""
import sys, os, re
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from html_converter_base import HTMLConverterBase, safe_print
from bs4 import BeautifulSoup, NavigableString


class Pojie52Converter(HTMLConverterBase):
    """吾爱破解 — 正文提取 + NavigableString 代码块处理"""

    def __init__(self):
        super().__init__(
            domain='52pojie.cn',
            name='吾爱破解',
            content_selector='.pct, [class*=postcontent], .article-content',
            remove_selectors=[
                'script', 'style', 'nav', 'footer',
                '.sidebar', '.comment', '.comments',
                '.related', '.share', '.recommend',
                '.pstatus', '.quote', 'blockquote',
                '.attach', '.attachment',
            ],
        )

    def _extract_content(self, soup):
        content = super()._extract_content(soup)
        if not content:
            return None
        # Remove h1 (already in YAML title)
        for h1 in content.find_all('h1'):
            h1.decompose()
        return content

    def _html_to_markdown(self, content):
        # Extract code blocks to NavigableString placeholders
        code_blocks = []
        for pre in list(content.find_all('pre')):
            code = pre.find('code')
            text = (code or pre).get_text().rstrip('\n')
            if not text.strip():
                pre.decompose()
                continue
            # Detect language
            lang = ''
            if code:
                for c in code.get('class', []):
                    if c.startswith('language-'):
                        lang = c.replace('language-', '')
                        break
            idx = len(code_blocks)
            code_blocks.append('```{lang}\n{code}\n```\n'.format(lang=lang, code=text))
            placeholder = NavigableString('\n\n@@CODE_BLOCK_{idx}@@\n\n'.format(idx=idx))
            pre.replace_with(placeholder)

        # Convert to markdown
        md = super()._html_to_markdown(content)

        # Restore code blocks
        for i, block in enumerate(code_blocks):
            md = md.replace('@@CODE_BLOCK_{idx}@@'.format(idx=i), block)

        # Cut at 免费评分 / 评分
        import re as _re
        idx = md.find('免费评分')
        if idx < 0:
            idx = _re.search(r'\n#{1,6}\s*评分\s*\n', md)
            idx = idx.start() if idx else -1
        if idx > 0:
            line_start = md.rfind('\n', 0, idx)
            md = md[:line_start if line_start > 0 else idx]

        return md


if __name__ == '__main__':
    conv = Pojie52Converter()
    if len(sys.argv) > 1:
        conv.convert(sys.argv[1])
    else:
        conv.batch_convert('.')
