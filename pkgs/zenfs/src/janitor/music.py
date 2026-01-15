######
# scripts/janitor/music.py
######
import os
import sys
import json
import shutil
import re
import subprocess
import time
import threading
from pathlib import Path
import mutagen
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Import shared notify module
sys.path.append(os.path.join(os.path.dirname(__file__), '../core'))
import notify

# [ CONFIG ]
CONFIG_PATH = os.environ.get("JANITOR_CONFIG")
DEBOUNCE_SECONDS = 10 # Wait this long after last event before regenerating

def load_config():
    if not CONFIG_PATH or not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError("JANITOR_CONFIG not set")
    with open(CONFIG_PATH, 'r') as f:
        return json.load(f)['music']

def create_link(source, dest):
    """
    Creates a link to the source file.
    Priority: Hardlink (Native file status) -> Symlink (Fallback for external drives)
    """
    try:
        if not dest.parent.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
        
        # Force overwrite
        if dest.exists() or dest.is_symlink():
            dest.unlink()
        
        abs_source = source.resolve()
        
        # [ FIX ] Try Hardlink first (Solves Gnome Music "Not a regular file")
        try:
            os.link(abs_source, dest)
        except OSError:
            # Fallback to absolute symlink if cross-device
            os.symlink(abs_source, dest)
            
    except Exception as e:
        pass

def sanitize_name(name):
    if not name: return "Unknown"
    name = name.replace("/", "-").replace("\\", "-")
    name = "".join(c for c in name if c.isprintable())
    name = name.strip()
    if name in [".", ".."]: return "Unknown"
    return name if name else "Unknown"

def get_list(audio, key):
    val = audio.get(key)
    if not val: return []
    if isinstance(val, list): return val
    return [str(val)]

def generate_forest(config):
    db_root = Path(config['unsorted_dir'])
    view_root = Path(config['music_dir'])
    split_symbols = config.get('split_symbols', [';', ','])
    
    # [ HOTSWAP ] Build in a hidden temporary directory first
    # Must be on same filesystem for atomic rename, so we keep it in view_root
    build_root = view_root / ".zenfs_building"
    if build_root.exists():
        shutil.rmtree(build_root)
    build_root.mkdir()

    if not db_root.exists():
        print(f"Database root {db_root} does not exist.")
        return

    print("Regenerating Forest (Hybrid Linking)...")
    count = 0
    split_pattern = '|'.join(map(re.escape, split_symbols))

    for item in db_root.rglob('*'):
        if item.is_file():
            try:
                audio = mutagen.File(item, easy=True)
                if not audio: continue
                
                artists_raw = get_list(audio, 'artist')
                album_artists_raw = get_list(audio, 'albumartist')
                albums_raw = get_list(audio, 'album')
                titles_raw = get_list(audio, 'title')
                dates_raw = get_list(audio, 'date')
                genres_raw = get_list(audio, 'genre')
                
                title = titles_raw[0] if titles_raw else item.stem
                album_tag = albums_raw[0] if albums_raw else None
                year = dates_raw[0][:4] if dates_raw else "0000"
                
                primary_artist = album_artists_raw[0] if album_artists_raw else (artists_raw[0] if artists_raw else "Unknown Artist")
                primary_artist = sanitize_name(primary_artist)

                source_artists = artists_raw if artists_raw else [primary_artist]
                all_artists = set()
                
                for entry in source_artists:
                    if split_pattern:
                        parts = re.split(split_pattern, entry)
                    else:
                        parts = [entry]
                    for part in parts:
                        cleaned = part.strip()
                        if cleaned:
                            all_artists.add(sanitize_name(cleaned))

                s_title = sanitize_name(title)
                s_album = sanitize_name(album_tag) if album_tag else "Singles"
                s_year = sanitize_name(year)
                
                filename = f"{s_title}{item.suffix}"

                # [ STRUCTURE ]
                for artist in all_artists:
                    target_category = "Albums"
                    target_subfolder = s_album

                    if artist == primary_artist:
                        if not album_tag: 
                            target_category = "Singles"
                            target_subfolder = ""
                    else:
                        target_category = "Features"
                        target_subfolder = "" 

                    path_parts = ["Artists", artist, target_category]
                    if target_subfolder: path_parts.append(target_subfolder)
                    path_parts.append(filename)
                    
                    create_link(item, build_root.joinpath(*path_parts))
                
                if album_tag:
                    create_link(item, build_root / "Years" / s_year / s_album / filename)
                else:
                    create_link(item, build_root / "Years" / s_year / "Singles" / filename)
                
                for genre in genres_raw:
                    s_genre = sanitize_name(genre)
                    create_link(item, build_root / "Genres" / s_genre / filename)
                
                is_ost = any('soundtrack' in g.lower() for g in genres_raw) or (album_tag and 'ost' in album_tag.lower())
                if is_ost:
                    create_link(item, build_root / "OSTs" / (s_album if album_tag else "Unknown") / filename)

                count += 1
                
            except Exception as e:
                continue

    # [ PERMISSIONS ]
    # Recursive chmod 777 on the build directory to ensure visibility
    try:
        subprocess.run(["chmod", "-R", "777", str(build_root)], check=False)
    except Exception:
        pass

    # [ HOTSWAP ]
    categories = ["Artists", "Years", "Genres", "OSTs"]
    
    for cat in categories:
        new_dir = build_root / cat
        target_dir = view_root / cat
        trash_dir = view_root / f".trash_{cat}"
        
        # Only swap if we generated content
        if new_dir.exists():
            # 1. Atomic Move: Active -> Trash
            if target_dir.exists():
                try: target_dir.rename(trash_dir)
                except OSError: pass
            
            # 2. Atomic Move: New -> Active
            try: new_dir.rename(target_dir)
            except OSError:
                # Rollback if fail
                if trash_dir.exists(): trash_dir.rename(target_dir)
            
            # 3. Cleanup Trash
            if trash_dir.exists(): shutil.rmtree(trash_dir)

    if build_root.exists(): shutil.rmtree(build_root)

    if count > 0:
        notify.send(
            "ZenOS Conductor",
            f"Forest Regenerated ({count} files).",
            urgency="low",
            icon="audio-x-generic"
        )

class MusicChangeHandler(FileSystemEventHandler):
    def __init__(self, config):
        self.config = config
        self.timer = None

    def _trigger_regen(self):
        print("Change detected. Scheduling forest regeneration...")
        if self.timer:
            self.timer.cancel()
        # Debounce: Wait DEBOUNCE_SECONDS after last event
        self.timer = threading.Timer(DEBOUNCE_SECONDS, generate_forest, args=[self.config])
        self.timer.start()

    def on_created(self, event):
        if not event.is_directory: self._trigger_regen()

    def on_deleted(self, event):
        if not event.is_directory: self._trigger_regen()

    def on_moved(self, event):
        if not event.is_directory: self._trigger_regen()

    def on_modified(self, event):
        # Optional: React to modifications if tags change in place
        if not event.is_directory: self._trigger_regen()

def main():
    print("::: ZenFS Music Janitor (Watcher Mode) :::")
    try:
        config = load_config()
        
        # 1. Initial Generation on Startup
        generate_forest(config)
        
        # 2. Setup Watcher
        db_root = config['unsorted_dir']
        if not os.path.exists(db_root):
            print(f"Error: Database root {db_root} missing.")
            return

        observer = Observer()
        handler = MusicChangeHandler(config)
        
        # Watch the Source of Truth (.database) recursively
        observer.schedule(handler, db_root, recursive=True)
        observer.start()
        
        print(f"Watching {db_root} for changes...")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
        observer.join()

    except Exception as e:
        print(f"Music Janitor Error: {e}")

if __name__ == "__main__":
    main()