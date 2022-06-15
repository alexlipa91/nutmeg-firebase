import os
from enum import Enum

import firebase_admin
import stripe
from firebase_admin import firestore
from datetime import datetime
from nutmeg_utils.notifications import send_notification_to_users
from nutmeg_utils.payments import get_payment_intent


class CancellationTrigger(Enum):
    MANUAL = "manual"
    AUTOMATIC = "automatic"


firebase_admin.initialize_app()


def cancel_match(request):
    request_json = request.get_json(silent=True)
    print("args {}, data {}".format(request.args, request_json))

    request_data = request_json["data"]

    match_id = request_data["match_id"]

    _cancel_match_firestore(match_id, CancellationTrigger.MANUAL)

    return {"data": {}}, 200


def cancel_or_confirm_match(request):
    request_json = request.get_json(silent=True)
    print("args {}, data {}".format(request.args, request_json))

    request_data = request_json["data"]

    match_id = request_data["match_id"]

    db = firestore.client()
    match_data = db.collection('matches').document(match_id).get().to_dict()

    if len(match_data.get("going", {}).keys()) < match_data["minPlayers"]:
        print("canceling match")
        _cancel_match_firestore(match_id, CancellationTrigger.AUTOMATIC)
    else:
        print("confirming match")
        db.collection('matches').document(match_id).update({"confirmedAt": datetime.now()})

    return {"data": {}}, 200


def _cancel_match_firestore(match_id, trigger):
    db = firestore.client()

    match_doc_ref = db.collection('matches').document(match_id)

    match_data = match_doc_ref.get().to_dict()

    if match_data.get("cancelledAt", None):
        raise Exception("Match has already been cancelled")

    users_stats_docs = {}
    for u in match_data.get("going", {}).keys():
        users_stats_docs[u] = db.collection('users_stats').document(u)

    _cancel_match_firestore_transactional(db.transaction(), match_doc_ref, users_stats_docs,
                                          match_id, match_data["isTest"], trigger)


@firestore.transactional
def _cancel_match_firestore_transactional(transaction, match_doc_ref, users_stats_docs, match_id, is_test, trigger):
    stripe.api_key = os.environ["STRIPE_TEST_KEY" if is_test else "STRIPE_PROD_KEY"]
    db = firestore.client()

    match = match_doc_ref.get(transaction=transaction).to_dict()
    sport_center = db.collection('sport_centers').document(match["sportCenterId"]).get().to_dict()["name"]
    price = match["pricePerPerson"] / 100

    transaction.update(match_doc_ref, {
        "cancelledAt": datetime.now()
    })

    users = list(match.get("going", {}).keys())
    for u in users:
        print("processing cancellation for {}: refund and remove from stats".format(u))

        # remove match in user list (if present)
        transaction.update(users_stats_docs[u], {
            u'joinedMatches.' + match_id: firestore.DELETE_FIELD
        })

        # refund
        payment_intent = get_payment_intent(match_id, u)
        refund_amount = match["pricePerPerson"]
        refund = stripe.Refund.create(payment_intent=payment_intent, amount=refund_amount, reverse_transfer=True)

        # record transaction
        transaction_doc_ref = db.collection("matches").document(match_id).collection("transactions").document()
        transaction.set(transaction_doc_ref,
                        {"type": trigger.name.lower() + "_cancellation", "userId": u, "createdAt": datetime.now(),
                         "paymentIntent": payment_intent,
                         "refund_id": refund.id, "moneyRefunded": refund_amount})

    send_notification_to_users(title="Match cancelled!",
                               body="Your match at {} has been cancelled! € {} have been refunded on your payment method"
                               .format(sport_center, "{:.2f}".format(price)),
                               data={
                                   "click_action": "FLUTTER_NOTIFICATION_CLICK",
                                   "match_id": match_id
                               },
                               users=list(users))

    send_notification_to_users(title="Match cancelled!",
                               body="Your match at {} has been automatically cancelled as you requested! All players have been refundend € {}"
                               .format(sport_center, "{:.2f}".format(price)),
                               data={
                                   "click_action": "FLUTTER_NOTIFICATION_CLICK",
                                   "match_id": match_id
                               },
                               users=[match["organizerId"]])


