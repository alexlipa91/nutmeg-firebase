import firebase_admin
from firebase_admin import firestore
from datetime import datetime

firebase_admin.initialize_app()


def add_user_to_match(request):
    request_json = request.get_json(silent=True)
    print(request.args)
    print(request_json)

    request_data = request_json["data"]

    match_id = request_data["match_id"]
    user_id = request_data["user_id"]
    payment_intent = request_data["payment_intent"]

    _add_user_to_match_firestore(match_id, user_id, payment_intent)
    # redirect_url = _build_redirect_to_app_link(match_id)

    return {}, 200


def _add_user_to_match_firestore(match_id, user_id, payment_intent):
    db = firestore.client()

    timestamp = datetime.today()

    new_doc_ref = db.collection('matches').document(match_id).collection("going") \
        .document(user_id)

    if new_doc_ref.get().exists:
        raise Exception("User already going")

    # remove if user is in refunds
    db.collection('matches').document(match_id).collection("refunded") \
        .document(user_id).delete()

    # add user to list of going
    new_doc_ref.set({
        'createdAt': timestamp,
        'paymentIntent': payment_intent,
        'userId': user_id,
    })

# if __name__ == '__main__':
#     # _add_user_to_match_firestore("test_match_id", "IwrZWBFb4LZl3Kto1V3oUKPnCni1", 100, 200)
#     _build_redirect_to_app_link(123)

