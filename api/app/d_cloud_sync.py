"""
Standalone script to sync category 18 artworks from Divoom Cloud API.
Fetches artworks, maintains a local gallery file, and downloads/decodes them.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import requests

from servoom import DivoomClient, PixelBeanDecoder
from servoom.config import Config
from credentials import CONFIG_EMAIL, CONFIG_MD5_PASSWORD


# Constants
CATEGORY_ID = 18
BATCH_SIZE = 30
MAX_ARTWORKS = 1000

# Paths
SCRIPT_DIR = Path(__file__).parent
GALLERY_FILE = SCRIPT_DIR / "utils" / "gallery_18_cache.json"
DOWNLOAD_DIR = SCRIPT_DIR.parent / "divoom" / "download"
DECODE_DIR = SCRIPT_DIR.parent / "divoom" / "decode"

# Ensure directories exist
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
DECODE_DIR.mkdir(parents=True, exist_ok=True)


def load_gallery_file() -> List[Dict]:
    """Load the gallery JSON file, returning empty list if it doesn't exist."""
    if not GALLERY_FILE.exists():
        return []
    
    try:
        with open(GALLERY_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            return []
    except (json.JSONDecodeError, IOError) as e:
        print(f"[WARNING] Failed to load gallery file: {e}")
        return []


def save_gallery_file(artworks: List[Dict]) -> None:
    """Save the gallery JSON file."""
    GALLERY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(GALLERY_FILE, 'w', encoding='utf-8') as f:
        json.dump(artworks, f, indent=2, ensure_ascii=False)


def fetch_category_artworks(client: DivoomClient, category_id: int, max_count: int, batch_size: int) -> List[Dict]:
    """Fetch artworks from a category, up to max_count items."""
    print(f"Fetching up to {max_count} artworks from category {category_id} (batch size: {batch_size})...")
    
    all_artworks = []
    start_num = 1
    safety_limit = max_count * 2  # Safety stop at double the target (total fetched)
    total_fetched = 0  # Track total artworks fetched from API (before filtering)
    
    while len(all_artworks) < max_count:
        # Safety stop: if we've fetched double the target from API and still don't have enough collected, stop
        if total_fetched >= safety_limit:
            print(f"[WARNING] Safety limit reached: fetched {total_fetched} artworks from API but only collected {len(all_artworks)}/{max_count}")
            print(f"[WARNING] Stopping fetch to prevent infinite loop")
            break
        
        end_num = start_num + batch_size - 1
        
        payload = {
            "StartNum": start_num,
            "EndNum": end_num,
            "Classify": category_id,
            "FileSize": Config.FILE_SIZE_FILTER,
            "FileType": 5,
            "FileSort": 0,
            "Version": 12,
            "RefreshIndex": 0,
            'Token': client.token,
            'UserId': client.user_id,
        }
        
        try:
            resp = requests.post(
                Config.GET_CATEGORY_FILES_ENDPOINT,
                headers=client.HEADERS,
                json=payload,
                timeout=client._request_timeout
            )
            
            # Try to parse JSON response
            try:
                data = resp.json()
            except ValueError as e:
                print(f"\n  [ERROR] Failed to parse JSON response")
                print(f"  Status Code: {resp.status_code}")
                print(f"  Response Body (first 500 chars): {resp.text[:500]}")
                break
            
            # Check for errors
            if data.get('ReturnCode', 0) != 0:
                print(f"  [ERROR] Server returned error code: {data.get('ReturnCode')}")
                break
            
            # Check various possible field names for the files list
            files = data.get('FileList', data.get('CategoryFileList', []))
            
            if not files:
                print(f"  No more files available. Stopping fetch.")
                break
            
            # Track total fetched before filtering
            total_fetched += len(files)
            
            # Filter out hidden artworks
            filtered_files = [file for file in files if not client._should_exclude_hidden(file)]
            
            # Add files up to max_count
            remaining = max_count - len(all_artworks)
            all_artworks.extend(filtered_files[:remaining])
            
            print(f"  Retrieved files {start_num}-{end_num}. Total collected: {len(all_artworks)}/{max_count} (fetched: {total_fetched})")
            
            # If we've reached our target, stop
            if len(all_artworks) >= max_count:
                break
            
            # Continue fetching even if we got fewer files than batch_size
            # This allows us to make up for filtered items (hidden artworks)
            start_num += batch_size
            
        except requests.RequestException as e:
            print(f"[ERROR] Request failed: {e}")
            break
    
    print(f"[OK] Fetched {len(all_artworks)} artworks from category {category_id} (total retrieved from API: {total_fetched})")
    return all_artworks


def add_new_artworks(existing_artworks: List[Dict], new_artworks: List[Dict]) -> List[Dict]:
    """Add new artworks to the existing list, deduplicating by GalleryId."""
    # Create lookup of existing GalleryIds
    existing_ids = {art.get('GalleryId') for art in existing_artworks if art.get('GalleryId')}
    
    # Add new artworks that don't exist
    added_count = 0
    current_time = datetime.now().isoformat()
    
    for artwork in new_artworks:
        gallery_id = artwork.get('GalleryId')
        if not gallery_id:
            continue
        
        if gallery_id not in existing_ids:
            # Create new artwork entry with all metadata
            new_entry = artwork.copy()
            new_entry['added_date'] = current_time
            new_entry['downloaded_file'] = ''
            new_entry['decoded_file'] = ''
            new_entry['health'] = 'ok'
            
            existing_artworks.append(new_entry)
            existing_ids.add(gallery_id)
            added_count += 1
            
            # Save after each addition
            save_gallery_file(existing_artworks)
    
    print(f"[OK] Added {added_count} new artworks to gallery file")
    return existing_artworks


def trim_gallery_file(artworks: List[Dict], max_count: int) -> tuple[List[Dict], int]:
    """Trim the gallery file to max_count items, removing oldest by added_date.
    
    Returns:
        tuple: (trimmed artworks list, count of removed items)
    """
    if len(artworks) <= max_count:
        return artworks, 0
    
    # Sort by added_date (oldest first)
    def get_added_date(art: Dict) -> str:
        return art.get('added_date', '')
    
    sorted_artworks = sorted(artworks, key=get_added_date)
    removed_count = 0
    
    # Remove oldest items
    while len(sorted_artworks) > max_count:
        removed = sorted_artworks.pop(0)
        gallery_id = removed.get('GalleryId')
        removed_count += 1
        
        # Delete associated files if they exist
        downloaded_file = removed.get('downloaded_file', '')
        decoded_file = removed.get('decoded_file', '')
        
        if downloaded_file and os.path.exists(downloaded_file):
            try:
                os.remove(downloaded_file)
                print(f"  Deleted downloaded file: {downloaded_file}")
            except Exception as e:
                print(f"  [WARNING] Failed to delete downloaded file {downloaded_file}: {e}")
        
        if decoded_file and os.path.exists(decoded_file):
            try:
                os.remove(decoded_file)
                print(f"  Deleted decoded file: {decoded_file}")
            except Exception as e:
                print(f"  [WARNING] Failed to delete decoded file {decoded_file}: {e}")
        
        print(f"  Removed artwork GalleryId={gallery_id} (oldest by added_date)")
        
        # Save after each removal
        save_gallery_file(sorted_artworks)
    
    print(f"[OK] Trimmed gallery file to {len(sorted_artworks)} items")
    return sorted_artworks, removed_count


def process_artwork_download_decode(client: DivoomClient, artwork: Dict, gallery_file: List[Dict]) -> bool:
    """Process a single artwork: download and decode if needed.
    
    Returns:
        bool: True if a file was downloaded in this execution, False otherwise
    """
    gallery_id = artwork.get('GalleryId')
    if not gallery_id:
        return False
    
    health = artwork.get('health', 'ok')
    if health != 'ok':
        return False
    
    # Step 7.a: Download file
    downloaded_file = artwork.get('downloaded_file', '')
    if not downloaded_file:
        # Set the download path
        downloaded_file = str(DOWNLOAD_DIR / f"{gallery_id}.dat")
        artwork['downloaded_file'] = downloaded_file
        save_gallery_file(gallery_file)
    
    # Check if file already exists
    file_downloaded = False
    if not os.path.exists(downloaded_file):
        try:
            # Download the artwork (client will create a file with format: {gallery_id}.dat)
            pixel_bean, file_path = client.download_art_by_id(gallery_id, output_dir=str(DOWNLOAD_DIR))
            
            pixel_bean.update_from_download(file_path)
            
            artwork['downloaded_file'] = file_path
            save_gallery_file(gallery_file)
            file_downloaded = True
            
        except Exception as e:
            print(f"  [ERROR] Download failed for GalleryId={gallery_id}: {e}")
            artwork['health'] = 'download failed'
            save_gallery_file(gallery_file)
            return False
    
    # Step 7.b: Decode file
    decoded_file = artwork.get('decoded_file', '')
    if not decoded_file:
        # Set the decode path
        decoded_file = str(DECODE_DIR / f"{gallery_id}.webp")
        artwork['decoded_file'] = decoded_file
        save_gallery_file(gallery_file)
    
    # Check if decoded file already exists
    if not os.path.exists(decoded_file):
        try:
            # Decode the downloaded file
            pixel_bean = PixelBeanDecoder.decode_file(downloaded_file)
            if pixel_bean is None:
                raise ValueError("Failed to decode file: unsupported format or corrupted file")
            
            # Save as WebP (lossless is already the default)
            pixel_bean.save_to_webp(decoded_file)
            
            artwork['decoded_file'] = decoded_file
            artwork['health'] = 'ok'
            save_gallery_file(gallery_file)
            
        except Exception as e:
            print(f"  [ERROR] Decode failed for GalleryId={gallery_id}: {e}")
            artwork['health'] = 'decode failed'
            save_gallery_file(gallery_file)
            return file_downloaded
    
    # Success
    artwork['health'] = 'ok'
    save_gallery_file(gallery_file)
    return file_downloaded


def foo():
    """Placeholder function to be filled in later."""
    print("Foo function called")


def main():
    """Main execution function."""
    print("=" * 70)
    print("Divoom Cloud Sync Script")
    print("=" * 70)
    
    # Step 1: Connect to Divoom Cloud
    print("\n[1] Connecting to Divoom Cloud...")
    client = DivoomClient(CONFIG_EMAIL, CONFIG_MD5_PASSWORD)
    if not client.login():
        print("[ERROR] Failed to login to Divoom Cloud")
        return
    
    # Step 2: Fetch recent artworks from category 18
    print(f"\n[2] Fetching most recent {MAX_ARTWORKS} artworks from category {CATEGORY_ID}...")
    new_artworks = fetch_category_artworks(client, CATEGORY_ID, MAX_ARTWORKS, BATCH_SIZE)
    
    if not new_artworks:
        print("[WARNING] No artworks fetched from category")
        return
    
    # Step 3: Load and update gallery file
    print(f"\n[3] Loading gallery file: {GALLERY_FILE}")
    gallery_file = load_gallery_file()
    
    print(f"[3] Adding new artworks to gallery file...")
    gallery_file = add_new_artworks(gallery_file, new_artworks)
    
    # Step 4: Trim gallery file to max 1000 items
    print(f"\n[4] Trimming gallery file to {MAX_ARTWORKS} items...")
    gallery_file, removed_count = trim_gallery_file(gallery_file, MAX_ARTWORKS)
    
    # Step 5: Sort by added_date (oldest first) and process artworks with health="ok"
    print(f"\n[5] Processing artworks (download/decode)...")
    
    def get_added_date(art: Dict) -> str:
        return art.get('added_date', '')
    
    sorted_artworks = sorted(gallery_file, key=get_added_date)
    
    processed_count = 0
    downloaded_count = 0
    for artwork in sorted_artworks:
        if artwork.get('health') == 'ok':
            gallery_id = artwork.get('GalleryId')
            print(f"  Processing GalleryId={gallery_id}...")
            
            try:
                was_downloaded = process_artwork_download_decode(client, artwork, gallery_file)
                if was_downloaded:
                    downloaded_count += 1
                processed_count += 1
            except Exception as e:
                print(f"  [ERROR] Unknown error processing GalleryId={gallery_id}: {e}")
                artwork['health'] = 'unknown error'
                save_gallery_file(gallery_file)
    
    print(f"[OK] Processed {processed_count} artworks")
    
    # Step 6: Call foo() function
    print(f"\n[6] Calling foo() function...")
    foo()
    
    # Step 7: Generate final report
    print(f"\n[7] Generating final report...")
    
    # Reload gallery file to get final state
    gallery_file = load_gallery_file()
    
    # Count artworks by health status
    ok_count = sum(1 for art in gallery_file if art.get('health') == 'ok')
    not_ok_count = sum(1 for art in gallery_file if art.get('health') != 'ok')
    
    print("\n" + "=" * 70)
    print("FINAL REPORT")
    print("=" * 70)
    print(f"  Files with 'ok' health: {ok_count}")
    print(f"  Files downloaded in this execution: {downloaded_count}")
    print(f"  Files removed in this execution: {removed_count}")
    print(f"  Files with health != 'ok': {not_ok_count}")
    print("=" * 70)
    
    print("\n" + "=" * 70)
    print("Sync completed successfully")
    print("=" * 70)


if __name__ == '__main__':
    main()

