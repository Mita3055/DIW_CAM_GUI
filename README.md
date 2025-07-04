# Multi-Camera Still Capture System

A Python application for capturing high-resolution still images from multiple cameras simultaneously with a graphical user interface.

## Project Structure

The project has been refactored into three main files for better maintainability:

### `main.py`
- Entry point for the application
- Handles initialization and dependency checks
- Starts the GUI application

### `camera_manager.py`
- Contains all camera-related functionality
- Camera configuration and settings
- Video stream management
- Still image capture functions (fswebcam and OpenCV)
- Focus control functions
- Dependency and permission checking

### `gui.py`
- Contains the graphical user interface
- Tkinter-based GUI components
- Camera preview displays
- User controls and status updates
- Event handling and threading

## Features

- **Multi-camera support**: Capture from multiple cameras simultaneously
- **High-resolution capture**: Support for different capture and preview resolutions
- **Focus control**: Manual and automatic focus settings
- **Image rotation**: 180-degree rotation support
- **Real-time preview**: Live video preview for each camera
- **Dual capture methods**: fswebcam (primary) and OpenCV (fallback)

## Dependencies

### Python Packages
```bash
pip install -r requirements.txt
```

### System Dependencies
```bash
# Ubuntu/Debian
sudo apt install fswebcam v4l-utils

# CentOS/RHEL/Fedora
sudo yum install fswebcam v4l-utils
```

## Usage

1. **Run the application**:
   ```bash
   python main.py
   ```

2. **Camera permissions**: Ensure your user has access to video devices:
   ```bash
   sudo chmod 666 /dev/video*
   ```

3. **Configure cameras**: Edit the `VIDEO_DEVICES` configuration in `camera_manager.py` to match your camera setup.

## Configuration

Camera settings are defined in `camera_manager.py`:

```python
VIDEO_DEVICES = {
    'video0': {
        'node': '/dev/video0',
        'capture_resolution': (8000, 6000),
        'preview_resolution': (640, 480),
        'focus_value': 120,  # Manual focus value
        'rotate': True,      # 180-degree rotation
        'name': 'Overhead Camera'
    },
    # Add more cameras as needed
}
```

## Troubleshooting

- **Camera not found**: Check if the video device exists and has proper permissions
- **Capture fails**: Try the OpenCV fallback method or check fswebcam installation
- **Focus issues**: Ensure v4l2-ctl is installed and camera supports focus control
- **Permission errors**: Run with appropriate permissions or adjust device file permissions

## File Organization Benefits

- **Separation of concerns**: Camera logic, GUI, and entry point are separate
- **Easier maintenance**: Each file has a specific responsibility
- **Better testing**: Individual components can be tested separately
- **Reusability**: Camera manager can be used in other applications
- **Cleaner imports**: Clear dependencies between modules 