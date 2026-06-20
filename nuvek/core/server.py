import socket
import threading
from flask import Flask, request, jsonify
from flask_cors import CORS
import cv2
import numpy as np

PORT = 8080

_latest_frame  = None
_frame_counter = 0
_frame_lock    = threading.Lock()

_cam_config = {
    "fps":        30,
    "brightness": 0,
    "contrast":   0,
    "saturation": 0,
}
_config_lock = threading.Lock()

app = Flask(__name__)
CORS(app)

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    finally:
        s.close()

@app.route("/")
def index():
    return get_html()

@app.route("/frame", methods=["POST"])
def receive_frame():
    global _latest_frame, _frame_counter
    data  = request.data
    arr   = np.frombuffer(data, np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if frame is not None:
        with _config_lock:
            brightness = _cam_config["brightness"]
            contrast   = _cam_config["contrast"]
            saturation = _cam_config["saturation"]

        if brightness != 0 or contrast != 0:
            alpha = 1.0 + contrast / 100.0
            beta  = brightness
            frame = cv2.convertScaleAbs(frame, alpha=alpha, beta=beta)

        if saturation != 0:
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV).astype("float32")
            hsv[:, :, 1] = np.clip(hsv[:, :, 1] * (1 + saturation / 100.0), 0, 255)
            frame = cv2.cvtColor(hsv.astype("uint8"), cv2.COLOR_HSV2BGR)

        with _frame_lock:
            _latest_frame  = frame
            _frame_counter += 1

    return "ok", 200

@app.route("/config", methods=["POST"])
def set_config():
    data = request.get_json(silent=True) or {}
    with _config_lock:
        for key in ("fps", "brightness", "contrast", "saturation"):
            if key in data:
                _cam_config[key] = int(data[key])
    return jsonify(_cam_config)

@app.route("/config", methods=["GET"])
def get_config():
    with _config_lock:
        return jsonify(_cam_config)

def get_html():
    return """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Nuvek</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { background:#0a0a0a; color:#eee; font-family:sans-serif;
       display:flex; flex-direction:column; min-height:100vh; }
video { width:100vw; max-height:50vh; object-fit:contain; background:#000; }
.controls { padding:14px; display:flex; flex-direction:column; gap:12px; }
.section-title { font-size:10px; color:#555; text-transform:uppercase; letter-spacing:1px; margin-bottom:2px; }
.row { display:flex; align-items:center; justify-content:space-between; gap:10px; }
label { font-size:12px; color:#888; min-width:90px; }
input[type=range] { flex:1; accent-color:#D0271D; }
span.val { font-size:12px; color:#eee; min-width:40px; text-align:right; }
button { padding:10px; border-radius:8px; border:none; background:#D0271D;
         color:#fff; font-size:14px; font-weight:500; cursor:pointer; flex:1; }
#status { font-size:11px; color:#555; text-align:center; padding:4px; }
select { background:#1a1a1a; color:#eee; border:1px solid #333;
         border-radius:6px; padding:6px; font-size:13px; flex:1; }
hr { border:none; border-top:1px solid #1e1e1e; margin:4px 0; }
</style>
</head>
<body>
<video id="v" autoplay playsinline muted></video>
<div class="controls">
  <div class="row">
    <button onclick="flip()">Cambiar camara</button>
  </div>
  <hr>
  <div class="section-title">Stream</div>
  <div class="row">
    <label>Calidad JPEG</label>
    <input type="range" id="quality" min="20" max="100" value="60"
           oninput="document.getElementById('qval').textContent=this.value+'%'">
    <span class="val" id="qval">60%</span>
  </div>
  <div class="row">
    <label>Resolucion</label>
    <select id="resolution" onchange="changeRes()">
      <option value="1920x1080">1080p</option>
      <option value="1280x720" selected>720p</option>
      <option value="854x480">480p</option>
      <option value="640x360">360p</option>
    </select>
  </div>
  <div class="row">
    <label>FPS limite</label>
    <input type="range" id="fps" min="5" max="60" value="30"
           oninput="document.getElementById('fval').textContent=this.value; sendConfig()">
    <span class="val" id="fval">30</span>
  </div>
  <hr>
  <div class="section-title">Imagen</div>
  <div class="row">
    <label>Brillo</label>
    <input type="range" id="brightness" min="-100" max="100" value="0"
           oninput="document.getElementById('bval').textContent=this.value; sendConfig()">
    <span class="val" id="bval">0</span>
  </div>
  <div class="row">
    <label>Contraste</label>
    <input type="range" id="contrast" min="-100" max="100" value="0"
           oninput="document.getElementById('cval').textContent=this.value; sendConfig()">
    <span class="val" id="cval">0</span>
  </div>
  <div class="row">
    <label>Saturacion</label>
    <input type="range" id="saturation" min="-100" max="100" value="0"
           oninput="document.getElementById('sval').textContent=this.value; sendConfig()">
    <span class="val" id="sval">0</span>
  </div>
  <div id="status">iniciando...</div>
</div>
<script>
let facing = 'environment';
let stream = null;
let sending = false;
let resW = 1280, resH = 720;
const canvas = document.createElement('canvas');
const ctx2d = canvas.getContext('2d');

async function start() {
  if (stream) stream.getTracks().forEach(t => t.stop());
  sending = false;
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: facing, width: {ideal: resW}, height: {ideal: resH} },
      audio: false
    });
    const v = document.getElementById('v');
    v.srcObject = stream;
    await v.play();
    const s = stream.getVideoTracks()[0].getSettings();
    resW = s.width || resW;
    resH = s.height || resH;
    canvas.width = resW;
    canvas.height = resH;
    document.getElementById('status').textContent =
      (facing==='environment'?'trasera':'delantera') + ' — ' + resW + 'x' + resH;
    startSending(v);
  } catch(e) {
    document.getElementById('status').textContent = 'Error: ' + e.message;
  }
}

function startSending(v) {
  sending = true;
  let lastSend = 0;
  function loop(ts) {
    if (!sending) return;
    const targetFps = parseInt(document.getElementById('fps').value);
    const interval = 1000 / targetFps;
    if (ts - lastSend >= interval && v.readyState >= 2) {
      lastSend = ts;
      const quality = parseInt(document.getElementById('quality').value) / 100;
      ctx2d.drawImage(v, 0, 0, canvas.width, canvas.height);
      canvas.toBlob(blob => {
        if (blob) {
          fetch('/frame', {
            method: 'POST', body: blob,
            headers: {'Content-Type': 'image/jpeg'}
          }).catch(()=>{});
        }
      }, 'image/jpeg', quality);
    }
    requestAnimationFrame(loop);
  }
  requestAnimationFrame(loop);
}

function sendConfig() {
  fetch('/config', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      fps:        parseInt(document.getElementById('fps').value),
      brightness: parseInt(document.getElementById('brightness').value),
      contrast:   parseInt(document.getElementById('contrast').value),
      saturation: parseInt(document.getElementById('saturation').value),
    })
  }).catch(()=>{});
}

function flip() {
  facing = facing === 'environment' ? 'user' : 'environment';
  start();
}

function changeRes() {
  const val = document.getElementById('resolution').value.split('x');
  resW = parseInt(val[0]);
  resH = parseInt(val[1]);
  start();
}

start();
</script>
</body>
</html>"""

CERT_PATH = "/home/devflorian/nuvek/cert.pem"
KEY_PATH  = "/home/devflorian/nuvek/key.pem"

class NuvekServer:
    def __init__(self):
        self.thread = None
        self.ip = get_local_ip()
        self.url = f"https://{self.ip}:{PORT}"

    def start(self):
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        app.run(host="0.0.0.0", port=PORT,
                debug=False, use_reloader=False, threaded=True,
                ssl_context=(CERT_PATH, KEY_PATH))

    def stop(self):
        pass

def get_latest_frame():
    with _frame_lock:
        return _latest_frame, _frame_counter
