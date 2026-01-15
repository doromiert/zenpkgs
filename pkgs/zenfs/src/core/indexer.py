######
# scripts/core/indexer.py
######
import os
import sys
import time
import json
import shutil
import threading
import pwd
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# [ CONSTANTS ]
SYSTEM_DB = "/System/ZenFS/Database"
ROOT_ID_FILE = "/System/ZenFS/drive.json"
POTENTIAL_ROAMING_ROOTS = [
    os.environ.get("ZENFS_ROAMING_ROOT", "/Mount/Roaming"),
    "/Drives/Roaming",
    "/Mount/Roaming"
]
USERS_ROOT = "/home"

EXCLUDED_ROOTS = {
    'nix', 'proc', 'sys', 'dev', 'run', 'boot', 
    'etc', 'var', 'tmp', 'usr', 'bin', 'sbin', 
    'lib', 'lib64', 'mnt', 'media', 'srv', 'opt', 
    'System', 'Live', 'Mount', 'Users', 'Apps', 'Config', 'Drives'
}

MUSIC_PSEUDO_DIRS = {
    'Artists', 'Albums', 'Years', 'Genres', 'OSTs', '.building', '.trash_Artists', 
    '.trash_Albums', '.trash_Years', '.trash_Genres', '.trash_OSTs'
}

print_lock = threading.Lock()
def safe_print(msg):
    with print_lock:
        print(msg)

def get_drive_uuid(mount_point=None):
    path = ROOT_ID_FILE
    if mount_point:
        path = os.path.join(mount_point, "System/ZenFS/drive.json")
    if os.path.exists(path):
        try:
            with open(path, 'r') as f:
                data = json.load(f)
                return data.get('drive_identity', {}).get('uuid', 'UNKNOWN')
        except: pass
    return "UNKNOWN"

def get_conflict_name(filename, drive_uuid):
    """
    Generates a unique name for conflicting files.
    Format: filename-[uuid].extension
    """
    p = Path(filename)
    return f"{p.stem}-{drive_uuid}{p.suffix}"

class ZenFSHandler(FileSystemEventHandler):
    def __init__(self, drive_root, drive_uuid, executor, is_roaming=False):
        self.drive_root = drive_root
        self.drive_uuid = drive_uuid
        self.executor = executor
        self.is_roaming = is_roaming
        if is_roaming:
            self.local_db_root = os.path.join(drive_root, "System/ZenFS/Database")
        else:
            self.local_db_root = SYSTEM_DB 

    def _get_rel_path(self, src_path):
        try:
            rel = os.path.relpath(src_path, self.drive_root)
            if rel == ".": rel = ""
            return rel
        except ValueError:
            return src_path

    def _is_ignored_path(self, path):
        path_obj = Path(path)
        if path_obj.name.startswith('.') and path_obj.name not in ('.', '..'): return True
        for part in path_obj.parts:
            if part.startswith('.') and part not in ('.', '..', '/'): return True
            if part.startswith('nixbld'): return True
        try:
            rel = os.path.relpath(path, self.drive_root)
            if not rel.startswith('..'):
                if rel.startswith("System/ZenFS") or rel == "System" or rel == "System/ZenFS": return True
        except ValueError: pass
        parts = path_obj.parts
        if 'Music' in parts:
            try:
                music_idx = parts.index('Music')
                if len(parts) > music_idx + 1:
                    subdir = parts[music_idx + 1]
                    if subdir in MUSIC_PSEUDO_DIRS: return True
            except ValueError: pass
        return False

    def _ensure_dir_structure(self, base_path, rel_path):
        target_dir = os.path.join(base_path, rel_path)
        if not os.path.exists(target_dir):
            try:
                os.makedirs(target_dir, exist_ok=True)
                os.chmod(target_dir, 0o755)
            except OSError: return target_dir
        meta_file = os.path.join(target_dir, ".zenfs-folder-info")
        if not os.path.exists(meta_file):
            try:
                with open(meta_file, 'w') as f:
                    f.write(self.drive_uuid)
                os.chmod(meta_file, 0o644)
            except: pass
        return target_dir

    def _write_db_entry(self, db_root, rel_path, filename):
        db_dir = os.path.join(db_root, rel_path)
        self._ensure_dir_structure(db_root, rel_path)
        target_path = os.path.join(db_dir, filename)
        try:
            with open(target_path, 'w') as f:
                f.write(self.drive_uuid)
            os.chmod(target_path, 0o644)
        except Exception as e:
            safe_print(f"[Err] DB Write ({target_path}): {e}")

    def _remap_path(self, rel_path):
        parts = Path(rel_path).parts
        if len(parts) > 1 and parts[0] == "Users":
            if parts[1].startswith('nixbld'): return None
            return os.path.join(USERS_ROOT, *parts[1:])
        return None

    def _project_symlink(self, src_path, rel_path):
        if not rel_path.startswith("Users/"): return
        target_sys_path = self._remap_path(rel_path)
        if not target_sys_path: return
        
        # [ LOGIC ] Conflict Handling
        if os.path.lexists(target_sys_path):
            is_link = os.path.islink(target_sys_path)
            
            # Case 1: It's a symlink pointing to the correct source
            if is_link:
                try:
                    if os.readlink(target_sys_path) == src_path: return
                except: pass
                # Stale link? Remove it.
                try: os.unlink(target_sys_path)
                except: pass

            # Case 2: It's a REAL file (Conflict!)
            else:
                # Collision: Use conflict naming scheme.
                filename = os.path.basename(target_sys_path)
                parent = os.path.dirname(target_sys_path)
                conflict_name = get_conflict_name(filename, self.drive_uuid)
                target_sys_path = os.path.join(parent, conflict_name)
                
                safe_print(f"[Link] Conflict detected. Redirecting to: {target_sys_path}")
                
                # If conflict path ALSO exists, we give up
                if os.path.lexists(target_sys_path):
                    return

        try:
            parent_dir = os.path.dirname(target_sys_path)
            if not os.path.exists(parent_dir):
                os.makedirs(parent_dir, exist_ok=True)
            
            # [ RESTORED ] Use Standard Symlinks
            os.symlink(src_path, target_sys_path, target_is_directory=os.path.isdir(src_path))
            safe_print(f"[Link] Hologram: {target_sys_path} -> {src_path}")
            
            # Fix permissions of the LINK (lchown)
            try:
                parent_stat = os.stat(parent_dir)
                os.lchown(target_sys_path, parent_stat.st_uid, parent_stat.st_gid)
            except Exception as e:
                safe_print(f"[Err] Chown failed: {e}")
                
        except Exception as e:
            if "File exists" not in str(e):
                safe_print(f"[Err] Link Projection: {e}")

    def _remove_hologram(self, rel_path):
        if not rel_path.startswith("Users/"): return
        target_sys_path = self._remap_path(rel_path)
        if not target_sys_path: return

        # Try removing standard name
        if os.path.islink(target_sys_path):
            try:
                os.unlink(target_sys_path)
                safe_print(f"[Link] Removed: {target_sys_path}")
            except: pass
        
        # Try removing conflict name (just in case)
        filename = os.path.basename(target_sys_path)
        parent = os.path.dirname(target_sys_path)
        conflict_name = get_conflict_name(filename, self.drive_uuid)
        conflict_path = os.path.join(parent, conflict_name)
        
        if os.path.islink(conflict_path):
            try:
                os.unlink(conflict_path)
                safe_print(f"[Link] Removed Conflict Link: {conflict_path}")
            except: pass

    def _project_dir_hologram(self, rel_path):
        if not rel_path.startswith("Users/"): return
        target_sys_path = self._remap_path(rel_path)
        if not target_sys_path: return
        if not os.path.exists(target_sys_path):
            try:
                os.makedirs(target_sys_path, exist_ok=True)
                parent_dir = os.path.dirname(target_sys_path)
                parent_stat = os.stat(parent_dir)
                os.chown(target_sys_path, parent_stat.st_uid, parent_stat.st_gid)
                safe_print(f"[Link] Dir Hologram: {target_sys_path}")
            except Exception as e:
                safe_print(f"[Err] Dir Projection: {e}")

    def _sync_dir(self, src_path):
        if self._is_ignored_path(src_path): return
        rel_path = self._get_rel_path(src_path)
        if self.is_roaming:
            self._ensure_dir_structure(self.local_db_root, rel_path)
        self._ensure_dir_structure(SYSTEM_DB, rel_path)
        if self.is_roaming:
            self._project_dir_hologram(rel_path)

    def _sync_file(self, src_path):
        if os.path.isdir(src_path): return
        if os.path.islink(src_path): return 
        if self._is_ignored_path(src_path): return 
        rel_path = os.path.dirname(self._get_rel_path(src_path))
        filename = os.path.basename(src_path)
        if self.is_roaming:
            self._write_db_entry(self.local_db_root, rel_path, filename)
        self._write_db_entry(SYSTEM_DB, rel_path, filename)
        if self.is_roaming:
            full_rel = os.path.join(rel_path, filename)
            self._project_symlink(src_path, full_rel)

    def on_created(self, event):
        if self._is_ignored_path(event.src_path): return
        if event.is_directory:
            safe_print(f"[Event] Created Dir: {event.src_path}")
            self.executor.submit(self._sync_dir, event.src_path)
        elif os.path.islink(event.src_path):
            safe_print(f"[Event] Created Link: {event.src_path}")
        else:
            safe_print(f"[Event] Created File: {event.src_path}")
            self.executor.submit(self._sync_file, event.src_path)

    def on_modified(self, event):
        if event.is_directory: return
        if self._is_ignored_path(event.src_path): return
        self.executor.submit(self._sync_file, event.src_path)

    def on_deleted(self, event):
        if self._is_ignored_path(event.src_path): return
        safe_print(f"[Event] Deleted: {event.src_path}")
        if self.is_roaming:
             rel_path = self._get_rel_path(event.src_path)
             self.executor.submit(self._remove_hologram, rel_path)
        if not self.is_roaming:
            self.executor.submit(self._handle_local_deletion, event.src_path)

    def on_moved(self, event):
        if self._is_ignored_path(event.src_path) or self._is_ignored_path(event.dest_path): return
        safe_print(f"[Event] Moved: {event.src_path} -> {event.dest_path}")
        if not event.is_directory and self.is_roaming:
            old_rel = self._get_rel_path(event.src_path)
            self.executor.submit(self._remove_hologram, old_rel)
        if event.is_directory:
            self.executor.submit(initial_scan, event.dest_path, self.drive_uuid, self.executor, self.is_roaming)
        else:
            self.executor.submit(self._sync_file, event.dest_path)

    def _handle_local_deletion(self, local_path):
        try:
            rel = os.path.relpath(local_path, USERS_ROOT)
            roaming_rel = os.path.join("Users", rel)
        except ValueError: return
        unique_roots = set(filter(None, POTENTIAL_ROAMING_ROOTS))
        for root_path in unique_roots:
            if os.path.exists(root_path):
                for item in os.listdir(root_path):
                    drive_root = os.path.join(root_path, item)
                    target_file = os.path.join(drive_root, roaming_rel)
                    if os.path.exists(target_file):
                        try:
                            if os.path.isdir(target_file): os.rmdir(target_file)
                            else: os.remove(target_file)
                            safe_print(f"[Sync] Deleting Source: {target_file}")
                        except Exception as e:
                            safe_print(f"[Err] Source Delete Failed: {e}")

def initial_scan(root, uuid_str, executor, is_roaming=False):
    safe_print(f"[Scan] Starting background scan for {root} ({uuid_str})")
    handler = ZenFSHandler(root, uuid_str, executor, is_roaming)
    count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        if root == '/': dirnames[:] = [d for d in dirnames if d not in EXCLUDED_ROOTS]
        dirnames[:] = [d for d in dirnames if not d.startswith('.') and not d.startswith('nixbld')]
        if "System/ZenFS" in dirpath: continue
        if 'Music' in Path(dirpath).parts:
            dirnames[:] = [d for d in dirnames if d not in MUSIC_PSEUDO_DIRS]
        for d in dirnames:
            if d.startswith('.') or d.startswith('nixbld'): continue
            full_path = os.path.join(dirpath, d)
            handler._sync_dir(full_path)
        for f in filenames:
            if f.startswith('.'): continue
            full_path = os.path.join(dirpath, f)
            handler._sync_file(full_path)
            count += 1
    safe_print(f"[Scan] Finished {root}. Processed {count} items.")

def main():
    sys.stdout.reconfigure(line_buffering=True)
    print("::: ZenFS Librarian (Symlink Mode) :::")
    if not os.path.exists(SYSTEM_DB):
        os.makedirs(SYSTEM_DB)
    os.chmod(SYSTEM_DB, 0o755)
    root_uuid = get_drive_uuid()
    observer = Observer()
    scan_executor = ThreadPoolExecutor(max_workers=4)
    active_watches = {}
    if os.path.exists("/home"):
        safe_print("[Librarian] Watching /home...")
        observer.schedule(ZenFSHandler("/", root_uuid, scan_executor, is_roaming=False), "/home", recursive=True)
        scan_executor.submit(initial_scan, "/home", root_uuid, scan_executor, False)
    unique_roots = set(filter(None, POTENTIAL_ROAMING_ROOTS))
    for root_path in unique_roots:
        if os.path.exists(root_path):
            safe_print(f"[Librarian] Checking Root: {root_path}")
            for item in os.listdir(root_path):
                mount_path = os.path.join(root_path, item)
                if os.path.isdir(mount_path) and os.path.ismount(mount_path):
                    r_uuid = get_drive_uuid(mount_path)
                    if r_uuid != "UNKNOWN" and mount_path not in active_watches:
                        safe_print(f"[Librarian] Startup: Found Roaming Drive {r_uuid} at {mount_path}")
                        watch = observer.schedule(ZenFSHandler(mount_path, r_uuid, scan_executor, is_roaming=True), mount_path, recursive=True)
                        active_watches[mount_path] = watch
                        scan_executor.submit(initial_scan, mount_path, r_uuid, scan_executor, True)
    observer.start()
    try:
        while True:
            for root_path in unique_roots:
                if os.path.exists(root_path):
                    current_mounts = set()
                    for item in os.listdir(root_path):
                        mount_path = os.path.join(root_path, item)
                        if os.path.isdir(mount_path) and os.path.ismount(mount_path):
                            r_uuid = get_drive_uuid(mount_path)
                            if mount_path not in active_watches and r_uuid != "UNKNOWN":
                                safe_print(f"[Librarian] Detected Roaming Drive: {r_uuid} at {mount_path}")
                                watch = observer.schedule(ZenFSHandler(mount_path, r_uuid, scan_executor, is_roaming=True), mount_path, recursive=True)
                                active_watches[mount_path] = watch
                                scan_executor.submit(initial_scan, mount_path, r_uuid, scan_executor, True)
                            current_mounts.add(mount_path)
            for path in list(active_watches.keys()):
                if not os.path.ismount(path):
                    safe_print(f"[Librarian] Lost Drive: {path}")
                    observer.unschedule(active_watches[path])
                    del active_watches[path]
            time.sleep(5)
    except KeyboardInterrupt:
        observer.stop()
        scan_executor.shutdown(wait=False)
    observer.join()

if __name__ == "__main__":
    main()