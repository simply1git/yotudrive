import os
import time
import shutil
import logging

logger = logging.getLogger(__name__)

class Janitor:
    def __init__(self, upload_dir="data/uploads", frames_dir="data/frames", max_age_hours=24):
        self.upload_dir = upload_dir
        self.frames_dir = frames_dir
        self.max_age_hours = max_age_hours
        self.max_age_seconds = max_age_hours * 3600

    def cleanup(self):
        """Perform a full system sweep and cleanup."""
        logger.info(f"[Janitor] Starting cleanup sweep (max_age={self.max_age_hours}h)...")
        now = time.time()
        
        # 1. Clean data/uploads
        self._clean_dir(self.upload_dir, now)
        
        # 2. Clean data/frames (and subdirs)
        self._clean_dir(self.frames_dir, now, recursive=True)
        
        # 3. Clean any project-level temp dirs
        temp_dirs = ["output_frames", "test_frames", "test_restore_frames"]
        for d in temp_dirs:
            if os.path.exists(d):
                self._clean_dir(d, now, recursive=True)

    def _clean_dir(self, directory, now, recursive=False):
        if not os.path.exists(directory):
            return
            
        for item in os.listdir(directory):
            item_path = os.path.join(directory, item)
            try:
                mtime = os.path.getmtime(item_path)
                if now - mtime > self.max_age_seconds:
                    if os.path.isfile(item_path):
                        os.remove(item_path)
                        logger.info(f"[Janitor] Deleted file: {item_path}")
                    elif os.path.isdir(item_path) and recursive:
                        shutil.rmtree(item_path)
                        logger.info(f"[Janitor] Deleted directory: {item_path}")
            except Exception as e:
                logger.error(f"[Janitor] Error cleaning {item_path}: {e}")

def start_janitor_thread(interval_minutes=60):
    import threading
    def run():
        jan = Janitor()
        while True:
            try:
                jan.cleanup()
            except Exception as e:
                logger.error(f"Janitor thread error: {e}")
            time.sleep(interval_minutes * 60)
            
    thread = threading.Thread(target=run, daemon=True, name="JanitorThread")
    thread.start()
    return thread
