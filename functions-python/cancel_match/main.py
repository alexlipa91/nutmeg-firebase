import firebase_admin
from firebase_admin import firestore
from datetime import datetime
from google.cloud.firestore_v1 import Increment
from nutmeg_utils.notifications import send_notification_to_users


firebase_admin.initialize_app()


def cancel_match(request):
    request_json = request.get_json(silent=True)
    print("args {}, data {}".format(request.args, request_json))

    request_data = request_json["data"]

    match_id = request_data["match_id"]

    _cancel_match_firestore(match_id)

    return {"data": {}}, 200


def _cancel_match_firestore(match_id):
    db = firestore.client()

    match_doc_ref = db.collection('matches').document(match_id)
    transactions_doc_ref = db.collection('matches').document(match_id).collection("transactions").document()

    match_data = match_doc_ref.get().to_dict()

    if match_data["cancelledAt"]:
        raise Exception("Match has already been cancelled")

    users_docs = {}
    for u in match_data["going"].keys():
        users_docs[u] = db.collection('users').document(u)

    _cancel_match_firestore_transactional(db.transaction(), match_doc_ref, users_docs, transactions_doc_ref,
                                          match_id)


@firestore.transactional
def _cancel_match_firestore_transactional(transaction, match_doc_ref, user_doc_refs,
                                          transaction_doc_ref, match_id):
    db = firestore.client()

    match = match_doc_ref.get(transaction=transaction).to_dict()
    sport_center = db.collection('sport_centers').document(match["sportCenterId"]).get().to_dict()["name"]
    price = match["pricePerPerson"] / 100

    t = datetime.now()

    transaction.update(match_doc_ref, {
        "cancelledAt": datetime.now()
    })

    users = list(match["going"].keys())
    for u in users:
        print("updating data for {}".format(u))

        # remove match in user list (if there)
        transaction.update(user_doc_refs[u], {
            u'joined_matches.' + match_id: firestore.DELETE_FIELD,
            u'cancelled_matches': firestore.firestore.ArrayUnion([match_id])
        })

        credits_refunded = match['pricePerPerson']

        # record transaction
        refund_type = "refund_cancellation"
        transaction.set(transaction_doc_ref,
                        {"type": refund_type, "userId": u, "createdAt": t,
                         "creditsRefunded": credits_refunded})

        # update user credits count
        transaction.update(user_doc_refs[u], {'credits': Increment(credits_refunded)})

    send_notification_to_users(title="Match cancelled!",
                               body="Your match at {} has been cancelled! € {} credits have been added to your account"
                               .format(sport_center, "{:.2f}".format(price)),
                               data={
                                   "click_action": "FLUTTER_NOTIFICATION_CLICK",
                                   "match_id": match_id
                               },
                               users=list(users))


if __name__ == '__main__':
    _cancel_match_firestore("gAYBoHYPUmX1GMfCajou")
