from flask import Blueprint, current_app, jsonify

from ensemblinator.db.clients import WebAPIClient

bp = Blueprint("api", __name__, url_prefix="/api")


@bp.get("ping")
def ping():
    return jsonify({"ok": True})


def _get_db() -> WebAPIClient:
    return current_app.config["DB_CLIENT"]
