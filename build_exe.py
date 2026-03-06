# YotuDrive Build Script
# Usage: python build_exe.py

import PyInstaller.__main__
import os
import shutil

# Ensure data directory exists in dist
if os.path.exists("dist/YotuDrive"):
    shutil.rmtree("dist/YotuDrive")

# PyInstaller arguments
args = [
    'yotudrive_gui.py',  # Main entry point (Robust wrapper for frozen app)
    '--name=YotuDrive',
    '--onedir',    # Directory based (easier for debugging than --onefile)
    '--noconsole', # Hide console window (for GUI)
    '--clean',
    '--add-data=README.md;.', # Add README
    
    # Imports to ensure
    '--hidden-import=PIL._tkinter_finder',
    '--hidden-import=tkinter',
    '--hidden-import=imageio',
    '--hidden-import=imageio.core',
    '--hidden-import=imageio.plugins',
    '--hidden-import=imageio_ffmpeg',
    '--hidden-import=numpy',
    '--hidden-import=cryptography',
    '--hidden-import=reedsolo',
    '--hidden-import=requests',
    '--hidden-import=certifi',
    '--hidden-import=idna',
    '--hidden-import=urllib3',
    '--hidden-import=charset_normalizer',
    '--hidden-import=yt_dlp',
    '--hidden-import=ttkbootstrap',
    '--hidden-import=src.verifier',
    '--hidden-import=src.logger',
    '--hidden-import=src.gui',
    '--hidden-import=src.ffmpeg_utils',
    '--hidden-import=src.file_utils',
    '--hidden-import=src.db',
    
    # Collect all data for complex packages
    '--collect-all=imageio_ffmpeg',
    '--collect-all=cryptography',
    '--collect-all=certifi',
    '--collect-all=yt_dlp',
    '--collect-all=ttkbootstrap',
]

print("Building YotuDrive...")
PyInstaller.__main__.run(args)

print("Build complete. Check 'dist/YotuDrive'")
print("Note: FFmpeg should be bundled via imageio-ffmpeg. If not, ensure it is in the system PATH.")
