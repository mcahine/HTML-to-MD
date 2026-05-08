#!/usr/bin/env python3
"""Generic HTML-to-Markdown converter — auto-detects content and metadata for any site."""
import os, sys, re, base64
from pathlib import Path
from datetime import datetime

try:
    from html_converter_base import HTMLConverterBase, safe_print
    HAS_BASE = True
except ImportError:
    HAS_BASE = False
    import html2text

    def safe_print(msg):
        try: print(msg)
        except: pass


class GenericConverter(HTMLConverterBase if HAS_BASE else object):
    """Generic converter for any website. Auto-detects content area and metadata."""

    # Common content selectors (tried in order)
    CONTENT_SELECTORS = [
        'article',
        '.article-content', '.article-body', '.post-content', '.post-body',
        '.entry-content', '.content', '.markdown-body',
        '.blog-content', '.story-content', '.news-content',
        'main', '#content', '#article', '#main-content',
        '.rich_media_content',  # WeChat
        '.article', '.post', '.blog-post',
    ]

    # Elements to remove from content
    REMOVE_SELECTORS = [
        'script', 'style', 'nav', 'footer', 'header',
        '.sidebar', '.comment', '.comments', '.recommend',
        '.share', '.social', '.advertisement', '.ads',
        '.related-posts', '.related-articles', '.suggest',
        '.navigation', '.pagination', '.breadcrumb',
        '.author-box', '.author-bio', '.meta-info',
        '.tag-list', '.category-list',
        '.qr-code', '.app-download', '.download-app',
    ]

    def __init__(self):
        if HAS_BASE:
            super().__init__(
                domain='',
                name='Generic',
                content_selector=', '.join(self.CONTENT_SELECTORS),
                remove_selectors=self.REMOVE_SELECTORS,
            )

    def _extract_metadata(self, soup, html_path):
        """Auto-detect metadata from HTML."""
        metadata = {
            'title': '',
            'author': '',
            'date': '',
            'source': '',
            'url': '',
        }

        html_str = str(soup)

        # 1. URL from SingleFile comment, canonical, or og:url
        url_match = re.search(r'url:\s*(https?://[^\s\]]+)', html_str)
        if not url_match:
            url_match = re.search(r'original\s+url:\s*(https?://[^\s\]]+)', html_str, re.I)
        if url_match:
            metadata['url'] = url_match.group(1).rstrip()

        if not metadata['url']:
            for tag in soup.find_all(['link', 'meta']):
                if tag.get('rel') == ['canonical'] or tag.get('property') == 'og:url':
                    href = tag.get('href') or tag.get('content')
                    if href:
                        metadata['url'] = href
                        break

        # 2. Source from domain
        if metadata['url']:
            domain_match = re.search(r'https?://(?:www\.)?([^/]+)', metadata['url'])
            if domain_match:
                metadata['source'] = domain_match.group(1)

        # 3. Title from og:title, h1, or <title>
        for tag in soup.find_all('meta'):
            if tag.get('property') in ('og:title', 'twitter:title'):
                t = tag.get('content', '').strip()
                if t:
                    metadata['title'] = t
                    break

        if not metadata['title']:
            h1 = soup.find('h1')
            if h1:
                metadata['title'] = h1.get_text(strip=True)

        if not metadata['title']:
            title_tag = soup.find('title')
            if title_tag:
                metadata['title'] = title_tag.get_text(strip=True)

        # 4. Author from meta
        for tag in soup.find_all('meta'):
            if tag.get('name') in ('author', 'article:author') or tag.get('property') == 'article:author':
                a = tag.get('content', '').strip()
                if a:
                    metadata['author'] = a
                    break

        # 5. Date from meta or filename
        for tag in soup.find_all('meta'):
            prop = tag.get('property', '') or tag.get('name', '')
            if 'published_time' in prop or 'date' in prop:
                d = tag.get('content', '').strip()
                if d:
                    date_match = re.search(r'(\d{4})-(\d{2})-(\d{2})', d)
                    if date_match:
                        metadata['date'] = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
                        break

        if not metadata['date'] and metadata['url']:
            date_match = re.search(r'/(\d{4})/(\d{2})/(\d{2})/', metadata['url'])
            if date_match:
                metadata['date'] = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"

        if not metadata['date']:
            filename = os.path.basename(str(html_path))
            date_match = re.search(r'(\d{4})(\d{2})(\d{2})', filename)
            if date_match:
                metadata['date'] = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"

        return metadata

    def _extract_content(self, soup):
        """Auto-detect content area."""
        # Try selectors in order
        for selector in self.CONTENT_SELECTORS:
            content = soup.select_one(selector)
            if content:
                # Verify it has substantial text
                text = content.get_text(strip=True)
                if len(text) > 200:
                    # Clean unwanted elements
                    for rm_sel in self.REMOVE_SELECTORS:
                        for elem in content.select(rm_sel):
                            elem.decompose()
                    return content

        # Fallback: use body
        body = soup.find('body')
        if body:
            for rm_sel in self.REMOVE_SELECTORS:
                for elem in body.select(rm_sel):
                    elem.decompose()
            return body

        return None

    def convert(self, html_path, output_dir=None):
        """Convert a single HTML file with auto-detection."""
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            safe_print("Error: beautifulsoup4 required")
            return False

        html_path = Path(html_path)
        if not html_path.exists():
            safe_print(f"File not found: {html_path}")
            return False

        try:
            with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
                html_content = f.read()
        except Exception as e:
            safe_print(f"Read error: {e}")
            return False

        soup = BeautifulSoup(html_content, 'lxml')

        # Extract metadata
        metadata = self._extract_metadata(soup, html_path)

        # Determine output directory
        if output_dir is None:
            output_dir = html_path.parent
        else:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

        # Extract images
        img_count = self._extract_base64_images(soup, html_path, output_dir)
        if img_count > 0:
            safe_print(f"  Images: {img_count}")

        # Extract content
        content = self._extract_content(soup)
        if not content:
            safe_print(f"No content found: {html_path.name}")
            return False

        # Convert to Markdown
        md_body = self._html_to_markdown(content)

        # Clean data:image residuals
        md_body = re.sub(r'!\[([^\]]*)\]\(data:[^)]+\)\n*', '', md_body)

        # Build YAML + body
        yaml_block = self._build_yaml_front_matter(metadata)
        output_path = output_dir / f"{html_path.stem}.md"

        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(yaml_block + '\n' + md_body)
            safe_print(f"  OK: {output_path.name}")
            return True
        except Exception as e:
            safe_print(f"Write error: {e}")
            return False
