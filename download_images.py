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

# Known profile picture URLs (verified via local HTML analysis of faculty page)
PROFILE_PICS = {
    # Active Professors
    'goehring-daniel': 'https://www.mi.fu-berlin.de/inf/_faculty/profs/photo-daniel-goehring.jpg',
    'jahn-katharina': 'https://www.mi.fu-berlin.de/inf/_faculty/profs/photo-katharina-jahn.jpg',
    'kozma-laszlo': 'https://www.mi.fu-berlin.de/inf/_faculty/profs/photo-laszlo-kozma.png',
    'landgraf-tim': 'https://www.mi.fu-berlin.de/inf/groups/ag-ki/_images/Tim_Landgraf_2021.jpg',
    'margraf-marian': 'https://www.mi.fu-berlin.de/inf/_faculty/profs/photo-marian-margraf.jpg',
    'mueller-birn-claudia': 'https://www.mi.fu-berlin.de/inf/_faculty/profs/photo-claudia-mueller-birn.jpg',
    'mulzer-wolfgang': 'https://www.mi.fu-berlin.de/inf/_faculty/profs/photo-wolfgang-mulzer.jpg',
    'paschke-adrian': 'https://www.mi.fu-berlin.de/inf/_faculty/profs/photo-adrian-paschke.jpg',
    'prechelt-lutz': 'https://www.mi.fu-berlin.de/inf/_faculty/profs/photo-lutz-prechelt.jpg',
    'reinert-knut': 'https://www.mi.fu-berlin.de/inf/_faculty/profs/photo-knut-reinert.jpg',
    'romeike-ralf': 'https://www.mi.fu-berlin.de/inf/_faculty/profs/photo-ralf-romeike.jpg',
    'rote-guenter': 'https://www.mi.fu-berlin.de/inf/_faculty/profs/photo-guenter-rote.jpg',
    'roth-volker': 'https://www.mi.fu-berlin.de/inf/_faculty/profs/photo-volker-roth.jpg',
    'schiller-jochen': 'https://www.mi.fu-berlin.de/inf/_faculty/profs/photo-jochen-schiller.jpg',
    'schwarz-heiko': 'https://www.mi.fu-berlin.de/inf/_faculty/profs/photo-heiko-schwarz.jpg',
    'voisard-agnes': 'https://www.mi.fu-berlin.de/inf/_faculty/profs/photo-agnes-voisard.jpg',
    'wolter-katinka': 'https://www.mi.fu-berlin.de/inf/_faculty/profs/photo-katinka-wolter.jpg',

    # Associate/Honorary
    'baccelli-emmanuel': 'https://www.mi.fu-berlin.de/inf/_faculty/lecturers/photo-emmanuel-baccelli.jpg',
    'benzmueller-christoph': 'https://www.mi.fu-berlin.de/inf/_faculty/lecturers/photo-christoph-benzmueller.jpg',
    'eichler-joern': 'https://www.mi.fu-berlin.de/inf/_faculty/lecturers/Eichler-klein.jpg',
    'wunder-gerhard': 'https://www.mi.fu-berlin.de/inf/_faculty/lecturers/photo-gerhard-wunder.jpg',

    # Emeriti
    'alt-helmut': 'https://www.mi.fu-berlin.de/inf/_faculty/emeritus/photo-alt.jpg',
    'rojas-raul': 'https://www.mi.fu-berlin.de/inf/_faculty/emeritus/photo-raul-rojas.jpg',
}


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
    
    downloaded = 0
    failed = 0
    skipped = 0
    
    print(f"\nChecking {len(PROFILE_PICS)} known profile pictures...\n")
    
    for person_id, url in PROFILE_PICS.items():
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
    
    # Update JSON with local image paths
    if downloaded > 0:
        print("\nUpdating JSON with local image paths...")
        for person in data['personen']:
            if person['id'] in PROFILE_PICS:
                ext = get_extension(PROFILE_PICS[person['id']])
                person['profilbild'] = f"research/images/{person['id']}{ext}"
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print("✓ JSON updated with profilbild paths")


if __name__ == '__main__':
    main()
