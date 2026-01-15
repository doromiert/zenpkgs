######
# scripts/core/offloader.py
######
import os
import sys
import time
import shutil
import subprocess
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# [ CONFIG ]
WATCH_ROOT = "/Users"
ROAMING_ROOT = "/Mount/Roaming"
THRESHOLD_PERCENT = 80  # Offload if usage > 80%
CHECK_INTERVAL = 10     # Seconds between queue checks

# Queue for files waiting to be processed (path -> timestamp)
pending_queue = {}

def is_dotfile(path):
    """Checks if file or any parent directory in relative path is hidden."""
    # We only care about the path relative to the watch root to avoid identifying '/Users' as hidden if it were
    try:
        p = Path(path)
        # Check the filename itself
        if p.name.startswith('.'): return True
        # Check parents up to WATCH_ROOT
        for parent in p.parents:
            if str(parent) == WATCH_ROOT: break
            if parent.name.startswith('.'): return True
    except:
        return False
    return False

def is_file_open(filepath):
    """
    Checks if a file is currently open by any process using lsof.
    Returns True if open (busy), False if closed (safe to move).
    """
    try:
        # Run lsof on the specific file. 
        # If it returns output, the file is open.
        # -t terse mode (PID only), -F f (file descriptor)
        result = subprocess.run(
            ["lsof", "-t", str(filepath)], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.DEVNULL
        )
        return len(result.stdout.strip()) > 0
    except Exception:
        # If lsof fails, assume safe or risk it? 
        # Safer to assume busy if uncertain, but usually empty stdout means safe.
        return False

def get_disk_usage(path="/"):
    """Returns usage percentage (0-100)."""
    try:
        total, used, free = shutil.disk_usage(path)
        return (used / total) * 100
    except:
        return 0

def find_best_target_drive(required_space):
    """Finds the Roaming Drive with the most free space."""
    candidates = []
    
    if not os.path.exists(ROAMING_ROOT):
        return None

    for drive in os.listdir(ROAMING_ROOT):
        drive_path = os.path.join(ROAMING_ROOT, drive)
        if os.path.isdir(drive_path):
            try:
                # Check if it has a Users directory structure (ZenFS compliant)
                # If not, we might create it, but prefer pre-minted drives.
                # mint.py creates /Users on drives.
                target_users_dir = os.path.join(drive_path, "Users")
                
                total, used, free = shutil.disk_usage(drive_path)
                if free > required_space:
                    candidates.append((free, drive_path))
            except:
                pass
    
    # Sort by free space descending
    candidates.sort(key=lambda x: x[0], reverse=True)
    
    if candidates:
        return candidates[0][1] # Return path of best drive
    return None

def offload_file(filepath):
    """Moves file to external drive and symlinks back."""
    
    # 1. Check Threshold
    usage = get_disk_usage("/")
    if usage < THRESHOLD_PERCENT:
        # Disk is healthy, no need to offload
        return True # "Processed" (ignored)

    print(f"[Offloader] Disk Usage {usage:.1f}% > {THRESHOLD_PERCENT}%. Triggering Offload for {filepath}")

    try:
        file_size = os.path.getsize(filepath)
    except FileNotFoundError:
        return True # File gone

    # 2. Find Target
    target_drive = find_best_target_drive(file_size + 1024) # buffer
    if not target_drive:
        print("[Offloader] No suitable external drive found!")
        return False # Retry later

    # 3. Construct Target Path
    # Source: /Users/doromiert/Downloads/file.iso
    # Target: /Mount/Roaming/[UUID]/Users/doromiert/Downloads/file.iso
    
    rel_path = os.path.relpath(filepath, WATCH_ROOT)
    dest_path = os.path.join(target_drive, "Users", rel_path)
    dest_dir = os.path.dirname(dest_path)

    print(f"[Offloader] Offloading -> {dest_path}")

    try:
        os.makedirs(dest_dir, exist_ok=True)
        
        # 4. Copy (preserve metadata)
        shutil.copy2(filepath, dest_path)
        
        # 5. Verify Copy (Simple size check)
        if os.path.getsize(dest_path) == file_size:
            # 6. Delete Original
            os.remove(filepath)
            
            # 7. Symlink Back (Shadowing)
            os.symlink(dest_path, filepath)
            print(f"[Offloader] Success. Shadow link created.")
            return True
        else:
            print("[Offloader] Copy verification failed. Aborting.")
            if os.path.exists(dest_path): os.remove(dest_path)
            return False

    except Exception as e:
        print(f"[Offloader] Error moving file: {e}")
        return False

class NewFileHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory: return
        if is_dotfile(event.src_path): return
        
        # Add to queue
        print(f"[Offloader] New file detected: {event.src_path}")
        pending_queue[event.src_path] = time.time()

    def on_modified(self, event):
        if event.is_directory: return
        # If modified, it might be growing (downloading). Reset timer/ensure in queue.
        if event.src_path not in pending_queue:
            if not is_dotfile(event.src_path):
                pending_queue[event.src_path] = time.time()

def process_queue():
    """Iterates through pending files and processes them."""
    # Create a copy of keys to allow modification of dict during iteration
    for filepath in list(pending_queue.keys()):
        if not os.path.exists(filepath):
            del pending_queue[filepath]
            continue
            
        # Check if file is open
        if is_file_open(filepath):
            # Still busy, skip this cycle
            continue
            
        # File is closed. Attempt offload.
        # Note: offload_file returns True if processed (moved OR skipped due to low usage)
        # Returns False if it failed/needs retry (e.g. no drive space)
        if offload_file(filepath):
            del pending_queue[filepath]

def main():
    print(f"::: ZenFS Offloader (Threshold: {THRESHOLD_PERCENT}%) :::")
    
    observer = Observer()
    handler = NewFileHandler()
    
    if not os.path.exists(WATCH_ROOT):
        print(f"Error: Watch root {WATCH_ROOT} does not exist.")
        return

    observer.schedule(handler, WATCH_ROOT, recursive=True)
    observer.start()
    
    print(f"Watching {WATCH_ROOT}...")
    
    try:
        while True:
            time.sleep(CHECK_INTERVAL)
            process_queue()
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    main()