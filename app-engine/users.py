from firebase_admin import firestore
from flask import Blueprint


bp = Blueprint('users', __name__, url_prefix='/users')

syncDb = firestore.client()


@bp.route("/<user_id>", methods=["GET"])
def get_user(user_id):
    return {"data": _get_user_firestore(user_id)}, 200


def _get_user_firestore(user_id):
    data = syncDb.collection('users').document(user_id).get().to_dict()

    if not data:
        return None

    if "scores" in data and data["scores"].get("number_of_scored_games", 0) != 0:
        data["avg_score"] = data["scores"]["total_sum"] / data["scores"]["number_of_scored_games"]

    return data
