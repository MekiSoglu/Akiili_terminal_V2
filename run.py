import sys
import os

# src/ dizinini path'e ekle — böylece "from core.X" çalışır
src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# tools/ dizinini de ekle — tool_selector için
tools_dir = os.path.join(src_dir, "tools")
if tools_dir not in sys.path:
    sys.path.insert(0, tools_dir)

from src.main import main

if __name__ == "__main__":
    main()