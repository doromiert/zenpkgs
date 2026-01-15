######
# scripts/core/mounting.py
######
import os
import sys
import subprocess
import pwd
import json
import uuid
import time

# [ CONSTANTS ]
SYSTEM_DB = "/System/ZenFS/Database"
ROOT_ID_FILE = "/System/ZenFS/drive.json"

XDG_TEMPLATE = [
    "Projects", "3D", "Android", "AI", "Apps & Scripts", 
    "Doom", "Rift", "Misc", "Passwords", "Downloads/Waiting"
]

def ensure_dir(path, uid, gid, mode=0o755):
    if not os.path.exists(path):
        os.makedirs(path)
    os.chmod(path, mode)
    os.chown(path, uid, gid)

def init_system_root():
    if not os.path.exists(SYSTEM_DB):
        os.makedirs(SYSTEM_DB)
    os.chmod(SYSTEM_DB, 0o700) 

    if not os.path.exists(ROOT_ID_FILE):
        print("[Gatekeeper] Root Identity missing. Minting new System UUID...")
        identity = {
            "drive_identity": {
                "uuid": str(uuid.uuid4()),
                "label": "ZeroRoot",
                "type": "system",
                "created_at": time.time(),
                "node": os.uname().nodename
            }
        }
        try:
            os.makedirs(os.path.dirname(ROOT_ID_FILE), exist_ok=True)
            with open(ROOT_ID_FILE, 'w') as f:
                json.dump(identity, f, indent=2)
            os.chmod(ROOT_ID_FILE, 0o644)
        except Exception as e:
            print(f"[Gatekeeper] Failed to write root identity: {e}")

def main():
    print("::: ZenFS Gatekeeper :::")
    init_system_root()
    
    # Ensure basic XDG dirs exist in /home for all users
    if os.path.exists("/home"):
        for username in os.listdir("/home"):
            home_dir = os.path.join("/home", username)
            if os.path.isdir(home_dir):
                try:
                    user_info = pwd.getpwnam(username)
                    for folder in XDG_TEMPLATE:
                        ensure_dir(os.path.join(home_dir, folder), user_info.pw_uid, user_info.pw_gid)
                except: pass

    print("[Gatekeeper] Gates are open.")

if __name__ == "__main__":
    main()