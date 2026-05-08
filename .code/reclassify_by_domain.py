#!/usr/bin/env python3
"""
Re-classify HTML files by actual domain (from SingleFile URL comment).
Reads domain rules from domain_config.py — no hardcoded mappings here.

- Domains in DOMAIN_TO_DIR  → stay in project, move to target dir
- Domains in DOMAIN_ARCHIVE → move to ../Project-20260303-分类存档/<category>/
- Unknown domains           → stay in place (needs manual review)
"""
import os, sys, re, shutil
from pathlib import Path
from collections import defaultdict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
os.chdir(PROJECT_ROOT)

# Import domain config
sys.path.insert(0, str(Path(__file__).resolve().parent))
from 配置与导航.domain_config import DOMAIN_TO_DIR, DOMAIN_ARCHIVE, classify_domain

ARCHIVE_ROOT = PROJECT_ROOT.parent / 'Project-20260303-分类存档'
SPECIAL_DIRS = {'.code', '.docx', '__pycache__', '.git', '.claude'}


def extract_url_and_domain(html_path):
    """Extract original URL and domain from SingleFile HTML."""
    try:
        with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
            text = f.read(5000)
    except Exception:
        return None, None

    # SingleFile comment: url: https://example.com/...
    match = re.search(r'url:\s*(https?://[^\s\]\"\']+)', text)
    if not match:
        for pattern in [
            r'<meta\s+property="og:url"\s+content="(https?://[^"]+)"',
            r'<link\s+rel="canonical"\s+href="(https?://[^"]+)"',
            r'original\s+url:\s*(https?://[^\s\]]+)',
        ]:
            match = re.search(pattern, text, re.I)
            if match:
                break

    if match:
        url = match.group(1).rstrip('/')
        m = re.search(r'https?://(?:www\.)?([^/\s]+)', url)
        domain = m.group(1) if m else None
        return url, domain

    return None, None


def domain_to_dirname(domain):
    """Resolve domain to target directory using domain_config."""
    typ, name = classify_domain(domain)
    if typ == 'project':
        return name
    elif typ == 'archive':
        return f'__ARCHIVE__:{name}'
    else:
        return domain  # unknown, keep as-is


def main():
    os.chdir(PROJECT_ROOT)

    # Collect ALL HTML files from ALL directories
    all_htmls = []
    for d in sorted(Path('.').iterdir()):
        if not d.is_dir() or d.name in SPECIAL_DIRS or d.name.startswith('.'):
            continue
        for hf in d.glob('*.html'):
            all_htmls.append(hf)

    print(f"Found {len(all_htmls)} HTML files across all directories")
    print("Extracting domains...")

    domain_groups = defaultdict(list)
    no_domain = []

    for hf in all_htmls:
        url, domain = extract_url_and_domain(hf)
        if domain:
            domain_groups[domain].append((hf, url))
        else:
            no_domain.append(hf)

    print(f"  With domain: {sum(len(v) for v in domain_groups.values())}")
    print(f"  Without domain: {len(no_domain)}")

    if no_domain:
        print("\nFiles without detectable domain (will stay in place):")
        for hf in sorted(no_domain)[:20]:
            print(f"  {hf}")

    # Classify each domain
    target_groups = defaultdict(list)  # target → [(path, url)]
    archive_groups = defaultdict(list)  # category → [(path, url)]
    unknown_groups = defaultdict(list)   # domain → [(path, url)]

    for domain, files in domain_groups.items():
        typ, name = classify_domain(domain)
        if typ == 'project':
            target_groups[name].extend(files)
        elif typ == 'archive':
            archive_groups[name].extend(files)
        else:
            unknown_groups[domain].extend(files)

    # Print summary
    print(f"\n{'='*60}")
    print(f"  Classification Summary")
    print(f"{'='*60}")

    if target_groups:
        print(f"\n  [PROJECT] Stay in project:")
        for target in sorted(target_groups, key=lambda t: -len(target_groups[t])):
            files = target_groups[target]
            is_new = not (PROJECT_ROOT / target).is_dir()
            tag = "NEW" if is_new else "EXISTING"
            print(f"    [{tag}] {target}/ ({len(files)} files)")

    if archive_groups:
        print(f"\n  [ARCHIVE] Move to {ARCHIVE_ROOT.name}:")
        for cat in sorted(archive_groups, key=lambda c: -len(archive_groups[c])):
            print(f"    {cat}/ ({len(archive_groups[cat])} files)")

    if unknown_groups:
        print(f"\n  [UNKNOWN] Will keep domain as dir name:")
        for domain in sorted(unknown_groups, key=lambda d: -len(unknown_groups[d])):
            print(f"    {domain}/ ({len(unknown_groups[domain])} files)")

    # Confirm
    response = input("\nRe-classify and move files? [y/N]: ").strip().lower()
    if response not in ('y', 'yes'):
        print("Aborted.")
        return

    # ── Move project files ──
    moved_project = 0
    created = 0
    for target, file_list in target_groups.items():
        dest_dir = PROJECT_ROOT / target
        if not dest_dir.exists():
            dest_dir.mkdir(parents=True, exist_ok=True)
            created += 1
        for hf, url in file_list:
            if hf.parent == dest_dir:
                continue
            dest = dest_dir / hf.name
            if dest.exists():
                print(f"  CONFLICT: {hf.name} in {target}/, skipping")
                continue
            shutil.move(str(hf), str(dest))
            moved_project += 1

    # ── Move archive files ──
    moved_archive = 0
    for cat, file_list in archive_groups.items():
        cat_dir = ARCHIVE_ROOT / cat
        # Group by domain for subdirectory
        domain_files = defaultdict(list)
        for hf, url in file_list:
            m = re.search(r'https?://(?:www\.)?([^/\s]+)', url)
            dom = m.group(1) if m else 'unknown'
            domain_files[dom].append(hf)

        for dom, files in domain_files.items():
            dom_dir = cat_dir / dom
            dom_dir.mkdir(parents=True, exist_ok=True)
            for hf in files:
                dest = dom_dir / hf.name
                if dest.exists():
                    continue
                shutil.move(str(hf), str(dest))
                moved_archive += 1

    # ── Move unknown files (keep by domain) ──
    moved_unknown = 0
    for domain, file_list in unknown_groups.items():
        dest_dir = PROJECT_ROOT / domain
        dest_dir.mkdir(parents=True, exist_ok=True)
        for hf, url in file_list:
            if hf.parent == dest_dir:
                continue
            dest = dest_dir / hf.name
            if dest.exists():
                continue
            shutil.move(str(hf), str(dest))
            moved_unknown += 1

    print(f"\n  Project dirs created: {created}")
    print(f"  Project files moved: {moved_project}")
    print(f"  Archive files moved: {moved_archive}")
    print(f"  Unknown files moved: {moved_unknown}")

    # Remove empty directories
    removed = 0
    for d in sorted(Path('.').iterdir()):
        if not d.is_dir() or d.name in SPECIAL_DIRS or d.name.startswith('.'):
            continue
        try:
            remaining = list(d.rglob('*'))
            if not remaining:
                d.rmdir()
                removed += 1
                print(f"  Removed empty: {d.name}/")
        except OSError:
            pass

    print(f"  Empty directories removed: {removed}")

    # Auto-update archive navigation if files were moved to archive
    if moved_archive > 0:
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
            pass


if __name__ == '__main__':
    main()
