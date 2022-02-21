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
    credits_used = request_data.get("credits_used", None)

    _add_user_to_match_firestore(match_id, user_id, payment_intent, credits_used)

    return {"data": {}}, 200


def _add_user_to_match_firestore(match_id, user_id, payment_intent, credits_used):
    db = firestore.client()

    going_doc_ref = db.collection('matches').document(match_id).collection("going").document(user_id)
    transactions_doc_ref = db.collection('matches').document(match_id).collection("transactions").document()
    user_doc_ref = db.collection('users').document(user_id)
    match_doc_ref = db.collection('matches').document(match_id)

    _add_user_to_match_firestore_transaction(db.transaction(), going_doc_ref, transactions_doc_ref, user_doc_ref,
                                             match_doc_ref, credits_used, payment_intent, user_id)


@firestore.transactional
def _add_user_to_match_firestore_transaction(transaction, going_doc_ref, transactions_doc_ref, user_doc_ref,
                                                match_doc_ref, credits_used, payment_intent, user_id):
    timestamp = datetime.now(tz)

    # check if already going
    if going_doc_ref.get(transaction=transaction).exists:
        raise Exception("User already going")

    # check if enough credits
    match = match_doc_ref.get(transaction=transaction).to_dict()
    match_price = match["pricePerPerson"]

    user = user_doc_ref.get(transaction=transaction).to_dict()
    available_credits = user['credits']

    if credits_used is not None and credits_used != 0 and credits_used > available_credits:
        raise Exception("User has not enough credits. Needed {}, actual {}".format(credits_used, available_credits))

    # add user to list of going
    transaction.set(match_doc_ref, {"going": {user_id: {"createdAt" : timestamp}}}, merge=True)

    # record transaction
    transaction.set(transactions_doc_ref, {"type": "joined", "userId": user_id, "createdAt": timestamp,
                                           "paymentIntent": payment_intent, "creditsUsed": credits_used})

    # update user credits count
    if credits_used is not None and credits_used != 0:
        transaction.update(user_doc_ref, {
            'credits': Increment(-credits_used)
        })
