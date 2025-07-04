#!/usr/bin/env python3

import cv2
import subprocess
import threading
import time
import os
import tkinter as tk
from PIL import Image, ImageTk
from datetime import datetime

# — CONFIG —
VIDEO_DEVICES = {
    'video0': {
        'node': '/dev/video0',
        'capture_resolution': (8000, 6000),
        'preview_resolution': (640, 480),
        'focus_value': None,  # Auto focus
        'rotate': False,
        'name': 'Camera_0'
    },
    'video2': {
        'node': '/dev/video2', 
        'capture_resolution': (1920, 1080),
        'preview_resolution': (640, 480),
        'focus_value': 120,  # Manual focus at 120
        'rotate': True,  # Rotate 180 degrees
        'name': 'Camera_2'
    }
}

# Preview settings
PREVIEW_FOURCC = cv2.VideoWriter_fourcc(*'YUYV')
PREVIEW_FPS = 20

# Focus range
FOCUS_MIN, FOCUS_MAX = 0, 127

def set_camera_focus(device_node: str, focus_value: int = None):
    """Set camera focus - manual if value provided, auto if None"""
    try:
        if focus_value is not None:
            # Set manual focus
            subprocess.run([
                "v4l2-ctl", "-d", device_node,
                "--set-ctrl=focus_automatic_continuous=0",
                f"--set-ctrl=focus_absolute={focus_value}"
            ], check=False)
            print(f"[*] {device_node}: Manual focus set to {focus_value}")
        else:
            # Set auto focus
            subprocess.run([
                "v4l2-ctl", "-d", device_node,
                "--set-ctrl=focus_automatic_continuous=1"
            ], check=False)
            print(f"[*] {device_node}: Auto focus enabled")
    except Exception as e:
        print(f"[!] Failed to set focus for {device_node}: {e}")

def capture_still_fswebcam(device_config: dict, app_instance=None):
    """Capture high-resolution still using fswebcam"""
    device_node = device_config['node']
    width, height = device_config['capture_resolution']
    camera_name = device_config['name']
    rotate = device_config['rotate']
    device_id = None
    
    # Find device_id from node
    for did, config in VIDEO_DEVICES.items():
        if config['node'] == device_node:
            device_id = did
            break
    
    # Generate timestamped filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{camera_name}_{timestamp}.jpg"
    
    print(f"[*] Capturing from {device_node} ({width}x{height})...")
    
    # Stop preview stream to free the camera
    if app_instance and device_id and device_id in app_instance.streams:
        print(f"[*] Stopping preview for {device_node}")
        app_instance.streams[device_id].stop()
        time.sleep(0.5)  # Give time for device to be released
    
    try:
        # Build fswebcam command
        cmd = [
            "fswebcam",
            "-d", device_node,
            "-r", f"{width}x{height}",
            "--jpeg", "95",
            "--no-banner",
            "--skip", "2",  # Skip frames for better exposure
            "-v",
            filename
        ]
        
        # Add rotation if specified
        if rotate:
            cmd.extend(["--rotate", "180"])
        
        print(f"[*] Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0 and os.path.exists(filename):
            file_size = os.path.getsize(filename) / (1024*1024)  # MB
            print(f"[+] Photo saved: {os.path.abspath(filename)}")
            print(f"[+] File size: {file_size:.1f} MB")
            return_value = (True, filename)
        else:
            print(f"[!] fswebcam failed for {device_node}:")
            print(f"    stdout: {result.stdout}")
            print(f"    stderr: {result.stderr}")
            return_value = (False, f"fswebcam error: {result.stderr}")
            
    except subprocess.TimeoutExpired:
        print(f"[!] fswebcam timed out for {device_node}")
        return_value = (False, "Capture timed out")
    except Exception as e:
        print(f"[!] fswebcam exception for {device_node}: {e}")
        return_value = (False, str(e))
    finally:
        # Always restart the preview stream after capture
        if app_instance and device_id and device_id in app_instance.streams:
            print(f"[*] Restarting preview for {device_node}")
            time.sleep(0.3)
            # Recreate the stream
            config = VIDEO_DEVICES[device_id]
            new_stream = VideoStream(config)
            if new_stream.start():
                app_instance.streams[device_id] = new_stream
                app_instance.root.after(0, lambda: app_instance.status_labels[device_id].config(
                    text="Preview restarted", fg="blue"
                ))
            else:
                app_instance.root.after(0, lambda: app_instance.status_labels[device_id].config(
                    text="Preview failed to restart", fg="orange"
                ))
    
    return return_value

def capture_still_opencv(device_config: dict, app_instance=None):
    """Capture still using OpenCV (alternative method)"""
    device_node = device_config['node']
    width, height = device_config['capture_resolution']
    camera_name = device_config['name']
    rotate = device_config['rotate']
    device_id = None
    
    # Find device_id from node
    for did, config in VIDEO_DEVICES.items():
        if config['node'] == device_node:
            device_id = did
            break
    
    # Extract device number from node path
    device_num = int(device_node.split('video')[-1])
    
    # Generate timestamped filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{camera_name}_{timestamp}_opencv.jpg"
    
    print(f"[*] OpenCV capture from {device_node} ({width}x{height})...")
    
    # Stop preview stream to free the camera
    if app_instance and device_id and device_id in app_instance.streams:
        print(f"[*] Stopping preview for OpenCV capture on {device_node}")
        app_instance.streams[device_id].stop()
        time.sleep(0.5)
    
    try:
        # Open camera
        cap = cv2.VideoCapture(device_num, cv2.CAP_V4L2)
        
        if not cap.isOpened():
            return_value = (False, f"Failed to open {device_node}")
        else:
            # Set resolution
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
            
            # Allow camera to adjust
            time.sleep(1)
            
            # Capture frame
            ret, frame = cap.read()
            cap.release()
            
            if ret and frame is not None:
                # Apply rotation if specified
                if rotate:
                    frame = cv2.flip(frame, -1)  # 180 degree rotation
                
                # Save image
                success = cv2.imwrite(filename, frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
                
                if success:
                    file_size = os.path.getsize(filename) / (1024*1024)  # MB
                    print(f"[+] Photo saved: {os.path.abspath(filename)}")
                    print(f"[+] File size: {file_size:.1f} MB")
                    return_value = (True, filename)
                else:
                    return_value = (False, "Failed to save image")
            else:
                return_value = (False, "Failed to capture frame")
            
    except Exception as e:
        return_value = (False, str(e))
    finally:
        # Always restart the preview stream after capture
        if app_instance and device_id and device_id in app_instance.streams:
            print(f"[*] Restarting preview after OpenCV capture on {device_node}")
            time.sleep(0.3)
            # Recreate the stream
            config = VIDEO_DEVICES[device_id]
            new_stream = VideoStream(config)
            if new_stream.start():
                app_instance.streams[device_id] = new_stream
                app_instance.root.after(0, lambda: app_instance.status_labels[device_id].config(
                    text="Preview restarted", fg="blue"
                ))
            else:
                app_instance.root.after(0, lambda: app_instance.status_labels[device_id].config(
                    text="Preview failed to restart", fg="orange"
                ))
    
    return return_value

class VideoStream:
    def __init__(self, device_config):
        self.config = device_config
        self.node = device_config['node']
        self.w, self.h = device_config['preview_resolution']
        self.rotate = device_config['rotate']
        self.device_num = int(self.node.split('video')[-1])
        self.cap = None
        self.frame = None
        self.running = False

    def start(self):
        """Start the video stream"""
        try:
            print(f"[*] Starting preview for {self.node}: {self.w}x{self.h}")
            
            self.cap = cv2.VideoCapture(self.device_num, cv2.CAP_V4L2)
            
            if not self.cap.isOpened():
                print(f"[!] Failed to open {self.node}")
                return False
            
            # Set preview format
            self.cap.set(cv2.CAP_PROP_FOURCC, PREVIEW_FOURCC)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.w)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.h)
            self.cap.set(cv2.CAP_PROP_FPS, PREVIEW_FPS)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            
            print(f"[+] Preview started for {self.node}")
            
            self.running = True
            threading.Thread(target=self._reader, daemon=True).start()
            return True
            
        except Exception as e:
            print(f"[!] VideoStream start error for {self.node}: {e}")
            return False

    def _reader(self):
        """Background thread to read frames"""
        while self.running:
            if self.cap and self.cap.isOpened():
                ret, frame = self.cap.read()
                if ret and frame is not None:
                    # Apply rotation if specified
                    if self.rotate:
                        frame = cv2.flip(frame, -1)
                    self.frame = frame
                else:
                    time.sleep(0.01)
            else:
                time.sleep(0.1)

    def stop(self):
        """Stop the video stream"""
        self.running = False
        if self.cap:
            self.cap.release()
            self.cap = None
        print(f"[*] Preview stopped for {self.node}")

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

def check_dependencies():
    """Check if required tools are available"""
    dependencies_ok = True
    
    try:
        result = subprocess.run(["fswebcam", "--version"], 
                              capture_output=True, text=True)
        print(f"[+] fswebcam found")
    except FileNotFoundError:
        print("[!] fswebcam not found. Install with: sudo apt install fswebcam")
        dependencies_ok = False
    
    try:
        subprocess.run(["v4l2-ctl", "--version"], 
                      capture_output=True, check=True)
        print("[+] v4l2-ctl found")
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("[!] v4l2-ctl not found. Install with: sudo apt install v4l-utils")
        dependencies_ok = False
    
    return dependencies_ok

if __name__ == "__main__":
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
    available_cameras = 0
    for device_id, config in VIDEO_DEVICES.items():
        if os.path.exists(config['node']):
            if os.access(config['node'], os.R_OK | os.W_OK):
                print(f"[+] {config['node']} found and accessible")
                available_cameras += 1
            else:
                print(f"[!] No permission for {config['node']}")
                print(f"    Try: sudo chmod 666 {config['node']}")
        else:
            print(f"[!] {config['node']} not found")
    
    if available_cameras == 0:
        print("[!] No cameras available!")
        print("Available video devices:")
        os.system("ls -la /dev/video* 2>/dev/null || echo 'No video devices found'")
        exit(1)
    
    print(f"[+] {available_cameras} camera(s) ready")
    print()
    
    # Start GUI
    root = tk.Tk()
    app = MultiCameraApp(root)
    root.mainloop()