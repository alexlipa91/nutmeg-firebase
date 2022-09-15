import logging
import time
import calendar
from functools import reduce

import firebase_admin
from firebase_admin import firestore
from datetime import datetime, timedelta
import pytz
from flask_cors import cross_origin

from nutmeg_utils.schedule_function import schedule_function

tz = pytz.timezone('Europe/Amsterdam')
firebase_admin.initialize_app()


@cross_origin(origins=["*"], allow_headers=["firebase-instance-id-token", "content-type", "authorization"])
def add_user_to_match(request):
    request_json = request.get_json(silent=True)
    print("args {}, data {}".format(request.args, request_json))

    request_data = request_json["data"]

    match_id = request_data["match_id"]
    user_id = request_data["user_id"]
    payment_intent = request_data.get("payment_intent", None)

    _add_user_to_match_firestore(match_id, user_id, payment_intent)

    return {"data": {}}, 200


def _add_user_to_match_firestore(match_id, user_id, payment_intent):
    db = firestore.client()

    transactions_doc_ref = db.collection('matches').document(match_id).collection("transactions").document()
    user_stat_doc_ref = db.collection("users").document(user_id).collection("stats").document("match_votes")
    match_doc_ref = db.collection('matches').document(match_id)

    _add_user_to_match_firestore_transaction(db.transaction(), transactions_doc_ref, user_stat_doc_ref,
                                             match_doc_ref, payment_intent, user_id, match_id)

    # if has teams assigned, recompute them
    going_dict = db.collection("matches").document(match_id).get(field_paths=["going"]).to_dict()["going"]
    has_teams = len(going_dict) > 0 and reduce(lambda a, b: a or b, ["team" in going_dict[u] for u in going_dict])

    if has_teams:
        schedule_function(
            task_name="update_teams_{}_{}".format(match_id, calendar.timegm(time.gmtime())),
            function_name="make_teams",
            function_payload={"match_id": match_id},
            date_time_to_execute=datetime.utcnow() + timedelta(seconds=10)
        )

@firestore.transactional
def _add_user_to_match_firestore_transaction(transaction, transactions_doc_ref, user_stat_doc_ref,
                                             match_doc_ref, payment_intent, user_id, match_id):
    timestamp = datetime.now(tz)

    match = match_doc_ref.get(transaction=transaction).to_dict()

    if match.get("going", {}).get(user_id, None):
        logging.warning("User already going")
        return

    # add user to list of going
    transaction.set(match_doc_ref, {"going": {user_id: {"createdAt": timestamp}}}, merge=True)

    # add match to user
    if not match["isTest"]:
        transaction.set(user_stat_doc_ref, {"joinedMatches": {match_id: match["dateTime"]}}, merge=True)

    # record transaction
    transaction.set(transactions_doc_ref, {"type": "joined", "userId": user_id, "createdAt": timestamp,
                                           "paymentIntent": payment_intent})


if __name__ == '__main__':
    _add_user_to_match_firestore("gP8Rhh0DZV0SPT22oXL9", "7rZqLhiIK5gNBEeEATymCWwkwNk2", "pi_3LAxKiGRb87bTNwH3sQPLFzG")