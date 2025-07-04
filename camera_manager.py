#!/usr/bin/env python3

import cv2
import subprocess
import threading
import time
import os
from datetime import datetime

# — CONFIG —
VIDEO_DEVICES = {
    'video0': {
        'node': '/dev/video0',
        'capture_resolution': (8000, 6000),
        'preview_resolution': (640, 480),
        'focus_value': 120,  # Auto focus
        'rotate': True,
        'name': 'Overhead Camera'
    },
    'video2': {
        'node': '/dev/video2', 
        'capture_resolution': (1920, 1080),
        'preview_resolution': (640, 480),
        'focus_value': None,  # Manual focus at 120
        'rotate': False,  # Rotate 180 degrees
        'name': 'Side Camera'
    }
}

# Preview settings
PREVIEW_FOURCC = cv2.VideoWriter_fourcc(*'YUYV')
PREVIEW_FPS = 20

# Focus range
FOCUS_MIN, FOCUS_MAX = 0, 127

def set_camera_focus(device_node: str, focus_value: int | None = None):
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

def check_camera_permissions():
    """Check camera permissions and availability"""
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
        return False
    
    print(f"[+] {available_cameras} camera(s) ready")
    return True 