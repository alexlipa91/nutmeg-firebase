import os

import firebase_admin
import flask
import stripe
from firebase_admin import firestore
from flask import Blueprint, Flask
from flask import current_app as app


bp = Blueprint('users', __name__, url_prefix='/users')


@bp.route("/<user_id>", methods=["GET", "POST"])
def get_user(user_id):
    if flask.request.method == "GET":
        return {"data": _get_user_firestore(user_id)}, 200
    elif flask.request.method == "POST":
        data = flask.request.get_json()
        app.db_client.collection("users").document(user_id).update(data)
        return {}, 200


@bp.route("/<user_id>/add", methods=["POST"])
def add_user(user_id):
    data = flask.request.get_json()
    _add_user(user_id, data)
    return {}, 200

@bp.route("/<user_id>/tokens", methods=["POST"])
def add_token(user_id):
    data = flask.request.get_json()
    app.db_client.collection("users").document(user_id)\
        .update({"tokens": firestore.firestore.ArrayUnion([data["token"]])})
    return {}, 200


@bp.route("/organisers_with_fee", methods=["GET"])
def get_organisers_with_fees():
    return {'data': {'users': ['bQHD0EM265V6GuSZuy1uQPHzb602', 'IwrZWBFb4LZl3Kto1V3oUKPnCni1']}}, 200


def _add_user(user_id,data, create_stripe_customer=True):
    assert "email" in data, "Required field missing"
    data["createdAt"] = firestore.firestore.SERVER_TIMESTAMP

    if create_stripe_customer:
        # create stripe customer
        stripe.api_key = os.environ["STRIPE_KEY"]
        response = stripe.Customer.create(
            email=data.get("email", None),
            name=data.get("name", None)
        )
        data["stripeId"] = response["id"]

    doc_ref = app.db_client.collection('users').document(user_id)
    doc_ref.set(data)

def _get_user_firestore(user_id):
    data = app.db_client.collection('users').document(user_id).get().to_dict()

    if not data:
        return None

    if "scores" in data and data["scores"].get("number_of_scored_games", 0) != 0:
        data["avg_score"] = data["scores"]["total_sum"] / data["scores"]["number_of_scored_games"]

    if "last_date_scores" in data and len(data["last_date_scores"]) > 10:
        l = data["last_date_scores"]
        l_top = sorted(l.items(), key=lambda item: item[0], reverse=True)[:min(len(l), 10)]
        data["last_date_scores"] = {k: v for k, v in l_top}
        app.db_client.collection('users').document(user_id).update({"last_date_scores": data["last_date_scores"]})

    if "avg_score" in data and len(data.get("last_date_scores", {})) > 1:
        previous_score = sorted(data["last_date_scores"].items(), key=lambda item: item[0], reverse=True)[0][1]
        previous_avg_score = (data["scores"]["total_sum"] - previous_score) / (data["scores"]["number_of_scored_games"] - 1)
        data["delta_from_last_score"] = data["avg_score"] - previous_avg_score

    return data


def _get_users_collection_name(is_test=False):
    return "users_test" if is_test else "users"


if __name__ == '__main__':
    firebase_admin.initialize_app()
    app = Flask("test_app")
    app.db_client = firestore.client()

    for i in range(10):
        _add_user("test_{}".format(i), {"name": "test_{}".format(i), "email": "test_{}@test.com".format(i), "fake_user": True}, create_stripe_customer=False)