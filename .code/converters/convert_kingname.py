#!/usr/bin/env python3
"""一日一技 (kingname.info) HTML 转 Markdown 转换器"""
import sys, os, re
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from html_converter_base import HTMLConverterBase, safe_print
from bs4 import NavigableString


class KingnameConverter(HTMLConverterBase):
    """一日一技 — table→code, 去掉表格残余"""

    def __init__(self):
        super().__init__(
            domain='kingname.info',
            name='一日一技',
            content_selector='article, .entry-content, .post-content, .content',
            remove_selectors=[
                'script', 'style', 'nav', 'footer',
                '.sidebar', '.comment', '.comments',
            ],
        )

    def _protect_code_blocks(self, content_elem):
        """Convert table-wrapped code blocks + regular <pre> to clean code fences."""
        from bs4 import NavigableString
        code_blocks = []

        # 1. Table-based code blocks: line numbers (gutter) + code (code td)
        for table in list(content_elem.find_all('table')):
            code_td = table.select_one('td.code')
            if code_td:
                pre = code_td.find('pre')
                if pre:
                    # Replace <br> with newlines, then get text
                    from copy import deepcopy
                    p2 = deepcopy(pre)
                    for br in p2.find_all('br'):
                        br.replace_with('\n')
                    text = p2.get_text().strip()
                else:
                    text = code_td.get_text().strip()
            else:
                text = table.get_text().strip()

            if not text or re.match(r'^[\d\s]+$', text):
                table.decompose()
                continue

            idx = len(code_blocks)
            code_blocks.append(f'\n```\n{text}\n```\n')
            placeholder = NavigableString(f'@@CODE_BLOCK_{idx}@@')
            table.replace_with(placeholder)

        # 2. Regular <pre> blocks
        for pre in list(content_elem.find_all('pre')):
            code = pre.find('code')
            text = (code or pre).get_text().strip()
            if not text or re.match(r'^[\d\s]+$', text):
                pre.decompose()
                continue
            lang = ''
            if code:
                for c in code.get('class', []):
                    if c.startswith('language-'):
                        lang = c.replace('language-', '')
                        break
            idx = len(code_blocks)
            code_blocks.append(f'\n```{lang}\n{text}\n```\n')
            placeholder = NavigableString(f'@@CODE_BLOCK_{idx}@@')
            pre.replace_with(placeholder)

        return code_blocks

    def _html_to_markdown(self, content):
        # Protect code blocks
        code_blocks = self._protect_code_blocks(content)
        md = super()._html_to_markdown(content)
        md = self._restore_code_blocks(md, code_blocks)
        # Remove stray | and |---|--- table remnants
        md = re.sub(r'^\s*\|[-\s|]+\|\s*$', '', md, flags=re.MULTILINE)
        md = re.sub(r'^\s*\|\s*$', '', md, flags=re.MULTILINE)
        # Remove meta line: __ 发布于 ...
        md = re.sub(r'^_{1,2}\s*(?:发布于|更新于).+$', '', md, flags=re.MULTILINE)
        return md


if __name__ == '__main__':
    conv = KingnameConverter()
    if len(sys.argv) > 1:
        conv.convert(sys.argv[1])
    else:
        conv.batch_convert('.')
