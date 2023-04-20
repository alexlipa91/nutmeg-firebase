import firebase_admin
import pytz
from firebase_admin import firestore
from nutmeg_utils import notifications

firebase_admin.initialize_app()


def send_prematch_notification(request):
    request_json = request.get_json(silent=True)
    print("args {}, data {}".format(request.args, request_json))

    request_data = request_json["data"]

    match_id = request_data["match_id"]

    _send_prematch_notification(match_id)

    return {"data": {}}, 200


def send_start_voting_notification(request):
    request_json = request.get_json(silent=True)
    print("args {}, data {}".format(request.args, request_json))

    request_data = request_json["data"]

    match_id = request_data["match_id"]

    _send_start_voting_notification(match_id)

    return {"data": {}}, 200


def send_pre_cancellation_organizer_notification(request):
    request_json = request.get_json(silent=True)
    print("args {}, data {}".format(request.args, request_json))

    request_data = request_json["data"]

    match_id = request_data["match_id"]

    db = firestore.client()

    match = db.collection("matches").document(match_id).get().to_dict()
    organizer_id = match["organizerId"]
    num_going = len(match.get("going", {}))
    min_players = match["minPlayers"]

    if num_going < min_players:
        notifications.send_notification_to_users(
            title="Your match might be canceled in 1 hour!",
            body="Currently only {} players out of {} have joined your match.".format(num_going, min_players),
            users=[organizer_id],
            data={
                "click_action": "FLUTTER_NOTIFICATION_CLICK",
                "route": "/match/" + match_id,
                "match_id": match_id
            }
        )

    return {"data": {}}, 200


def send_notification_to_users(request):
    request_json = request.get_json(silent=True)
    print("args {}, data {}".format(request.args, request_json))

    request_data = request_json["data"]

    notifications.send_notification_to_users(request_data["title"], request_data["body"], request_data["data"],
                                             request_data["users"])

    return {"data": {}}, 200


def _send_prematch_notification(match_id):
    db = firestore.client()

    match = db.collection("matches").document(match_id).get().to_dict()
    if not match or match.get("cancelledAt", None) is not None:
        print("match not existing or cancelled...skipping")
        return

    users = match.get("going", {}).keys()

    if "sportCenterId" in match:
        sport_center = db.collection('sport_centers').document(match["sportCenterId"]).get().to_dict()
    else:
        sport_center = match["sportCenter"]

    date_time = match["dateTime"]
    date_time_ams = date_time.astimezone(pytz.timezone("Europe/Amsterdam"))

    notifications.send_notification_to_users(
        title="Ready for the match? " + u"\u26BD\uFE0F",
        body="Your match today is at {} at {}. Tap here to check your team!".format(date_time_ams.strftime("%H:%M"),
                                                                                    sport_center["name"]),
        users=users,
        data={
            "click_action": "FLUTTER_NOTIFICATION_CLICK",
            "route": "/match/" + match_id,
            "match_id": match_id
        }
    )


def _send_start_voting_notification(match_id):
    db = firestore.client()

    match = db.collection("matches").document(match_id).get().to_dict()
    if not match or match.get("cancelledAt", None) is not None:
        print("Match is cancelled! Not sending any notification...")
        return

    users = match.get("going", {}).keys()

    notifications.send_notification_to_users(
        title="Rate players! " + u"\u2B50\uFE0F",
        body="You have 24h to rate the players of today's match.",
        users=users,
        data={
            "click_action": "FLUTTER_NOTIFICATION_CLICK",
            "route": "/match/" + match_id,
            "match_id": match_id
        }
    )
