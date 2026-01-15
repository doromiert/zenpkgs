######
# scripts/core/roaming.py
######
import os
import json
import subprocess
import time
import sys
import pwd
import threading
from pathlib import Path

# Import notify
sys.path.append(os.path.join(os.path.dirname(__file__), '../core'))
try:
    import notify
except ImportError:
    print("[Nomad] Warning: notify module not found. Notifications disabled.")
    notify = None

# [ CONSTANTS ]
MOUNT_ROOT = "/Drives/Roaming"

# [ STATE ]
processing_uuids = set()
processing_lock = threading.Lock()
logged_skips = set()
last_device_state = set() # Cache for state diffing

def run_command(cmd):
    try:
        result = subprocess.run(
            cmd, check=True, shell=True, 
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        return True, result.stdout, ""
    except subprocess.CalledProcessError as e:
        return False, e.stdout, e.stderr

def get_block_devices():
    try:
        output = subprocess.check_output(
            ["lsblk", "-J", "-o", "NAME,UUID,LABEL,FSTYPE,MOUNTPOINT"],
            text=True
        )
        data = json.loads(output)
        devices = []
        for device in data.get("blockdevices", []):
            def extract(node):
                if node.get("uuid") and node.get("fstype"):
                    devices.append(node)
                for child in node.get("children", []):
                    extract(child)
            extract(device)
        return devices
    except Exception as e:
        print(f"[Nomad] Error scanning devices: {e}")
        return []

def is_mounted(path):
    return os.path.ismount(path)

def read_identity(mount_path):
    identity_file = os.path.join(mount_path, "System/ZenFS/drive.json")
    if os.path.exists(identity_file):
        try:
            with open(identity_file, 'r') as f:
                data = json.load(f)
                return data.get("drive_identity", {})
        except:
            pass
    return None

def provision_users(drive_root):
    users_dir = os.path.join(drive_root, "Users")
    if not os.path.exists(users_dir):
        try:
            os.makedirs(users_dir)
            os.chmod(users_dir, 0o755)
        except OSError:
            return

    try:
        system_users = [u for u in pwd.getpwall() if u.pw_uid >= 1000 and u.pw_uid < 65534]
        for user in system_users:
            user_path = os.path.join(users_dir, user.pw_name)
            if not os.path.exists(user_path):
                print(f"[Nomad] Provisioning user: {user.pw_name}")
                os.makedirs(user_path)
                os.chown(user_path, user.pw_uid, user.pw_gid)
                os.chmod(user_path, 0o700)
    except Exception:
        pass

def handle_drive(uuid, dev_name, mount_point, fstype):
    try:
        print(f"[Nomad] Worker started for {uuid} ({dev_name}) [{fstype}]...")
        dev_path = f"/dev/{dev_name}"
        if not os.path.exists(mount_point):
            os.makedirs(mount_point)
            
        cmd = f"mount {dev_path} {mount_point}"
        if fstype in ['vfat', 'exfat', 'ntfs', 'ntfs-3g', 'msdos']:
            cmd += " -o umask=000"
        
        success, out, err = run_command(cmd)
        
        if success:
            try: os.chmod(mount_point, 0o777)
            except: pass
            
            identity = read_identity(mount_point)
            if identity and identity.get("uuid") and identity.get("type") == "roaming":
                zen_id = identity.get("uuid")
                print(f"[Nomad] Valid ZenFS Roaming Drive: {zen_id}")
                provision_users(mount_point)
                if notify:
                    notify.send("ZenOS Nomad", f"Drive Mounted: {zen_id}", icon="drive-harddisk")
            else:
                reason = "No Identity" if not identity else f"Invalid Type ({identity.get('type')})"
                print(f"[Nomad] Rejecting {uuid}: {reason}. Unmounting...")
                run_command(f"umount {mount_point}")
                try: os.rmdir(mount_point)
                except: pass
        else:
            print(f"[Nomad] Failed to mount {uuid}. Error: {err.strip()}")

    except Exception as e:
        print(f"[Nomad] Worker failed for {uuid}: {e}")
    finally:
        with processing_lock:
            processing_uuids.discard(uuid)

def reconcile(verbose=False):
    global last_device_state
    
    current_devices = get_block_devices()
    
    # [ FIX ] State Caching
    # Capture a signature of the current system state
    # We include mountpoint so we react if a drive gets unmounted
    current_state = set()
    for dev in current_devices:
        current_state.add((dev['uuid'], dev.get('mountpoint'), dev.get('fstype')))
    
    # If nothing changed since last run, do nothing (Silent Mode)
    if current_state == last_device_state and not verbose:
        return
        
    last_device_state = current_state
    if not verbose:
        print("[Nomad] Hardware change detected. Scanning...")

    current_scan_uuids = set()
    for dev in current_devices:
        uuid = dev['uuid']
        name = dev['name']
        fstype = dev.get('fstype', 'unknown')
        mountpoint = dev.get('mountpoint')
        
        current_scan_uuids.add(uuid)
        target_mount = os.path.join(MOUNT_ROOT, uuid)
        
        if mountpoint:
            if uuid not in logged_skips:
                if mountpoint == target_mount:
                    print(f"[Nomad] Skipping {uuid}: Already managed.")
                else:
                    print(f"[Nomad] Skipping {uuid}: External mount.")
                logged_skips.add(uuid)
            continue
            
        with processing_lock:
            if uuid in processing_uuids: continue
            
            if uuid in logged_skips: logged_skips.remove(uuid)

            processing_uuids.add(uuid)
            t = threading.Thread(
                target=handle_drive, 
                args=(uuid, name, target_mount, fstype), 
                daemon=True
            )
            t.start()
            
    for u in list(logged_skips):
        if u not in current_scan_uuids:
            logged_skips.remove(u)

    if os.path.exists(MOUNT_ROOT):
        for item in os.listdir(MOUNT_ROOT):
            path = os.path.join(MOUNT_ROOT, item)
            if os.path.isdir(path) and not is_mounted(path):
                with processing_lock:
                    if item not in processing_uuids:
                        try: os.rmdir(path)
                        except: pass

def main():
    sys.stdout.reconfigure(line_buffering=True)
    print("::: ZenFS Nomad (Smart Mode) Started :::")
    
    if not os.path.exists(MOUNT_ROOT):
        os.makedirs(MOUNT_ROOT)
        
    reconcile(verbose=True)
    
    try:
        while True:
            reconcile(verbose=False)
            time.sleep(2)
    except KeyboardInterrupt:
        print("\n[Nomad] Stopped.")

if __name__ == "__main__":
    main()