from datetime import datetime, timedelta

import firebase_admin
import pytz
from firebase_admin import firestore
from nutmeg_utils import notifications
from nutmeg_utils.schedule_function import schedule_function

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

    sport_center = db.collection('sport_centers').document(match["sportCenterId"]).get().to_dict()
    date_time = match["dateTime"]
    date_time_ams = date_time.astimezone(pytz.timezone("Europe/Amsterdam"))

    notifications.send_notification_to_users(
        title="Ready for the match? " + u"\u26BD\uFE0F",
        body="Your match today is at {} at {}. Tap here to check your team!".format(date_time_ams.strftime("%H:%M"), sport_center["name"]),
        users=users,
        data={
            "click_action": "FLUTTER_NOTIFICATION_CLICK",
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
            "match_id": match_id
        }
    )


"""
gcloud functions deploy schedule_prematch_notification \
                         --runtime python37 \
                         --trigger-event "providers/cloud.firestore/eventTypes/document.create" \
                         --trigger-resource "projects/nutmeg-9099c/databases/(default)/documents/matches/{matchId}" \
                         --region europe-central2
"""
def schedule_prematch_notification(data, context):
    trigger_resource = context.resource
    print('Function triggered by change to: %s' % trigger_resource)

    match_id = data["value"]["name"].split("/")[-1]
    date_time = datetime.strptime(data["value"]["fields"]["dateTime"]["timestampValue"], "%Y-%m-%dT%H:%M:%SZ")

    schedule_function(
        task_name="send_prematch_notification_{}".format(match_id),
        function_name="send_prematch_notification",
        function_payload={"match_id": match_id},
        date_time_to_execute=date_time - timedelta(hours=1)
    )


"""
gcloud functions deploy schedule_start_voting_notification \
                         --runtime python37 \
                         --trigger-event "providers/cloud.firestore/eventTypes/document.create" \
                         --trigger-resource "projects/nutmeg-9099c/databases/(default)/documents/matches/{matchId}" \
                         --region europe-central2
"""
def schedule_start_voting_notification(data, context):
    trigger_resource = context.resource
    print('Function triggered by change to: %s' % trigger_resource)

    match_id = data["value"]["name"].split("/")[-1]
    date_time = datetime.strptime(data["value"]["fields"]["dateTime"]["timestampValue"], "%Y-%m-%dT%H:%M:%SZ")

    _schedule_start_voting_notification(match_id, date_time)


def _schedule_start_voting_notification(match_id, date_time):
    send_at = date_time + timedelta(hours=3)

    schedule_function(
        task_name="send_start_voting_notification_{}".format(match_id),
        function_name="send_start_voting_notification",
        function_payload={"match_id": match_id},
        date_time_to_execute=send_at
    )

