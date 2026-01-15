######
# scripts/janitor/dumb.py
######
import os
import sys
import json
import shutil
import time
import logging
from pathlib import Path
from datetime import datetime

# Import shared notify module
sys.path.append(os.path.join(os.path.dirname(__file__), '../core'))
import notify

# [ CONFIG ]
CONFIG_PATH = os.environ.get("JANITOR_CONFIG")

def load_config():
    if not CONFIG_PATH or not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError("JANITOR_CONFIG not set or file missing")
    with open(CONFIG_PATH, 'r') as f:
        return json.load(f)['dumb']

def get_destination(extension, rules):
    """Finds the destination folder key for a given extension."""
    ext = extension.lower().strip('.')
    for folder, extensions in rules.items():
        if ext in extensions:
            return folder
    return None

def main():
    try:
        config = load_config()
    except Exception as e:
        print(f"Janitor Config Error: {e}")
        return

    grace_period = config.get('grace_period', 60)
    now = time.time()
    
    # Store unmatched files for batching: { parent_dir: [file_paths] }
    unmatched_files = {}

    for watch_dir_str in config.get('watched_dirs', []):
        watch_dir = Path(watch_dir_str)
        if not watch_dir.exists():
            continue
        
        unmatched_files[watch_dir] = []

        # Iterate files in watched directory
        for item in watch_dir.iterdir():
            if not item.is_file() or item.name.startswith('.'):
                continue

            # [ SPEC 2.2 ] Check Grace Period
            mtime = item.stat().st_mtime
            if (now - mtime) < grace_period:
                continue

            # Determine destination
            dest_key = get_destination(item.suffix, config['rules'])
            
            if dest_key:
                # [ LOGIC ] Matched Rule -> Move to Gate
                user_root = watch_dir.parent
                target_dir = user_root / dest_key
                
                if not target_dir.exists():
                    try:
                        target_dir.mkdir(parents=True, exist_ok=True)
                    except PermissionError:
                        continue

                target_file = target_dir / item.name
                if target_file.exists():
                    stem = item.stem
                    suffix = item.suffix
                    counter = 1
                    while target_file.exists():
                        target_file = target_dir / f"{stem}_{counter}{suffix}"
                        counter += 1

                try:
                    print(f"[Dumb Janitor] Moving {item.name} -> {dest_key}")
                    shutil.move(str(item), str(target_file))
                except Exception as e:
                    print(f"Error moving {item.name}: {e}")
            else:
                # No rule matched -> Add to potential batch
                unmatched_files[watch_dir].append(item)

    # [ SPEC 2.2 ] The Cluster Protocol
    # Group unmatched files into bursts
    for parent, files in unmatched_files.items():
        if not files:
            continue
            
        # Create Waiting Gate
        waiting_dir = parent / "Waiting"
        if not waiting_dir.exists():
            waiting_dir.mkdir(exist_ok=True)
            
        # Simple Clustering: If we have multiple files, create a batch folder
        # Logic: If > 1 file, create batch. If 1 file, move to Waiting/Misc?
        # Spec says "Groups bursts". We'll just batch everything for hygiene.
        
        batch_name = datetime.now().strftime("Batch_%Y-%m-%d_%H%M")
        target_batch_dir = waiting_dir / batch_name
        
        if not target_batch_dir.exists():
            target_batch_dir.mkdir(exist_ok=True)
            
        moved_count = 0
        for item in files:
            try:
                shutil.move(str(item), str(target_batch_dir / item.name))
                moved_count += 1
            except Exception as e:
                print(f"Error batching {item.name}: {e}")
                
        if moved_count > 0:
            notify.send(
                "ZenOS Sorting Deck",
                f"Moved {moved_count} unclassified items to {batch_name}",
                urgency="low"
            )

if __name__ == "__main__":
    main()