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

    if not match.get("going", {}).get(user_id, None):
        raise Exception("User is not part of the match")

    # remove if user is in going
    db.collection('matches').document(match_id).update({
        u'going.' + user_id: firestore.DELETE_FIELD
    })

    credits_refunded = match['pricePerPerson']

    # record transaction
    db.collection('matches').document(match_id).collection("transactions").document().set(
        {"type": "refund", "userId": user_id, "createdAt": timestamp, "creditsRefunded": credits_refunded})

    # update user credits count
    db.collection('users').document(user_id).update({
        'credits': Increment(credits_refunded)
    })
