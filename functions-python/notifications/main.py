import json
from datetime import datetime, timedelta

import firebase_admin
import pytz
from firebase_admin import firestore, messaging
from google.cloud import tasks_v2
from google.protobuf import timestamp_pb2


firebase_admin.initialize_app()


def send_prematch_notification(request):
    request_json = request.get_json(silent=True)
    print("args {}, data {}".format(request.args, request_json))

    request_data = request_json["data"]

    match_id = request_data["match_id"]

    _send_prematch_notification(match_id)

    return {"data": {}}, 200


def _send_prematch_notification(match_id):
    db = firestore.client()

    match = db.collection("matches").document(match_id).get().to_dict()
    if match.get("cancelledAt", None) is not None:
        print("match cancelled...skipping")
        return

    users = match["going"].keys()

    tokens = []
    for user_id in users:
        user_tokens = db.collection('users').document(user_id).get(field_paths={"tokens"}).to_dict()["tokens"]
        tokens.extend(user_tokens)

    match = db.collection("matches").document(match_id).get().to_dict()
    if match["cancelledAt"] is not None:
        raise Exception("Match is cancelled! Not sending any notification...")

    sport_center = db.collection('sport_centers').document(match["sportCenterId"]).get().to_dict()

    date_time = match["dateTime"]
    date_time_ams = date_time.astimezone(pytz.timezone("Europe/Amsterdam"))

    message = messaging.MulticastMessage(
        notification=messaging.Notification(
            title="Ready for the match? " + u"\u26BD\uFE0F",
            body="Your match today is at {} at {}".format(date_time_ams.strftime("%H:%M"), sport_center["name"]),
        ),
        tokens=tokens,
    )
    response = messaging.send_multicast(message)
    print('Successfully sent {} messages'.format(response.success_count))


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

    _schedule_prematch_notification(match_id, date_time)


def _schedule_prematch_notification(match_id, date_time):
    # schedule task
    client = tasks_v2.CloudTasksClient()

    project = 'nutmeg-9099c'
    queue = 'match-notifications'
    location = 'europe-west1'
    url = 'https://europe-central2-nutmeg-9099c.cloudfunctions.net/send_prematch_notification'
    payload = {'data': {"match_id": match_id}}
    task_name = "send_prematch_notification_for_{}".format(match_id)

    parent = client.queue_path(project, location, queue)

    # Construct the request body.
    task = {
        "http_request": {  # Specify the type of request.
            "http_method": tasks_v2.HttpMethod.POST,
            "url": url,  # The full url path that the task will be sent to.
        }
    }

    if payload is not None:
        if isinstance(payload, dict):
            # Convert dict to JSON string
            payload = json.dumps(payload)
            # specify http content-type to application/json
            task["http_request"]["headers"] = {"Content-type": "application/json"}

    # The API expects a payload of type bytes.
    converted_payload = payload.encode()

    # Add the payload to the request.
    task["http_request"]["body"] = converted_payload

    # Create Timestamp protobuf.
    date_time_to_send = date_time - timedelta(hours=1)
    timestamp = timestamp_pb2.Timestamp()
    timestamp.FromDatetime(date_time_to_send)

    # Add the timestamp to the tasks.
    task["schedule_time"] = timestamp

    if task_name is not None:
        # Add the name to tasks.
        task["name"] = client.task_path(project, location, queue, task_name)

    # Use the client to build and send the task.
    response = client.create_task(request={"parent": parent, "task": task})
    print("Created task {}".format(response.name))


if __name__ == '__main__':
    db = firestore.client()
    match_id = "ZAEd7UF1ULPJyruQdUEi"
    d = db.collection("matches").document("ZAEd7UF1ULPJyruQdUEi").get().to_dict()["dateTime"]
    _schedule_prematch_notification(match_id, d)