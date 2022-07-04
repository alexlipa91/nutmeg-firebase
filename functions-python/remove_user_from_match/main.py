import os
import time
import calendar
from functools import reduce

import firebase_admin
from firebase_admin import firestore
from datetime import datetime, timedelta
import pytz
import stripe
from flask_cors import cross_origin

from nutmeg_utils import payments
from nutmeg_utils.schedule_function import schedule_function

tz = pytz.timezone('Europe/Amsterdam')
firebase_admin.initialize_app()


@cross_origin(origins=["*"], allow_headers=["firebase-instance-id-token"])
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

    transactions_doc_ref = db.collection('matches').document(match_id).collection("transactions").document()
    user_stat_doc_ref = db.collection('users_stats').document(user_id)
    match_doc_ref = db.collection('matches').document(match_id)

    _remove_user_from_match_stripe_refund_firestore_transaction(db.transaction(), match_doc_ref, user_stat_doc_ref,
                                                                transactions_doc_ref, user_id, match_id)

    # if has teams assigned, recompute them
    going_dict = db.collection("matches").document(match_id).get(field_paths=["going"]).to_dict()["going"]
    has_teams = reduce(lambda a, b: a or b, ["team" in going_dict[u] for u in going_dict])

    if has_teams:
        schedule_function(
            task_name="update_teams_{}_{}".format(match_id, calendar.timegm(time.gmtime())),
            function_name="make_teams",
            function_payload={"match_id": match_id},
            date_time_to_execute=datetime.utcnow() + timedelta(seconds=10)
        )


@firestore.transactional
def _remove_user_from_match_stripe_refund_firestore_transaction(transaction, match_doc_ref, user_stat_doc_ref,
                                                                transaction_doc_ref, user_id, match_id):
    timestamp = datetime.now(tz)

    match = match_doc_ref.get(transaction=transaction).to_dict()

    if not match.get("going", {}).get(user_id, None):
        raise Exception("User is not part of the match")

    payment_intent = payments.get_payment_intent(match_id, user_id)

    # remove if user is in going
    transaction.update(match_doc_ref, {
        u'going.' + user_id: firestore.DELETE_FIELD
    })

    # remove match in user list
    transaction.update(user_stat_doc_ref, {
        u'joinedMatches.' + match_id: firestore.DELETE_FIELD
    })

    # issue_refund
    stripe.api_key = os.environ["STRIPE_TEST_KEY" if match["isTest"] else "STRIPE_PROD_KEY"]
    refund_amount = match["pricePerPerson"] - match.get("fee", 50)
    refund = stripe.Refund.create(payment_intent=payment_intent, amount=refund_amount, reverse_transfer=True)

    # record transaction
    transaction.set(transaction_doc_ref,
                    {"type": "user_left", "userId": user_id, "createdAt": timestamp,
                     "paymentIntent": payment_intent, "refund_id": refund.id,
                     "moneyRefunded": refund_amount})


if __name__ == '__main__':
    _remove_user_from_match_firestore("kiRs4EiqEkeF4vU27cB7", "bQHD0EM265V6GuSZuy1uQPHzb602")