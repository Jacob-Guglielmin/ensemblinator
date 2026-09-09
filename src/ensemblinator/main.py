import argparse
import logging
import signal
import sys
import threading
from pathlib import Path

from ensemblinator import error_handlers, installer, logging_setup
from ensemblinator.config import Config, load_config
from ensemblinator.connectivity.connectivity import wait_for_ntp_sync
from ensemblinator.notifier import notifier
from ensemblinator.scheduler.scheduler import Scheduler

ROOT_DIR = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT_DIR / "config"
JOBS_DIR = ROOT_DIR / "jobs"

_scheduler: Scheduler
_logger: logging.Logger


def main():
    args = _parse_args()
    if args.install:
        installer.install()
        sys.exit(0)

    sys.excepthook = error_handlers.handle_uncaught
    threading.excepthook = error_handlers.handle_thread_exception

    logging_setup.configure_logging(logging.INFO)

    global _logger
    _logger = logging.getLogger(__name__)

    try:
        config = load_config(args.config)
    except TypeError as e:
        _logger.fatal(e)
        sys.exit(1)
    _initialize(config)

    if not wait_for_ntp_sync(timeout=120, poll_interval=2):
        _logger.error("proceeding without confirmed NTP sync after timeout")

    if args.manual_job_run is None:
        _run()
    else:
        _scheduler.run_immediate(args.manual_job_run)


def _parse_args():
    parser = argparse.ArgumentParser(prog="ensemblinator", add_help=False)
    parser.add_argument(
        "--install",
        action="store_true",
        help="if set, rather than starting ensemblinator, sets up a systemd service to run automatically",
    )
    parser.add_argument("--config", type=Path, help="path to ensemblinator.toml")
    parser.add_argument(
        "--manual-job-run",
        type=Path,
        help="path to a job file to run once and immediately exit",
    )
    args = parser.parse_args()

    if args.install and (args.config or args.manual_job_run):
        parser.error("--install cannot be combined with --config or --manual-job-run")
    if not args.install and not args.config:
        parser.error("--config is required unless --install is set")

    return args


def _initialize(config: Config):
    _logger.info("initializing...")

    notifier.init_notifier(notifier.Notifier(config.notify, config.paths.state_dir))

    global _scheduler
    _scheduler = Scheduler(config.paths.jobs_dir, config.paths.state_dir)

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
