import os
from pathlib import Path

from ensemblinator.webui.app import create_app

state_dir = Path(os.environ["ENSEMBLINATOR_STATE_DIR"])
app = create_app(state_dir)
