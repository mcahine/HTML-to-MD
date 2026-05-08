#!/usr/bin/env python3
"""
Markdown post-processor for Obsidian reading mode.
Scans all converted .md files, fixes formatting issues,
normalizes YAML front matter, produces clean, beautiful output.

Reusable: run `python polish_markdown.py` from project root.
"""

import os, re, sys, io
from pathlib import Path

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

PROJECT_ROOT = Path(__file__).resolve().parent.parent
os.chdir(PROJECT_ROOT)

# ── YAML normalization ──────────────────────────────────────────

STANDARD_YAML_KEYS = ['title', 'author', 'date', 'source', 'url', 'converted_at']
STRIP_YAML_KEYS = ['author_title', 'description', 'original_title',
                   'original_author', 'original_url', 'original_date',
                   'tags', 'keywords', 'category', 'summary', 'excerpt']


def normalize_yaml(text):
    """Normalize YAML: remove empty/non-standard fields, keep standard order."""
    if not text.startswith('---'):
        return text
    end = text.find('---', 3)
    if end == -1:
        return text

    yaml_block = text[3:end].strip()
    body = text[end + 3:]

    kept = {}
    for line in yaml_block.split('\n'):
        line = line.strip()
        if ':' not in line:
            continue
        key, _, val = line.partition(':')
        key, val = key.strip(), val.strip()
        if key in STRIP_YAML_KEYS:
            continue
        if not val or val in ('""', "''", 'None', 'null'):
            continue
        kept[key] = val

    rebuilt = ['---']
    for key in STANDARD_YAML_KEYS:
        if key in kept:
            rebuilt.append(f"{key}: {kept[key]}")
    for key, val in kept.items():
        if key not in STANDARD_YAML_KEYS:
            rebuilt.append(f"{key}: {val}")
    rebuilt.append('---')

    yaml_str = '\n'.join(rebuilt)
    yaml_str = _quote_yaml_title(yaml_str)
    return yaml_str + '\n' + body


def _quote_yaml_title(yaml_str):
    """Wrap the title value in double quotes — idempotent, won't double-quote."""
    import re
    lines = yaml_str.split('\n')
    for i, line in enumerate(lines):
        m = re.match(r'(title:\s*)(.+)', line)
        if not m:
            continue
        prefix, value = m.group(1), m.group(2)
        if value.startswith('"') and value.endswith('"'):
            return yaml_str
        if value.startswith("'") and value.endswith("'"):
            return yaml_str
        lines[i] = f'{prefix}"{value}"'
        return '\n'.join(lines)
    return yaml_str


# ── Content fixes ───────────────────────────────────────────────

def fix_backslash_paths(text):
    """Replace Windows backslash paths with forward slashes in []() and ![]()."""
    def replacer(m):
        path = m.group(0)
        path = path.replace('\\\\', '/').replace('\\', '/')
        # Collapse double slashes (from html2text backslash escaping)
        while '//' in path:
            path = path.replace('//', '/')
        return path
    text = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', replacer, text)
    text = re.sub(r'(?<!!)\[([^\]]*)\]\(([^)]+)\)', replacer, text)
    return text


def fix_list_spacing(text):
    """Remove blank lines between consecutive same-type list items (both UL and OL)."""
    lines = text.split('\n')
    result = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        result.append(line)

        # Check if current line is a list item
        is_li = bool(re.match(r'^(\s*)[-*+]\s', stripped))
        is_ol = bool(re.match(r'^(\s*)\d+\.\s', stripped))

        if is_li or is_ol:
            # Peek ahead: if next line is blank and the one after is a same-type list item
            if i + 2 < len(lines):
                next_line = lines[i + 1].strip()
                after_line = lines[i + 2].strip()
                next_is_same = False
                if is_li and re.match(r'^[-*+]\s', after_line):
                    next_is_same = True
                if is_ol and re.match(r'^\d+\.\s', after_line):
                    next_is_same = True
                if next_line == '' and next_is_same:
                    i += 1  # skip blank line between list items
        i += 1
    return '\n'.join(result)


def fix_spaced_bold(text):
    """Remove spaces between ** markers and the text they wrap.
    Only fixes clear patterns: ** text** → **text**, **text ** → **text**, ** text ** → **text**."""
    # 1. ** text ** → **text** (space on both sides of content)
    text = re.sub(r'\*\*[ \t]+([^*]+?)[ \t]+\*\*', r'**\1**', text)
    # 2. ** text** → **text** (space after opening ** only)
    text = re.sub(r'\*\*[ \t]+([^*]+?)\*\*', r'**\1**', text)
    # 3. **text ** → **text** (space before closing ** only)
    text = re.sub(r'\*\*([^*]+?)[ \t]+\*\*', r'**\1**', text)
    # 4. **text****more** → **textmore** (merge adjacent bold blocks)
    text = re.sub(r'\*\*\*\*', '', text)
    # 5. **text**\n\n**more** → **textmore** (split bold across paragraphs)
    text = re.sub(r'\*\*([^*\n]+)\*\*\n\n\*\*([^*]+)\*\*', r'**\1\2**', text)
    return text


def fix_latex_inline(text):
    """Wrap inline LaTeX segments (_{}, ^{}, \\commands) with $...$"""
    ds = chr(36)
    bs = chr(92)
    bt = chr(96)*3

    def wrap(m):
        seg = m.group(0)
        if ds in seg:
            return seg
        return ds + seg + ds

    # Process line by line, skip lines inside code fences
    lines = text.split(chr(10))
    in_fence = False
    result = []
    for line in lines:
        s = line.strip()
        if s.startswith(bt):
            in_fence = not in_fence
            result.append(line)
            continue
        if in_fence:
            result.append(line)
            continue
        # Wrap LaTeX tokens inline
        line = re.sub(r'[A-Za-z0-9.]+_[{][A-Za-z0-9,()\[\]]+[}]', wrap, line)
        line = re.sub(r'[A-Za-z0-9.]+\^[{][A-Za-z0-9,()\[\]]+[}]', wrap, line)
        line = re.sub(r'(?<![A-Za-z])' + bs + bs + r'[a-zA-Z]+(?:\{[^}]*\})?', wrap, line)
        result.append(line)

    text = chr(10).join(result)
    # Merge adjacent $...$ patterns
    for _ in range(3):
        text = re.sub(r'\x24([^$\n]+?)\x24\x24([^$\n]+?)\x24', ds + r'\1\2' + ds, text)
    return text


def fix_image_spacing(text):
    """Ensure images are on their own line with blank lines around them."""
    text = re.sub(r'([^\n])(!\[[^\]]*\]\([^)]+\))', r'\1\n\n\2', text)
    text = re.sub(r'(!\[[^\]]*\]\([^)]+\))([^\n])', r'\1\n\n\2', text)
    return text


def fix_image_alt(text):
    """Replace generic/empty alt text with 'Image N' numbering."""
    img_counter = [0]

    def replacer(m):
        alt = m.group(1).strip()
        src = m.group(2)
        if not alt or alt in ('图片', 'image', 'img', '图像', '图'):
            img_counter[0] += 1
            alt = f'Image {img_counter[0]}'
        return f'![{alt}]({src})'

    return re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', replacer, text)


def fix_blank_lines(text):
    """Normalize: max 1 blank line between paragraphs (2 newlines = 1 empty line)."""
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text


def fix_heading_spacing(text):
    """Ensure blank line and proper spacing around headings."""
    # Fix: ###**text** → ### **text** (space between # and **)
    text = re.sub(r'^(#{1,6})\*\*', r'\1 **', text, flags=re.MULTILINE)
    # Blank line before heading: "text\n# Heading" -> "text\n\n# Heading"
    text = re.sub(r'([^\n])\n(#{1,6}\s)', r'\1\n\n\2', text)
    # Blank line after heading: "# Heading\ntext" -> "# Heading\n\ntext"
    text = re.sub(r'(#{1,6}\s[^\n]+)\n([^\n#])', r'\1\n\n\2', text)
    return text


def fix_fence_spacing(text):
    """Ensure $$$$ and ``` blocks have blank lines around them."""
    # $$ display math: ensure blank line before and after
    text = re.sub(r'([^\n])\n(\$\$)', r'\1\n\n\2', text)
    text = re.sub(r'(\$\$)\n([^\n$])', r'\1\n\n\2', text)
    # ``` code: ensure blank line before and after
    text = re.sub(r'([^\n])\n(```)', r'\1\n\n\2', text)
    text = re.sub(r'(```)\n([^\n`])', r'\1\n\n\2', text)
    return text


def fix_table_spacing(text):
    """Ensure tables (| --- | separators) have blank lines around them."""
    # Table separator line: | --- | --- |
    # Add blank line before separator if needed
    text = re.sub(r'([^\n|])\n(\|[-\s|:]+\|)', r'\1\n\n\2', text)
    # Add blank line after last table row
    text = re.sub(r'(\|[-\s|:]+\|)\n([^\n|])', r'\1\n\n\2', text)
    return text


def fix_bare_urls(text):
    """Convert bare URLs and empty-bracket links to <url> format."""
    # Bare URLs on their own line → <url>
    text = re.sub(r'(?<![<(\[])(https?://[^\s<>\[\]]+)(?![>)\]])', r'<\1>', text)
    # Empty bracket links: [](url) → <url>
    text = re.sub(r'\[\s*\]\(([^)]+)\)', r'<\1>', text)
    # Remove any remaining [](url) that survived
    text = re.sub(r'\[\s*\]\(https?://[^)]+\)', '', text)
    return text


def fix_data_uri_images(text, site_dir=None):
    """Replace remaining data:image references with local assets paths.
    Maps data URIs to actual files in assets/{stem}_assets/ based on MD filename."""
    if not site_dir:
        return text
    import re as _re
    from pathlib import Path as _Path

    # Find all data:image references
    data_refs = _re.findall(r'!\[([^\]]*)\]\((data:image/[^)]+)\)', text)
    if not data_refs:
        return text

    # Build a map of asset files by the stem directory name
    assets_dir = _Path(site_dir) / 'assets'
    if not assets_dir.is_dir():
        return text

    # For each data ref, try to find a matching extracted image
    # The base class names them image_001, image_002, etc. by order of appearance
    fixed = 0
    for i, (alt, data_uri) in enumerate(data_refs, 1):
        # Search all subdirs for image_{i:03d}.*
        for sub in sorted(assets_dir.glob('*_assets')):
            for ext in ['png', 'jpg', 'jpeg', 'webp', 'gif', 'svg']:
                candidate = f'assets/{sub.name}/image_{i:03d}.{ext}'
                if (_Path(site_dir) / candidate).exists():
                    text = text.replace(f'![{alt}]({data_uri})', f'![{alt}]({candidate})', 1)
                    fixed += 1
                    break
            else:
                continue
            break

    return text


def fix_source_date_junk(text):
    """Remove source/date metadata lines that leak into markdown body.
    Patterns: 2025-12-22 22:19 星期一财联社, [topic](url)2026-01-08...星期X>"""
    # Date+weekday line: 2025-12-22 22:19 星期一...
    text = re.sub(
        r'^\s*\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}\s+星期[一二三四五六日].*$',
        '', text, flags=re.MULTILINE)
    # Topic link + date line: [xxx](url)2026-01-08 15:39 星期四...
    text = re.sub(
        r'^\s*\[[^\]]+\]\([^)]+\)\s*\d{4}-\d{2}-\d{2}.*$',
        '', text, flags=re.MULTILINE)
    # Date line ending with >
    text = re.sub(
        r'^\s*.*星期[一二三四五六日].*>\s*$',
        '', text, flags=re.MULTILINE)
    return text


def fix_html_remnants(text):
    """Strip HTML tags (except markdown autolinks <url>) and decode entities."""
    text = re.sub(r'<\s*(?:br|hr)\s*/?\s*>', '', text, flags=re.IGNORECASE)
    # Protect autolinks: <https://...> is valid markdown, not HTML
    text = re.sub(r'<(?!https?://)(?!!--)[^>]+>', '', text)
    text = text.replace('&nbsp;', ' ')
    text = text.replace('&amp;', '&')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    text = text.replace('&quot;', '"')
    return text


def fix_broken_links(text):
    """Repair malformed markdown links: missing ) or ending with >"""
    # [text](url> → [text](url)
    text = re.sub(r'\[([^\]]*)\]\(([^)\n]+)>', r'[\1](\2)', text)
    # [text](url\n → [text](url)\n  (missing closing paren before newline)
    text = re.sub(r'\[([^\]]*)\]\(([^)\n]+)\n', r'[\1](\2)\n', text)
    return text


def fix_chinese_brackets_in_links(text):
    """Replace \[...\] or nested [...] inside link/image text with 【...】"""
    # Fix escaped brackets everywhere: \[xxx\] → 【xxx】
    text = re.sub(r'\\\[([^\[\]]+)\\\]', r'【\1】', text)
    # Fix image alt: ![alt [inner]](url) → ![alt 【inner】](url)
    def replace_img_alt(m):
        alt = m.group(1)
        url = m.group(2)
        alt = re.sub(r'\[([^\[\]]+)\]', r'【\1】', alt)
        return f'![{alt}]({url})'
    text = re.sub(r'!\[([^\]]*\[[^\]]*\][^\]]*)\]\(([^)]+)\)', replace_img_alt, text)
    # Fix link text: [text [inner]](url) → [text 【inner】](url)
    def replace_link_text(m):
        link_text = m.group(1)
        url = m.group(2)
        link_text = re.sub(r'\[([^\[\]]+)\]', r'【\1】', link_text)
        return f'[{link_text}]({url})'
    text = re.sub(r'(?<!\!)\[([^\]]*\[[^\]]*\][^\]]*)\]\(([^)]+)\)', replace_link_text, text)
    return text


def fix_title_inner_quotes(text):
    if not text.startswith('---'):
        return text
    end = text.find('---', 3)
    if end == -1:
        return text
    yaml_block = text[:end+3]
    body = text[end+3:]
    lines = yaml_block.split(chr(10))
    for i, line in enumerate(lines):
        m = re.match(r'(title:\s*)"(.+)"\s*$', line)
        if not m:
            continue
        prefix = m.group(1)
        content = m.group(2)
        if chr(0x22) not in content:
            continue
        odd = True
        new = ''
        for ch in content:
            if ch == chr(0x22):
                new += chr(0x201C) if odd else chr(0x201D)
                odd = not odd
            else:
                new += ch
        lines[i] = prefix + chr(0x22) + new + chr(0x22)
        break
    yaml_block = chr(10).join(lines)
    return yaml_block + body

def fix_trailing_whitespace(text):
    """Remove trailing whitespace from each line."""
    return '\n'.join(line.rstrip() for line in text.split('\n'))


def fix_javascript_void_links(text):
    """Remove [text](javascript:void(0)) heading/TOC links completely."""
    # Match the full pattern: [text](javascript:void/... "title")
    # SingleFile sometimes serializes as javascript:void/(0/)
    text = re.sub(r'\[[^\]]*\]\(javascript:void[^)]*\)\s*', '', text)
    # Also handle the variant with quotes: "title")
    text = re.sub(r'\s*"[^"]*"\)\s*', '', text)
    return text


def fix_indented_code_blocks(text):
    """Convert 4-space indented code blocks to fenced ``` blocks.
    Skips lines already inside existing fenced code blocks."""
    lines = text.split('\n')
    result = []
    code_buf = []
    in_code = False
    in_fence = False

    for line in lines:
        stripped = line.strip()
        # Track fenced code blocks — don't touch content inside them
        if stripped.startswith('```'):
            in_fence = not in_fence
            # Flush any pending indented code before the fence
            if in_code:
                code_text = '\n'.join(code_buf)
                if code_text.strip():
                    result.append('```')
                    result.append(code_text)
                    result.append('```')
                    result.append('')
                code_buf = []
                in_code = False
            result.append(line)
            continue

        if in_fence:
            result.append(line)
            continue

        if line.startswith('    ') and stripped:
            # 4-space indented code line (outside fence)
            if not in_code:
                in_code = True
                code_buf = []
            code_buf.append(line[4:])
        else:
            if in_code:
                code_text = '\n'.join(code_buf)
                if code_text.strip():
                    result.append('```')
                    result.append(code_text)
                    result.append('```')
                    result.append('')
                code_buf = []
                in_code = False
            result.append(line)

    # Flush any trailing code block
    if in_code and code_buf:
        code_text = '\n'.join(code_buf)
        if code_text.strip():
            result.append('```')
            result.append(code_text)
            result.append('```')
            result.append('')

    return '\n'.join(result)


def fix_tipster_line(text):
    """Add > blockquote to IT之家 tipster credit lines that lack it.
    Also ensure blank line between tipster quote and article body."""
    lines = text.split('\n')
    result = []
    for i, line in enumerate(lines):
        stripped = line.strip()

        # Add > prefix if missing
        if not stripped.startswith('>') and ('感谢' in stripped and '线索投递' in stripped):
            result.append('> ' + stripped)
        else:
            result.append(line)

        # If this is a tipster blockquote and next line has content but no > prefix,
        # insert a blank line
        if stripped.startswith('> 感谢') and '线索投递' in stripped:
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line and not next_line.startswith('>') and next_line:
                    result.append('')  # Add blank line
    return '\n'.join(result)


def fix_bbcode_markers(text):
    """Remove [code]/[/code] bbcode markers left by some converters."""
    # Line consisting only of [code] or [/code]
    text = re.sub(r'^\s*\[/?code\]\s*$', '', text, flags=re.MULTILINE)
    # [code] at start of line with content following → keep content
    text = re.sub(r'(?m)^\[code\]\s*', '', text)
    # [/code] at end of line
    text = re.sub(r'\s*\[/code\]$', '', text, flags=re.MULTILINE)
    return text


def fix_naked_asterisks(text):
    """Remove orphaned * or - lines (broken list markers)."""
    return '\n'.join(
        line for line in text.split('\n')
        if line.strip() not in ('*', '-')
    )


def fix_code_block_spacing(text):
    """Normalize line endings only — no structural changes to fences."""
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    return text


def fix_orphan_chars(text):
    """Remove lines that are just a single > or ) or ）with optional trailing spaces."""
    text = re.sub(r'^\s*[>)）]\s*$', '', text, flags=re.MULTILINE)
    return text


# ── Pipeline ────────────────────────────────────────────────────

def polish_body(text):
    """Apply all content-level fixes to a markdown body (without YAML)."""
    text = fix_backslash_paths(text)
    text = fix_broken_links(text)
    text = fix_chinese_brackets_in_links(text)
    text = fix_spaced_bold(text)
    text = fix_javascript_void_links(text)
    text = fix_tipster_line(text)
    text = fix_source_date_junk(text)
    text = fix_indented_code_blocks(text)
    text = fix_bbcode_markers(text)
    text = fix_list_spacing(text)
    text = fix_latex_inline(text)
    text = fix_image_spacing(text)
    text = fix_image_alt(text)
    text = fix_bare_urls(text)
    text = fix_html_remnants(text)
    text = fix_heading_spacing(text)
    text = fix_orphan_chars(text)
    text = fix_fence_spacing(text)
    text = fix_table_spacing(text)
    text = fix_trailing_whitespace(text)
    text = fix_naked_asterisks(text)
    text = fix_blank_lines(text)
    return text.strip() + '\n'


def polish_file(filepath):
    """Polish a single markdown file. Returns True if modified."""
    path = Path(filepath)
    original = path.read_text(encoding='utf-8')

    # Split YAML front matter from body
    if original.startswith('---'):
        end = original.find('---', 3)
        if end != -1:
            yaml_block = original[:end + 3]
            body = original[end + 3:]
            has_yaml = True
        else:
            yaml_block, body, has_yaml = '', original, False
    else:
        yaml_block, body, has_yaml = '', original, False

    body = polish_body(body)

    if has_yaml:
        full = yaml_block + '\n' + body
        full = normalize_yaml(full)
        full = fix_title_inner_quotes(full)
        result = full
    else:
        result = body

    # Fix remaining data:image URIs → local assets paths
    result = fix_data_uri_images(result, str(path.parent))

    # Final pass: ensure code block internals are clean (independent of YAML handling)
    result = fix_code_block_spacing(result)

    if result != original:
        path.write_text(result, encoding='utf-8')
        return True
    return False


def scan_and_polish(target='.'):
    """Scan .md files and apply polish."""
    target = Path(target)
    files = sorted(target.rglob('*.md')) if target.is_dir() else [target]

    total = changed = 0
    for f in files:
        try:
            if polish_file(f):
                changed += 1
            total += 1
        except Exception as e:
            print(f"  ERROR: {f.name}: {e}")

    print(f"Processed {total} files, modified {changed}")


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else PROJECT_ROOT
    scan_and_polish(target)
