import firebase_admin
from firebase_admin import firestore
from datetime import datetime
import pytz
from google.cloud.firestore_v1 import Increment

tz = pytz.timezone('Europe/Amsterdam')
firebase_admin.initialize_app()


def add_user_to_match(request):
    request_json = request.get_json(silent=True)
    print("args {}, data {}".format(request.args, request_json))

    request_data = request_json["data"]

    match_id = request_data["match_id"]
    user_id = request_data["user_id"]
    payment_intent = request_data.get("payment_intent", None)
    credits_used = request_data.get("credits_used", 0)

    _add_user_to_match_firestore(match_id, user_id, payment_intent, credits_used)

    return {"data": {}}, 200


def _add_user_to_match_firestore(match_id, user_id, payment_intent, credits_used):
    db = firestore.client()

    going_doc_ref = db.collection('matches').document(match_id).collection("going").document(user_id)
    refunded_doc_ref = db.collection('matches').document(match_id).collection("refunded").document(user_id)
    user_doc_ref = db.collection('users').document(user_id)
    match_doc_ref = db.collection('matches').document(match_id)

    _add_user_to_match_firestore_transaction(db.transaction(), going_doc_ref, refunded_doc_ref, user_doc_ref,
                                             match_doc_ref, credits_used, payment_intent, user_id)


@firestore.transactional
def _add_user_to_match_firestore_transaction(transaction, going_doc_ref, refunded_doc_ref, user_doc_ref, match_doc_ref,
                                             credits_used, payment_intent, user_id):
    timestamp = datetime.now(tz)

    # check if already going
    if going_doc_ref.get(transaction=transaction).exists:
        raise Exception("User already going")

    # check if enough credits
    match = match_doc_ref.get(transaction=transaction).to_dict()
    match_price = match["pricePerPerson"]

    user = user_doc_ref.get(transaction=transaction).to_dict()
    available_credits = user['credits']

    if credits_used > available_credits:
        raise Exception("User has not enough credits. Needed {}, actual {}".format(credits_used, available_credits))

    # remove if user is in refunds
    transaction.delete(refunded_doc_ref)

    # add user to list of going
    transaction.set(going_doc_ref, {
        'createdAt': timestamp,
        'paymentIntent': payment_intent,
        'userId': user_id,
        'credits_used': credits_used
    })

    # update user credits count
    transaction.update(user_doc_ref, {
        'credits': Increment(-match_price)
    })


if __name__ == '__main__':
    _add_user_to_match_firestore("FKxTBQl32LFig3J2iHoA", "IwrZWBFb4LZl3Kto1V3oUKPnCni1", "py", 0)

