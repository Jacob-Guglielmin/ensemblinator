import logging
import os
import subprocess
import sys
from pathlib import Path

_logger = logging.getLogger(__name__)


class WebAPIProcess:
    def __init__(self, state_dir: Path, host: str = "0.0.0.0", port: int = 5000):
        self._state_dir = state_dir
        self._host = host
        self._port = port
        self._proc: subprocess.Popen | None = None

    def start(self) -> None:
        env = os.environ.copy()
        env["ENSEMBLINATOR_STATE_DIR"] = str(self._state_dir)
        self._proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "gunicorn",
                "ensemblinator.webui.wsgi:app",
                "--bind",
                f"{self._host}:{self._port}",
                "--log-level",
                "warning",
            ],
            env=env,
        )

    def begin_stop(self) -> None:
        if self._proc is not None:
            _logger.info("shutting down web ui...")
            self._proc.terminate()

    def ensure_killed(self, timeout: float) -> None:
        if self._proc is None:
            return
        try:
            self._proc.wait(timeout)
        except subprocess.TimeoutExpired:
            self._proc.kill()
            self._proc.wait()
        _logger.info("web ui shutdown complete")
