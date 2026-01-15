######
# scripts/janitor/ml.py
######
import os
import sys
import json
import time
from pathlib import Path
from PIL import Image

# Import shared notify module
sys.path.append(os.path.join(os.path.dirname(__file__), '../core'))
import notify

# [ CONFIG ]
CONFIG_PATH = os.environ.get("JANITOR_CONFIG")

class JanitorML:
    def __init__(self):
        self.config = self._load_config()
        self.suggestions_db_path = Path(self.config['suggestions_db'])
        self.suggestions = self._load_suggestions()
        self.new_suggestions_count = 0

    def _load_config(self):
        if not CONFIG_PATH or not os.path.exists(CONFIG_PATH):
            raise FileNotFoundError("JANITOR_CONFIG not set")
        with open(CONFIG_PATH, 'r') as f:
            return json.load(f)['ml']

    def _load_suggestions(self):
        if self.suggestions_db_path.exists():
            try:
                with open(self.suggestions_db_path, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return []
        return []

    def _save_suggestions(self):
        if not self.suggestions_db_path.parent.exists():
            self.suggestions_db_path.parent.mkdir(parents=True, exist_ok=True)
            
        with open(self.suggestions_db_path, 'w') as f:
            json.dump(self.suggestions, f, indent=2)

    def analyze_image(self, filepath):
        try:
            with Image.open(filepath) as img:
                width, height = img.size
                aspect = width / height if height else 0
                
                is_screenshot = False
                if 1.77 <= aspect <= 1.78 or 0.56 <= aspect <= 0.57:
                    is_screenshot = True
                
                parent_name = filepath.parent.name.lower()
                if "camera" in parent_name and is_screenshot:
                     return {
                        "action": "move",
                        "target": "Screenshots",
                        "reason": "Detected 16:9 aspect ratio in Camera folder",
                        "confidence": 0.85
                    }
        except Exception:
            pass
        return None

    def analyze_text(self, filepath):
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                head = f.read(1024)
                
            if "#!/usr/bin" in head or "#!/usr/env" in head:
                return {
                    "action": "move",
                    "target": "Projects/Scripts",
                    "reason": "Detected Shebang",
                    "confidence": 0.99
                }
                
            if "import " in head and "def " in head:
                return {
                    "action": "move",
                    "target": "Projects/Python",
                    "reason": "Detected Python syntax",
                    "confidence": 0.90
                }
        except Exception:
            pass
        return None

    def add_suggestion(self, filepath, analysis):
        if not analysis:
            return

        suggestion = {
            "source": str(filepath),
            "suggested_target": analysis['target'],
            "reason": analysis['reason'],
            "confidence": analysis['confidence'],
            "timestamp": time.time(),
            "status": "pending"
        }
        
        # Avoid duplicates
        for s in self.suggestions:
            if s['source'] == str(filepath) and s['status'] == 'pending':
                return

        print(f"[Oracle] Suggestion: Move {filepath.name} -> {analysis['target']} ({analysis['reason']})")
        self.suggestions.append(suggestion)
        self.new_suggestions_count += 1

    def run(self):
        print("ZenOS Oracle: Beginning Scan...")
        scan_dirs = self.config.get('scan_dirs', [])
        
        for dir_path in scan_dirs:
            path = Path(dir_path)
            if not path.exists():
                continue
                
            for item in path.rglob('*'):
                if item.is_file():
                    if item.name.startswith('.'):
                        continue
                        
                    ext = item.suffix.lower()
                    result = None
                    
                    if ext in ['.png', '.jpg', '.jpeg', '.webp']:
                        result = self.analyze_image(item)
                    elif ext in ['.txt', '.md', '.py', '.sh']:
                        result = self.analyze_text(item)
                        
                    if result:
                        self.add_suggestion(item, result)

        self._save_suggestions()
        print("ZenOS Oracle: Scan Complete.")
        
        # [ NOTIFY ]
        if self.new_suggestions_count > 0:
            notify.send(
                "ZenOS Oracle", 
                f"I have {self.new_suggestions_count} new optimization suggestions.", 
                urgency="low",
                icon="dialog-information"
            )

if __name__ == "__main__":
    app = JanitorML()
    app.run()