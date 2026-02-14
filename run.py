import sys
import os

# Proje kök dizinini ve src dizinini ekle
root_path = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(root_path, "src"))

from main import main

if __name__ == "__main__":
    main()