import firebase_admin
from firebase_admin import firestore
from datetime import datetime
import pytz
from google.cloud.firestore_v1 import Increment

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

    match = db.collection('matches').document(match_id).get().to_dict()
    new_doc_ref = db.collection('matches').document(match_id).collection("refunded").document(user_id)

    if new_doc_ref.get().exists:
        raise Exception("User already refunded")

    # remove if user is in going
    going_doc_ref = db.collection('matches').document(match_id).collection("going").document(user_id)

    if not going_doc_ref.get().exists:
        raise Exception("User is not going. Cannot refund")

    going_doc_ref.delete()

    # add user to list of refunded
    new_doc_ref.set({
        'createdAt': timestamp,
        'userId': user_id,
    })

    # update user credits count
    db.collection('users').document(user_id).update({
        'credits': Increment(match['pricePerPerson'])
    })


if __name__ == '__main__':
    _remove_user_from_match_firestore("FKxTBQl32LFig3J2iHoA", "IwrZWBFb4LZl3Kto1V3oUKPnCni1")
