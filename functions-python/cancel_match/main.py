import firebase_admin
from firebase_admin import firestore
from datetime import datetime
from nutmeg_utils.notifications import send_notification_to_users
from nutmeg_utils.functions_client import call_function


firebase_admin.initialize_app()


def cancel_match(request):
    request_json = request.get_json(silent=True)
    print("args {}, data {}".format(request.args, request_json))

    request_data = request_json["data"]

    match_id = request_data["match_id"]

    _cancel_match_firestore(match_id)

    return {"data": {}}, 200


def cancel_or_confirm_match(request):
    request_json = request.get_json(silent=True)
    print("args {}, data {}".format(request.args, request_json))

    request_data = request_json["data"]

    match_id = request_data["match_id"]

    db = firestore.client()
    match_data = db.collection('matches').document(match_id).get().to_dict()

    if len(match_data["going"].keys()) < match_data["minPlayers"]:
        print("canceling match")
        _cancel_match_firestore(match_id)
    else:
        print("confirming match")
        db.collection('matches').document(match_id).update({"confirmedAt": datetime.now()})

    return {"data": {}}, 200


def _cancel_match_firestore(match_id):
    db = firestore.client()

    match_doc_ref = db.collection('matches').document(match_id)

    match_data = match_doc_ref.get().to_dict()

    if match_data["cancelledAt"]:
        raise Exception("Match has already been cancelled")

    users_docs = {}
    for u in match_data["going"].keys():
        users_docs[u] = db.collection('users').document(u)

    _cancel_match_firestore_transactional(db.transaction(), match_doc_ref)


@firestore.transactional
def _cancel_match_firestore_transactional(transaction, match_doc_ref, match_id):
    db = firestore.client()

    match = match_doc_ref.get(transaction=transaction).to_dict()
    sport_center = db.collection('sport_centers').document(match["sportCenterId"]).get().to_dict()["name"]
    price = match["pricePerPerson"] / 100

    transaction.update(match_doc_ref, {
        "cancelledAt": datetime.now()
    })

    users = list(match["going"].keys())
    for u in users:
        print("updating data for {}".format(u))

        call_function("remove_user_from_match", {
            "match_id": match_id,
            "user_id": u,
            "reason": "automatic_cancellation"
        })

    send_notification_to_users(title="Match cancelled!",
                               body="Your match at {} has been cancelled! € {} have been refunded on your payment method"
                               .format(sport_center, "{:.2f}".format(price)),
                               data={
                                   "click_action": "FLUTTER_NOTIFICATION_CLICK",
                                   "match_id": match_id
                               },
                               users=list(users))


if __name__ == '__main__':
    _cancel_match_firestore("gAYBoHYPUmX1GMfCajou")
