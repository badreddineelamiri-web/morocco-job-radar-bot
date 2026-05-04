"""Download Arabic fonts for image generation."""

import os
from pathlib import Path
import urllib.request

FONTS_DIR = Path("assets/fonts")
FONTS_DIR.mkdir(parents=True, exist_ok=True)

# Font URLs (using Google Fonts CDN)
FONTS = {
    "Cairo-Regular.ttf": "https://fonts.gstatic.com/s/cairo/v28/SLXGc1nY6Hkvalh0l5FosEyjQ.ttf",
    "Cairo-Bold.ttf": "https://fonts.gstatic.com/s/cairo/v28/SLXGc1nY6Hkvalh0l5FosEyjQ.ttf",  # Same as regular, will use different weight
    "Tajawal-Regular.ttf": "https://fonts.gstatic.com/s/tajawal/v9/Iura6YBj_oY6U6S7Bv7aaz8.ttf",
    "Tajawal-Bold.ttf": "https://fonts.gstatic.com/s/tajawal/v9/Iura6YBj_oY6U6S7Bv7aaz8.ttf",  # Same as regular
}

def download_font(filename: str, url: str) -> bool:
    """Download a font file."""
    filepath = FONTS_DIR / filename
    if filepath.exists():
        print(f"✓ {filename} already exists")
        return True
    
    try:
        print(f"Downloading {filename}...")
        urllib.request.urlretrieve(url, filepath)
        print(f"✓ Downloaded {filename}")
        return True
    except Exception as e:
        print(f"✗ Failed to download {filename}: {e}")
        return False

if __name__ == "__main__":
    print("Downloading Arabic fonts...")
    success_count = 0
    for filename, url in FONTS.items():
        if download_font(filename, url):
            success_count += 1
    
    print(f"\nDownloaded {success_count}/{len(FONTS)} fonts")
    
    # List downloaded fonts
    print("\nAvailable fonts:")
    for font_file in FONTS_DIR.glob("*.ttf"):
        print(f"  - {font_file.name}")
