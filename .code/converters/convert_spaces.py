#!/usr/bin/env python3
"""科学空间 (spaces.ac.cn) HTML 转 Markdown 转换器"""
import sys, os, re
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from html_converter_base import HTMLConverterBase, safe_print


class SpacesAcConverter(HTMLConverterBase):
    """科学空间 — #PostContent，LaTeX 转 $$，去掉打赏及之后"""

    def __init__(self):
        super().__init__(
            domain='spaces.ac.cn',
            name='科学空间',
            content_selector='#PostContent',
            remove_selectors=[
                'script', 'style', 'nav',
                '.sidebar', '.comment', '.comments',
            ],
        )

    def convert(self, html_path, output_dir=None):
        """Override to add LaTeX wrapping and 打赏 removal."""
        if not os.path.exists(html_path):
            safe_print(f"File not found: {html_path}")
            return False

        html_path = Path(html_path)
        if output_dir is None:
            output_dir = html_path.parent
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_path.read_text(encoding='utf-8', errors='ignore'), 'lxml')

        # ── Metadata ──
        metadata = self._extract_metadata(soup, html_path)

        # ── Content ──
        content = soup.select_one('#PostContent')
        if not content:
            safe_print(f"Content not found: {html_path}")
            return False

        # Remove unwanted elements
        for sel in self.remove_selectors:
            for elem in content.select(sel):
                elem.decompose()

        # ── Unwrap images from <a> links (avoid broken [![alt](img)](url) ──
        import re as _re
        for a in content.find_all('a'):
            img = a.find('img')
            if img:
                a.replace_with(img)

        # ── Wrap MathJax: inline $...$ / display $$\n...\n$$ ──
        for span in content.find_all('span', class_='MathJax_Preview'):
            tex = span.get_text().strip()
            if not tex:
                continue
            # Display: has \begin/\end, or long formula (>=100 chars)
            if '\\begin{' in tex or '\\end{' in tex or len(tex) >= 100:
                span.string = f'\n$$\n{tex}\n$$\n'
            else:
                span.string = f'${tex}$'

        # ── Extract images ──
        img_count = self._extract_base64_images(soup, html_path, out)

        # ── Convert to markdown ──
        md_body = self._html_to_markdown(content)
        md_body = _re.sub(r'!\[([^\]]*)\]\(data:[^)]+\)\n*', '', md_body)

        # ── Cut at 打赏 ──
        idx = md_body.find('打赏')
        if idx > 0:
            # Go back to the start of the line containing 打赏
            line_start = md_body.rfind('\n', 0, idx)
            md_body = md_body[:line_start if line_start > 0 else idx]

        # ── Remove residual junk ──
        for pattern in [
            r'_?[*]{0,3}更详细的转载事宜.*$',
            r'_?[*]{0,3}如果您还有什么疑惑.*$',
            r'_?[*]{0,3}如果您觉得本文还不错.*$',
            r'_?[*]{0,3}因为网站后台对打赏.*$',
            r'_?[*]{0,3}转载到请包括本文地址.*$',
            r'_?[*]{0,3}转载到包括本文地址.*$',
        ]:
            md_body = _re.sub(pattern, '', md_body, flags=_re.MULTILINE)

        # Clean LaTeX artifacts
        # Collapse double $$ around inline formulas
        md_body = _re.sub(r'\$\$([^$\n]{1,80}?)\$\$', r'$\1$', md_body)
        # Fix overlapping $$ like $$...$$...
        md_body = _re.sub(r'\$\$(\s*\$[^$]+\$\s*)\$\$', r'\1', md_body)
        md_body = _re.sub(r'\$\$\s*\n\s*\$\$', '$$\n$$', md_body)
        md_body = _re.sub(r'\n{3,}', '\n\n', md_body).strip()

        # ── Output ──
        yaml_block = self._build_yaml_front_matter(metadata)
        output_path = out / f"{html_path.stem}.md"
        output_path.write_text(yaml_block + '\n' + md_body + '\n', encoding='utf-8')
        safe_print(f"Converted: {output_path}")
        return True

    def _extract_metadata(self, soup, html_path):
        metadata = {
            'title': '', 'author': '', 'date': '',
            'source': '科学空间', 'url': '',
        }
        # URL from SingleFile comment
        m = re.search(r'url:\s*(https?://[^\s\]\"]+)', str(soup))
        if m:
            metadata['url'] = m.group(1).rstrip('/')

        # Title from <title> tag
        tt = soup.find('title')
        if tt:
            t = tt.get_text(strip=True)
            t = re.sub(r'\s*[|｜-]\s*科学空间.*$', '', t)
            metadata['title'] = t

        # Date from filename
        dm = re.search(r'(\d{4})(\d{2})(\d{2})', os.path.basename(str(html_path)))
        if dm:
            metadata['date'] = f"{dm.group(1)}-{dm.group(2)}-{dm.group(3)}"

        # Author
        author_el = soup.select_one('.post-author, .author, [class*=author]')
        if author_el:
            metadata['author'] = author_el.get_text(strip=True)

        return metadata


if __name__ == '__main__':
    conv = SpacesAcConverter()
    if len(sys.argv) > 1:
        conv.convert(sys.argv[1])
    else:
        conv.batch_convert('.')
