import subprocess
import sys
import atexit
from pathlib import Path

class API():
    def __init__(self, api_dir: Path, host: str, port: int, workers: int):
        self._api_dir = api_dir
        self._host = host
        self._port = port
        self._workers = workers

    def start(self):
        self._gunicorn_proc = subprocess.Popen(
            [
                sys.executable, "-m", "gunicorn",
                f"web.server:create_server('{self._api_dir}')",
                "--bind", f"{self._host}:{self._port}",
                "--workers", str(self._workers),
                "--log-level", "warning"
            ],
            cwd=Path(__file__).resolve().parents[1]
        )
        atexit.register(self.stop)

    def stop(self):
        if self._gunicorn_proc and self._gunicorn_proc.poll() is None:
            self._gunicorn_proc.terminate()
            try:
                self._gunicorn_proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._gunicorn_proc.kill()
