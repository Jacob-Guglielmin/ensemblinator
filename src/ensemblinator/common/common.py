from pathlib import Path
import os

# TODO this will most certainly not work anymore
STATE_DIR = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "ensemblinator"
SKIPPED_DISCOVERY_DIRS = {"node_modules", "__pycache__", ".git"}
