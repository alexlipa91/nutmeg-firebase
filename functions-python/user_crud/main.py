import firebase_admin
from firebase_admin import firestore
from google.cloud import functions

firebase_admin.initialize_app()


def add_user(request):
    request_json = request.get_json(silent=True)
    print("args {}, data {}".format(request.args, request_json))

    request_data = request_json["data"]

    try:
        _add_user_firestore(request_data["id"], request_data["data"])
    except:
        return HttpResponseServerError

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
    db = firestore.client()

    going = db.collection("matches").document("crFHcsL52YvzXl0LFJ28").collection("going")

    for s in db.collection("matches").document("crFHcsL52YvzXl0LFJ28").collection("subscriptions").stream():
        d = s.to_dict()
        if d['status'] == 'going':
            print(d['userId'])
            going.document(d['userId']).set({'userId': d['userId'], 'createdAt': d['createdAt'], 'paymentIntent': ""})

