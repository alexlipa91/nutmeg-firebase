import firebase_admin
from firebase_admin import firestore

firebase_admin.initialize_app()


def add_user(request):
    request_json = request.get_json(silent=True)
    print("args {}, data {}".format(request.args, request_json))

    request_data = request_json["data"]

    _add_user_firestore(request_data["id"], request_data["data"])

    return {"data": {}}, 200


def edit_user(request):
    request_json = request.get_json(silent=True)
    print("args {}, data {}".format(request.args, request_json))

    request_data = request_json["data"]

    _edit_user_firestore(request_data["id"], request_data["data"])
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


def _edit_user_firestore(user_id, user_data):
    db = firestore.client()

    doc_ref = db.collection("users").document(user_id)
    if not doc_ref.get().exists:
        raise Exception("User {} does not exists".format(user_id))

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
    return db.collection('users').document(user_id).get().to_dict()


if __name__ == '__main__':
    _store_user_token_firestore("IwrZWBFb4LZl3Kto1V3oUKPnCni1", "t")
