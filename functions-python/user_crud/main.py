import os
from datetime import datetime

import firebase_admin
import stripe
from firebase_admin import firestore
from firebase_admin import auth

firebase_admin.initialize_app()


def add_user(request):
    request_json = request.get_json(silent=True)
    print("args {}, data {}".format(request.args, request_json))

    request_data = request_json["data"]

    _add_user_firestore(request_data["id"], request_data["data"])

    return {"data": {}}, 200


def edit_user(request):
    request_json = request.get_json(silent=True)

    auth_data = auth.verify_id_token(request.headers["Authorization"].split(" ")[1])
    uid = auth.get_user(auth_data["user_id"])

    print("args {}, data {}".format(request.args, request_json))

    request_data = request_json["data"]

    _edit_user_firestore(request_data["id"], request_data["data"], uid.custom_claims.get("isAdmin", False))
    return {"data": {}}, 200


def get_user(request):
    request_json = request.get_json(silent=True)
    print("args {}, data {}".format(request.args, request_json))

    request_data = request_json["data"]

    return {"data": _get_user_firestore(request_data["id"])}, 200


def store_user_token(request):
    request_json = request.get_json(silent=True)
    print("args {}, data {}".format(request.args, request_json))

    request_data = request_json["data"]

    return {"data": _store_user_token_firestore(request_data["id"], request_data["token"])}, 200


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
    doc_ref.set(user_data)
    return doc_ref.id


def _get_user_firestore(user_id):
    db = firestore.client()
    data = db.collection('users').document(user_id).get().to_dict()

    if not data:
        return None

    if "joined_matches" in data:
        for m in data["joined_matches"]:
            data["joined_matches"][m] = _serialize_date(data["joined_matches"][m])

    return data


def _is_account_complete(account_id, is_test):
    stripe.api_key = os.environ["STRIPE_PROD_KEY" if not is_test else "STRIPE_TEST_KEY"]
    return len(stripe.Account.retrieve(account_id)["requirements"]["currently_due"]) == 0


def _serialize_date(date):
    return datetime.isoformat(date)


if __name__ == '__main__':
    # stripe.api_key = os.environ["STRIPE_PROD_KEY"]
    # db = firestore.client()
    # for t in db.collection("matches").document("Ozn0feqcNjETQ2fCnOlT").collection("transactions").get():
    #     data = t.to_dict()
    #     print(data["type"])
    #     print(data.get("paymentIntent", None))
    # print(stripe.PaymentIntent.retrieve("pi_3Kic2rGRb87bTNwH2wt7JlRe"))
    print(_get_user_firestore("JZlioztjrmbJisBLMrh8bwSCjUn1"))
