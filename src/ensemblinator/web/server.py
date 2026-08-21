from ensemblinator.common import common

from flask import Flask
from pathlib import Path
import importlib.util

def discover_blueprints(api_dir: Path):
    for path in sorted(api_dir.rglob("*.py")):
        if path.name.startswith("_"):
            continue
        if any(part in common.SKIPPED_DISCOVERY_DIRS for part in path.relative_to(api_dir).parts):
            continue
        spec = importlib.util.spec_from_file_location(f"api_endpoints.{path.stem}", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        bp = getattr(module, "bp", None)
        if bp is None:
            continue
        yield bp

def create_server(api_dir: str):
    app = Flask(__name__)
    for bp in discover_blueprints(Path(api_dir)):
        app.register_blueprint(bp)
    return app
