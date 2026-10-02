from pathlib import Path

from flask import Flask, send_from_directory

from ensemblinator.db.clients import WebAPIClient
from ensemblinator.webui.api import bp as api_bp

STATIC_DIR = Path(__file__).parent / "static"


def create_app(state_dir: Path) -> Flask:
    app = Flask(__name__, static_folder=None)
    app.config["DB_CLIENT"] = WebAPIClient(state_dir)
    app.register_blueprint(api_bp)

    @app.get("/")
    @app.get("/<path:path>")
    def serve_ui(path=""):
        requested = STATIC_DIR / path
        if path and requested.is_file():
            return send_from_directory(STATIC_DIR, path)
        return send_from_directory(STATIC_DIR, "index.html")

    return app
