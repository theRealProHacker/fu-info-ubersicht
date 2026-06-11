#!/usr/bin/env python3
"""
Download profile pictures for FU Informatik Institut members.
Saves images to research/images/ folder.
"""

import json
import os
import re
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

# Headers to mimic browser request
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
    'Accept-Language': 'de-DE,de;q=0.9,en;q=0.8',
    'Referer': 'https://www.mi.fu-berlin.de/',
}

# Profile picture URLs live in research/profile_pics.json (shared with
# research/fill_missing.py, which appends newly found URLs there).
PROFILE_PICS_PATH = Path(__file__).parent / 'research' / 'profile_pics.json'


def load_profile_pics() -> dict:
    with open(PROFILE_PICS_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def download_image(url: str, save_path: Path) -> bool:
    """Download image from URL and save to path."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        
        # Check if we got an image
        content_type = response.headers.get('Content-Type', '')
        if 'image' not in content_type and 'octet-stream' not in content_type:
            print(f"  ⚠ Not an image: {content_type}")
            return False
        
        save_path.write_bytes(response.content)
        print(f"  ✓ Saved: {save_path.name} ({len(response.content)} bytes)")
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"  ✗ Error: {e}")
        return False


def get_extension(url: str, content_type: str = '') -> str:
    """Get file extension from URL or content type."""
    # Try URL first
    path = urlparse(url).path
    ext = Path(path).suffix.lower()
    if ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
        return ext
    
    # Try content type
    if 'jpeg' in content_type or 'jpg' in content_type:
        return '.jpg'
    elif 'png' in content_type:
        return '.png'
    elif 'gif' in content_type:
        return '.gif'
    elif 'webp' in content_type:
        return '.webp'
    
    return '.jpg'  # Default


def main():
    # Setup paths
    script_dir = Path(__file__).parent
    images_dir = script_dir / 'research' / 'images'
    json_path = script_dir / 'research' / 'fu-informatik-data.json'

    images_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("FU Informatik - Profilbilder Download")
    print("=" * 60)

    # Load JSON data
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    profile_pics = load_profile_pics()

    downloaded = 0
    failed = 0
    skipped = 0

    print(f"\nChecking {len(profile_pics)} known profile pictures...\n")

    for person_id, url in profile_pics.items():
        print(f"[{person_id}]")
        
        # Check if person exists in data
        person = next((p for p in data['personen'] if p['id'] == person_id), None)
        if not person:
            print(f"  ⚠ Person not found in JSON")
        
        # Get extension from URL
        ext = get_extension(url)
        save_path = images_dir / f"{person_id}{ext}"
        
        # Skip if already downloaded
        if save_path.exists():
            print(f"  → Already exists: {save_path.name}")
            skipped += 1
            continue
        
        # Download
        if download_image(url, save_path):
            downloaded += 1
        else:
            failed += 1
        
        # Be nice to the server
        time.sleep(0.5)
    
    print("\n" + "=" * 60)
    print(f"Done! Downloaded: {downloaded}, Failed: {failed}, Skipped: {skipped}")
    print(f"Images saved to: {images_dir}")
    print("=" * 60)
    
    # Update JSON with local image paths. Stamp profilbild only for images
    # that actually exist on disk — a failed download must never produce a
    # broken path, and a file left by an earlier run still gets stamped.
    print("\nUpdating JSON with local image paths...")
    stamped = 0
    for person in data['personen']:
        if person['id'] in profile_pics:
            ext = get_extension(profile_pics[person['id']])
            image_path = images_dir / f"{person['id']}{ext}"
            if image_path.exists():
                person['profilbild'] = f"research/images/{person['id']}{ext}"
                stamped += 1

    tmp_path = json_path.with_suffix('.json.tmp')
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    os.replace(tmp_path, json_path)
    print(f"✓ JSON updated: {stamped} profilbild paths set")


if __name__ == '__main__':
    main()
