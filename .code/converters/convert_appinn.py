#!/usr/bin/env python3
"""小众软件 (appinn.com) HTML 转 Markdown 转换器"""
import sys, os, re
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from html_converter_base import HTMLConverterBase, safe_print


class AppinnConverter(HTMLConverterBase):
    """小众软件 — article 正文，去掉侧栏和评论"""

    def __init__(self):
        super().__init__(
            domain='appinn.com',
            name='小众软件',
            content_selector='.entry-content, .post-single-content, .post-content, article',
            title_selector='h1, .entry-title, .post-title',
            remove_selectors=[
                'script', 'style', 'nav', 'footer',
                '.sidebar', '.comment', '.comments',
                '.related-posts', '.share-buttons',
                '.post-meta', '.entry-meta',
                'header', '.header', '.navbar',
                '.site-header', '.top-header',
                '.breadcrumb', '.breadcrumbs',
                '.post-actions', '.action-bar',
                '.topad', '.bottomad',           # 标签/广告
                '.google-auto-placed',           # Google 自动广告
                '.wp-block-separator',           # 分隔线
            ],
        )

    def _extract_content(self, soup):
        content = super()._extract_content(soup)
        if not content:
            return None
        for a in list(content.find_all('a')):
            txt = a.get_text(strip=True)
            if txt in ('Home', '首页', 'Homepage', 'About'):
                a.decompose()
        for h1 in content.find_all('h1'):
            h1.decompose()
        # Merge adjacent <code> elements into one (insert space between them)
        for code in list(content.find_all('code')):
            ns = code.next_sibling
            if ns and isinstance(ns, str) and ns.strip() == '':
                nn = ns.next_sibling
                if hasattr(nn, 'name') and nn.name == 'code':
                    # Merge: append next code's text with a space
                    code.string = (code.get_text() + ' ' + nn.get_text())
                    nn.decompose()
        # Unwrap lists that were wrapped in <pre> or <code> tags
        for pre in list(content.find_all(['pre', 'code'])):
            if pre.find('li') or pre.find('ul') or pre.find('ol'):
                pre.unwrap()
        return content

    def _html_to_markdown(self, content):
        code_blocks = self._protect_code_blocks(content)
        md = super()._html_to_markdown(content)
        md = self._restore_code_blocks(md, code_blocks)
        # Unwrap fenced lists
        md = re.sub(r'```\s*\n((?:\s*[-*+]\s.+\n)+)```', r'\n\1\n', md)
        # Fix 2-space indented list items
        md = re.sub(r'^  ([-*+]|\d+\.)\s', r'\1 ', md, flags=re.MULTILINE)
        # Merge adjacent inline code spans
        # First: `x``y` (no space between) → leave as `xy` then add spaces back
        md = re.sub(r'`\s*`', '', md)
        # Merge spans with space between: `x` `y` → `x y`
        for _ in range(3):
            md = re.sub(r'(`[^`]+`)\s(`[^`]+`)', r'\1 \2', md)
        # Insert spaces between lowercase/uppercase word boundaries in merged code
        # e.g. `mkdirartisanal-git` → `mkdir artisanal-git`
        def add_word_spaces(m):
            inner = m.group(1)
            # Insert space at word boundaries: lowercase→uppercase, letter→dash, etc
            inner = re.sub(r'([a-z])([A-Z])', r'\1 \2', inner)
            inner = re.sub(r'([a-zA-Z0-9])([./\\-]{1,2})([a-zA-Z])', r'\1 \2 \3', inner)
            return '`' + inner + '`'
        # Apply to merged code spans that are missing spaces
        md = re.sub(r'`([^` ]{30,})`', add_word_spaces, md)
        # Restore command line breaks: `$ cmd1$ cmd2` → each $ on its own line
        # But only within backtick spans (inline code or table cells)
        def split_commands(m):
            content = m.group(1)
            # Replace ' $ ' or '$' before a command with newline prefix
            content = re.sub(r'(?<!\n)\s*(\$ )', r'\n\1', content)
            # Remove duplicate newlines
            content = re.sub(r'\n{2,}', '\n', content)
            return '`' + content + '`'
        md = re.sub(r'`([^`]+\$ [^`]+)`', split_commands, md)
        return md


if __name__ == '__main__':
    conv = AppinnConverter()
    if len(sys.argv) > 1:
        conv.convert(sys.argv[1])
    else:
        conv.batch_convert('.')
