#!/usr/bin/env python3
"""果壳网 (guokr.com) HTML 转 Markdown 转换器"""
import sys, os, re
from pathlib import Path
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from html_converter_base import HTMLConverterBase, safe_print


class GuokrConverter(HTMLConverterBase):
    def __init__(self):
        super().__init__(
            domain='guokr.com',
            name='果壳',
            content_selector=None,
            title_selector=None,
            author_selector=None,
            date_selector=None,
            remove_selectors=[
                'script', 'style',
                '#footer', '.Footer__FooterWrap',
                '#modalRoot', '#toastRoot', '#actionSheetRoot',
                '.Header__HeaderWrap',
            ]
        )

    def convert(self, html_path, output_dir=None):
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

        # Metadata
        metadata = {'title': '', 'author': '', 'date': '', 'source': '果壳', 'url': ''}

        title_tag = soup.find('title')
        if title_tag:
            t = title_tag.get_text(strip=True)
            t = re.sub(r'\s*[|｜]\s*果壳.*$', '', t)
            metadata['title'] = t

        for meta in soup.find_all('meta'):
            prop = meta.get('property', '')
            name = meta.get('name', '')
            content = meta.get('content', '')
            if prop == 'og:url' or name == 'url':
                metadata['url'] = content
            if name == 'author':
                metadata['author'] = content

        # SingleFile comment URL fallback
        if not metadata['url']:
            html_str = str(soup)
            url_match = re.search(r'url:\s*(https?://[^\s\]\"]+)', html_str)
            if url_match:
                metadata['url'] = url_match.group(1).rstrip('/')

        filename = os.path.basename(html_path)
        dm = re.search(r'(\d{4})(\d{2})(\d{2})', filename)
        if dm:
            metadata['date'] = f"{dm.group(1)}-{dm.group(2)}-{dm.group(3)}"

        # Content
        content = soup.select_one('section[class*="Article__StyledContent"]')
        if not content:
            content = soup.find(id='app')
        if not content:
            safe_print(f"Content not found: {html_path}")
            return False

        # ── Clean unwanted elements ──
        for sel in self.remove_selectors:
            for elem in content.select(sel):
                elem.decompose()

        # Remove elements by text pattern (styled-components class names are hashed)
        for el in list(content.find_all(['div', 'span', 'section', 'p', 'strong', 'b', 'em', 'i'])):
            # Skip if already decomposed
            if not el.parent:
                continue
            txt = el.get_text(strip=True)

            # Header meta strip: "科学人", word count, reading time
            if txt and '需用时' in txt and len(txt) < 100:
                el.decompose()
                continue

            # Footer: "The End" + copyright + "举报这篇文章"
            if 'The End' in txt and '发布于' in txt and len(txt) < 500:
                el.decompose()
                continue

            # Footer: 果壳病人 promo / submission / copyright
            if any(p in txt for p in [
                '这里是果壳病人', '本文来自果壳病人', '未经授权不得转载',
                '投稿至health@guokr.com', '投稿至**health@guokr.com**',
            ]) and len(txt) < 500:
                el.decompose()
                continue

            # "点个"小爱心"吧" — like button text
            if '点个' in txt and '小爱心' in txt and len(txt) < 30:
                el.decompose()
                continue

            # Author card: "果壳网官方帐号"
            if txt == '果壳网官方帐号':
                el.decompose()
                continue

            # Pure author card with avatar link
            if re.match(r'^果壳$', txt):
                parent_cls = ' '.join(el.parent.get('class', []))
                # Only remove if it's a standalone author link, not in the middle of body text
                if len(el.parent.get_text(strip=True)) < 50:
                    el.parent.decompose()
                continue

        # ── Extract images ──
        img_count = self._extract_base64_images(soup, html_path, out)

        # ── Convert to markdown ──
        md_body = self._html_to_markdown(content)
        md_body = re.sub(r'!\[([^\]]*)\]\(data:[^)]+\)\n*', '', md_body)

        # ── Post-process MD to catch any remaining junk ──
        lines = md_body.split('\n')
        clean_lines = []
        skip_block = False
        for line in lines:
            stripped = line.strip()

            # Skip header meta blocks
            if '需用时' in stripped:
                continue
            if stripped in ('科学人', '* 科学人', '**科学人**'):
                continue
            if re.match(r'^\d+字$', stripped):
                continue

            # Skip footer junk
            if 'The End' in stripped:
                skip_block = True
                continue
            if skip_block and ('发布于' in stripped or '版权' in stripped or '举报' in stripped):
                continue
            if '点个' in stripped and '小爱心' in stripped:
                continue
            if stripped == '果壳网官方帐号':
                continue
            if stripped == '__The End __':
                skip_block = True
                continue
            # Reset skip after we've passed the footer block
            if skip_block and not stripped:
                skip_block = False

            clean_lines.append(line)

        md_body = '\n'.join(clean_lines)
        md_body = re.sub(r'\n{3,}', '\n\n', md_body).strip()

        yaml_block = self._build_yaml_front_matter(metadata)
        output_path = out / f"{html_path.stem}.md"
        output_path.write_text(yaml_block + '\n' + md_body + '\n', encoding='utf-8')
        safe_print(f"Converted: {output_path}")
        return True


if __name__ == '__main__':
    converter = GuokrConverter()
    if len(sys.argv) > 1:
        if sys.argv[1].endswith('.html'):
            converter.convert(sys.argv[1])
        else:
            converter.batch_convert(sys.argv[1])
    else:
        converter.batch_convert('果壳')
