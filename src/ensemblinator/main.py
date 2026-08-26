from ensemblinator.scheduler.scheduler import Scheduler
from ensemblinator.notifier import notifier

import signal
from pathlib import Path
import sys
import argparse
import tomllib

ROOT_DIR = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT_DIR / "config"
JOBS_DIR = ROOT_DIR / "jobs"

_scheduler: Scheduler

def main():
    args = _parse_args()
    config = _load_config(args.config)
    _initialize(config)

    if args.manual_job_run is None:
        _run()
    else:
        _scheduler.run_immediate(args.manual_job_run)

def _parse_args():
    parser = argparse.ArgumentParser(prog="ensemblinator", add_help=False)
    parser.add_argument("--config", type=Path, required=True, help="path to ensemblinator.toml")
    parser.add_argument("--manual-job-run", type=Path, required=False, help="path to a job file to run once and immediately exit")
    return parser.parse_args()

def _load_config(config_path: Path):
    config_path = config_path.resolve()

    print("Loading configuration...")
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
    print("Initializing...")
    global _scheduler

    notifier.init_notifier(notifier.Notifier(config["notify"], config["paths"]["state_dir"]))

    _scheduler = Scheduler(config["paths"]["jobs_dir"], config["paths"]["state_dir"])

    signal.signal(signal.SIGTERM, _stop_app)

def _run():
    print("Starting services...")
    global _scheduler

    _scheduler.register_jobs()

    _scheduler.start()

    try:
        signal.pause()
    except KeyboardInterrupt:
        print("\rKeyboard interrupt: stopping...")

def _stop_app(signum, frame):
    sys.exit(0)

if __name__ == "__main__":
    main()
