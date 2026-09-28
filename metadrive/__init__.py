import sys
from pathlib import Path


_ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(_ROOT / "submodules" / "st-renderer" / "src"), str(_ROOT / "submodules" / "fast-gauss-paral")]
