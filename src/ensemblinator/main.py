from ensemblinator.web import manager
from ensemblinator.scheduler.scheduler import Scheduler
from ensemblinator.common.notifier import notifier

import signal
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT_DIR / "config"
API_DIR = ROOT_DIR / "api"
JOBS_DIR = ROOT_DIR / "jobs"

def start_app():
    notifier.init_notifier(notifier.Notifier(CONFIG_DIR))

    scheduler = Scheduler(JOBS_DIR)
    manager.start_web(API_DIR)

    signal.signal(signal.SIGTERM, stop_app)
    signal.signal(signal.SIGINT, stop_app)

    try:
        signal.pause()
    except KeyboardInterrupt:
        print("\rKeyboard interrupt: stopping...")

def stop_app(signum, frame):
    sys.exit(0)

if __name__ == "__main__":
    start_app()
