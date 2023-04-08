import os

import flask
from firebase_admin import firestore
from flask import Blueprint
from flask import current_app as app

from utils import get_remote_config

bp = Blueprint('users', __name__, url_prefix='/users')


@bp.route("/<user_id>", methods=["GET", "POST"])
def get_user(user_id):
    if flask.request.method == "GET":
        return {"data": _get_user_firestore(user_id)}, 200
    elif flask.request.method == "POST":
        data = flask.request.get_json()
        app.db_client.collection("users").document(user_id).update(data)
        return {}, 200


@bp.route("/test", methods=["GET"])
def test():
    t = get_remote_config()
    print(t)
    print(os.environ)
    return {}, 200


@bp.route("/<user_id>/tokens", methods=["POST"])
def add_token(user_id):
    data = flask.request.get_json()
    app.db_client.collection("users").document(user_id)\
        .update({"tokens": firestore.firestore.ArrayUnion([data["token"]])})
    return {}, 200


def _get_user_firestore(user_id):
    data = app.db_client.collection('users').document(user_id).get().to_dict()

    if not data:
        return None

    if "scores" in data and data["scores"].get("number_of_scored_games", 0) != 0:
        data["avg_score"] = data["scores"]["total_sum"] / data["scores"]["number_of_scored_games"]

    return data
