from flask import Blueprint
from flask import current_app as app

bp = Blueprint('leaderboard', __name__, url_prefix='/leaderboard')


@bp.route("/<leaderboard_id>", methods=["GET"])
def get_leaderboard(leaderboard_id):
    return {"data" : app.db_client.collection("leaderboards").document(leaderboard_id).get().to_dict()}
