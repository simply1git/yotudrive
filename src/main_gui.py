import sys
import os

# Add project root to sys.path to allow imports from src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tkinter as tk
import ttkbootstrap as ttk
from src.gui import YotuDriveGUI

def main():
    # Create the root window
    root = ttk.Window(themename="darkly")
    
    # Set title and icon if available
    root.title("YotuDrive - Infinite YouTube Storage")
    
    # Set geometry
    root.geometry("1000x700")
    
    # Initialize the application
    app = YotuDriveGUI(root)
    
    # Start the main event loop
    root.mainloop()

if __name__ == "__main__":
    main()
