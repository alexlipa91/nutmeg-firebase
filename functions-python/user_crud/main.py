import os
from datetime import datetime

import firebase_admin
import stripe
from firebase_admin import firestore
from firebase_admin import auth
from flask_cors import cross_origin


firebase_admin.initialize_app()


@cross_origin(origins=["*"], allow_headers=["firebase-instance-id-token", "content-type", "authorization"])
def add_user(request):
    request_json = request.get_json(silent=True)
    print("args {}, data {}".format(request.args, request_json))

    request_data = request_json["data"]

    _add_user_firestore(request_data["id"], request_data["data"])

    return {"data": {}}, 200


@cross_origin(origins=["*"], allow_headers=["firebase-instance-id-token", "content-type", "authorization"])
def edit_user(request):
    request_json = request.get_json(silent=True)

    auth_data = auth.verify_id_token(request.headers["Authorization"].split(" ")[1])
    uid = auth.get_user(auth_data["user_id"])

    print("args {}, data {}".format(request.args, request_json))

    request_data = request_json["data"]

    is_admin = False
    if uid.custom_claims and uid.custom_claims.get("isAdmin", False):
        is_admin = True

    _edit_user_firestore(request_data["id"], request_data["data"], is_admin)
    return {"data": {}}, 200


@cross_origin(origins=["*"], allow_headers=["firebase-instance-id-token", "content-type", "authorization"])
def get_user(request):
    request_json = request.get_json(silent=True)
    print("args {}, data {}".format(request.args, request_json))

    request_data = request_json["data"]

    return {"data": _get_user_firestore(request_data["id"])}, 200


@cross_origin(origins=["*"], allow_headers=["firebase-instance-id-token", "content-type", "authorization"])
def store_user_token(request):
    request_json = request.get_json(silent=True)
    print("args {}, data {}".format(request.args, request_json))

    request_data = request_json["data"]

    return {"data": _store_user_token_firestore(request_data["id"], request_data["token"])}, 200


@cross_origin(origins=["*"], allow_headers=["firebase-instance-id-token", "content-type", "authorization"])
def is_organizer_account_complete(request):
    request_json = request.get_json(silent=True)
    print("args {}, data {}".format(request.args, request_json))

    request_data = request_json["data"]

    user_id = request_data["user_id"]
    is_test = request_data["is_test"]

    field_name = "stripeConnectedAccountId" if not is_test else "stripeConnectedAccountTestId"
    account_id = _get_user_firestore(user_id)[field_name]

    stripe.api_key = os.environ["STRIPE_PROD_KEY" if not is_test else "STRIPE_TEST_KEY"]
    is_complete = len(stripe.Account.retrieve(account_id)["requirements"]["currently_due"]) == 0

    return {"data": {"is_complete": is_complete}}, 200


def _store_user_token_firestore(user_id, token):
    db = firestore.client()

    doc_ref = db.collection("users").document(user_id)
    doc_ref.update({"tokens": firestore.firestore.ArrayUnion([token])})


def _edit_user_firestore(user_id, user_data, is_admin):
    db = firestore.client()

    doc_ref = db.collection("users").document(user_id)
    if not doc_ref.get().exists:
        raise Exception("User {} does not exists".format(user_id))

    if db.collection('users').document(user_id).get().to_dict()["credits"] != user_data["credits"]:
        if not is_admin:
            raise Exception("Not admin cannot update user credits")
        else:
            print("Modifying credit amount since caller is admin")

    doc_ref.update(user_data)


def _add_user_firestore(user_id, user_data):
    assert "email" in user_data, "Required field missing"

    user_data["createdAt"] = firestore.firestore.SERVER_TIMESTAMP

    db = firestore.client()

    doc_ref = db.collection('users').document(user_id)
    print(user_data)
    print(type(user_data))

    doc_ref.set(user_data)
    return doc_ref.id


def _get_user_firestore(user_id):
    db = firestore.client()
    data = db.collection('users').document(user_id).get().to_dict()

    if not data:
        return None

    if "scores" in data and data["scores"].get("number_of_scored_games", 0) != 0:
        data["avg_score"] = data["scores"]["total_sum"] / data["scores"]["number_of_scored_games"]

    return data


def _serialize_date(date):
    return datetime.isoformat(date)

