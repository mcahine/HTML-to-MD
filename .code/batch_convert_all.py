#!/usr/bin/env python3
"""
Universal batch HTML-to-Markdown converter.
Converts ALL HTML files in site directories to clean, uniform Markdown.

Output layout:
  {site_dir}/file.md               ← alongside .html
  {site_dir}/assets/file_assets/   ← images extracted from Base64

Strategy:
  Run from project root. Custom converters that create subdirectories
  receive output_dir='.' so their subdir resolves to ./site_dir/.
  Simple config converters use base class convert() with default
  output_dir (html_path.parent → outputs alongside .html).
  Directory name mismatches are resolved by moving files post-conversion.
"""

import os
import sys
import io
import shutil
import traceback
from pathlib import Path

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONVERTERS_DIR = Path(__file__).resolve().parent
os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(CONVERTERS_DIR))


def safe_print(msg):
    try:
        print(msg)
    except:
        pass


# ── Converter registry ───────────────────────────────────────────
# (dir_name, module, class, output_subdir, call_style)
# call_style:
#   'convert_file'     → converter.convert_file(str(html_path))
#   'convert_root'     → converter.convert(str(html_path), output_dir='.')
#   'convert_simple'   → converter.convert(str(html_path))  (base class, outputs alongside)
CONVERTERS = [
    ('财联社',       'convert_cailianshe', 'CaiLianSheConverter',       '财联社',       'convert_root'),
    ('人人都是产品经理', 'convert_woshipm',   'WoshipmHtmlToMarkdownConverter', '人人都是产品经理', 'convert_file'),
    ('界面新闻',      'convert_jiemian',    'JiemianConverter',          '界面新闻',      'convert_file'),
    ('IT之家',       'convert_ithome',     'ITHomeConverter',           'IT之家',       'convert_root'),
    ('观察者网',      'convert_guancha',    'GuanchaConverter',          '观察者网',      'convert_file'),
    ('掘金',         'convert_juejin',     'JuejinConverter',           '掘金',         'convert_simple'),
    ('爱范儿',       'convert_ifanr',      'IfanrConverter',            '爱范儿',       'convert_root'),
    ('中国政府网',    'convert_gov_cn',     'GovCnConverter',            '中国政府网',    'convert_root'),
    ('微信公众号',    'convert_weixin',     'WeixinConverter',           'mp_weixin_qq_com', 'convert_root'),
    ('东西智库',      'convert_dx2035',     'DX2035Converter',           '东西智库',      'convert_root'),
    ('中国日报',      'convert_chinadaily', 'ChinaDailyConverter',       '中国日报网',    'convert_root'),
    ('宝玉的分享',    'convert_baoyu',      'BaoyuConverter',            '宝玉的分享',    'convert_root'),
    ('新华网',       'convert_news_cn',     'NewsCnConverter',           '新华网',       'convert_root'),
    ('国家发展改革委', 'convert_ndrc',      'NDRCConverter',             '国家发展改革委', 'convert_simple'),
    ('张鑫旭',       'convert_zhangxinxu', 'ZhangxinxuConverter',       'zhangxinxu_com', 'convert_root'),
    ('少数派',       'convert_sspai',      'SspaiConverter',            'sspai_com',    'convert_root'),
    ('美团',         'convert_meituan_tech','MeituanTechConverter',      'tech_meituan_com', 'convert_root'),
    ('工信部',       'convert_miit',       'MIITConverter',             '工信部',       'convert_simple'),
    ('虎嗅',         'convert_huxiu',      'HuxiuConverter',            '虎嗅',         'convert_root'),
    ('求是网',       'convert_qstheory',   'QstheoryConverter',         '求是网',       'convert_root'),
    ('知乎专栏',     'convert_zhihu',      'ZhihuConverter',            'zhihu_com',    'convert_root'),
    ('树莓派实验室',  'convert_shumeipai',  'ShumeipaiConverter',        'shumeipai_nxez_com', 'convert_root'),
    ('七猫',         'convert_qimao_tech', 'QimaoTechConverter',        'tech_qimao_com', 'convert_root'),
    ('果壳',         'convert_guokr',      'GuokrConverter',            '果壳',          'convert_simple'),
    ('阮一峰',       'convert_ruanyifeng', 'RuanyifengConverter',       '阮一峰',        'convert_simple'),
    # New sites (2026-05) — generic converter
    ('机核',         'convert_gcores',    'GcoresConverter',           '机核',          'convert_simple'),
    ('机器之心',     'convert_jiqizhixin','JiqizhixinConverter',       '机器之心',      'convert_simple'),
    ('36氪',         'convert_36kr',       'Kr36Converter',             '36氪',          'convert_simple'),
    ('极客公园',     'convert_geekpark',  'GeekparkConverter',         '极客公园',      'convert_simple'),
    ('小众软件',     'convert_appinn',    'AppinnConverter',           '小众软件',      'convert_simple'),
    ('游研社',       'convert_generic',    'GenericConverter',          '游研社',        'convert_simple'),

    ('一日一技',     'convert_kingname',  'KingnameConverter',         '一日一技',      'convert_simple'),
    ('华尔街见闻',   'convert_generic',    'GenericConverter',          '华尔街见闻',    'convert_simple'),
    ('BiliBili',     'convert_generic',    'GenericConverter',          'BiliBili',      'convert_simple'),
    ('动点科技',     'convert_technode',   'TechnodeConverter',         '动点科技',      'convert_simple'),
]


def import_converter(module_name, class_name):
    mod = __import__(f'converters.{module_name}', fromlist=[class_name])
    return getattr(mod, class_name)()


def move_output(src_dir, dst_dir):
    """Move .md and assets/ from src_dir into dst_dir (merge)."""
    src = Path(src_dir)
    dst = Path(dst_dir)
    if not src.exists():
        return 0, 0

    md_moved = 0
    for md_file in src.glob('*.md'):
        shutil.move(str(md_file), str(dst / md_file.name))
        md_moved += 1

    asset_moved = 0
    src_assets = src / 'assets'
    if src_assets.is_dir():
        dst_assets = dst / 'assets'
        dst_assets.mkdir(parents=True, exist_ok=True)
        for item in src_assets.iterdir():
            dst_item = dst_assets / item.name
            if dst_item.exists():
                if dst_item.is_dir():
                    shutil.rmtree(str(dst_item))
                else:
                    dst_item.unlink()
            shutil.move(str(item), str(dst_item))
        src_assets.rmdir()
        asset_moved = 1

    # Clean up empty src dir
    try:
        remaining = list(src.rglob('*'))
        if not remaining:
            shutil.rmtree(str(src))
    except OSError:
        pass

    return md_moved, asset_moved


def run_all():
    total_ok = 0
    total_fail = 0

    safe_print("=" * 60)
    safe_print("  Batch HTML -> Markdown Conversion")
    safe_print(f"  Project root: {PROJECT_ROOT}")
    safe_print("=" * 60)

    for dir_name, mod_name, cls_name, out_subdir, style in CONVERTERS:
        html_dir = PROJECT_ROOT / dir_name
        if not html_dir.is_dir():
            continue

        html_files = sorted(html_dir.glob('*.html'))
        if not html_files:
            continue

        n = len(html_files)
        safe_print(f"\n{'─' * 55}")
        safe_print(f"  [{dir_name}]  {n} files  ({style})")
        safe_print(f"{'─' * 55}")

        try:
            conv = import_converter(mod_name, cls_name)
        except Exception as e:
            safe_print(f"  [FATAL] Import error: {e}")
            total_fail += n
            continue

        # Bypass site-domain checks — files are already in the correct directory
        for method_name in ('is_woshipm_site', 'is_jiemian_site', 'is_guancha_site'):
            if hasattr(conv, method_name):
                setattr(conv, method_name, lambda soup, m=method_name: True)

        ok = 0
        fail = 0

        for i, hf in enumerate(html_files, 1):
            try:
                if style == 'convert_file':
                    result = conv.convert_file(hf)       # expects Path
                elif style == 'convert_root':
                    result = conv.convert(str(hf), output_dir='.')
                else:  # convert_simple
                    result = conv.convert(str(hf))

                if result:
                    ok += 1
                else:
                    fail += 1
                    # Print failures for small batches
                    if n <= 10:
                        safe_print(f"  [{i}/{n}] FAIL: {hf.name}")

            except Exception as e:
                safe_print(f"  [{i}/{n}] ERROR: {hf.name} — {e}")
                fail += 1

        # Handle output directory name mismatch
        if out_subdir != dir_name:
            src = PROJECT_ROOT / out_subdir
            if src.is_dir():
                md_count, _ = move_output(src, html_dir)
                if md_count > 0:
                    safe_print(f"  Moved {md_count} files: '{out_subdir}' -> '{dir_name}'")

        status = f"{ok} ok" if fail == 0 else f"{ok} ok, {fail} fail"
        safe_print(f"  => {status}")
        total_ok += ok
        total_fail += fail

    total = total_ok + total_fail
    safe_print(f"\n{'=' * 60}")
    safe_print(f"  TOTAL: {total_ok}/{total} converted")
    if total_fail > 0:
        safe_print(f"  Failed: {total_fail}")
    safe_print(f"{'=' * 60}")


if __name__ == '__main__':
    run_all()
