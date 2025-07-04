#!/usr/bin/env python3

import tkinter as tk
import os

from camera_manager import (
    VIDEO_DEVICES, 
    check_dependencies, 
    check_camera_permissions
)
from gui import MultiCameraApp

def main():
    """Main entry point for the Multi-Camera Still Capture System"""
    print("=== Multi-Camera Still Capture System ===")
    print("Configured cameras:")
    for device_id, config in VIDEO_DEVICES.items():
        print(f"  {config['name']}: {config['node']}")
        print(f"    Capture: {config['capture_resolution'][0]}x{config['capture_resolution'][1]}")
        print(f"    Focus: {'Manual (' + str(config['focus_value']) + ')' if config['focus_value'] else 'Auto'}")
        print(f"    Rotation: {'180°' if config['rotate'] else 'None'}")
    print()
    
    # Check dependencies
    if not check_dependencies():
        print("Please install missing dependencies and try again.")
        exit(1)
    
    # Check camera permissions
    if not check_camera_permissions():
        exit(1)
    
    print()
    
    # Start GUI
    root = tk.Tk()
    app = MultiCameraApp(root)
    root.mainloop()

if __name__ == "__main__":
    main() 