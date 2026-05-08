#!/usr/bin/env python3
"""
Navigation page generator & server.

Two modes:
  1. Server  (default)  → python 导航.py [--all]
     Browse the project (and optionally the archive) live via HTTP.

  2. Generate            → python 导航.py --generate <dir>
     Write a static 导航.html into <dir>, covering its full directory tree.
     Called automatically by classify scripts after moving files to archive.

Output: 导航.html sits in the scanned directory root, opens in any browser.
The tree is built from the actual filesystem — add/remove files, re-run to update.
"""
import json
import os
import socket
import sys
import threading
import webbrowser
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent.parent
ARCHIVE_ROOT = PROJECT_ROOT.parent / 'Project-20260303-分类存档'
SKIP_DIRS = {'__pycache__', '.git', '.claude', '.docx', 'assets'}


# ── Shared tree scanning ────────────────────────────────────────────

def scan_dir(path, base_path, serve_idx=None):
    """Recursively scan a directory tree. Returns list of {name, path?, children?}.
    If serve_idx is given, leaf nodes get a `servePath` for the HTTP server.
    Otherwise leaf nodes get a plain `path` (relative to base) for static mode.
    """
    entries = []
    try:
        items = sorted(path.iterdir())
    except OSError:
        return entries

    for item in items:
        name = item.name
        if name.startswith('.') or name in SKIP_DIRS or name == '导航.html':
            continue

        if item.is_dir():
            children = scan_dir(item, base_path, serve_idx)
            if children:
                entries.append({'name': name, 'children': children})
        elif item.suffix.lower() in ('.html', '.md'):
            rel = item.relative_to(base_path).as_posix()
            name = item.stem
            # Get title: MD → YAML front matter, HTML → <title> tag
            if item.suffix == '.md':
                try:
                    with open(item, 'r', encoding='utf-8') as f:
                        for line in f:
                            if line.startswith('title:'):
                                t = line[6:].strip().strip('"').strip("'")
                                if t: name = t
                                break
                except Exception: pass
            elif item.suffix == '.html':
                try:
                    import re as _re
                    with open(item, 'r', encoding='utf-8', errors='ignore') as f:
                        html_text = f.read(4000)
                    m = _re.search(r'<title[^>]*>(.+?)</title>', html_text, _re.I)
                    if m:
                        t = m.group(1).strip()
                        # Remove HTML entities and sanitize
                        t = t.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '\"')
                        t = t.replace('&nbsp;', ' ')
                        t = _re.sub(r'<[^>]+>', '', t)  # strip any nested tags
                        t = t.replace('\\n', ' ').replace('\\r', ' ').replace('\\t', ' ').replace('\"', '\"')
                        if t and len(t) > 2: name = t[:120]
                except Exception: pass
            leaf = {'name': name}
            if serve_idx is not None:
                leaf['servePath'] = f'/file/{serve_idx}/{rel}'
            else:
                leaf['path'] = rel
            entries.append(leaf)

    # Flatten: if a dir has exactly 1 child that is itself a dir, merge
    result = []
    for entry in entries:
        if 'children' in entry and len(entry['children']) == 1:
            child = entry['children'][0]
            if 'children' in child:
                # Parent has 1 dir child → flatten: "类别 (域名)"
                merged = {'name': f"{entry['name']} ({child['name']})", 'children': child['children']}
                result.append(merged)
                continue
        result.append(entry)
    return result


# ── Static HTML page (shared by both modes) ─────────────────────────

def nav_html_page(title, tree_json, is_static=False):
    """Return full HTML string for the navigation page.
    tree_json is the JSON-encoded tree data.
    """
    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>{title}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{height:100%;font-family:-apple-system,"Microsoft YaHei",sans-serif;font-size:14px;background:#1a1a2e;color:#e0e0e0;overflow:hidden}}
.container{{display:flex;height:100%;width:100%}}
.sidebar{{width:320px;min-width:160px;height:100%;background:#16213e;border-right:1px solid #2a3a5c;display:flex;flex-direction:column;overflow:hidden}}
.sidebar-header{{padding:14px 12px 10px;border-bottom:1px solid #2a3a5c;flex-shrink:0}}
.sidebar-header h2{{font-size:15px;font-weight:600;color:#a0c4ff;white-space:nowrap}}
.sidebar-header .stats{{font-size:11px;color:#6a7a9a;margin-top:3px}}
.toggle-all{{margin-top:6px;display:flex;gap:4px;justify-content:space-between;align-items:center}}
.toggle-all .toggle-btn{{font-size:16px;cursor:pointer;color:#8899bb;opacity:0.6;line-height:1;user-select:none;transition:all 0.2s}}
.toggle-all .toggle-btn:hover{{opacity:1;color:#c0d0f0}}
.toggle-all .hide-btn{{font-size:14px;cursor:pointer;color:#8899bb;opacity:0.5;line-height:1;user-select:none;padding:0 2px}}
.toggle-all .hide-btn:hover{{opacity:1;color:#c0d0f0}}
.sidebar.hidden{{width:0!important;min-width:0!important;border:none;overflow:hidden}}
.sidebar.hidden>*{{display:none}}
.sidebar-toggle-float{{display:none;position:fixed;left:6px;top:10px;z-index:100;font-size:18px;cursor:pointer;color:#8899bb;opacity:0.5;background:#1a1a2e;padding:4px 8px;border-radius:4px;border:1px solid #2a3a5c}}
.sidebar-toggle-float:hover{{opacity:1;color:#c0d0f0}}
.sidebar-toggle-float.visible{{display:block}}
.nav-tree{{flex:1;overflow:auto;padding:6px 0}}
.tree-label{{display:flex;align-items:flex-start;padding:3px 6px;cursor:pointer;border-radius:0 4px 4px 0;margin:1px 6px 1px 0;word-break:break-word;white-space:normal;line-height:1.4;min-height:24px;transition:background .08s}}
.tree-label:hover{{background:#1e3050}}
.tree-label.active{{background:#2a4a7a;color:#fff}}
.tree-label .icon{{flex-shrink:0;width:16px;height:18px;display:flex;align-items:center;justify-content:center;font-size:10px;color:#8899bb;margin-right:4px}}
.tree-label .icon.folder{{color:#e0b040}}
.tree-label .text{{flex:1;min-width:0;padding-top:1px}}
.tree-children{{padding-left:14px}}
.tree-children.collapsed{{display:none}}
.depth-0{{font-weight:600;font-size:13px;color:#c0d0f0;padding-top:5px;padding-bottom:5px}}
.depth-1{{font-size:12px;color:#8ab4d8;padding-top:3px;padding-bottom:3px}}
.depth-2{{font-size:12px;color:#b0b8c8}}
.depth-3,.depth-4,.depth-5{{font-size:11px;color:#9098a8;padding-left:20px}}
.resizer{{width:4px;height:100%;background:#2a3a5c;cursor:col-resize;flex-shrink:0;position:relative;z-index:10}}
.resizer:hover,.resizer.active{{background:#4a7aba}}
.content{{flex:1;height:100%;display:flex;flex-direction:column;background:#1a1a2e;min-width:0}}
.content-header{{padding:8px 14px;border-bottom:1px solid #2a3a5c;flex-shrink:0;display:flex;align-items:center;gap:8px}}
.content-header .file-title{{font-size:12px;color:#a0c4ff;flex:1;word-break:break-word;white-space:normal;line-height:1.4}}
.open-external{{font-size:11px;color:#6a8aba;text-decoration:none;white-space:nowrap;padding:3px 8px;border:1px solid #3a5a7a;border-radius:3px;cursor:pointer;flex-shrink:0}}
.open-external:hover{{background:#2a3a5c;color:#a0c4ff}}
.content-frame{{flex:1;width:100%;border:none;background:#fff}}
.placeholder{{flex:1;display:flex;align-items:center;justify-content:center;color:#4a5a7a;font-size:14px;flex-direction:column;gap:8px}}
.nav-tree::-webkit-scrollbar{{width:5px;height:5px}}
.nav-tree::-webkit-scrollbar-track{{background:transparent}}
.nav-tree::-webkit-scrollbar-thumb{{background:#3a4a6a;border-radius:3px}}
.nav-tree::-webkit-scrollbar-thumb:hover{{background:#5a6a8a}}
</style>
</head>
<body>
<div class="sidebar-toggle-float" id="floatBtn" onclick="toggleSidebar()">&#9654;</div>
<div class="container">
<div class="sidebar" id="sidebar">
<div class="sidebar-header"><h2>{title}</h2><div class="stats" id="stats"></div><div class="toggle-all"><span class="toggle-btn" id="toggleBtn" onclick="smartToggle()" title="展开/折叠">&#9654;</span><span class="hide-btn" id="hideBtn" onclick="toggleSidebar()" title="隐藏/显示导航栏">&#9664;</span></div></div>
<div class="nav-tree" id="navTree"></div>
</div>
<div class="resizer" id="resizer"></div>
<div class="content" id="content">
<div class="content-header" id="contentHeader" style="display:none">
<span class="file-title" id="fileTitle"></span>
<a class="open-external" id="openExternal" href="#" target="_blank">外部打开</a>
</div>
<div class="placeholder" id="placeholder"><div>&#9776;</div><div>从左侧导航选择文件</div></div>
<iframe class="content-frame" id="contentFrame" style="display:none"></iframe>
</div>
</div>
<script>
var TREE = {tree_json};
var IS_STATIC = {'true' if is_static else 'false'};
var ICONS = ['▶','▼'];
var activeLabel = null;

function buildNav(roots){{
  var nav = document.getElementById('navTree');
  nav.innerHTML = '';
  var totalDirs = 0, totalFiles = 0;
  function render(nodes, parent, depth){{
    nodes.forEach(function(node, i){{
      var div = document.createElement('div');
      var id = 'n_'+depth+'_'+i+'_'+Math.random().toString(36).slice(2,6);
      var label = document.createElement('div');
      label.className = 'tree-label depth-'+Math.min(depth,5);
      if(node.children){{
        totalDirs++;
        var count = countFiles(node);
        label.innerHTML = '<span class="icon folder">'+ICONS[0]+'</span><span class="text">'+esc(node.name)+(count>0?' <span style="color:#6a7a9a;font-size:10px">('+count+')</span>':'')+'</span>';
        label.onclick = function(){{ toggle(id, label); }};
        var cd = document.createElement('div');
        cd.className = 'tree-children collapsed';
        cd.id = id;
        render(node.children, cd, depth+1);
        div.appendChild(label);
        div.appendChild(cd);
      }}else{{
        totalFiles++;
        label.innerHTML = '<span class="icon" style="color:#8899bb">&#9671;</span><span class="text">'+esc(node.name)+'</span>';
        label.title = node.name;
        label.onclick = function(){{ selectFile(node, label); }};
        div.appendChild(label);
      }}
      parent.appendChild(div);
    }});
  }}
  render(roots, nav, 0);
  document.getElementById('stats').textContent = totalDirs+' 个目录 / '+totalFiles+' 个文件';
}}

function countFiles(node){{ if(!node.children) return 0; var c=0; node.children.forEach(function(n){{ if(n.children) c+=countFiles(n); else c++; }}); return c; }}
function esc(s){{ var d=document.createElement('div'); d.textContent=s; return d.innerHTML; }}

function toggle(id, label){{
  var el = document.getElementById(id);
  if(!el) return;
  if(el.classList.contains('collapsed')){{ el.classList.remove('collapsed'); label.querySelector('.icon').textContent=ICONS[1]; }}
  else{{ el.classList.add('collapsed'); label.querySelector('.icon').textContent=ICONS[0]; }}
}}

function selectFile(node, label){{
  if(activeLabel) activeLabel.classList.remove('active');
  label.classList.add('active');
  activeLabel = label;
  document.getElementById('placeholder').style.display='none';
  document.getElementById('contentHeader').style.display='flex';
  document.getElementById('fileTitle').textContent=node.name;
  var frame=document.getElementById('contentFrame');
  frame.style.display='block';
  frame.src=IS_STATIC ? node.path : node.servePath;
  document.getElementById('openExternal').href=IS_STATIC ? node.path : node.servePath;
  var p=label.parentElement;
  while(p){{ if(p.classList.contains('tree-children')&&p.classList.contains('collapsed')){{ p.classList.remove('collapsed'); var pl=p.previousElementSibling; if(pl&&pl.classList.contains('tree-label')){{ var icon=pl.querySelector('.icon'); if(icon) icon.textContent=ICONS[1]; }}}} p=p.parentElement; }}
}}

// Resizer
(function(){{
  var sidebar=document.getElementById('sidebar'), resizer=document.getElementById('resizer'), dragging=false, startX, startW;
  resizer.onmousedown=function(e){{ dragging=true; startX=e.clientX; startW=sidebar.offsetWidth; resizer.classList.add('active'); document.body.style.cursor='col-resize'; document.body.style.userSelect='none'; e.preventDefault(); }};
  window.addEventListener('mousemove',function(e){{ if(!dragging) return; requestAnimationFrame(function(){{ var w=startW+(e.clientX-startX); if(w<160) w=160; if(w>window.innerWidth*0.55) w=window.innerWidth*0.55; sidebar.style.width=w+'px'; }}); }});
  window.addEventListener('mouseup',function(){{ if(dragging){{ dragging=false; resizer.classList.remove('active'); document.body.style.cursor=''; document.body.style.userSelect=''; }} }});
}})();

function smartToggle(){{
  var nodes=document.querySelectorAll('.tree-children');
  var allCollapsed=true;
  nodes.forEach(function(n){{ if(!n.classList.contains('collapsed')) allCollapsed=false; }});
  var btn=document.getElementById('toggleBtn');
  nodes.forEach(function(n){{ if(allCollapsed){{ n.classList.remove('collapsed'); }}else{{ n.classList.add('collapsed'); }} }});
  var icons=document.querySelectorAll('.tree-label .icon.folder');
  icons.forEach(function(i){{ i.textContent=allCollapsed?'▼':'▶'; }});
  btn.innerHTML=allCollapsed?'▼':'▶';
}}

function toggleSidebar(){{
  var sb=document.getElementById('sidebar');
  var btn=document.getElementById('hideBtn');
  var fb=document.getElementById('floatBtn');
  sb.classList.toggle('hidden');
  if(sb.classList.contains('hidden')){{
    btn.innerHTML='&#9654;'; fb.classList.add('visible');
  }}else{{
    btn.innerHTML='&#9664;'; fb.classList.remove('visible');
  }}
}}

buildNav(TREE);
</script>
</body>
</html>'''


# ══════════════════════════════════════════════════════════════════════
#  Mode 1: HTTP Server
# ══════════════════════════════════════════════════════════════════════

SERVER_HTML = nav_html_page('项目导航', '[]', is_static=False).replace(
    'var TREE = []',
    'var TREE = []; async function loadTree(){ try{ var r=await fetch("/api/tree"); var tree=await r.json(); document.getElementById("navTitle")&&(document.getElementById("navTitle").textContent=tree.title||"项目导航"); buildNav(tree.roots); }catch(e){ document.getElementById("stats").textContent="加载失败: "+e.message; } } loadTree();'
).replace(
    'buildNav(TREE);',
    '// Server mode — tree loaded via /api/tree'
)


class NavHandler(SimpleHTTPRequestHandler):
    serve_dirs = []

    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self._serve_html(SERVER_HTML)
        elif self.path == '/api/tree':
            self._serve_tree()
        elif self.path.startswith('/file/'):
            self._serve_file()
        else:
            super().do_GET()

    def _serve_html(self, content):
        data = content.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_tree(self):
        roots = []
        for idx, (name, root_path) in enumerate(self.serve_dirs):
            if not root_path.is_dir():
                continue
            children = scan_dir(root_path, root_path, idx)
            if children:
                roots.append({'name': name, 'children': children})
        title = ' / '.join(n for n, _ in self.serve_dirs)
        data = json.dumps({'title': title, 'roots': roots}, ensure_ascii=False).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_file(self):
        parts = self.path.split('/', 3)
        if len(parts) < 4:
            self.send_error(400); return
        try:
            idx = int(parts[2])
        except ValueError:
            self.send_error(400); return
        if idx < 0 or idx >= len(self.serve_dirs):
            self.send_error(404); return
        _, root_path = self.serve_dirs[idx]
        file_path = root_path / parts[3]
        if not file_path.is_file() or file_path.suffix.lower() != '.html':
            self.send_error(404); return
        try:
            content = file_path.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except OSError:
            self.send_error(500)

    def log_message(self, format, *args):
        pass


def _find_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('', 0))
    port = s.getsockname()[1]
    s.close()
    return port


def run_server(include_archive=False):
    NavHandler.serve_dirs = [('项目', PROJECT_ROOT)]
    if include_archive and ARCHIVE_ROOT.is_dir():
        NavHandler.serve_dirs.append(('分类存档', ARCHIVE_ROOT))

    port = _find_port()
    server = HTTPServer(('127.0.0.1', port), NavHandler)
    url = f'http://127.0.0.1:{port}/'
    print(f'导航服务: {url}')
    print(f'覆盖: {", ".join(n for n,_ in NavHandler.serve_dirs)}')
    print('按 Ctrl+C 停止')
    threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n已停止')
        server.shutdown()


# ══════════════════════════════════════════════════════════════════════
#  Mode 2: Static generator
# ══════════════════════════════════════════════════════════════════════

def generate_static(target_dir):
    """Generate a static 导航.html for the given directory.
    Called by classify scripts after moving files to archive.
    """
    target = Path(target_dir)
    if not target.is_dir():
        print(f'[导航] 目录不存在: {target}')
        return False

    tree = scan_dir(target, target)
    if not tree:
        print(f'[导航] 目录无 HTML 文件: {target}')
        return False

    title = target.name
    tree_json = json.dumps(tree, ensure_ascii=False)
    html = nav_html_page(title, tree_json, is_static=True)

    output = target / '导航.html'
    with open(output, 'w', encoding='utf-8') as f:
        f.write(html)

    file_count = sum(1 for _ in target.rglob('*.html'))
    dir_count = sum(1 for _ in target.rglob('*') if _.is_dir())
    print(f'[导航] {output}  ({dir_count} 目录, {file_count} 文件)')
    return True


# ══════════════════════════════════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    if '--generate' in sys.argv:
        idx = sys.argv.index('--generate')
        if idx + 1 < len(sys.argv):
            target = sys.argv[idx + 1]
        else:
            target = str(ARCHIVE_ROOT) if ARCHIVE_ROOT.is_dir() else str(PROJECT_ROOT)
        generate_static(target)
    else:
        include_archive = '--all' in sys.argv
        run_server(include_archive)
