import firebase_admin
from firebase_admin import firestore
from datetime import datetime
from google.cloud.firestore_v1 import Increment


def add_user_to_match(request):
    request_json = request.get_json(silent=True)
    print(request_json)

    match_id = request_json["match_id"]
    user_id = request_json["user_id"]
    credits_used = request_json["credits_used"]
    money_paid = request_json["money_paid"]

    _add_user_to_match_firestore(match_id, user_id, credits_used, money_paid)

    return {}, 200


def _add_user_to_match_firestore(match_id, user_id, credits_used, money_paid):
    firebase_admin.initialize_app()
    db = firestore.client()

    timestamp = datetime.today()

    new_doc_ref = db.collection('matches').document(match_id).collection("going") \
        .document(user_id)

    if new_doc_ref.get().exists:
        raise Exception("User already going")

    # remove if user is in refunds
    db.collection('matches').document(match_id).collection("refunded") \
        .document(user_id).delete()

    # update user credits count
    db.collection('users').document(user_id).update({
        'credits': Increment(-credits_used)
    })

    # add user to list of going
    new_doc_ref.set({
        'createdAt': timestamp,
        'credits_used': credits_used,
        'money_paid': money_paid,
        'user_id': user_id,
    })


if __name__ == '__main__':
    _add_user_to_match_firestore("test_match_id", "IwrZWBFb4LZl3Kto1V3oUKPnCni1", 100, 200)
