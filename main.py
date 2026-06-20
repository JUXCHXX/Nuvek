import socket
from nuvek.ui.app import NuvekApp

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip = s.getsockname()[0]
    s.close()
    return ip

if __name__ == "__main__":
    local_ip = get_local_ip()
    local_url = f"https://{local_ip}:8080"
    print(f"URL: {local_url}")
    app = NuvekApp(ngrok_url=local_url)
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
