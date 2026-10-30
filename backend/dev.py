"""Inicia a interface Blade e a API Python para desenvolvimento local."""

import os
import secrets
import signal
import socket
import subprocess
import sys
import time
from urllib.request import urlopen
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
environment = os.environ.copy()
environment.setdefault("SECRET_KEY", secrets.token_urlsafe(48))
environment.setdefault("PYTHON_API_URL", "http://localhost:8001")
# O Laravel só entrega Blade; seu middleware de sessão também não precisa de MySQL.
environment["SESSION_DRIVER"] = "file"
environment["CACHE_STORE"] = "file"
environment["QUEUE_CONNECTION"] = "sync"

def port_is_open(port: int) -> bool:
    with socket.socket() as connection:
        connection.settimeout(0.5)
        return connection.connect_ex(("127.0.0.1", port)) == 0


def is_our_service(port: int) -> bool:
    try:
        with urlopen(f"http://127.0.0.1:{port}/", timeout=1) as response:
            body = response.read(4096).decode("utf-8", errors="ignore")
            return ("Cadastro Seguro" in body) if port == 8000 else '"Cadastro Seguro API"' in body
    except Exception:
        return False


ports = {8000: "interface Blade", 8001: "API Python"}
for port, service in ports.items():
    if port_is_open(port) and not is_our_service(port):
        raise SystemExit(f"A porta {port} já está sendo usada por outro serviço ({service}). Feche-o e tente novamente.")

processes = []
if not port_is_open(8001):
    processes.append(subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app:app", "--app-dir", "backend", "--reload", "--host", "0.0.0.0", "--port", "8001"],
        cwd=ROOT, env=environment, start_new_session=True,
    ))
if not port_is_open(8000):
    processes.append(subprocess.Popen(
        ["php", "artisan", "serve", "--host=0.0.0.0", "--port=8000"],
        cwd=ROOT, env=environment, start_new_session=True,
    ))

print("Interface: http://localhost:8000", flush=True)
print("API Python: http://localhost:8001", flush=True)
if not processes:
    print("A aplicação já estava rodando.", flush=True)
    raise SystemExit(0)

try:
    while all(process.poll() is None for process in processes):
        time.sleep(0.25)
finally:
    for process in processes:
        if process.poll() is None:
            process.send_signal(signal.SIGTERM)
    for process in processes:
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()

exit_code = next((process.returncode for process in processes if process.returncode not in (0, None)), 0)
raise SystemExit(exit_code)
