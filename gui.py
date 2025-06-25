import cv2
import subprocess
import threading
import time
import os
import tkinter as tk
from PIL import Image, ImageTk

# — CONFIG —
VIDEO_NODE = "/dev/video0"

# Preview (YUYV @ 640×480, 20fps)
PREVIEW_W, PREVIEW_H = 640, 480
PREVIEW_FOURCC = cv2.VideoWriter_fourcc(*'YUYV')
PREVIEW_FPS = 20

# Full-res capture via fswebcam (MJPG @ 8000×6000)
HIGHRES_W, HIGHRES_H = 8000, 6000

# Focus range
FOCUS_MIN, FOCUS_MAX = 0, 127

def set_focus_manual(val: int):
    """Set manual focus value"""
    subprocess.run([
        "v4l2-ctl", "-d", VIDEO_NODE,
        "--set-ctrl=focus_automatic_continuous=0",
        f"--set-ctrl=focus_absolute={val}"
    ], check=False)

def set_focus_auto(on: bool):
    """Toggle automatic focus"""
    mode = 1 if on else 0
    subprocess.run([
        "v4l2-ctl", "-d", VIDEO_NODE,
        f"--set-ctrl=focus_automatic_continuous={mode}"
    ], check=False)

def fswebcam_capture():
    """Use fswebcam to capture high-resolution photo"""
    timestamp = int(time.time())
    filename = f"fswebcam_capture_{timestamp}.jpg"
    
    print(f"[*] Starting fswebcam capture...")
    
    # Stop GUI stream first
    App.instance.streaming = False
    time.sleep(0.3)  # Give time for stream to stop
    
    try:
        # fswebcam command for ELP-48
        cmd = [
            "fswebcam",
            "-d", VIDEO_NODE,
            "-r", f"{HIGHRES_W}x{HIGHRES_H}",
            "--jpeg", "95",
            "--rotate", "180",
            "--no-banner",
            "--skip", "10",  # Skip frames for better exposure
            "-v",  # Verbose output
            filename
        ]
        
        print(f"[*] Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0 and os.path.exists(filename):
            file_size = os.path.getsize(filename) / (1024*1024)  # MB
            print(f"[+] Photo saved: {os.path.abspath(filename)}")
            print(f"[+] File size: {file_size:.1f} MB")
            return True, filename
        else:
            print(f"[!] fswebcam failed:")
            print(f"    stdout: {result.stdout}")
            print(f"    stderr: {result.stderr}")
            return False, f"fswebcam error: {result.stderr}"
            
    except subprocess.TimeoutExpired:
        print("[!] fswebcam timed out")
        return False, "Capture timed out"
    except Exception as e:
        print(f"[!] fswebcam exception: {e}")
        return False, str(e)
    finally:
        # Always restart the stream
        time.sleep(0.5)
        App.instance.start_preview()

class VideoStream:
    def __init__(self, node, fourcc, w, h, fps):
        self.node = node
        self.fourcc = fourcc
        self.w = w
        self.h = h
        self.fps = fps
        self.cap = None
        self.frame = None
        self.running = False

    def start(self):
        """Start the video stream"""
        try:
            print(f"[*] Starting video stream: {self.w}x{self.h} YUYV @ {self.fps}fps")
            
            # Use V4L2 backend explicitly for better control
            self.cap = cv2.VideoCapture(self.node, cv2.CAP_V4L2)
            
            if not self.cap.isOpened():
                print(f"[!] Failed to open {self.node}")
                return False
            
            # Set video format
            self.cap.set(cv2.CAP_PROP_FOURCC, self.fourcc)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.w)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.h)
            self.cap.set(cv2.CAP_PROP_FPS, self.fps)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Minimize latency
            
            # Verify settings
            actual_w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            actual_fps = self.cap.get(cv2.CAP_PROP_FPS)
            
            print(f"[+] Stream started: {actual_w}x{actual_h} @ {actual_fps:.1f}fps")
            
            self.running = True
            threading.Thread(target=self._reader, daemon=True).start()
            return True
            
        except Exception as e:
            print(f"[!] VideoStream start error: {e}")
            return False

    def _reader(self):
        """Background thread to read frames"""
        consecutive_failures = 0
        while self.running:
            if self.cap and self.cap.isOpened():
                ret, frame = self.cap.read()
                if ret and frame is not None:
                    # Flip 180 degrees to match fswebcam rotation
                    self.frame = cv2.flip(frame, -1)
                    consecutive_failures = 0
                else:
                    consecutive_failures += 1
                    if consecutive_failures > 50:
                        print("[!] Too many read failures, attempting reconnect...")
                        self._reconnect()
                        consecutive_failures = 0
                    time.sleep(0.01)
            else:
                time.sleep(0.1)

    def _reconnect(self):
        """Attempt to reconnect to camera"""
        try:
            if self.cap:
                self.cap.release()
            time.sleep(1)
            self.cap = cv2.VideoCapture(self.node, cv2.CAP_V4L2)
            if self.cap.isOpened():
                self.cap.set(cv2.CAP_PROP_FOURCC, self.fourcc)
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.w)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.h)
                self.cap.set(cv2.CAP_PROP_FPS, self.fps)
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                print("[+] Stream reconnected")
        except Exception as e:
            print(f"[!] Reconnect failed: {e}")

    def stop(self):
        """Stop the video stream"""
        self.running = False
        if self.cap:
            self.cap.release()
            self.cap = None
        print("[*] Video stream stopped")

class App:
    instance = None
    
    def __init__(self, root):
        App.instance = self
        self.root = root
        root.title("ELP-48 Camera: YUYV Stream + fswebcam Capture")
        root.geometry("700x600")
        self.streaming = False

        # Initialize video stream
        self.stream = VideoStream(VIDEO_NODE, PREVIEW_FOURCC, PREVIEW_W, PREVIEW_H, PREVIEW_FPS)
        
        # UI Layout (create UI first)
        self._create_ui()
        
        # Then start preview
        self.start_preview()
        
        # Start update loop
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.update_loop()

    def _create_ui(self):
        """Create the user interface"""
        # Video display
        self.video_frame = tk.Frame(self.root, bg='black')
        self.video_frame.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)
        
        self.lbl = tk.Label(self.video_frame, text="Starting camera...", bg='black', fg='white')
        self.lbl.pack(expand=True)

        # Control panel
        control_frame = tk.Frame(self.root)
        control_frame.pack(pady=10, padx=10, fill=tk.X)

        # Row 1: Capture and Focus controls
        row1 = tk.Frame(control_frame)
        row1.pack(fill=tk.X, pady=5)

        # Capture button
        self.capture_btn = tk.Button(
            row1, 
            text="📸 Capture High-Res (fswebcam)", 
            command=self.capture_photo,
            bg='green', 
            fg='white',
            font=('Arial', 10, 'bold')
        )
        self.capture_btn.pack(side=tk.LEFT, padx=5)

        # Auto-focus toggle
        self.af_on = True
        self.af_btn = tk.Button(row1, text="AF: ON", command=self.toggle_af)
        self.af_btn.pack(side=tk.LEFT, padx=5)

        # Manual focus controls
        focus_frame = tk.Frame(row1)
        focus_frame.pack(side=tk.LEFT, padx=10)
        
        tk.Label(focus_frame, text="Manual Focus:").pack(side=tk.LEFT)
        self.slider = tk.Scale(
            focus_frame, 
            from_=FOCUS_MIN, 
            to=FOCUS_MAX,
            orient="horizontal", 
            command=self.on_focus_change,
            length=200
        )
        self.slider.set(FOCUS_MAX // 2)
        self.slider.pack(side=tk.LEFT, padx=5)

        # Row 2: Status and info
        row2 = tk.Frame(control_frame)
        row2.pack(fill=tk.X, pady=5)

        # Status label
        self.status_lbl = tk.Label(row2, text="Initializing...", fg="orange")
        self.status_lbl.pack(side=tk.LEFT)

        # Stream info
        self.info_lbl = tk.Label(row2, text=f"Stream: YUYV {PREVIEW_W}x{PREVIEW_H}@{PREVIEW_FPS}fps | Capture: MJPG {HIGHRES_W}x{HIGHRES_H}", fg="blue")
        self.info_lbl.pack(side=tk.RIGHT)

    def start_preview(self):
        """Start the preview stream"""
        if not self.streaming:
            if self.stream.start():
                self.streaming = True
                print("[+] Preview stream started")
                self.status_lbl.config(text="Stream active", fg="green")
            else:
                self.status_lbl.config(text="Failed to start camera", fg="red")
                print("[!] Failed to start preview stream")

    def capture_photo(self):
        """Capture high-resolution photo using fswebcam"""
        self.capture_btn.config(state="disabled", text="📷 Capturing...")
        self.status_lbl.config(text="Capturing high-res photo (this may take a few seconds)...", fg="orange")
        
        # Run capture in background thread
        threading.Thread(target=self._do_capture, daemon=True).start()

    def _do_capture(self):
        """Background capture process"""
        try:
            success, message = fswebcam_capture()
            
            if success:
                self.root.after(0, lambda: self.status_lbl.config(
                    text=f"✓ Photo saved: {message}", fg="green"
                ))
            else:
                self.root.after(0, lambda: self.status_lbl.config(
                    text=f"✗ Capture failed: {message}", fg="red"
                ))
                
        except Exception as e:
            print(f"[!] Capture thread error: {e}")
            self.root.after(0, lambda: self.status_lbl.config(
                text="Capture error occurred", fg="red"
            ))
        finally:
            self.root.after(0, lambda: self.capture_btn.config(
                state="normal", text="📸 Capture High-Res (fswebcam)"
            ))

    def toggle_af(self):
        """Toggle auto-focus"""
        self.af_on = not self.af_on
        set_focus_auto(self.af_on)
        self.af_btn.config(text=f"AF: {'ON' if self.af_on else 'OFF'}")
        print(f"[*] Auto-focus: {'ON' if self.af_on else 'OFF'}")

    def on_focus_change(self, val):
        """Handle manual focus changes"""
        if not self.af_on:
            set_focus_manual(int(val))

    def update_loop(self):
        """Main display update loop"""
        if self.streaming and self.stream.frame is not None:
            try:
                # Convert BGR to RGB for display
                img = cv2.cvtColor(self.stream.frame, cv2.COLOR_BGR2RGB)
                
                # Create PhotoImage and display
                imgtk = ImageTk.PhotoImage(Image.fromarray(img))
                self.lbl.imgtk = imgtk  # Keep a reference
                self.lbl.configure(image=imgtk)
                
                # Update status if still initializing
                if self.status_lbl.cget("text") == "Initializing...":
                    self.status_lbl.config(text="Stream active", fg="green")
                    
            except Exception as e:
                print(f"[!] Display update error: {e}")
        
        # Schedule next update (50ms = ~20fps)
        self.lbl.after(50, self.update_loop)

    def on_close(self):
        """Clean shutdown"""
        print("[*] Shutting down...")
        self.streaming = False
        self.stream.stop()
        time.sleep(0.1)
        self.root.destroy()

def check_dependencies():
    """Check if required tools are available"""
    try:
        result = subprocess.run(["fswebcam", "--version"], 
                              capture_output=True, text=True)
        print(f"[+] fswebcam found: {result.stdout.split()[1] if result.stdout else 'version unknown'}")
    except FileNotFoundError:
        print("[!] fswebcam not found. Install with: sudo apt install fswebcam")
        return False
    
    try:
        subprocess.run(["v4l2-ctl", "--version"], 
                      capture_output=True, check=True)
        print("[+] v4l2-ctl found")
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("[!] v4l2-ctl not found. Install with: sudo apt install v4l-utils")
        return False
    
    return True

if __name__ == "__main__":
    print("=== ELP-48 Camera GUI ===")
    print(f"Stream format: YUYV {PREVIEW_W}x{PREVIEW_H} @ {PREVIEW_FPS}fps")
    print(f"Capture format: MJPG {HIGHRES_W}x{HIGHRES_H} via fswebcam")
    print()
    
    # Check dependencies
    if not check_dependencies():
        print("Please install missing dependencies and try again.")
        exit(1)
    
    # Check if camera exists
    if not os.path.exists(VIDEO_NODE):
        print(f"[!] Camera device {VIDEO_NODE} not found!")
        print("Available video devices:")
        os.system("ls -la /dev/video*")
        exit(1)
    
    # Check camera permissions
    if not os.access(VIDEO_NODE, os.R_OK | os.W_OK):
        print(f"[!] No permission to access {VIDEO_NODE}")
        print(f"Try: sudo chmod 666 {VIDEO_NODE}")
        exit(1)
    
    print(f"[+] Camera device {VIDEO_NODE} found and accessible")
    print()
    
    # Start GUI
    root = tk.Tk()
    app = App(root)
    root.mainloop()
    
