from flask import Blueprint

bp = Blueprint("root", __name__, url_prefix="/")

@bp.route("/health")
def health():
    return "OK"
