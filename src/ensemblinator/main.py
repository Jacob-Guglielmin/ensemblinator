import web
from scheduler import Scheduler
from common.notifier import Notifier, init_notifier

import signal
from pathlib import Path
import signal
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT_DIR / "config"
API_DIR = ROOT_DIR / "api"
JOBS_DIR = ROOT_DIR / "jobs"

def start_app():
    init_notifier(Notifier(CONFIG_DIR))

    scheduler = Scheduler(JOBS_DIR)
    web.start_web(API_DIR)

    signal.signal(signal.SIGTERM, stop_app)
    signal.signal(signal.SIGINT, stop_app)

    try:
        signal.pause()
    except KeyboardInterrupt:
        print("\rKeyboard interrupt: stopping...")

def stop_app():
    sys.exit(0)

if __name__ == "__main__":
    start_app()
