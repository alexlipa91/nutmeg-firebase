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
    refund_type = request_data.get("type", None)

    _remove_user_from_match_firestore(match_id, user_id, refund_type)

    return {"data": {}}, 200


def _remove_user_from_match_firestore(match_id, user_id, refund_type=None):
    db = firestore.client()

    transactions_doc_ref = db.collection('matches').document(match_id).collection("transactions").document()
    user_doc_ref = db.collection('users').document(user_id)
    match_doc_ref = db.collection('matches').document(match_id)

    _remove_user_from_match_firestore_transaction(db.transaction(), match_doc_ref, user_doc_ref, transactions_doc_ref,
                                                  user_id, match_id, refund_type)


@firestore.transactional
def _remove_user_from_match_firestore_transaction(transaction, match_doc_ref, user_doc_ref, transaction_doc_ref,
                                                  user_id, match_id, refund_type=None):
    timestamp = datetime.now(tz)

    match = match_doc_ref.get(transaction=transaction).to_dict()

    if not match.get("going", {}).get(user_id, None):
        raise Exception("User is not part of the match")

    # remove if user is in going
    transaction.update(match_doc_ref, {
        u'going.' + user_id: firestore.DELETE_FIELD
    })

    # remove match in user list
    transaction.update(user_doc_ref, {
        u'joined_matches.' + match_id: firestore.DELETE_FIELD
    })

    credits_refunded = match['pricePerPerson']

    # record transaction
    refund_type = "refund" + "_{}".format(refund_type) if refund_type else ""
    transaction.set(transaction_doc_ref,
                    {"type": refund_type, "userId": user_id, "createdAt": timestamp,
                     "creditsRefunded": credits_refunded})

    # update user credits count
    transaction.update(user_doc_ref, {'credits': Increment(credits_refunded)})


if __name__ == '__main__':
    _remove_user_from_match_firestore("0fn2zd8IjTDgoYtC1C6Z", "IwrZWBFb4LZl3Kto1V3oUKPnCni1")
