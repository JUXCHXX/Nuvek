import cv2
import threading
import subprocess
import numpy as np
from nuvek.core.server import get_latest_frame

VIRTUAL_DEVICE = "/dev/video10"
WIDTH  = 1280
HEIGHT = 720
FPS    = 30

class VirtualCam:
    def __init__(self):
        self.running = False
        self.thread  = None
        self.process = None

    def start(self):
        if self.running:
            return
        self.running = True
        self._start_ffmpeg()
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def _start_ffmpeg(self):
        cmd = [
            "ffmpeg",
            "-loglevel", "quiet",
            "-f", "rawvideo",
            "-pix_fmt", "bgr24",
            "-s", f"{WIDTH}x{HEIGHT}",
            "-r", str(FPS),
            "-i", "pipe:0",
            "-pix_fmt", "yuv420p",
            "-f", "v4l2",
            VIRTUAL_DEVICE
        ]
        self.process = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    def _loop(self):
        blank = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
        while self.running:
            frame, _ = get_latest_frame()
            if frame is None:
                out = blank
            else:
                out = cv2.resize(frame, (WIDTH, HEIGHT))
            try:
                self.process.stdin.write(out.tobytes())
            except Exception:
                break

    def stop(self):
        self.running = False
        if self.process:
            try:
                self.process.stdin.close()
                self.process.terminate()
            except Exception:
                pass
            self.process = None
