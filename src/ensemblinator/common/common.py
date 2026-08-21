from pathlib import Path
import os

SRC_DIR = Path(__file__).resolve().parents[1]
STATE_DIR = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "ensemblinator"
SKIPPED_DISCOVERY_DIRS = {"node_modules", "__pycache__", ".git"}
