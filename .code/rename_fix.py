#!/usr/bin/env python3
"""
Rename files to follow key1_key2_key3_YYYYMMDD_source convention.
Reads title/date from MD front matter or HTML <title> tag.
"""
import re, shutil
from pathlib import Path
from datetime import datetime

PROJECT = Path(__file__).resolve().parent.parent
TODAY = datetime.now().strftime('%Y%m%d')

# Source name -> canonical
SOURCE_MAP = {
    'IT之家': 'IT之家', '掘金': '掘金', '人人都是产品经理': '人人都是产品经理',
    '界面新闻': '界面新闻', '财联社': '财联社', '观察者网': '观察者网',
    '爱范儿': '爱范儿', '中国政府网': '中国政府网', '微信公众号': '微信公众号',
    '东西智库': '东西智库', '中国日报': '中国日报', '宝玉的分享': '宝玉的分享',
    '新华网': '新华网', '国家发展改革委': '国家发展改革委', '张鑫旭': '张鑫旭',
    '少数派': '少数派', '美团': '美团', '工信部': '工信部', '虎嗅': '虎嗅',
    '求是网': '求是网', '知乎专栏': '知乎专栏', '树莓派实验室': '树莓派实验室',
    '七猫': '七猫', '果壳': '果壳', '阮一峰': '阮一峰',
}

date8 = re.compile(r'\d{8}')
bad_date = re.compile(r'(?:_\d{4,7}_|_\d{9,}_|_\d{4}_\d{1,2}_|_[A-Z]\d)')

def has_correct_format(name):
    """Check if filename follows key1_key2_YYYYMMDD_source pattern."""
    parts = name.split('_')
    if len(parts) < 3:
        return False
    # Check second-to-last part is 8-digit date
    if not date8.fullmatch(parts[-2]):
        return False
    # Check last part is a known source
    if parts[-1] not in SOURCE_MAP:
        return False
    return True

def extract_date(text):
    """Try to find YYYYMMDD or similar date in text."""
    # YYYYMMDD
    m = re.search(r'(\d{4})(\d{2})(\d{2})', text)
    if m:
        return f'{m.group(1)}{m.group(2)}{m.group(3)}'
    # YYYY-MM-DD
    m = re.search(r'(\d{4})-(\d{2})-(\d{2})', text)
    if m:
        return f'{m.group(1)}{m.group(2)}{m.group(3)}'
    return None

def extract_title(text):
    """Extract a usable title snippet from YAML or HTML."""
    # From YAML
    m = re.search(r'title:\s*"?([^"\n]{3,60})"?', text)
    if m:
        t = m.group(1).strip()
        # Clean up
        t = re.sub(r'[|｜\-—–\s]+$', '', t)
        t = re.sub(r'\s*[-|｜]\s*.*$', '', t)  # Remove site suffix
        # Take first 3 meaningful words
        words = re.findall(r'[\w一-鿿]+', t)
        if len(words) >= 3:
            return '_'.join(words[:4])  # Up to 4 key words
        return t.replace(' ', '_')[:60]
    return None

def get_source_from_dir(dir_name):
    """Map directory name to canonical source."""
    return SOURCE_MAP.get(dir_name, dir_name)

def rename_files():
    count = 0
    for d in sorted(PROJECT.iterdir()):
        if not d.is_dir() or d.name.startswith('.') or d.name == '.code':
            continue

        source = get_source_from_dir(d.name)
        items = list(d.glob('*'))
        stems = {f.stem for f in items}

        for stem in sorted(stems):
            if has_correct_format(stem):
                continue

            html = d / f'{stem}.html'
            md = d / f'{stem}.md'
            asset_dir = d / 'assets' / f'{stem}_assets'

            # Get title and date from MD or HTML
            title = None
            date = None

            if md.exists():
                text = md.read_text(encoding='utf-8', errors='ignore')
                title = extract_title(text)
                m = re.search(r'date:\s*(\d{4}-\d{2}-\d{2})', text)
                if m:
                    date = m.group(1).replace('-', '')
                if not date:
                    date = extract_date(text)

            if (not title or not date) and html.exists():
                text = html.read_text(encoding='utf-8', errors='ignore')
                if not title:
                    # From <title> tag
                    m = re.search(r'<title>([^<]{3,80})</title>', text, re.IGNORECASE)
                    if m:
                        title = m.group(1).strip()
                        title = re.sub(r'\s*[-|｜]\s*.*$', '', title)
                        title = '_'.join(re.findall(r'[\w一-鿿]+', title)[:4])
                if not date:
                    date = extract_date(text)

            # Fallbacks
            if not title:
                # Try to extract meaningful words from old filename
                parts = stem.split('_')
                words = [p for p in parts if not re.match(r'^\d+$', p) and len(p) > 1]
                title = '_'.join(words[:4])
            if not title or len(title) < 4:
                continue

            if not date:
                date = TODAY

            new_stem = f'{title}_{date}_{source}'
            # Truncate if too long
            if len(new_stem) > 200:
                new_stem = new_stem[:200]

            if new_stem == stem:
                continue

            # Rename files
            for ext in ['.html', '.md']:
                old = d / f'{stem}{ext}'
                new = d / f'{new_stem}{ext}'
                if old.exists() and not new.exists():
                    shutil.move(str(old), str(new))

            # Rename assets dir
            old_assets = d / 'assets' / f'{stem}_assets'
            new_assets = d / 'assets' / f'{new_stem}_assets'
            if old_assets.exists() and not new_assets.exists():
                shutil.move(str(old_assets), str(new_assets))
                # Update image paths in MD
                new_md = d / f'{new_stem}.md'
                if new_md.exists():
                    text = new_md.read_text(encoding='utf-8', errors='ignore')
                    text = text.replace(f'{stem}_assets', f'{new_stem}_assets')
                    new_md.write_text(text, encoding='utf-8')

            print(f'{d.name}/{stem} -> {new_stem}')
            count += 1

    print(f'\nRenamed {count} files')

if __name__ == '__main__':
    rename_files()
