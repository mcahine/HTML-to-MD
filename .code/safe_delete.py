"""Safe file/directory deletion via Recycle Bin (Windows)."""
import sys
from pathlib import Path
from send2trash import send2trash

def safe_delete(path):
    """Move file or directory to Recycle Bin."""
    p = Path(path)
    if not p.exists():
        print(f'Not found: {path}')
        return False
    send2trash(str(p))
    print(f'Trashed: {path}')
    return True

if __name__ == '__main__':
    for arg in sys.argv[1:]:
        safe_delete(arg)
