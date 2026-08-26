from ensemblinator.scheduler.scheduler import Scheduler
from ensemblinator.notifier import notifier
from ensemblinator import error_handlers, logging_setup

import signal
from pathlib import Path
import sys
import argparse
import tomllib
import threading
import logging

ROOT_DIR = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT_DIR / "config"
JOBS_DIR = ROOT_DIR / "jobs"

_scheduler: Scheduler
_logger: logging.Logger

def main():
    sys.excepthook = error_handlers.handle_uncaught
    threading.excepthook = error_handlers.handle_thread_exception

    try:
        logging_setup.configure_logging(logging.INFO)

        global _logger
        _logger = logging.getLogger(__name__)

        args = _parse_args()
        config = _load_config(args.config)
        _initialize(config)

        if args.manual_job_run is None:
            _run()
        else:
            _scheduler.run_immediate(args.manual_job_run)
    except Exception as e:
        error_handlers.notify_crash(e)
        sys.exit(1)

def _parse_args():
    parser = argparse.ArgumentParser(prog="ensemblinator", add_help=False)
    parser.add_argument("--config", type=Path, required=True, help="path to ensemblinator.toml")
    parser.add_argument("--manual-job-run", type=Path, required=False, help="path to a job file to run once and immediately exit")
    return parser.parse_args()

def _load_config(config_path: Path):
    config_path = config_path.resolve()

    _logger.info("loading configuration...")
    with open(config_path, "rb") as f:
        config = tomllib.load(f)

    # TODO validation

    config_dir = config_path.parent
    for key in ("jobs_dir", "state_dir"):
        p = Path(config["paths"][key])
        if not p.is_absolute():
            p = (config_dir / p)
        config["paths"][key] = p.resolve()

    return config

def _initialize(config: dict):
    _logger.info("initializing...")

    notifier.init_notifier(notifier.Notifier(config["notify"], config["paths"]["state_dir"]))

    global _scheduler
    _scheduler = Scheduler(config["paths"]["jobs_dir"], config["paths"]["state_dir"])

    signal.signal(signal.SIGTERM, _stop_app)
    signal.signal(signal.SIGINT, _stop_app)

def _run():
    _logger.info("starting services...")

    _scheduler.register_jobs()

    _scheduler.start()

    _logger.info("all systems running")

    signal.pause()

def _stop_app(signum, frame):
    sys.exit(0)

if __name__ == "__main__":
    main()
