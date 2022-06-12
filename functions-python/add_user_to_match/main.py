from calendar import calendar

import firebase_admin
from firebase_admin import firestore
from datetime import datetime, timedelta
import pytz
import time

from nutmeg_utils.schedule_function import schedule_function

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

    transactions_doc_ref = db.collection('matches').document(match_id).collection("transactions").document()
    user_stat_doc_ref = db.collection('users_stats').document(user_id)
    match_doc_ref = db.collection('matches').document(match_id)

    _add_user_to_match_firestore_transaction(db.transaction(), transactions_doc_ref, user_stat_doc_ref,
                                             match_doc_ref, credits_used, payment_intent, user_id, match_id)

    teams_doc = db.collection("teams").document(match_id).get()
    if teams_doc.exists:
        schedule_function(
            task_name="update_teams_{}_{}".format(match_id, calendar.timegm(time.gmtime())),
            function_name="make_teams",
            function_payload={"match_id": match_id},
            date_time_to_execute=datetime.now() + timedelta(minutes=1)
        )

@firestore.transactional
def _add_user_to_match_firestore_transaction(transaction, transactions_doc_ref, user_stat_doc_ref,
                                             match_doc_ref, credits_used, payment_intent, user_id, match_id):
    timestamp = datetime.now(tz)

    match = match_doc_ref.get(transaction=transaction).to_dict()

    if match.get("going", {}).get(user_id, None):
        raise Exception("User already going")

    user = user_stat_doc_ref.get(transaction=transaction).to_dict()
    available_credits = user.get('credits', 0)

    if credits_used is not None and credits_used != 0 and credits_used > available_credits:
        raise Exception("User has not enough credits. Needed {}, actual {}".format(credits_used, available_credits))

    # add user to list of going
    transaction.set(match_doc_ref, {"going": {user_id: {"createdAt": timestamp}}}, merge=True)

    # add match to user
    if not match["isTest"]:
        transaction.set(user_stat_doc_ref, {"joinedMatches": {match_id: match["dateTime"]}}, merge=True)

    # record transaction
    transaction.set(transactions_doc_ref, {"type": "joined", "userId": user_id, "createdAt": timestamp,
                                           "paymentIntent": payment_intent, "creditsUsed": credits_used})


if __name__ == '__main__':
    _add_user_to_match_firestore("hy65YtfKF5K6iECCxuLc", "IwrZWBFb4LZl3Kto1V3oUKPnCni1", None, 1233)