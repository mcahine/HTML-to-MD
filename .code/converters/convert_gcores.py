#!/usr/bin/env python3
"""机核网 (gcores.com) HTML 转 Markdown 转换器"""
import sys, os, re
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from html_converter_base import HTMLConverterBase, safe_print


class GcoresConverter(HTMLConverterBase):
    """机核网文章转换器 — 清理投稿声明、评论区、标签、相关文章等"""

    def __init__(self):
        super().__init__(
            domain='gcores.com',
            name='机核',
            content_selector='.articlePage_body',
            title_selector='h1, .story_title, .article-title',
            remove_selectors=[
                'script', 'style', 'nav', 'footer',
                '.sidebar', '.header',
                # Disclaimer / copyright
                '.u_color-gray-desc',          # "本文系用户投稿"
                '.notice-bold',                 # "未经作者授权 禁止转载"
                # Comment section
                '.originalPage_comments',       # 评论区
                '.comment-box', '.comments',
                # Audio player
                '.m-playController_box',
                '.audio-player',
                # Tags at bottom
                '.story_tags',
                '.tag-list', '.tags',
                # Author / category cards at bottom
                '.story_authorInfo',
                # Related articles
                '.related-articles', '.recommend',
                # Share / social
                '.share-buttons', '.social-share',
                # Footer junk
                '.page-footer', '.back-to-top',
                '.footer-nav',
                # Like / comment counts
                '.like-count', '.comment-count',
                # Ad
                '.advertisement', '.ad',
            ],
        )

    def _extract_metadata(self, soup, html_path):
        """Extract metadata — title, author, date, URL from SingleFile."""
        metadata = {
            'title': '',
            'author': '',
            'date': '',
            'source': '机核',
            'url': '',
        }

        html_str = str(soup)

        # URL from SingleFile comment
        url_match = re.search(r'url:\s*(https?://[^\s\]\"]+)', html_str)
        if url_match:
            metadata['url'] = url_match.group(1).rstrip('/')
        if not metadata['url']:
            canonical = soup.find('link', {'rel': 'canonical'})
            if canonical and canonical.get('href'):
                metadata['url'] = canonical['href']

        # Title from og:title or h1
        og_title = soup.find('meta', {'property': 'og:title'})
        if og_title:
            t = og_title.get('content', '').strip()
            # Strip common suffixes
            for sfx in [' | 机核 GCORES', ' - 机核 GCORES', '丨机核']:
                if sfx in t:
                    t = t[:t.index(sfx)].strip()
            metadata['title'] = t

        if not metadata['title']:
            h1 = soup.select_one('h1, .story_title, .article-title')
            if h1:
                metadata['title'] = h1.get_text(strip=True)

        # Date from filename
        dm = re.search(r'(\d{4})(\d{2})(\d{2})', os.path.basename(str(html_path)))
        if dm:
            metadata['date'] = f"{dm.group(1)}-{dm.group(2)}-{dm.group(3)}"

        return metadata

    def _extract_content(self, soup):
        """Extract article body, remove header junk and footer junk."""
        content = super()._extract_content(soup)
        if not content:
            content = soup.select_one('.articlePage_body')
        if not content:
            return None

        # Remove H1 (already in YAML)
        for h1 in content.find_all('h1'):
            h1.decompose()

        # Remove audio note divs: "收听本文..."
        for el in list(content.find_all(['div', 'span'])):
            txt = el.get_text(strip=True)
            if re.match(r'^收听本文\s*\d+:\d+', txt) and len(txt) < 20:
                el.decompose()

        # Remove category link at top (like [知识挖掘机] link)
        # Usually the first link in the content is a category link
        first_el = content.find(recursive=False)
        if first_el:
            for a in list(first_el.find_all('a'))[:3]:
                if a.get('href', '').startswith('https://www.gcores.com/categories/'):
                    p = a.parent
                    p.decompose()
                    break

        return content

    def _html_to_markdown(self, content):
        """Convert to markdown, then clean residual patterns."""

        # ── Remove author/category/game cards (at bottom) ──
        for sc in list(content.select('.story_container')):
            txt = sc.get_text(strip=True)
            # Card-like: short text with links to user/category/game/portfolio
            is_card = (
                len(txt) < 200 and (
                    sc.select_one('a[href*="/users/"]') or
                    sc.select_one('a[href*="/categories/"]') or
                    sc.select_one('a[href*="/games/"]') or
                    sc.select_one('a[href*="/portfolios/"]')
                )
            )
            if is_card:
                sc.decompose()

        # ── Remove tag sections at bottom ──
        for el in list(content.select('[class*=tag], [class*=Tag]')):
            txt = el.get_text(strip=True)
            if len(txt) < 100:
                el.decompose()

        # ── Remove TOC lists ──
        for ul in list(content.find_all(['ul', 'ol'])):
            items = [li.get_text(strip=True) for li in ul.find_all('li')]
            if not items:
                continue
            # TOC items: short, no sentence-ending punctuation
            toc_score = 0
            for item in items:
                if len(item) >= 50:
                    break
                has_end = any(p in item for p in '。！？；')  # sentence-ending only
                if re.match(r'^[一二三四五六七八九十\d]+[、.．]', item):
                    toc_score += 1
                elif re.match(r'^(引言|绪论|结论|写在|前言|后记|参考|开始)', item):
                    toc_score += 1
                elif not has_end and len(item) < 35:
                    toc_score += 0.5  # short line without punctuation, likely TOC
            if toc_score >= len(items) * 0.5:
                ul.decompose()

        # ── Remove standalone number lines ──
        for el in list(content.find_all(['span', 'div', 'p'])):
            if el.find(['a', 'img', 'h1', 'h2', 'h3', 'ul', 'ol', 'li']):
                continue
            txt = el.get_text(strip=True)
            if re.match(r'^\d{1,5}$', txt):
                el.decompose()

        md = super()._html_to_markdown(content)

        # Clean residual stray characters and empty links
        md = re.sub(r'\n[IVXLCDMivxlcdm]{1,3}\s*\n\s*$', '\n', md)  # standalone roman numeral at end
        md = re.sub(r'\n{3,}', '\n\n', md)

        return md.strip()


if __name__ == '__main__':
    conv = GcoresConverter()
    if len(sys.argv) > 1:
        conv.convert(sys.argv[1])
    else:
        conv.batch_convert('.')
