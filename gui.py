#!/usr/bin/env python3

import tkinter as tk
from PIL import Image, ImageTk
import threading
import time
import cv2

from camera_manager import (
    VIDEO_DEVICES, 
    FOCUS_MIN, 
    FOCUS_MAX,
    set_camera_focus,
    capture_still_fswebcam,
    capture_still_opencv,
    VideoStream
)

class MultiCameraApp:
    def __init__(self, root):
        self.root = root
        root.title("Multi-Camera Still Capture System")
        root.geometry("1000x800")
        
        self.streams = {}
        self.active_devices = []
        self.focus_sliders = {}
        self.focus_values = {}
        
        # Initialize cameras and set focus
        self._initialize_cameras()
        
        # Create UI
        self._create_ui()
        
        # Start preview streams
        self._start_previews()
        
        # Start update loop
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.update_loop()

    def _initialize_cameras(self):
        """Initialize camera settings and check availability"""
        import os
        for device_id, config in VIDEO_DEVICES.items():
            if os.path.exists(config['node']):
                if os.access(config['node'], os.R_OK | os.W_OK):
                    # Set focus for this camera
                    set_camera_focus(config['node'], config['focus_value'])
                    self.active_devices.append(device_id)
                    # Store current focus value
                    self.focus_values[device_id] = config['focus_value']
                    print(f"[+] {config['node']} initialized")
                else:
                    print(f"[!] No permission for {config['node']}")
            else:
                print(f"[!] Device {config['node']} not found")

    def _create_ui(self):
        """Create the user interface"""
        # Title
        title_frame = tk.Frame(self.root)
        title_frame.pack(pady=10)
        
        tk.Label(title_frame, text="Multi-Camera Still Capture System", 
                font=('Arial', 16, 'bold')).pack()
        
        # Camera panels
        self.camera_frames = {}
        self.video_labels = {}
        self.status_labels = {}
        
        for device_id in self.active_devices:
            config = VIDEO_DEVICES[device_id]
            self._create_camera_panel(device_id, config)
        
        # Global controls
        control_frame = tk.Frame(self.root)
        control_frame.pack(pady=10, fill=tk.X, padx=20)
        
        # Capture all button
        self.capture_all_btn = tk.Button(
            control_frame,
            text="📸 Capture All Cameras",
            command=self.capture_all,
            bg='green',
            fg='white',
            font=('Arial', 12, 'bold')
        )
        self.capture_all_btn.pack(pady=5)
        
        # Status
        self.global_status = tk.Label(control_frame, text="Ready", fg="green")
        self.global_status.pack(pady=5)

    def _create_camera_panel(self, device_id, config):
        """Create UI panel for a single camera"""
        # Main frame for this camera
        camera_frame = tk.LabelFrame(self.root, text=f"{config['name']} ({config['node']})", 
                                   font=('Arial', 10, 'bold'))
        camera_frame.pack(pady=5, padx=20, fill=tk.X)
        
        # Left side - Video preview
        left_frame = tk.Frame(camera_frame)
        left_frame.pack(side=tk.LEFT, padx=10, pady=10)
        
        video_frame = tk.Frame(left_frame, bg='black', width=320, height=240)
        video_frame.pack()
        video_frame.pack_propagate(False)
        
        video_label = tk.Label(video_frame, text="Starting preview...", 
                             bg='black', fg='white')
        video_label.pack(expand=True)
        self.video_labels[device_id] = video_label
        
        # Right side - Controls
        controls_frame = tk.Frame(camera_frame)
        controls_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Camera info
        info_text = f"Preview: {config['preview_resolution'][0]}x{config['preview_resolution'][1]}\n"
        info_text += f"Capture: {config['capture_resolution'][0]}x{config['capture_resolution'][1]}\n"
        info_text += f"Rotation: {'180°' if config['rotate'] else 'None'}"
        
        tk.Label(controls_frame, text=info_text, justify=tk.LEFT, 
                font=('Arial', 9)).pack(anchor='w')
        
        # Focus controls
        focus_frame = tk.Frame(controls_frame)
        focus_frame.pack(fill=tk.X, pady=5)
        
        if config['focus_value'] is not None:
            # Manual focus with slider
            tk.Label(focus_frame, text="Manual Focus:", font=('Arial', 9, 'bold')).pack(anchor='w')
            
            # Focus value display
            focus_display = tk.Label(focus_frame, text=f"Value: {config['focus_value']}", 
                                   font=('Arial', 8))
            focus_display.pack(anchor='w')
            
            # Focus slider
            focus_slider = tk.Scale(
                focus_frame,
                from_=FOCUS_MIN,
                to=FOCUS_MAX,
                orient=tk.HORIZONTAL,
                command=lambda val, did=device_id: self._on_focus_change(did, val),
                length=200
            )
            focus_slider.set(config['focus_value'])
            focus_slider.pack(fill=tk.X, pady=2)
            
            self.focus_sliders[device_id] = {
                'slider': focus_slider,
                'display': focus_display
            }
        else:
            # Auto focus
            tk.Label(focus_frame, text="Focus: Auto", font=('Arial', 9, 'bold')).pack(anchor='w')
            tk.Label(focus_frame, text="(Automatic continuous focus)", 
                    font=('Arial', 8), fg='gray').pack(anchor='w')
        
        # Individual capture button
        capture_btn = tk.Button(
            controls_frame,
            text=f"📷 Capture {config['name']}",
            command=lambda did=device_id: self.capture_single(did),
            bg='blue',
            fg='white'
        )
        capture_btn.pack(pady=5, fill=tk.X)
        
        # Status label
        status_label = tk.Label(controls_frame, text="Initializing...", fg="orange")
        status_label.pack(anchor='w')
        self.status_labels[device_id] = status_label
        
        self.camera_frames[device_id] = camera_frame

    def _on_focus_change(self, device_id, value):
        """Handle focus slider changes"""
        focus_value = int(value)
        config = VIDEO_DEVICES[device_id]
        
        # Update the display
        if device_id in self.focus_sliders:
            self.focus_sliders[device_id]['display'].config(text=f"Value: {focus_value}")
        
        # Update the stored value
        self.focus_values[device_id] = focus_value
        
        # Apply focus change to camera
        def apply_focus():
            try:
                set_camera_focus(config['node'], focus_value)
                print(f"[*] Focus changed for {config['name']}: {focus_value}")
            except Exception as e:
                print(f"[!] Focus change failed for {config['name']}: {e}")
        
        # Use threading to avoid blocking the UI
        threading.Thread(target=apply_focus, daemon=True).start()

    def _start_previews(self):
        """Start preview streams for all active cameras"""
        for device_id in self.active_devices:
            config = VIDEO_DEVICES[device_id]
            stream = VideoStream(config)
            if stream.start():
                self.streams[device_id] = stream
                self.status_labels[device_id].config(text="Preview active", fg="green")
            else:
                self.status_labels[device_id].config(text="Preview failed", fg="red")

    def capture_single(self, device_id):
        """Capture from a single camera"""
        config = VIDEO_DEVICES[device_id]
        self.status_labels[device_id].config(text="Capturing...", fg="orange")
        
        # Run capture in background
        threading.Thread(target=self._do_single_capture, args=(device_id,), daemon=True).start()

    def _do_single_capture(self, device_id):
        """Background single capture process"""
        config = VIDEO_DEVICES[device_id]
        
        try:
            # Try fswebcam first, fallback to OpenCV
            success, message = capture_still_fswebcam(config, self)
            
            if not success:
                print(f"[*] fswebcam failed for {device_id}, trying OpenCV...")
                success, message = capture_still_opencv(config, self)
            
            if success:
                self.root.after(0, lambda: self.status_labels[device_id].config(
                    text=f"✓ Saved: {message}", fg="green"
                ))
            else:
                self.root.after(0, lambda: self.status_labels[device_id].config(
                    text=f"✗ Failed: {message}", fg="red"
                ))
                
        except Exception as e:
            print(f"[!] Capture error for {device_id}: {e}")
            self.root.after(0, lambda: self.status_labels[device_id].config(
                text="Capture error", fg="red"
            ))

    def capture_all(self):
        """Capture from all active cameras simultaneously"""
        self.global_status.config(text="Capturing from all cameras...", fg="orange")
        self.capture_all_btn.config(state="disabled")
        
        # Run all captures in background
        threading.Thread(target=self._do_all_captures, daemon=True).start()

    def _do_all_captures(self):
        """Background process to capture from all cameras"""
        capture_threads = []
        
        # Start all captures
        for device_id in self.active_devices:
            thread = threading.Thread(target=self._do_single_capture, args=(device_id,))
            thread.start()
            capture_threads.append(thread)
        
        # Wait for all to complete
        for thread in capture_threads:
            thread.join()
        
        # Update UI
        self.root.after(0, lambda: self.global_status.config(
            text="All captures completed", fg="green"
        ))
        self.root.after(0, lambda: self.capture_all_btn.config(state="normal"))

    def update_loop(self):
        """Main display update loop"""
        for device_id, stream in self.streams.items():
            if stream.frame is not None:
                try:
                    # Convert BGR to RGB and resize for display
                    img = cv2.cvtColor(stream.frame, cv2.COLOR_BGR2RGB)
                    img = cv2.resize(img, (320, 240))
                    
                    # Create PhotoImage and display
                    imgtk = ImageTk.PhotoImage(Image.fromarray(img))
                    label = self.video_labels[device_id]
                    label.imgtk = imgtk  # Keep a reference
                    label.configure(image=imgtk)
                    
                except Exception as e:
                    print(f"[!] Display update error for {device_id}: {e}")
        
        # Schedule next update
        self.root.after(50, self.update_loop)

    def on_close(self):
        """Clean shutdown"""
        print("[*] Shutting down...")
        for stream in self.streams.values():
            stream.stop()
        time.sleep(0.1)
        self.root.destroy()
