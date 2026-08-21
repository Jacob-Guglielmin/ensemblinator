import subprocess
import sys
import atexit
from pathlib import Path

_gunicorn_proc = None

def start_web(api_dir: Path, bind="0.0.0.0:5000", workers=1):
    global _gunicorn_proc
    _gunicorn_proc = subprocess.Popen(
        [
            sys.executable, "-m", "gunicorn",
            f"web.server:create_server('{api_dir}')",
            "--bind", bind,
            "--workers", str(workers),
            "--log-level", "warning"
        ],
        cwd=Path(__file__).resolve().parents[1]
    )
    atexit.register(stop_web)
    return _gunicorn_proc

def stop_web():
    global _gunicorn_proc
    if _gunicorn_proc and _gunicorn_proc.poll() is None:
        _gunicorn_proc.terminate()
        try:
            _gunicorn_proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            _gunicorn_proc.kill()
