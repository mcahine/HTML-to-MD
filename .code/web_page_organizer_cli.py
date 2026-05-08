#!/usr/bin/env python3
"""
Web Page Organizer CLI - 网页分类整理工具

自动将下载的HTML网页按域名分类存放，使用中文文件夹名。

用法:
    python web_page_organizer_cli.py [源目录] [选项]

选项:
    -o, --output      输出目录
    -d, --domains     只处理指定域名
    -m, --move        移动而非复制
    --no-chinese      不使用中文文件夹名
    -q, --quiet       静默模式

示例:
    # 基本用法（整理当前目录）
    python web_page_organizer_cli.py

    # 指定源目录和输出目录
    python web_page_organizer_cli.py ./downloads -o ./organized

    # 只处理特定网站
    python web_page_organizer_cli.py ./downloads -d woshipm.com jiemian.com

    # 移动文件而非复制
    python web_page_organizer_cli.py ./downloads -m

    # 使用域名作为文件夹名（不用中文）
    python web_page_organizer_cli.py ./downloads --no-chinese
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from web_page_organizer.main import main

if __name__ == '__main__':
    sys.exit(main())
