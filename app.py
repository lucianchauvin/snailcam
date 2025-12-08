import subprocess
import time
import numpy as np

from PIL import Image
from flask import Flask, Response, request, jsonify, send_file
from io import BytesIO
import os
from pathlib import Path
from datetime import datetime

import threading
import re

app = Flask(__name__)

# Set the desired camera resolution and format
WIDTH = 1920
HEIGHT = 1080
PIXEL_FORMAT = 'rgb24'
CAMERA_PATH = '/dev/video0'
SNAPSHOT_DIR = '/home/snail/snapshots/'

# Whitelist of allowed camera controls to prevent command injection
ALLOWED_CONTROLS = {
    "brightness", "contrast", "saturation", "gain", "sharpness",
    "backlight_compensation", "white_balance_temperature",
    "exposure_time_absolute", "focus_absolute", "zoom_absolute",
    "pan_absolute", "tilt_absolute"
}

# Start the FFmpeg process to capture video
# The command captures raw video data from the camera and pipes it to stdout
ffmpeg_command = [
    'ffmpeg',
    '-y',                      # Overwrite output files without asking
    '-r', '60',                # Set the frame rate to 60 FPS
    '-s', f'{WIDTH}x{HEIGHT}', # Set the frame size
    '-i', CAMERA_PATH,         # Input device path
    '-pix_fmt', PIXEL_FORMAT,  # Output pixel format
    '-vcodec', 'rawvideo',      # Output video codec
    '-an',                     # Disable audio
    '-f', 'image2pipe',        # Output to a pipe
    '-'                        # Use stdout as the output
]

try:
    # Start the FFmpeg process
    ffmpeg_process = subprocess.Popen(ffmpeg_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=10**8)
    # Give FFmpeg a moment to initialize the camera
    time.sleep(2)
    # Check if the process started correctly
    if ffmpeg_process.poll() is not None:

        error_output = ffmpeg_process.stderr.read().decode('utf-8')
        raise IOError(f"FFmpeg failed to start. Error: {error_output}")
    print(f"Success: FFmpeg process started with command: {' '.join(ffmpeg_command)}")
except FileNotFoundError:
    print("Error: FFmpeg is not installed or not in the system PATH. Please install it.")
    exit()
except IOError as e:
    print(e)
    exit()

def generate_frames():
    """Reads frames from FFmpeg, converts them to JPEG, and yields them."""
    frame_size = WIDTH * HEIGHT * 3
    while True:
        # Check if the FFmpeg process is still running
        if ffmpeg_process.poll() is not None:
            print("FFmpeg process has terminated, stopping video feed.")
            break
            

        # Read the raw video frame data from the FFmpeg process
        raw_frame = ffmpeg_process.stdout.read(frame_size)
        if not raw_frame:
            print("No raw frame data received, stopping video feed.")
            break

        # Convert the raw frame to a NumPy array and then to a Pillow Image
        frame_array = np.frombuffer(raw_frame, np.uint8).reshape((HEIGHT, WIDTH, 3))
        frame_image = Image.fromarray(frame_array)

        # Create an in-memory buffer to save the JPEG
        img_buffer = BytesIO()
        frame_image.save(img_buffer, format='JPEG', quality=95)
        frame_bytes = img_buffer.getvalue()
        
        # Yield the frame with the appropriate HTTP headers for a multipart response
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

def set_camera_control(control_name, value):
    """Sets a camera control using v4l2-ctl in a separate process."""
    try:
        # The inputs are validated in the /control route, making this call safe.
        subprocess.run(
            ['v4l2-ctl', '-d', CAMERA_PATH, '--set-ctrl', f'{control_name}={value}'],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        print(f"Set control '{control_name}' to '{value}' successfully.")
    except subprocess.CalledError as e:
        print(f"Failed to set control '{control_name}'. Error: {e.stderr.decode()}")
    except FileNotFoundError:
        print("Error: v4l2-ctl not found. Please ensure it is installed.")

@app.route('/control', methods=['POST'])
def control():
    """API endpoint to receive and set camera controls with input sanitization."""
    data = request.get_json()
    if not data:
        return jsonify({'status': 'error', 'message': 'Invalid JSON'}), 400

    control_name = data.get('control')
    value = data.get('value')

    # 1. Validate control_name against the whitelist.
    if control_name not in ALLOWED_CONTROLS:
        print(f"Error: Disallowed control '{control_name}'")
        return jsonify({'status': 'error', 'message': 'Invalid control name'}), 400

    # 2. Validate that the value is a clean number and contains no shell characters.
    # This regex matches an optional negative sign, digits, and an optional decimal part.
    if value is None or not re.match(r'^-?\d+(\.\d+)?$', str(value)):
        print(f"Error: Invalid or unsafe value '{value}' for control '{control_name}'")
        return jsonify({'status': 'error', 'message': 'Value must be a simple number.'}), 400


    # 3. Ensure both control and value are present after checks.
    # The checks above ensure the inputs are safe to be used in the command.
    threading.Thread(target=set_camera_control, args=(control_name, str(value))).start()
    return jsonify({'status': 'success'})
        

@app.route('/')
def index():
    """Serves the main HTML page with updated CSS for full-screen video."""
    return """
    <!DOCTYPE html>
    <html>
      <head>
        <title>nail cam</title>
        <style>
          /* Basic page setup */
          html {
            font-family: sans-serif;
            background-color: #111; /* Darker background for better viewing */
          }
          body {
            margin: 0;
            padding: 0;
            color: #eee;
          }
          .nav-bar {
            position: fixed;

            top: 10px;
            right: 10px;
            z-index: 1000;
          }
          .nav-link {
            display: inline-block;
            padding: 10px 20px;
            background: rgba(0, 123, 255, 0.8);
            color: white;
            text-decoration: none;
            border-radius: 4px;
            font-weight: bold;
            transition: background 0.2s;
          }
          .nav-link:hover {
            background: rgba(0, 123, 255, 1);
          }
          /* Video container fills the entire viewport height, pushing controls down */
          .video-container {
            position: relative;
            width: 100%;
            height: 100vh; /* Set height to 100% of the viewport height */
            display: flex;
            justify-content: center;
            align-items: center;
            overflow: hidden;
            background-color: #000;
          }
          /* Style the video stream to fit within the container while maintaining aspect ratio */
          #camera-stream {
            display: block;
            max-width: 100%;
            max-height: 100%;
            object-fit: contain; /* Key property to scale video within its box without cropping */
          }
          /* Overlay controls remain absolutely positioned within the video container */
          .overlay-controls {
            position: absolute;
            top: 0;
            bottom: 0;
            left: 0;
            right: 0;
            z-index: 10;
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            grid-template-rows: 1fr 1fr 1fr;
            padding: 20px;
          }
          .control-button {
            background-color: rgba(0, 123, 255, 0.4);
            border: 1px solid rgba(255, 255, 255, 0.5);
            border-radius: 50%; /* Make buttons circular */
            cursor: pointer;
            width: 50px;
            height: 50px;
            display: flex;
            justify-content: center;
            align-items: center;
            transition: background-color 0.2s;
            position: relative;
            font-size: 0; /* Hide any text inside the button */
          }
          .control-button:hover {
            background-color: rgba(0, 123, 255, 0.8);
          }
          /* Arrow shapes using pseudo-elements for better compatibility */
          .control-top {
            grid-column: 2;
            grid-row: 1;
            justify-self: center;
            align-self: start;
          }
          .control-left {
            grid-column: 1;
            grid-row: 2;
            justify-self: start;
            align-self: center;
          }
          .control-right {
            grid-column: 3;
            grid-row: 2;
            justify-self: end;
            align-self: center;
          }
          .control-bottom {
            grid-column: 2;
            grid-row: 3;
            justify-self: center;
            align-self: end;
          }
          .control-top .control-button::after {
            content: '';
            width: 0;
            height: 0;
            border-left: 10px solid transparent;
            border-right: 10px solid transparent;
            border-bottom: 15px solid white;
          }
          .control-bottom .control-button::after {
            content: '';
            width: 0;
            height: 0;
            border-left: 10px solid transparent;
            border-right: 10px solid transparent;
            border-top: 15px solid white;
          }
          .control-left .control-button::after {
            content: '';
            width: 0;
            height: 0;
            border-top: 10px solid transparent;
            border-bottom: 10px solid transparent;
            border-right: 15px solid white;
          }
          .control-right .control-button::after {
            content: '';
            width: 0;
            height: 0;
            border-top: 10px solid transparent;
            border-bottom: 10px solid transparent;
            border-left: 15px solid white;
          }
          .mouse-control-status {
            position: absolute;
            top: 10px;
            left: 10px;
            background-color: rgba(0, 0, 0, 0.7);
            color: white;
            padding: 5px 10px;
            border-radius: 5px;
            font-size: 0.8em;
            display: none;
          }
          .mouse-control-status.active {
            display: block;
          }
          /* Container for all the bottom controls, now below the video container */
          .bottom-controls-wrapper {
            width: 100%;
            padding: 2rem 1rem; /* Add more padding for better spacing */
            background-color: #222;
            box-shadow: 0 -4px 8px rgba(0, 0, 0, 0.2);
            box-sizing: border-box;
          }
          /* Reposition the zoom container to the bottom-left of the video overlay */
          .zoom-container {
            position: absolute;
            bottom: 20px;
            left: 20px;
            width: 200px;
            z-index: 20; /* Ensure it's above the video but below overlay controls if needed */
            background-color: rgba(34, 34, 34, 0.7); /* Semi-transparent background */
            padding: 1rem;
            border-radius: 10px;
            display: flex;
            flex-direction: column;
            align-items: center;
          }
          .zoom-slider-container {
            width: 100%;
            display: flex;
            flex-direction: column;
            align-items: center;
          }
          .zoom-slider-container label {
            font-weight: bold;
            margin-bottom: 5px;
          }
          .zoom-slider {
            -webkit-appearance: none;
            appearance: none;
            width: 100%;
            height: 15px;
            background: #444;
            outline: none;
            border-radius: 8px;
            transition: opacity 0.2s;
          }
          .zoom-slider::-webkit-slider-thumb {
            -webkit-appearance: none;
            appearance: none;
            width: 25px;
            height: 25px;
            background: #007bff;
            cursor: pointer;
            border-radius: 50%;
          }
          .zoom-slider::-moz-range-thumb {
            width: 25px;
            height: 25px;
            background: #007bff;
            cursor: pointer;
            border-radius: 50%;
          }
          .main-controls {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            width: 100%;
            max-width: 1200px;
            margin: 0 auto;
          }
          .slider-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            background: #333;
            padding: 1rem;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
          }
          .slider-container label {
            font-weight: bold;
            margin-bottom: 0.5rem;
            text-transform: capitalize;
          }
          .slider-container input[type="range"] {
            width: 100%;
          }
          .value-display {
            font-family: monospace;
            font-size: 1.2em;
            margin-top: 0.5rem;
          }
          /* Startup Notification Style */
          .startup-notification {
            position: absolute;
            top: 20px;
            left: 50%;
            transform: translateX(-50%);
            background-color: rgba(0, 0, 0, 0.8);
            color: white;
            padding: 10px 20px;
            border-radius: 8px;
            z-index: 100;
            font-size: 1.2em;
            font-weight: bold;
            text-align: center;
            transition: opacity 0.5s ease-out, transform 0.5s ease-out;
            opacity: 1;
          }
          .startup-notification.hidden {
            opacity: 0;
            transform: translateX(-50%) translateY(-50px);
            pointer-events: none; /* Make it non-interactive when hidden */
          }
        </style>
      </head>
      <body>
        <div class="nav-bar">
          <a href="/snapshots" class="nav-link">View Snapshots</a>
        </div>
        <div class="video-container">
          <div class="startup-notification" id="startup-notification">
            Press SHIFT to Toggle Mouse Control for Pan/Tilt/Zoom
          </div>
          <img id="camera-stream" src="/video_feed" />
          <div class="overlay-controls">
            <div class="control-top">
              <button class="control-button" id="tilt-up"></button>
            </div>
            <div class="control-left">
              <button class="control-button" id="pan-left"></button>
            </div>
            <div class="control-right">
              <button class="control-button" id="pan-right"></button>
            </div>
            <div class="control-bottom">
              <button class="control-button" id="tilt-down"></button>
            </div>
            <div class="mouse-control-status" id="mouse-control-status">
              Mouse Control Active (SHIFT)
            </div>
          </div>
          <div class="zoom-container">
            <div class="zoom-slider-container">
              <label for="zoom_absolute">Zoom</label>
              <input
                type="range"
                id="zoom_absolute"
                min="100"
                max="500"
                step="1"
                value="100"
                class="zoom-slider"
              />
            </div>
          </div>
        </div>
        <div class="bottom-controls-wrapper">
          <div class="main-controls"></div>
        </div>
        <script>
          document.addEventListener('DOMContentLoaded', () => {
            const notification = document.getElementById('startup-notification');
            setTimeout(() => {
              notification.classList.add('hidden');
            }, 7000); // Hide after 7 seconds
          });

          const allControls = [
            { name: 'brightness', min: 0, max: 255, step: 1, default: 128 },
            { name: 'contrast', min: 0, max: 255, step: 1, default: 128 },
            { name: 'saturation', min: 0, max: 255, step: 1, default: 128 },
            { name: 'gain', min: 0, max: 255, step: 1, default: 0 },
            { name: 'sharpness', min: 0, max: 255, step: 1, default: 128 },
            { name: 'backlight_compensation', min: 0, max: 1, step: 1, default: 0 },
            {
              name: 'white_balance_temperature',
              min: 2000,
              max: 7500,
              step: 10,
              default: 4000,
            },
            {
              name: 'exposure_time_absolute',
              min: 3,
              max: 2047,
              step: 1,
              default: 250,
            },
            { name: 'focus_absolute', min: 0, max: 255, step: 5, default: 30 },
          ];

          const panTiltZoomControls = [
            { name: 'zoom_absolute', min: 100, max: 500, step: 1, default: 100 },
            { name: 'pan_absolute', min: -36000, max: 36000, step: 3600, default: 0 },
            { name: 'tilt_absolute', min: -36000, max: 36000, step: 3600, default: 0 },
          ];

          const createSlider = (container, control) => {
            const sliderContainer = document.createElement('div');
            sliderContainer.className = 'slider-container';

            const label = document.createElement('label');
            label.innerText = control.name.replace(/_/g, ' ');
            label.setAttribute('for', control.name);

            const slider = document.createElement('input');
            slider.type = 'range';
            slider.id = control.name;
            slider.min = control.min;
            slider.max = control.max;
            slider.step = control.step;
            slider.value = control.default;

            const valueDisplay = document.createElement('span');
            valueDisplay.className = 'value-display';
            valueDisplay.innerText = control.default;

            const sendControlValue = (value) => {
              fetch('/control', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ control: control.name, value: value }),
              });
            };

            slider.addEventListener('input', (e) => {
              valueDisplay.innerText = e.target.value;
              sendControlValue(e.target.value);
            });

            sliderContainer.appendChild(label);
            sliderContainer.appendChild(valueDisplay);
            sliderContainer.appendChild(slider);

            container.appendChild(sliderContainer);
          };

          const mainControlsContainer = document.querySelector('.main-controls');
          allControls.forEach((control) => {
            createSlider(mainControlsContainer, control);
          });

          // Pan/Tilt controls
          let panValue = panTiltZoomControls.find(
            (c) => c.name === 'pan_absolute'
          ).default;
          let tiltValue = panTiltZoomControls.find(
            (c) => c.name === 'tilt_absolute'
          ).default;
          const panStep = panTiltZoomControls.find(
            (c) => c.name === 'pan_absolute'
          ).step;
          const tiltStep = panTiltZoomControls.find(
            (c) => c.name === 'tilt_absolute'
          ).step;
          const panMax = panTiltZoomControls.find(
            (c) => c.name === 'pan_absolute'
          ).max;
          const panMin = panTiltZoomControls.find(
            (c) => c.name === 'pan_absolute'
          ).min;
          const tiltMax = panTiltZoomControls.find(
            (c) => c.name === 'tilt_absolute'
          ).max;
          const tiltMin = panTiltZoomControls.find(
            (c) => c.name === 'tilt_absolute'
          ).min;

          // Store initial zoom values for scaling calculation
          const zoomMin = panTiltZoomControls.find(
            (c) => c.name === 'zoom_absolute'
          ).min;
          const zoomMaxGlobal = panTiltZoomControls.find(
            (c) => c.name === 'zoom_absolute'
          ).max;

          document.getElementById('pan-left').addEventListener('click', () => {
            panValue = Math.max(panMin, panValue - panStep);
            fetch('/control', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ control: 'pan_absolute', value: panValue }),
            });
          });

          document.getElementById('pan-right').addEventListener('click', () => {
            panValue = Math.min(panMax, panValue + panStep);
            fetch('/control', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ control: 'pan_absolute', value: panValue }),
            });
          });

          document.getElementById('tilt-up').addEventListener('click', () => {
            tiltValue = Math.min(tiltMax, tiltValue + tiltStep);
            fetch('/control', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ control: 'tilt_absolute', value: tiltValue }),
            });
          });

          document.getElementById('tilt-down').addEventListener('click', () => {
            tiltValue = Math.max(tiltMin, tiltValue - tiltStep);
            fetch('/control', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ control: 'tilt_absolute', value: tiltValue }),
            });
          });

          // Mouse controls for pan, tilt, and zoom (toggled by Shift)
          const videoContainer = document.querySelector('.video-container');
          const mouseStatus = document.getElementById('mouse-control-status');
          const zoomSlider = document.getElementById('zoom_absolute');
          const zoomStep = panTiltZoomControls.find(
            (c) => c.name === 'zoom_absolute'
          ).step;

          let isMouseControlActive = false;

          document.addEventListener('keydown', (e) => {
            if (e.key === 'Shift' && !e.repeat) {
              isMouseControlActive = !isMouseControlActive;
              if (isMouseControlActive) {
                mouseStatus.classList.add('active');
              } else {
                mouseStatus.classList.remove('active');
              }
            }
          });

          videoContainer.addEventListener('mousemove', (e) => {
            if (isMouseControlActive) {
              const rect = videoContainer.getBoundingClientRect();

              // Calculate normalized mouse position (0-1) within the video frame
              const normalizedX = (e.clientX - rect.left) / rect.width;
              const normalizedY = (e.clientY - rect.top) / rect.height;

              // Interpolate pan_absolute value based on horizontal mouse position
              panValue = panMin + normalizedX * (panMax - panMin);

              // Interpolate tilt_absolute value based on vertical mouse position (inverted)
              tiltValue = tiltMin + (1 - normalizedY) * (tiltMax - tiltMin);

              // Send the new values to the server
              fetch('/control', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ control: 'pan_absolute', value: panValue }),
              });

              fetch('/control', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  control: 'tilt_absolute',
                  value: tiltValue,
                }),
              });
            }
          });

          // Zoom control (horizontal slider)
          const updateZoom = (newValue) => {
            fetch('/control', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ control: 'zoom_absolute', value: newValue }),
            });
          };

          zoomSlider.addEventListener('input', (e) => {
            updateZoom(e.target.value);
          });

          videoContainer.addEventListener('wheel', (e) => {
            if (isMouseControlActive) {
              e.preventDefault();
              let currentZoom = parseInt(zoomSlider.value);

              const scrollSpeedMultiplier = 2.5;
              if (e.deltaY < 0) {
                // Scroll up to zoom in
                currentZoom = Math.min(
                  zoomMaxGlobal,
                  currentZoom + zoomStep * scrollSpeedMultiplier
                );
              } else {
                // Scroll down to zoom out
                currentZoom = Math.max(
                  zoomMin,
                  currentZoom - zoomStep * scrollSpeedMultiplier
                );
              }
              zoomSlider.value = currentZoom;
              updateZoom(currentZoom);
            }
          });
        </script>
      </body>
    </html>
        """

@app.route('/video_feed')
def video_feed():
    """Route to stream the video frames."""
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/snapshots/list')
def list_snapshots():
    """API endpoint to get list of all snapshots."""
    try:
        snapshot_path = Path(SNAPSHOT_DIR)
        if not snapshot_path.exists():
            return jsonify({'error': 'Snapshot directory not found'}), 404
        
        # Get all .jpg files, sorted by filename (which includes timestamp)
        snapshots = sorted([f.name for f in snapshot_path.glob('*.jpg')])

        
        # Parse timestamps and create metadata
        snapshot_data = []
        for filename in snapshots:
            try:
                # Parse timestamp from filename (format: YYYYMMDD_HHMMSS.jpg)
                timestamp_str = filename.replace('.jpg', '')
                dt = datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S')
                snapshot_data.append({
                    'filename': filename,
                    'timestamp': dt.isoformat(),
                    'display': dt.strftime('%Y-%m-%d %H:%M:%S')
                })
            except ValueError:
                # Skip files that don't match the expected format
                continue
        
        return jsonify({'snapshots': snapshot_data})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/snapshots/image/<filename>')
def get_snapshot(filename):
    """Serve a specific snapshot image."""
    try:
        # Sanitize filename to prevent directory traversal
        safe_filename = os.path.basename(filename)
        filepath = os.path.join(SNAPSHOT_DIR, safe_filename)
        
        print(f"Attempting to serve: {filepath}")
        print(f"File exists: {os.path.exists(filepath)}")
        
        if not os.path.exists(filepath):
            print(f"File not found: {filepath}")
            return jsonify({'error': 'Snapshot not found'}), 404
        
        return send_file(filepath, mimetype='image/jpeg')
    except Exception as e:
        print(f"Error serving snapshot: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/snapshots')
def snapshots_page():
    """Serves the snapshot timeline browser page."""
    return """
    <!DOCTYPE html>
    <html>
      <head>

        <title>Snapshot Timeline</title>
        <style>
          * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
          }
          html, body {
            height: 100%;
            font-family: sans-serif;
            background-color: #111;
            color: #eee;
            overflow: hidden;

          }
          .container {
            display: flex;
            flex-direction: column;
            height: 100vh;
            padding: 20px;
            gap: 20px;
          }
          .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 20px;
            background: #222;
            border-radius: 8px;
          }
          .header h1 {
            font-size: 1.5em;
          }
          .nav-link {
            color: #007bff;
            text-decoration: none;
            padding: 8px 16px;
            border: 1px solid #007bff;
            border-radius: 4px;
            transition: all 0.2s;
          }
          .nav-link:hover {
            background: #007bff;
            color: white;
          }
          .image-container {
            flex: 1;
            display: flex;
            justify-content: center;
            align-items: center;
            background: #000;
            border-radius: 8px;
            overflow: hidden;

            position: relative;
            min-height: 0;
          }
          #snapshot-image {

            max-width: 100%;
            max-height: 100%;
            object-fit: contain;
          }
          .loading {
            position: absolute;
            color: #888;
            font-size: 1.2em;
          }
          .controls {
            background: #222;
            padding: 20px;
            border-radius: 8px;
            display: flex;
            flex-direction: column;
            gap: 15px;
          }
          .timeline-container {
            display: flex;
            align-items: center;
            gap: 15px;
          }
          .timeline-slider {
            flex: 1;
            -webkit-appearance: none;
            appearance: none;
            height: 20px;
            background: #444;
            outline: none;
            border-radius: 10px;
          }

          .timeline-slider::-webkit-slider-thumb {

            -webkit-appearance: none;
            appearance: none;
            width: 30px;
            height: 30px;
            background: #007bff;

            cursor: pointer;
            border-radius: 50%;
            border: 2px solid #fff;
          }
          .timeline-slider::-moz-range-thumb {
            width: 30px;
            height: 30px;
            background: #007bff;
            cursor: pointer;
            border-radius: 50%;
            border: 2px solid #fff;
          }

          .info-panel {
            display: flex;
            justify-content: space-between;

            align-items: center;
            flex-wrap: wrap;
            gap: 10px;
          }
          .timestamp {
            font-size: 1.2em;

            font-weight: bold;
            color: #007bff;
          }
          .counter {
            color: #888;
          }
          .button-group {
            display: flex;
            gap: 10px;
          }
          button {
            padding: 10px 20px;
            background: #007bff;
            border: none;
            border-radius: 4px;
            color: white;
            cursor: pointer;
            font-size: 1em;
            transition: background 0.2s;
          }
          button:hover {
            background: #0056b3;
          }
          button:disabled {
            background: #444;
            cursor: not-allowed;
          }
          .keyboard-hint {
            color: #666;
            font-size: 0.9em;
            text-align: center;
          }
        </style>
      </head>
      <body>
        <div class="container">
          <div class="header">
            <h1>Snapshot Timeline Browser</h1>
            <a href="/" class="nav-link">← Live Camera</a>
          </div>
          
          <div class="image-container">
            <div class="loading" id="loading">Loading snapshots...</div>
            <img id="snapshot-image" style="display: none;" />
          </div>
          
          <div class="controls">
            <div class="timeline-container">
              <button id="prev-btn" disabled>◀</button>
              <input 
                type="range" 
                id="timeline-slider" 
                class="timeline-slider"
                min="0"
                max="0"
                value="0"
                disabled
              />
              <button id="next-btn" disabled>▶</button>
            </div>
            

            <div class="info-panel">
              <div class="timestamp" id="timestamp">--</div>
              <div class="counter" id="counter">0 / 0</div>
              <div class="button-group">
                <button id="first-btn" disabled>⏮ First</button>
                <button id="last-btn" disabled>Last ⏭</button>
              </div>
            </div>
            
            <div class="keyboard-hint">
              Use ← → arrow keys or drag the slider to navigate
            </div>
          </div>
        </div>

        
        <script>
          let snapshots = [];
          let currentIndex = 0;
          

          const imageEl = document.getElementById('snapshot-image');
          const loadingEl = document.getElementById('loading');
          const sliderEl = document.getElementById('timeline-slider');
          const timestampEl = document.getElementById('timestamp');
          const counterEl = document.getElementById('counter');
          const prevBtn = document.getElementById('prev-btn');
          const nextBtn = document.getElementById('next-btn');
          const firstBtn = document.getElementById('first-btn');
          const lastBtn = document.getElementById('last-btn');
          
          // Load snapshot list
          async function loadSnapshots() {
            try {
              const response = await fetch('/snapshots/list');
              const data = await response.json();
              
              if (data.error) {
                loadingEl.textContent = 'Error: ' + data.error;
                return;
              }
              
              snapshots = data.snapshots;
              
              if (snapshots.length === 0) {
                loadingEl.textContent = 'No snapshots found';
                return;
              }
              
              // Initialize UI
              sliderEl.max = snapshots.length - 1;
              sliderEl.disabled = false;
              prevBtn.disabled = false;

              nextBtn.disabled = false;
              firstBtn.disabled = false;
              lastBtn.disabled = false;
              
              // Load the most recent snapshot
              currentIndex = snapshots.length - 1;
              loadSnapshot(currentIndex);
              
            } catch (error) {
              loadingEl.textContent = 'Error loading snapshots: ' + error.message;
            }
          }
          
          // Load and display a specific snapshot
          function loadSnapshot(index) {
            if (index < 0 || index >= snapshots.length) return;
            
            currentIndex = index;
            const snapshot = snapshots[index];
            
            imageEl.src = '/snapshots/image/' + snapshot.filename;
            imageEl.style.display = 'block';
            loadingEl.style.display = 'none';
            
            timestampEl.textContent = snapshot.display;
            counterEl.textContent = `${index + 1} / ${snapshots.length}`;
            sliderEl.value = index;
          }
          
          // Event listeners
          sliderEl.addEventListener('input', (e) => {
            loadSnapshot(parseInt(e.target.value));
          });

          
          prevBtn.addEventListener('click', () => {
            if (currentIndex > 0) {
              loadSnapshot(currentIndex - 1);
            }
          });
          
          nextBtn.addEventListener('click', () => {

            if (currentIndex < snapshots.length - 1) {
              loadSnapshot(currentIndex + 1);
            }
          });
          
          firstBtn.addEventListener('click', () => {
            loadSnapshot(0);
          });
          
          lastBtn.addEventListener('click', () => {
            loadSnapshot(snapshots.length - 1);
          });
          
          // Keyboard navigation
          document.addEventListener('keydown', (e) => {
            if (e.key === 'ArrowLeft') {
              e.preventDefault();
              if (currentIndex > 0) {
                loadSnapshot(currentIndex - 1);
              }
            } else if (e.key === 'ArrowRight') {
              e.preventDefault();
              if (currentIndex < snapshots.length - 1) {
                loadSnapshot(currentIndex + 1);
              }
            } else if (e.key === 'Home') {
              e.preventDefault();
              loadSnapshot(0);
            } else if (e.key === 'End') {
              e.preventDefault();
              loadSnapshot(snapshots.length - 1);
            }
          });
          
          // Load snapshots on page load
          loadSnapshots();
        </script>
      </body>
    </html>
    """

if __name__ == '__main__':
    # Run the Flask app
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)
