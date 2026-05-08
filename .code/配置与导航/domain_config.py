#!/usr/bin/env python3
"""
Domain configuration loader.
Reads domain mappings from domain_config.json — a pure data file.
No domain rules are hardcoded here. Edit the JSON file to adjust mappings.

JSON structure:
{
  "project": { "domain": "目录名", ... }   ← 走流程
  "archive": { "domain": "类别名", ... }  ← 只分类
}

Archive files go to: ../Project-20260303-分类存档/<类别>/<域名>/
Project files stay in: <项目根>/<目录名>/
Unknown domains → create <域名>/ directory in project root.
"""
import json
from pathlib import Path

_CONFIG_PATH = Path(__file__).resolve().parent / 'domain_config.json'


def _load():
    with open(_CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def _get_mappings():
    data = _load()
    return data.get('project', {}), data.get('archive', {})


# Loaded on import — cached for the session
_project, _archive = _get_mappings()

# Expose as module-level dicts for backward compatibility
DOMAIN_TO_DIR = _project
DOMAIN_ARCHIVE = _archive


def classify_domain(domain: str) -> tuple:
    """
    Classify a domain.
    Returns (target_type, target_name)
      - target_type: 'project' | 'archive' | 'unknown'
      - target_name: directory name, category name, or None
    """
    # Exact match
    if domain in _project:
        return ('project', _project[domain])
    if domain in _archive:
        return ('archive', _archive[domain])

    # Strip www.
    clean = domain[4:] if domain.startswith('www.') else domain
    if clean and clean in _project:
        return ('project', _project[clean])
    if clean and clean in _archive:
        return ('archive', _archive[clean])

    # Try bare domain (strip subdomain for 3+ part domains)
    parts = clean.split('.')
    if len(parts) >= 3:
        bare = '.'.join(parts[1:])
        if bare in _project:
            return ('project', _project[bare])
        if bare in _archive:
            return ('archive', _archive[bare])

    return ('unknown', None)


def reload():
    """Reload config from JSON (useful after editing)."""
    global _project, _archive, DOMAIN_TO_DIR, DOMAIN_ARCHIVE
    _project, _archive = _get_mappings()
    DOMAIN_TO_DIR = _project
    DOMAIN_ARCHIVE = _archive
