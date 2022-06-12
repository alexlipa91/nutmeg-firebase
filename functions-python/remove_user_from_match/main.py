import os
import time
from calendar import calendar

import firebase_admin
from firebase_admin import firestore
from datetime import datetime, timedelta
import pytz
import stripe
from nutmeg_utils import payments
from nutmeg_utils.schedule_function import schedule_function

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

    transactions_doc_ref = db.collection('matches').document(match_id).collection("transactions").document()
    user_stat_doc_ref = db.collection('users_stats').document(user_id)
    match_doc_ref = db.collection('matches').document(match_id)

    _remove_user_from_match_stripe_refund_firestore_transaction(db.transaction(), match_doc_ref, user_stat_doc_ref,
                                                                transactions_doc_ref, user_id, match_id)

    teams_doc = db.collection("teams").document(match_id).get()
    if teams_doc.exists:
        schedule_function(
            task_name="update_teams_{}_{}".format(match_id, calendar.timegm(time.gmtime())),
            function_name="make_teams",
            function_payload={"match_id": match_id},
            date_time_to_execute=datetime.now() + timedelta(minutes=1)
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
                     "refund_id": refund.id,
                     "moneyRefunded": refund_amount})
