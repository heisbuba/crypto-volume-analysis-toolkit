import threading
import sys
from pathlib import Path
import datetime

# --- Global State ---
USER_LOGS = {} 
USER_PROGRESS = {}
LOCK = threading.Lock()

# --- Configuration Constants ---
TEMP_DIR = Path("/tmp")
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# --- Helper Functions for State ---
def get_progress(uid):
    with LOCK:
        return USER_PROGRESS.get(uid, {"percent": 0, "text": "System Idle", "status": "idle"})

def update_progress(uid, percent, text, status):
    with LOCK:
        USER_PROGRESS[uid] = {"percent": percent, "text": text, "status": status}

def get_user_temp_dir(uid) -> Path:
    """Creates and returns a specific directory for the logged-in user."""
    user_dir = TEMP_DIR / uid
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir

# --- Log Capture System ---
class LogCatcher:
    """
    Redirects stdout. Detects which user triggered the log based on 
    the current thread name (which we will set to the User ID).
    """
    def __init__(self, original_stream):
        self.terminal = original_stream

    def write(self, msg):
        self.terminal.write(msg) # Keep server logs visible
        if msg and msg.strip():
            # Identify user by thread name (set in run_background_task)
            thread_name = threading.current_thread().name
            
            # Only capture logs for worker threads named "user_..."
            if thread_name.startswith("user_"):
                uid = thread_name.replace("user_", "")
                
                with LOCK:
                    if uid not in USER_LOGS:
                        USER_LOGS[uid] = []
                    
                    USER_LOGS[uid].append(msg)
                    if len(USER_LOGS[uid]) > 500:
                        USER_LOGS[uid].pop(0)
                
                # Update progress bars based on keywords
                text = msg.lower()
                if "scanning coingecko" in text:
                    update_progress(uid, 10, "Fetching CoinGecko Data...", "active")
                elif "scanning livecoinwatch" in text:
                    update_progress(uid, 30, "Fetching LiveCoinWatch...", "active")
                elif "parsing spot file" in text:
                    update_progress(uid, 50, "Analyzing Spot Volumes...", "active")
                elif "parsing futures pdf" in text:
                    update_progress(uid, 70, "Parsing Futures PDF...", "active")
                elif "converting to pdf" in text:
                    update_progress(uid, 90, "Compiling Report...", "active")
                elif "completed" in text or "pdf saved" in text:
                    update_progress(uid, 100, "Task Completed Successfully", "success")
                elif "error" in text:
                    update_progress(uid, 0, "Error Occurred", "error")

    def flush(self):
        self.terminal.flush()

# Apply the LogCatcher immediately when this module is imported
sys.stdout = LogCatcher(sys.stdout)