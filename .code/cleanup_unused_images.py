#!/usr/bin/env python3
"""
Cleanup unreferenced images.

Logic:
  1. For each site directory, collect ALL image paths referenced in MD files
     via ![alt](path) — these are relative paths from the site dir root.
  2. For each file in assets/ (or images/), compute its relative path
     from the site dir root.
  3. If no MD reference path matches the file's relative path → unreferenced → delete.

Usage:
  python cleanup_unused_images.py          # dry-run
  python cleanup_unused_images.py --do     # actually delete
"""
import re, sys
from pathlib import Path
from send2trash import send2trash

PROJECT = Path(__file__).resolve().parent.parent


def get_ref_paths(site_dir):
    """Return set of relative paths referenced in all MD files of a site."""
    refs = set()
    for md in site_dir.glob('*.md'):
        text = md.read_text(encoding='utf-8', errors='ignore')
        for m in re.finditer(r'!\[[^\]]*\]\(([^)]+)\)', text):
            path = m.group(1).strip()
            # Skip external URLs
            if path.startswith('http') or path.startswith('data:'):
                continue
            # Normalize: forward slashes, no leading ./
            path = path.replace('\\', '/')
            path = re.sub(r'^\./', '', path)
            refs.add(path)
    return refs


def main(dry_run=True):
    total_deleted = 0
    total_size = 0

    for site_dir in sorted(PROJECT.iterdir()):
        if not site_dir.is_dir() or site_dir.name.startswith('.') or site_dir.name == '.code':
            continue
        if not list(site_dir.glob('*.md')):
            continue

        refs = get_ref_paths(site_dir)
        if not refs:
            continue

        # Collect all image files (assets/ + images/)
        candidates = []
        for sub in ['assets', 'images']:
            d = site_dir / sub
            if d.is_dir():
                for f in d.rglob('*'):
                    if f.is_file():
                        candidates.append(f)

        deleted_here = 0
        for f in candidates:
            rel = f.relative_to(site_dir).as_posix()

            # Check if any reference path matches
            # Direct match
            if rel in refs:
                continue
            # Also try without the first dir (some refs skip assets/)
            parts = rel.split('/', 1)
            if len(parts) > 1 and parts[1] in refs:
                continue

            size = f.stat().st_size
            if dry_run:
                if deleted_here < 3:
                    print(f'  [DRY-RUN] {site_dir.name}/{rel}')
            else:
                send2trash(str(f))
                if deleted_here < 3:
                    print(f'  [DEL] {site_dir.name}/{rel}')

            deleted_here += 1
            total_size += size

        if deleted_here:
            print(f'  {site_dir.name}: {deleted_here} unreferenced ({total_size / 1024:.0f} KB)')
        total_deleted += deleted_here

    print(f'\n{"=" * 50}')
    if dry_run:
        print(f'DRY-RUN: {total_deleted} images would be deleted ({total_size / 1024 / 1024:.1f} MB)')
        print(f'Run with --do to actually delete')
    else:
        print(f'Deleted {total_deleted} images ({total_size / 1024 / 1024:.1f} MB)')
    print(f'{"=" * 50}')


if __name__ == '__main__':
    main(dry_run='--do' not in sys.argv)
