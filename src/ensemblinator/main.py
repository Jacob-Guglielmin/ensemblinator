import argparse
import logging
import signal
import sys
import threading
from pathlib import Path

from ensemblinator import error_handlers, installer, logging_setup
from ensemblinator.config import Config, load_config
from ensemblinator.connectivity.connectivity import wait_for_ntp_sync
from ensemblinator.db.clients import Database
from ensemblinator.jobs.registry import JobRegistry
from ensemblinator.notifier import notifier
from ensemblinator.scheduler.scheduler import Scheduler
from ensemblinator.webui.process import WebAPIProcess

ROOT_DIR = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT_DIR / "config"
JOBS_DIR = ROOT_DIR / "jobs"

_database: Database
_job_registry: JobRegistry
_scheduler: Scheduler
_webui: WebAPIProcess
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

    _run()


def _parse_args():
    parser = argparse.ArgumentParser(prog="ensemblinator", add_help=False)
    parser.add_argument(
        "--install",
        action="store_true",
        help="if set, rather than starting ensemblinator, sets up a systemd service to run automatically",
    )
    parser.add_argument("--config", type=Path, help="path to ensemblinator.toml")
    args = parser.parse_args()

    if args.install and args.config:
        parser.error("--install cannot be combined with --config")
    if not args.install and not args.config:
        parser.error("--config is required unless --install is set")

    return args


def _initialize(config: Config):
    _logger.info("initializing...")

    notifier.init_notifier(notifier.Notifier(config.notify, config.paths.state_dir))

    global _database
    _database = Database(config.paths.state_dir)

    global _job_registry
    _job_registry = JobRegistry(_database, config.paths.jobs_dir)

    jobs = _job_registry.discover()

    global _scheduler
    _scheduler = Scheduler(jobs, _database, config.paths.state_dir)

    global _webui
    _webui = WebAPIProcess(config.paths.state_dir)

    signal.signal(signal.SIGTERM, _stop_app)
    signal.signal(signal.SIGINT, _stop_app)


def _run():
    _logger.info("starting services...")

    _scheduler.start()

    _webui.start()

    _logger.info("all systems running")

    signal.pause()


def _stop_app(signum, frame):
    _webui.begin_stop()
    _scheduler.shutdown(timeout=50.0)
    _webui.ensure_killed(timeout=2.0)
    _database.close()
    sys.exit(0)


if __name__ == "__main__":
    main()
