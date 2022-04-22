import os

import firebase_admin
from firebase_admin import firestore
from datetime import datetime
import pytz
from google.cloud.firestore_v1 import Increment
import stripe

tz = pytz.timezone('Europe/Amsterdam')
firebase_admin.initialize_app()


def remove_user_from_match(request):
    request_json = request.get_json(silent=True)
    print("args {}, data {}".format(request.args, request_json))

    request_data = request_json["data"]

    match_id = request_data["match_id"]
    user_id = request_data["user_id"]
    refund_type = request_data.get("type", "credits")

    _remove_user_from_match_firestore(match_id, user_id, refund_type)

    return {"data": {}}, 200


def get_refund_amount(request):
    request_json = request.get_json(silent=True)
    print("args {}, body {}".format(request.args, request_json))

    request_data = request_json["data"]

    user_id = request_data["user_id"]
    match_id = request_data["match_id"]

    data = {'data': {'amount': _get_refund_amount(match_id, user_id)}}
    return data, 200


def _remove_user_from_match_firestore(match_id, user_id, refund_type="credits"):
    db = firestore.client()

    transactions_doc_ref = db.collection('matches').document(match_id).collection("transactions").document()
    user_doc_ref = db.collection('users').document(user_id)
    match_doc_ref = db.collection('matches').document(match_id)

    if refund_type == "credits":
        _remove_user_from_match_firestore_transaction(db.transaction(), match_doc_ref, user_doc_ref,
                                                      transactions_doc_ref, user_id, match_id, refund_type="refund"),
    elif refund_type == "stripe":
        _remove_user_from_match_stripe_refund_firestore_transaction(db.transaction(), match_doc_ref, user_doc_ref,
                                                                    transactions_doc_ref, user_id, match_id)


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


@firestore.transactional
def _remove_user_from_match_stripe_refund_firestore_transaction(transaction, match_doc_ref, user_doc_ref,
                                                                transaction_doc_ref, user_id,
                                                                match_id):
    timestamp = datetime.now(tz)

    match = match_doc_ref.get(transaction=transaction).to_dict()

    if not match.get("going", {}).get(user_id, None):
        raise Exception("User is not part of the match")

    payment_intent = _get_payment_intent(match_id, user_id)

    # remove if user is in going
    transaction.update(match_doc_ref, {
        u'going.' + user_id: firestore.DELETE_FIELD
    })

    # remove match in user list
    transaction.update(user_doc_ref, {
        u'joined_matches.' + match_id: firestore.DELETE_FIELD
    })

    # issue_refund
    stripe.api_key = os.environ["STRIPE_TEST_KEY" if match["isTest"] else "STRIPE_PROD_KEY"]
    net_amount = _get_net_refund_amount(payment_intent)
    refund = stripe.Refund.create(payment_intent=payment_intent, amount=net_amount)

    # record transaction
    refund_type = "stripe_refund"
    transaction.set(transaction_doc_ref,
                    {"type": refund_type, "userId": user_id, "createdAt": timestamp,
                     "refund_id": refund.id,
                     "moneyRefunded": net_amount})


def _get_payment_intent(match_id, user_id):
    db = firestore.client()

    trans = db.collection('matches').document(match_id).collection("transactions").get()

    user_trans = []
    for t in trans:
        t_data = t.to_dict()
        if t_data["userId"] == user_id:
            user_trans.append(t_data)

    # sort by most recent first
    user_trans.sort(key=lambda x: x["createdAt"], reverse=True)

    last_trans = user_trans[0]

    if last_trans["type"] != "joined":
        raise Exception("Expected a 'joined' transaction but not found")

    return last_trans["paymentIntent"]


def _get_net_refund_amount(pi):
    balance_transaction = stripe.PaymentIntent.retrieve(pi)["charges"]["data"][0]["balance_transaction"]
    net = stripe.BalanceTransaction.retrieve(balance_transaction)["net"]
    return net


def _get_refund_amount(match_id, user_id):
    db = firestore.client()

    test_mode = db.collection("matches").document(match_id).get().to_dict()["isTest"]

    stripe.api_key = os.environ["STRIPE_TEST_KEY" if test_mode else "STRIPE_PROD_KEY"]
    return _get_net_refund_amount(_get_payment_intent(match_id, user_id))


if __name__ == '__main__':
    _remove_user_from_match_firestore("WvORB60BiudmuXHwl1dP", "IwrZWBFb4LZl3Kto1V3oUKPnCni1", refund_type="stripe")
    # print(_get_refund_amount("WvORB60BiudmuXHwl1dP", "IwrZWBFb4LZl3Kto1V3oUKPnCni1"))
