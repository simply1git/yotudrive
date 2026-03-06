import sys
import os
import ttkbootstrap as ttk
from src.gui import YotuDriveGUI

def main():
    # Create the root window with theme
    # Using "superhero" or "darkly" as a default dark theme
    root = ttk.Window(themename="superhero")
    
    # Set title
    root.title("YotuDrive - Infinite YouTube Storage")
    
    # Set geometry
    root.geometry("1100x800")
    
    # Initialize the application
    app = YotuDriveGUI(root)
    
    # Start the main event loop
    root.mainloop()

if __name__ == "__main__":
    main()
