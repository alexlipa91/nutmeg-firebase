import firebase_admin
from firebase_admin import firestore
from datetime import datetime
import pytz

tz = pytz.timezone('Europe/Amsterdam')
firebase_admin.initialize_app()


def remove_user_from_match(request):
    request_json = request.get_json(silent=True)
    print("args {}, data {}".format(request.args, request_json))

    request_data = request_json["data"]

    match_id = request_data["match_id"]
    user_id = request_data["user_id"]

    _remove_user_from_match_firestore(match_id, user_id)

    return {"data": {}}, 200


def _remove_user_from_match_firestore(match_id, user_id):
    db = firestore.client()

    timestamp = datetime.now(tz)

    new_doc_ref = db.collection('matches').document(match_id).collection("refunded").document(user_id)

    if new_doc_ref.get().exists:
        raise Exception("User already refunded")

    # remove if user is in refunds
    going_doc_ref = db.collection('matches').document(match_id).collection("going").document(user_id)

    if not going_doc_ref.get().exists:
        raise Exception("User is not going. Cannot refund")

    going_doc_ref.delete()

    # add user to list of refunded
    new_doc_ref.set({
        'createdAt': timestamp,
        'userId': user_id,
    })

