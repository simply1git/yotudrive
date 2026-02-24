import sys
import tkinter as tk
import os

def check_dependencies():
    missing = []
    try:
        import numpy
    except ImportError:
        missing.append("numpy")
    try:
        import PIL
    except ImportError:
        missing.append("Pillow")
    try:
        import imageio_ffmpeg
    except ImportError:
        missing.append("imageio-ffmpeg")
    try:
        import tqdm
    except ImportError:
        missing.append("tqdm")
    try:
        import yt_dlp
    except ImportError:
        missing.append("yt-dlp")
    try:
        import ttkbootstrap
    except ImportError:
        missing.append("ttkbootstrap")
    try:
        import reedsolo
    except ImportError:
        missing.append("reedsolo")
    try:
        import click
    except ImportError:
        missing.append("click")
        
    if missing:
        print("Error: Missing dependencies:")
        for m in missing:
            print(f"  - {m}")
        print("\nPlease run: pip install -r requirements.txt")
        print("Or use the provided 'start_gui.bat' script.")
        
        # Show error in GUI if possible
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, f"Missing dependencies:\n{', '.join(missing)}\n\nPlease run 'start_gui.bat' or install requirements.", "YotuDrive Error", 0x10)
        except:
            pass
        sys.exit(1)

if __name__ == "__main__":
    check_dependencies()
    from src.gui import YotuDriveGUI

    root = tk.Tk()
    app = YotuDriveGUI(root)
    root.mainloop()
