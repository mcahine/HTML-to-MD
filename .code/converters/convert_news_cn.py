#!/usr/bin/env python3
"""新华网 (news.cn) HTML 转 Markdown 转换器"""
import sys
import os
import re
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from html_converter_base import safe_print


class NewsCnConverter:
    """新华网 HTML 转 Markdown 转换器"""
    
    def __init__(self):
        self.domain = 'news.cn'
        self.name = '新华网'
    
    def extract_metadata(self, soup, html_path):
        """提取文章元数据"""
        metadata = {
            'title': '',
            'author': '',
            'date': '',
            'source': '新华网',
            'url': '',
            'converted_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # 提取标题
        title_elem = soup.find('h1') or soup.select_one('.title') or soup.select_one('.headline')
        if title_elem:
            metadata['title'] = title_elem.get_text(strip=True)
        
        # 提取作者/来源
        source_elem = soup.select_one('.source') or soup.select_one('.author')
        if source_elem:
            metadata['author'] = source_elem.get_text(strip=True)
        else:
            metadata['author'] = '来源：新华网'
        
        # 提取日期 - 优先从meta标签获取
        # 1. 尝试 publishdate meta 标签
        meta_date = soup.find('meta', attrs={'name': 'publishdate'})
        if meta_date:
            metadata['date'] = meta_date.get('content', '').strip()
        
        # 2. 从HTML元素提取（检查是否为日期格式而非时间）
        if not metadata['date']:
            time_elem = soup.select_one('.time') or soup.select_one('.publish-time')
            if time_elem:
                date_text = time_elem.get_text(strip=True)
                # 只提取 YYYY-MM-DD 或 YYYY/MM/DD 格式（避免提取到时间如06:29:47）
                date_match = re.search(r'(\d{4})[-/](\d{2})[-/](\d{2})', date_text)
                if date_match:
                    metadata['date'] = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
        
        # 3. 从文件名提取日期作为备选
        if not metadata['date']:
            filename = os.path.basename(html_path)
            date_match = re.search(r'(\d{4})(\d{2})(\d{2})', filename)
            if date_match:
                metadata['date'] = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
        
        # 提取URL
        og_url = soup.find('meta', property='og:url')
        if og_url:
            metadata['url'] = og_url.get('content', '')
        
        return metadata
    
    def extract_content(self, soup):
        """提取文章正文"""
        content = soup.select_one('#detail') or soup.select_one('#detailContent') or soup.select_one('.detail-content')
        return content
    
    def process_content(self, content_elem):
        """处理内容，提取视频并清理播放器UI"""
        # 首先处理视频：查找并替换视频区域
        content_str = str(content_elem)
        seen_videos = set()
        video_blocks = []
        
        # 提取所有.mp4 URL
        mp4_urls = re.findall(r'https?://[^\s"<>]+\.mp4', content_str)
        
        for url in mp4_urls:
            if url in seen_videos:
                continue
            seen_videos.add(url)
            
            # 创建视频HTML块
            video_html = f'<video src="{url}" controls width="100%" style="max-width: 640px;"></video>'
            video_blocks.append(video_html)
        
        # 移除包含视频URL和播放器UI的脚本/样式区域
        for script in content_elem.find_all(['script', 'style']):
            script.decompose()
        
        # 收集所有段落文本
        paragraphs = []
        seen_texts = set()
        
        # 查找所有段落
        for p in content_elem.find_all('p'):
            text = p.get_text(strip=True)
            
            # 过滤空文本
            if not text:
                continue
            
            # 过滤播放器UI文本
            if self.is_player_ui(text):
                continue
            
            # 过滤版权信息
            if any(keyword in text for keyword in ['Copyright', '版权所有', '制作单位', '【纠错】', '【责任编辑']):
                continue
            
            # 过滤包含视频URL的文本（已用video标签替代）
            has_video_url = any(url in text for url in mp4_urls)
            if has_video_url:
                continue
            
            # 清理文本
            text = re.sub(r'\s+', ' ', text)
            
            # 去重
            if text in seen_texts:
                continue
            seen_texts.add(text)
            
            paragraphs.append(text)
        
        # 合并视频和段落（视频放在最前面，或者根据位置插入）
        # 这里简化处理：视频放在最前面
        result = video_blocks + paragraphs
        
        return result
    
    def is_player_ui(self, text):
        """检查是否是播放器UI文本"""
        ui_patterns = [
            r'^Play Video$',
            r'^Play Video\s*\d*:\d+',
            r'^\d:\d{2}$',
            r'^/\d:\d{2}$',
            r'^\d*:\d+/\d*:\d+$',
            r'^0:\d{2}/\d:\d{2}$',
        ]
        for pattern in ui_patterns:
            if re.match(pattern, text.strip()):
                return True
        return False
    
    def convert(self, html_path, output_dir=None):
        """转换单个HTML文件"""
        if not os.path.exists(html_path):
            safe_print(f"File not found: {html_path}")
            return False
        
        if output_dir is None:
            output_dir = os.path.dirname(html_path) or '.'
        
        # 使用'新华网'作为输出目录名
        domain_dir = os.path.join(output_dir, '新华网')
        os.makedirs(domain_dir, exist_ok=True)
        
        try:
            from bs4 import BeautifulSoup
            with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
                soup = BeautifulSoup(f.read(), 'lxml')
        except Exception as e:
            safe_print(f"Parse HTML failed: {e}")
            return False
        
        metadata = self.extract_metadata(soup, html_path)
        content_elem = self.extract_content(soup)
        
        if not content_elem:
            safe_print(f"Content not found: {html_path}")
            return False
        
        # 处理内容
        paragraphs = self.process_content(content_elem)
        
        # 合并为Markdown
        md_content = '\n\n'.join(paragraphs)
        
        # 清理多余空行
        md_content = re.sub(r'\n{3,}', '\n\n', md_content.strip())
        
        # 构建 YAML Front Matter
        yaml_lines = ["---"]
        yaml_lines.append(f"title: {metadata['title']}")
        if metadata['author']:
            yaml_lines.append(f"author: {metadata['author']}")
        if metadata['date']:
            yaml_lines.append(f"date: {metadata['date']}")
        yaml_lines.append(f"source: {metadata['source']}")
        if metadata['url']:
            yaml_lines.append(f"url: {metadata['url']}")
        yaml_lines.append(f"converted_at: {metadata['converted_at']}")
        yaml_lines.append("---")
        yaml_lines.append("")
        
        # 写入文件
        base_name = Path(html_path).stem
        md_path = os.path.join(domain_dir, f"{base_name}.md")
        
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(yaml_lines) + '\n' + md_content)
        
        safe_print(f"Converted: {md_path}")
        return True
    
    def batch_convert(self, input_dir, output_dir=None):
        """批量转换"""
        if output_dir is None:
            output_dir = input_dir
        
        import glob
        html_files = glob.glob(os.path.join(input_dir, "*新华网*.html"))
        success_count = 0
        
        safe_print(f"\n=== 新华网 ({self.domain}) ===")
        safe_print(f"Found {len(html_files)} HTML files")
        
        for html_file in html_files:
            if self.convert(html_file, output_dir):
                success_count += 1
        
        safe_print(f"\nCompleted: {success_count}/{len(html_files)}")
        return success_count


if __name__ == '__main__':
    converter = NewsCnConverter()
    if len(sys.argv) > 1:
        if sys.argv[1].endswith('.html'):
            converter.convert(sys.argv[1])
        else:
            converter.batch_convert(sys.argv[1])
    else:
        converter.batch_convert(r'C:/Users/D-001/Downloads/HTML')
