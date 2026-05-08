#!/usr/bin/env python3
"""
Archive original HTML files to a parallel backup directory.
Moves (not copies) all .html files from the project into
  ../Project-20260303-网页结构分析-副本/
preserving the exact subdirectory structure.
Only run after conversion + polish are confirmed good.
"""
import shutil
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
BACKUP = PROJECT.parent / (PROJECT.name + '-副本')


def main():
    BACKUP.mkdir(parents=True, exist_ok=True)

    moved = 0
    for d in sorted(PROJECT.iterdir()):
        if not d.is_dir() or d.name.startswith('.') or d.name == '.code':
            continue

        html_files = list(d.glob('*.html'))
        if not html_files:
            continue

        # Create matching subdirectory in backup
        dest_dir = BACKUP / d.name
        dest_dir.mkdir(parents=True, exist_ok=True)

        for hf in html_files:
            dest = dest_dir / hf.name
            shutil.move(str(hf), str(dest))
            moved += 1

        # Remove original dir if empty now
        remaining = list(d.glob('*'))
        if not remaining:
            d.rmdir()

    print(f'Moved {moved} HTML files to {BACKUP}')


if __name__ == '__main__':
    main()
