from ensemblinator.web.manager import API
from ensemblinator.scheduler.scheduler import Scheduler
from ensemblinator.common.notifier import notifier

import signal
from pathlib import Path
import sys
import argparse
import tomllib

ROOT_DIR = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT_DIR / "config"
API_DIR = ROOT_DIR / "api"
JOBS_DIR = ROOT_DIR / "jobs"

_scheduler: Scheduler
_api: API

def main():
    args = _parse_args()
    config = _load_config(args.config)
    _initialize(config)
    _run()

def _parse_args():
    parser = argparse.ArgumentParser(prog="ensemblinator")
    parser.add_argument("--config", type=Path, required=True, help="path to ensemblinator.toml")
    return parser.parse_args()

def _load_config(config_path: Path):
    with open(config_path, "rb") as f:
        config = tomllib.load(f)

    config_dir = config_path.parent
    for key in ("jobs_dir", "api_dir"):
        p = Path(config["paths"][key])
        if not p.is_absolute():
            p = (config_dir / p)
        config["paths"][key] = p.resolve()

    return config

def _initialize(config: dict):
    global _scheduler
    global _api

    notifier.init_notifier(notifier.Notifier(config["notify"]))

    _scheduler = Scheduler(config["paths"]["jobs_dir"])
    _scheduler.register_jobs()

    _api = API(config["paths"]["api_dir"], host="0.0.0.0", port=5000, workers=1)

    signal.signal(signal.SIGTERM, _stop_app)

def _run():
    global _scheduler
    global _api

    _scheduler.start()
    _api.start()

    try:
        signal.pause()
    except KeyboardInterrupt:
        print("\rKeyboard interrupt: stopping...")

def _stop_app(signum, frame):
    sys.exit(0)

if __name__ == "__main__":
    main()
