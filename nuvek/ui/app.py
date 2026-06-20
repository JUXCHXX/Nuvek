import customtkinter as ctk
import qrcode
from PIL import Image
import threading
import time
import cv2
import subprocess
from nuvek.core.server import NuvekServer, get_latest_frame
from nuvek.core.virtual_cam import VirtualCam

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

RED   = "#D0271D"
GRAY1 = "#0f0f0f"
GRAY2 = "#1a1a1a"
GRAY3 = "#2a2a2a"
GRAY4 = "#444444"
LIGHT = "#EDEDED"
MUTED = "#666666"
GREEN = "#1DB954"
YELLOW= "#F0A500"

PREVIEW_W = 640
PREVIEW_H = 480

def fit_frame(frame, max_w, max_h):
    h, w = frame.shape[:2]
    scale = min(max_w / w, max_h / h)
    new_w = int(w * scale)
    new_h = int(h * scale)
    return cv2.resize(frame, (new_w, new_h)), new_w, new_h


class USBModal(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Potencia señal — USB")
        self.geometry("480x560")
        self.configure(fg_color=GRAY1)
        self.resizable(False, False)
        self.adb_active = False
        self._build()
        self.update_idletasks()
        self.grab_set()

    def _build(self):
        ctk.CTkLabel(self, text="🔌  Potencia señal por USB",
                     font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=LIGHT).pack(pady=(24, 4))
        ctk.CTkLabel(self, text="Conectado por USB la latencia baja drásticamente\ny la señal es estable sin depender del WiFi.",
                     font=ctk.CTkFont(size=11), text_color=MUTED,
                     justify="center").pack(pady=(0, 16))

        ctk.CTkFrame(self, height=2, fg_color=RED, corner_radius=1).pack(fill="x", padx=32, pady=(0, 20))

        steps_frame = ctk.CTkFrame(self, fg_color=GRAY2, corner_radius=12)
        steps_frame.pack(fill="x", padx=24, pady=(0, 16))

        ctk.CTkLabel(steps_frame, text="Cómo activar Depuración USB en Android",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=LIGHT).pack(anchor="w", padx=16, pady=(14, 8))

        steps = [
            ("1", "Abre  Ajustes  en tu celular"),
            ("2", "Ve a  Acerca del teléfono"),
            ("3", "Toca  Número de compilación  7 veces\nhasta ver 'Eres desarrollador'"),
            ("4", "Regresa a  Ajustes → Opciones de desarrollador"),
            ("5", "Activa  Depuración USB"),
            ("6", "Conecta el cable USB y acepta\nel permiso en la pantalla del celular"),
        ]
        for num, text in steps:
            row = ctk.CTkFrame(steps_frame, fg_color="transparent")
            row.pack(fill="x", padx=14, pady=3)
            ctk.CTkLabel(row, text=num,
                         font=ctk.CTkFont(size=10, weight="bold"),
                         fg_color=RED, text_color=LIGHT,
                         width=22, height=22, corner_radius=11).pack(side="left", padx=(0, 10))
            ctk.CTkLabel(row, text=text,
                         font=ctk.CTkFont(size=11), text_color=LIGHT,
                         justify="left").pack(side="left", anchor="w")

        ctk.CTkFrame(steps_frame, height=1, fg_color=GRAY3).pack(fill="x", padx=14, pady=(10, 0))
        ctk.CTkLabel(steps_frame,
                     text="⚠  Una vez conectado abre http://localhost:8080 en el navegador del celular",
                     font=ctk.CTkFont(size=10), text_color=YELLOW,
                     wraplength=400, justify="center").pack(pady=(8, 14))

        self.adb_status = ctk.CTkLabel(self, text="Estado ADB: desconectado",
                                        font=ctk.CTkFont(size=11), text_color=MUTED)
        self.adb_status.pack(pady=(0, 8))

        self.btn = ctk.CTkButton(self, text="Activar túnel USB",
                                  fg_color=RED, hover_color="#a01e16",
                                  font=ctk.CTkFont(size=13, weight="bold"),
                                  height=40, corner_radius=10,
                                  command=self._toggle_adb)
        self.btn.pack(padx=32, fill="x", pady=(0, 12))

        ctk.CTkButton(self, text="Cerrar",
                      fg_color=GRAY3, hover_color=GRAY4,
                      font=ctk.CTkFont(size=12),
                      height=36, corner_radius=10,
                      command=self.destroy).pack(padx=32, fill="x")

    def _toggle_adb(self):
        if not self.adb_active:
            threading.Thread(target=self._run_adb, daemon=True).start()
        else:
            self._stop_adb()

    def _run_adb(self):
        self.after(0, lambda: self.adb_status.configure(text="Conectando...", text_color=YELLOW))
        try:
            result = subprocess.run(["adb", "reverse", "tcp:8080", "tcp:8080"],
                                    capture_output=True, text=True, timeout=8)
            if result.returncode == 0:
                self.adb_active = True
                self.after(0, lambda: [
                    self.adb_status.configure(
                        text="✓ Túnel USB activo — usa http://localhost:8080 en el celular",
                        text_color=GREEN),
                    self.btn.configure(text="Desactivar túnel USB",
                                       fg_color=GRAY3, hover_color=GRAY4)
                ])
            else:
                err = result.stderr.strip() or "No se encontró dispositivo"
                self.after(0, lambda e=err: self.adb_status.configure(
                    text=f"Error: {e}", text_color=RED))
        except FileNotFoundError:
            self.after(0, lambda: self.adb_status.configure(
                text="Error: adb no está instalado", text_color=RED))
        except subprocess.TimeoutExpired:
            self.after(0, lambda: self.adb_status.configure(
                text="Timeout: verifica que el celular esté conectado", text_color=RED))

    def _stop_adb(self):
        try:
            subprocess.run(["adb", "reverse", "--remove", "tcp:8080"],
                           capture_output=True, timeout=5)
        except Exception:
            pass
        self.adb_active = False
        self.adb_status.configure(text="Túnel USB desactivado", text_color=MUTED)
        self.btn.configure(text="Activar túnel USB", fg_color=RED, hover_color="#a01e16")


class MonitoreoModal(ctk.CTkToplevel):
    def __init__(self, parent, get_stats_fn):
        super().__init__(parent)
        self.title("Monitoreo de señal")
        self.geometry("420x480")
        self.configure(fg_color=GRAY1)
        self.resizable(False, False)
        self.get_stats = get_stats_fn
        self._running = True
        self._build()
        self.update_idletasks()
        self.grab_set()
        self._update_loop()

    def _build(self):
        ctk.CTkLabel(self, text="📊  Monitoreo de señal",
                     font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=LIGHT).pack(pady=(24, 4))
        ctk.CTkLabel(self, text="Estadísticas en tiempo real de la conexión",
                     font=ctk.CTkFont(size=11), text_color=MUTED).pack(pady=(0, 16))

        ctk.CTkFrame(self, height=2, fg_color=RED, corner_radius=1).pack(fill="x", padx=32, pady=(0, 20))

        grid = ctk.CTkFrame(self, fg_color=GRAY2, corner_radius=12)
        grid.pack(fill="x", padx=24, pady=(0, 16))

        def stat_row(parent, label):
            row = ctk.CTkFrame(parent, fg_color="transparent")
            row.pack(fill="x", padx=20, pady=8)
            ctk.CTkLabel(row, text=label, font=ctk.CTkFont(size=12),
                         text_color=MUTED, width=140, anchor="w").pack(side="left")
            lbl = ctk.CTkLabel(row, text="—", font=ctk.CTkFont(size=13, weight="bold"),
                               text_color=LIGHT)
            lbl.pack(side="right")
            return lbl

        ctk.CTkLabel(grid, text="Rendimiento actual",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=MUTED).pack(anchor="w", padx=20, pady=(14, 0))

        self.lbl_fps     = stat_row(grid, "FPS recibidos")
        self.lbl_latency = stat_row(grid, "Latencia estimada")
        self.lbl_res     = stat_row(grid, "Resolución")
        self.lbl_frames  = stat_row(grid, "Frames totales")

        ctk.CTkFrame(grid, height=1, fg_color=GRAY3).pack(fill="x", padx=14, pady=(4, 0))

        ctk.CTkLabel(grid, text="Conexión",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=MUTED).pack(anchor="w", padx=20, pady=(12, 0))

        self.lbl_mode   = stat_row(grid, "Modo")
        self.lbl_signal = stat_row(grid, "Calidad señal")
        ctk.CTkLabel(grid, text="", height=8).pack()

        ctk.CTkFrame(self, height=1, fg_color=GRAY3).pack(fill="x", padx=24, pady=(0, 12))

        ctk.CTkButton(self, text="🔌  Potencia señal (USB)",
                      fg_color=GRAY3, hover_color=GRAY4,
                      font=ctk.CTkFont(size=12), height=38, corner_radius=10,
                      command=lambda: USBModal(self)).pack(padx=24, fill="x", pady=(0, 8))

        ctk.CTkButton(self, text="Cerrar",
                      fg_color=GRAY2, hover_color=GRAY3,
                      font=ctk.CTkFont(size=12), height=36, corner_radius=10,
                      command=self._close).pack(padx=24, fill="x")

    def _update_loop(self):
        if not self._running:
            return
        try:
            s = self.get_stats()
            fps     = s.get("fps", 0)
            latency = s.get("latency_ms", 0)
            fps_color = GREEN if fps >= 24 else (YELLOW if fps >= 10 else RED)
            lat_color = GREEN if latency < 100 else (YELLOW if latency < 300 else RED)
            self.lbl_fps.configure(text=f"{fps} fps", text_color=fps_color)
            self.lbl_latency.configure(text=f"{latency} ms", text_color=lat_color)
            self.lbl_res.configure(text=s.get("res", "—"))
            self.lbl_frames.configure(text=str(s.get("frames", 0)))
            self.lbl_mode.configure(text="WiFi / HTTPS")
            sig = "Buena" if fps >= 24 else ("Regular" if fps >= 10 else "Débil")
            self.lbl_signal.configure(text=sig,
                text_color=GREEN if fps >= 24 else (YELLOW if fps >= 10 else RED))
        except Exception:
            pass
        self.after(500, self._update_loop)

    def _close(self):
        self._running = False
        self.destroy()


class NuvekApp(ctk.CTk):
    def __init__(self, ngrok_url=None):
        super().__init__()
        self.title("Nuvek")
        self.geometry("1100x700")
        self.configure(fg_color=GRAY1)
        self.resizable(True, True)

        self.server       = NuvekServer()
        self.vcam         = VirtualCam()
        self.running      = False
        self.ngrok_url    = ngrok_url
        self._ctk_img     = None
        self._qr_img      = None
        self._last_count  = -1
        self._fps_times   = []
        self._pending     = None
        self._frame_total = 0
        self._last_res    = "—"
        self._last_fps    = 0
        self._last_frame_time = None

        self._build_ui()
        self._start_all()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=0)
        self.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(self, fg_color=GRAY2, corner_radius=14)
        left.grid(row=0, column=0, padx=(14,6), pady=14, sticky="nsew")
        left.grid_rowconfigure(1, weight=1)
        left.grid_columnconfigure(0, weight=1)

        hdr = ctk.CTkFrame(left, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=14, pady=(14,6))
        ctk.CTkLabel(hdr, text="Vista previa",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=LIGHT).pack(side="left")
        self.status_pill = ctk.CTkLabel(hdr, text="  Sin señal  ",
                                         font=ctk.CTkFont(size=11),
                                         fg_color=GRAY4, text_color=MUTED,
                                         corner_radius=8)
        self.status_pill.pack(side="right")

        self.preview = ctk.CTkLabel(left,
                                    text="Abre Firefox en tu celular\ny ve a la URL del QR",
                                    font=ctk.CTkFont(size=14),
                                    text_color=GRAY4, fg_color=GRAY1, corner_radius=10)
        self.preview.grid(row=1, column=0, padx=14, pady=(0,14), sticky="nsew")

        bar = ctk.CTkFrame(left, fg_color="transparent")
        bar.grid(row=2, column=0, sticky="ew", padx=14, pady=(0,14))
        self.res_label = ctk.CTkLabel(bar, text="—", font=ctk.CTkFont(size=11), text_color=MUTED)
        self.res_label.pack(side="left")
        self.fps_label = ctk.CTkLabel(bar, text="", font=ctk.CTkFont(size=11), text_color=MUTED)
        self.fps_label.pack(side="right")

        right_outer = ctk.CTkFrame(self, fg_color=GRAY2, corner_radius=14, width=280)
        right_outer.grid(row=0, column=1, padx=(6,14), pady=14, sticky="nsew")
        right_outer.grid_propagate(False)
        right_outer.grid_rowconfigure(0, weight=1)
        right_outer.grid_columnconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(right_outer, fg_color="transparent",
                                        scrollbar_button_color=GRAY3,
                                        scrollbar_button_hover_color=GRAY4)
        scroll.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)

        ctk.CTkLabel(scroll, text="NUVEK",
                     font=ctk.CTkFont(size=26, weight="bold"), text_color=LIGHT).pack(pady=(20,0))
        ctk.CTkLabel(scroll, text="camera bridge",
                     font=ctk.CTkFont(size=11), text_color=MUTED).pack(pady=(2,0))

        ctk.CTkFrame(scroll, height=2, fg_color=RED, corner_radius=1).pack(fill="x", padx=24, pady=14)

        self.qr_label = ctk.CTkLabel(scroll, text="generando QR...")
        self.qr_label.pack(pady=(0,8))

        self.url_label = ctk.CTkLabel(scroll, text="",
                                      font=ctk.CTkFont(size=10), text_color=MUTED, wraplength=230)
        self.url_label.pack(pady=(0,2))

        ctk.CTkLabel(scroll, text="Abre con Firefox en el celular",
                     font=ctk.CTkFont(size=10), text_color=RED).pack(pady=(0,14))

        ctk.CTkFrame(scroll, height=1, fg_color=GRAY3).pack(fill="x", padx=16, pady=(0,14))

        ctk.CTkLabel(scroll, text="SEÑAL",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=MUTED).pack(anchor="w", padx=20, pady=(0,6))

        ctk.CTkButton(scroll, text="📊  Monitoreo",
                      fg_color=GRAY3, hover_color=GRAY4,
                      font=ctk.CTkFont(size=12), height=36, corner_radius=10,
                      command=self._open_monitoreo).pack(padx=16, fill="x", pady=(0,6))

        ctk.CTkButton(scroll, text="🔌  Potencia señal",
                      fg_color=GRAY3, hover_color=GRAY4,
                      font=ctk.CTkFont(size=12), height=36, corner_radius=10,
                      command=self._open_usb).pack(padx=16, fill="x", pady=(0,6))

        ctk.CTkButton(scroll, text="⚠️  Matar puerto",
                      fg_color="#3a1a1a", hover_color="#5a2a2a",
                      font=ctk.CTkFont(size=12), height=36, corner_radius=10,
                      command=self._kill_port).pack(padx=16, fill="x", pady=(0,14))

        ctk.CTkFrame(scroll, height=1, fg_color=GRAY3).pack(fill="x", padx=16, pady=(0,14))

        ctk.CTkLabel(scroll, text="OBS",
                     font=ctk.CTkFont(size=10, weight="bold"), text_color=MUTED).pack(anchor="w", padx=20)
        ctk.CTkLabel(scroll, text="/dev/video10  •  Nuvek Camera",
                     font=ctk.CTkFont(size=10), text_color=LIGHT).pack(anchor="w", padx=20, pady=(4,2))
        ctk.CTkLabel(scroll, text="Fuentes → + → Dispositivo\nde video → Nuvek Camera",
                     font=ctk.CTkFont(size=10), text_color=MUTED,
                     justify="left").pack(anchor="w", padx=20, pady=(0,20))

    def _kill_port(self):
        import subprocess
        result = subprocess.run(
            "sudo kill -9 $(sudo lsof -t -i:8080) 2>/dev/null; echo ok",
            shell=True, capture_output=True, text=True
        )
        self.server.start()

    def _open_monitoreo(self):
        MonitoreoModal(self, self._get_stats)

    def _open_usb(self):
        USBModal(self)

    def _get_stats(self):
        latency = 0
        if self._last_frame_time is not None:
            latency = int((time.time() - self._last_frame_time) * 1000)
            latency = min(latency, 9999)
        return {
            "fps":        self._last_fps,
            "latency_ms": latency,
            "res":        self._last_res,
            "frames":     self._frame_total,
        }

    def _start_all(self):
        self.server.start()
        self.vcam.start()
        qr_url = self.ngrok_url or self.server.url
        self.url_label.configure(text=qr_url)
        self._gen_qr(qr_url)
        self.running = True
        threading.Thread(target=self._preview_loop, daemon=True).start()
        self._tick()

    def _gen_qr(self, url):
        qr = qrcode.QRCode(border=2)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#0f0f0f", back_color="#EDEDED")
        img = img.resize((190, 190), Image.NEAREST)
        self._qr_img = ctk.CTkImage(light_image=img, dark_image=img, size=(190, 190))
        self.qr_label.configure(image=self._qr_img, text="")

    def _preview_loop(self):
        while self.running:
            frame, count = get_latest_frame()
            if frame is None or count == self._last_count:
                time.sleep(0.005)
                continue
            self._last_count = count
            self._frame_total += 1
            self._last_frame_time = time.time()
            now = time.time()
            self._fps_times.append(now)
            self._fps_times = [t for t in self._fps_times if now - t < 1.0]
            real_fps = len(self._fps_times)
            self._last_fps = real_fps
            h, w = frame.shape[:2]
            self._last_res = f"{w}×{h}"
            fitted, fw, fh = fit_frame(frame, PREVIEW_W, PREVIEW_H)
            rgb = cv2.cvtColor(fitted, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(rgb)
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(fw, fh))
            self._pending = (ctk_img, w, h, real_fps)

    def _tick(self):
        if not self.running:
            return
        if self._pending is not None:
            ctk_img, w, h, real_fps = self._pending
            self._pending = None
            self._ctk_img = ctk_img
            self.preview.configure(image=ctk_img, text="")
            self.res_label.configure(text=f"{w}×{h}")
            self.fps_label.configure(text=f"{real_fps} fps")
            self.status_pill.configure(text="  En vivo  ", fg_color=RED, text_color=LIGHT)
        self.after(16, self._tick)

    def on_closing(self):
        self.running = False
        self.vcam.stop()
        self.server.stop()
        self.destroy()
