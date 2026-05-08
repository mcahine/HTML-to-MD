#!/usr/bin/env python3
"""
Classify HTML files from project root into directories by DOMAIN
(extracted from SingleFile URL comment), not by filename suffix.

All domain → directory rules come from domain_config.py.
"""
import os, sys, re, shutil
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent))
from 配置与导航.domain_config import classify_domain

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ARCHIVE_ROOT = PROJECT_ROOT.parent / 'Project-20260303-分类存档'
SPECIAL_DIRS = {'.code', '.docx', '__pycache__', '.git', '.claude'}


def extract_domain(html_path):
    """Extract domain from SingleFile HTML."""
    try:
        with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
            text = f.read(5000)
    except Exception:
        return None

    match = re.search(r'url:\s*(https?://[^\s\]\"\']+)', text)
    if not match:
        for pattern in [
            r'<meta\s+property="og:url"\s+content="(https?://[^"]+)"',
            r'<link\s+rel="canonical"\s+href="(https?://[^"]+)"',
        ]:
            match = re.search(pattern, text, re.I)
            if match:
                break

    if match:
        m = re.search(r'https?://(?:www\.)?([^/\s]+)', match.group(1))
        return m.group(1) if m else None
    return None


def main():
    os.chdir(PROJECT_ROOT)
    html_files = sorted(Path('.').glob('*.html'))

    if not html_files:
        print("No HTML files found in project root.")
        return

    print(f"Classifying {len(html_files)} HTML files by domain...")

    # Three branches:
    # 1. project  → known domain, go to project dir (走流程)
    # 2. archive  → blacklist domain, go to archive (只分类)
    # 3. new_domain → unknown domain, create domain-named dir (待决定)
    project_groups = defaultdict(list)   # dir_name → [paths]
    archive_groups = defaultdict(list)   # category → [(domain, path)]
    domain_groups = defaultdict(list)    # domain → [paths]  (new/undecided)
    no_domain = []                        # cannot extract domain

    for hf in html_files:
        domain = extract_domain(hf)
        if not domain:
            no_domain.append(hf)
            continue

        typ, name = classify_domain(domain)
        if typ == 'project':
            project_groups[name].append(hf)
        elif typ == 'archive':
            archive_groups[name].append((domain, hf))
        else:
            domain_groups[domain].append(hf)

    # Print summary
    print("=" * 60)
    for dir_name in sorted(project_groups, key=lambda d: -len(project_groups[d])):
        files = project_groups[dir_name]
        is_new = not (PROJECT_ROOT / dir_name).is_dir()
        tag = "NEW" if is_new else "EXISTING"
        print(f"  [PROJECT] {dir_name}/ ({len(files)} files)")

    for cat in sorted(archive_groups, key=lambda c: -len(archive_groups[c])):
        print(f"  [ARCHIVE] {cat}/ ({len(archive_groups[cat])} files)")

    for domain in sorted(domain_groups, key=lambda d: -len(domain_groups[d])):
        print(f"  [NEW DOMAIN] {domain}/ ({len(domain_groups[domain])} files)")

    if no_domain:
        print(f"  [NO DOMAIN] {len(no_domain)} files (cannot detect domain)")

    # Confirm
    response = input("\nProceed with moving files? [y/N]: ").strip().lower()
    if response not in ('y', 'yes'):
        print("Aborted.")
        return

    moved = 0

    # Move to project directories
    for dir_name, files in project_groups.items():
        dest_dir = PROJECT_ROOT / dir_name
        dest_dir.mkdir(parents=True, exist_ok=True)
        for hf in files:
            dest = dest_dir / hf.name
            if dest.exists():
                print(f"  SKIP: {hf.name} (exists in {dir_name}/)")
                continue
            shutil.move(str(hf), str(dest))
            moved += 1

    # Move to archive
    for cat, entries in archive_groups.items():
        for domain, hf in entries:
            dom_dir = ARCHIVE_ROOT / cat / domain
            dom_dir.mkdir(parents=True, exist_ok=True)
            dest = dom_dir / hf.name
            if dest.exists():
                print(f"  SKIP: {hf.name} (exists in archive/{cat}/{domain}/)")
                continue
            shutil.move(str(hf), str(dest))
            moved += 1

    # Move to domain-named directories (new/undecided domains)
    for domain, files in domain_groups.items():
        dest_dir = PROJECT_ROOT / domain
        dest_dir.mkdir(parents=True, exist_ok=True)
        for hf in files:
            dest = dest_dir / hf.name
            if dest.exists():
                print(f"  SKIP: {hf.name} (exists in {domain}/)")
                continue
            shutil.move(str(hf), str(dest))
            moved += 1

    print(f"\n  Moved: {moved} files")

    # Auto-update archive navigation if any files were moved to archive
    if archive_groups:
        _update_archive_nav()


def _update_archive_nav():
    """Call the navigation generator to refresh the archive's 导航.html."""
    import subprocess
    nav_script = Path(__file__).resolve().parent / '配置与导航' / '导航.py'
    archive = PROJECT_ROOT.parent / 'Project-20260303-分类存档'
    if nav_script.exists() and archive.is_dir():
        try:
            subprocess.run(
                [sys.executable, str(nav_script), '--generate', str(archive)],
                capture_output=True, timeout=30
            )
        except Exception:
            pass  # nav generation is best-effort


if __name__ == '__main__':
    main()
