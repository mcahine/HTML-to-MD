#!/usr/bin/env python3
"""
File renamer — interactive (user types names) or CLI (agent-drivable).

Interactive mode (default):
  python rename_interactive.py

List bad files with metadata (for agent review):
  python rename_interactive.py --list

Agent mode — rename one specific file:
  python rename_interactive.py --rename "目录名/旧名" "新名"

Agent mode — batch rename via stdin (one per line: 目录名/旧名<TAB>新名):
  python rename_interactive.py --batch
  (pipe lines to stdin)

Agent mode — batch rename via file:
  python rename_interactive.py --batch-file renames.txt
  (file format: 目录名/旧名[tab]新名, one per line)
"""
import re, sys, shutil, io, json
from pathlib import Path

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    if sys.stdin.isatty():
        sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8', errors='replace')

PROJECT = Path(__file__).resolve().parent.parent

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


def get_source(dir_name):
    return SOURCE_MAP.get(dir_name, dir_name)


def get_metadata(html_path, md_path):
    info = {'title': '', 'date': '', 'source': '', 'url': ''}
    if md_path and md_path.exists():
        text = md_path.read_text(encoding='utf-8', errors='ignore')
        for key in ['title', 'date', 'source', 'url']:
            m = re.search(rf'^{key}:\s*(.+)$', text, re.MULTILINE)
            if m:
                info[key] = m.group(1).strip().strip('"')
    if not info['title'] and html_path and html_path.exists():
        text = html_path.read_text(encoding='utf-8', errors='ignore')
        m = re.search(r'<title>([^<]+)</title>', text, re.IGNORECASE)
        if m:
            t = m.group(1).strip()
            t = re.sub(r'\s*[-|｜]\s*[^-|｜]+$', '', t)
            info['title'] = t
    if not info['date']:
        info['date'] = 'YYYYMMDD'
    return info


def make_safe_filename(text):
    text = text.strip()
    text = re.sub(r'[<>:"/\\|?*]', '', text)
    text = re.sub(r'\s+', '_', text)
    text = re.sub(r'_+', '_', text)
    return text.strip('_')


def collect_bad_files():
    bad = []
    for d in sorted(PROJECT.iterdir()):
        if not d.is_dir() or d.name.startswith('.') or d.name == '.code':
            continue
        source = get_source(d.name)
        stems = {f.stem for f in d.glob('*') if f.suffix in ('.html', '.md')}
        for stem in sorted(stems):
            parts = stem.split('_')
            if len(parts) >= 2 and date8.fullmatch(parts[-2]) and parts[-1] in SOURCE_MAP:
                continue  # already correct
            html = d / f'{stem}.html'
            md = d / f'{stem}.md'
            meta = get_metadata(html if html.exists() else None, md if md.exists() else None)
            meta['source'] = source
            bad.append((d.name, stem, meta))
    return bad


def do_rename(dir_name, old_stem, new_stem):
    """Rename a single file stem and its assets."""
    d = PROJECT / dir_name
    new_stem = make_safe_filename(new_stem)
    if new_stem == old_stem:
        return True, 'unchanged'

    for ext in ['.html', '.md']:
        old = d / f'{old_stem}{ext}'
        new = d / f'{new_stem}{ext}'
        if old.exists():
            if new.exists():
                return False, f'target exists: {new.name}'
            shutil.move(str(old), str(new))

    old_assets = d / 'assets' / f'{old_stem}_assets'
    new_assets = d / 'assets' / f'{new_stem}_assets'
    if old_assets.exists():
        shutil.move(str(old_assets), str(new_assets))
        new_md = d / f'{new_stem}.md'
        if new_md.exists():
            text = new_md.read_text(encoding='utf-8', errors='ignore')
            text = text.replace(f'{old_stem}_assets', f'{new_stem}_assets')
            new_md.write_text(text, encoding='utf-8')

    return True, f'{old_stem} -> {new_stem}'


# ── CLI modes ──────────────────────────────────────────────────

def cmd_list():
    """List bad files as JSON for agent consumption."""
    bad = collect_bad_files()
    result = []
    for dir_name, stem, meta in bad:
        result.append({
            'dir': dir_name,
            'stem': stem,
            'title': meta['title'][:120],
            'date': meta['date'],
            'source': meta['source'],
            'url': meta.get('url', '')[:100],
        })
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_rename(dir_stem, new_stem):
    """Rename one file: --rename 'dir/oldstem' 'newstem'"""
    parts = dir_stem.rsplit('/', 1)
    if len(parts) != 2:
        print('ERROR: format must be "dir/oldstem"', file=sys.stderr)
        sys.exit(1)
    ok, msg = do_rename(parts[0], parts[1], new_stem)
    print(msg)
    sys.exit(0 if ok else 1)


def cmd_batch():
    """Read rename pairs from stdin (tab-separated): dir/oldstem\tnewstem"""
    count = 0
    for line in sys.stdin:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        parts = line.split('\t')
        if len(parts) != 2:
            print(f'SKIP (bad format): {line[:60]}', file=sys.stderr)
            continue
        dir_stem, new_stem = parts
        dp = dir_stem.rsplit('/', 1)
        if len(dp) != 2:
            print(f'SKIP (bad path): {dir_stem}', file=sys.stderr)
            continue
        ok, msg = do_rename(dp[0], dp[1], new_stem)
        print(msg)
        if ok:
            count += 1
    print(f'\nRenamed {count} files')


def cmd_batch_file(filepath):
    """Read rename pairs from a file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        sys.stdin = f
        cmd_batch()


def cmd_interactive():
    """Interactive mode — user types each name."""
    bad = collect_bad_files()
    if not bad:
        print('All files have correct names.')
        return

    print(f'Found {len(bad)} files to rename.\n')
    print('Format: 关键词1_关键词2_关键词3_YYYYMMDD_来源')
    print('Type "skip" to keep, "quit" to exit.\n')

    for i, (dir_name, old_stem, meta) in enumerate(bad, 1):
        print(f'{"=" * 60}')
        print(f'[{i}/{len(bad)}] 目录: {dir_name}')
        print(f'  当前: {old_stem}')
        print(f'  标题: {meta["title"][:120]}')
        print(f'  日期: {meta["date"]}')
        print(f'  来源: {meta["source"]}')

        # Suggest
        words = re.findall(r'[\w一-鿿]+', meta['title'])[:4]
        d = meta['date'].replace('-', '')
        if len(d) != 8:
            d = 'YYYYMMDD'
        suggestion = f'{"_".join(words)}_{d}_{meta["source"]}'
        print(f'  建议: {make_safe_filename(suggestion)[:150]}')

        while True:
            new_stem = input('  新文件名: ').strip()
            if new_stem.lower() == 'quit':
                print('已退出')
                return
            if new_stem.lower() == 'skip':
                print('  已跳过\n')
                break
            if not new_stem:
                print('  不能为空')
                continue
            ok, msg = do_rename(dir_name, old_stem, new_stem)
            print(f'  {msg}\n')
            break

    print('全部处理完毕。')


# ── Entry ──────────────────────────────────────────────────────

if __name__ == '__main__':
    if len(sys.argv) == 1:
        cmd_interactive()
    elif sys.argv[1] == '--list':
        cmd_list()
    elif sys.argv[1] == '--rename' and len(sys.argv) == 4:
        cmd_rename(sys.argv[2], sys.argv[3])
    elif sys.argv[1] == '--batch':
        cmd_batch()
    elif sys.argv[1] == '--batch-file' and len(sys.argv) == 3:
        cmd_batch_file(sys.argv[2])
    else:
        print(__doc__)
        sys.exit(1)
