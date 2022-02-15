import json
from datetime import datetime, timedelta

import firebase_admin
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

    users = []
    for sub in db.collection("matches").document(match_id).collection("going").stream():
        users.append(sub.to_dict()["userId"])

    tokens = []
    for user_id in users:
        user_tokens = db.collection('users').document(user_id).get(field_paths={"tokens"}).to_dict()["tokens"]
        tokens.extend(user_tokens)

    match = db.collection("matches").document(match_id).get().to_dict()
    sport_center = db.collection('sport_centers').document(match["sportCenter"]).get().to_dict()

    message = messaging.MulticastMessage(
        notification=messaging.Notification(
            title="Get ready",
            body="Your match at {} is coming up!".format(sport_center["name"]),
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
    data = {'oldValue': {}, 'updateMask': {}, 'value': {'createTime': '2022-02-14T23:08:37.516335Z', 'fields': {'cancelledAt': {'nullValue': None}, 'dateTime': {'timestampValue': '2022-02-16T17:00:00Z'}, 'duration': {'integerValue': '60'}, 'isTest': {'booleanValue': False}, 'maxPlayers': {'integerValue': '12'}, 'pricePerPerson': {'integerValue': '630'}, 'sport': {'stringValue': 'BvwIYDpu0f3RIT4EaWBH'}, 'sportCenter': {'stringValue': 'ChIJaaYbkP8JxkcR_lUNC3ssFuU'}, 'sportCenterId': {'stringValue': 'ChIJaaYbkP8JxkcR_lUNC3ssFuU'}, 'sportCenterSubLocation': {'nullValue': None}}, 'name': 'projects/nutmeg-9099c/databases/(default)/documents/matches/8fmbZokYTfjRDVyGPt1s', 'updateTime': '2022-02-14T23:08:37.516335Z'}}
    schedule_prematch_notification(data=data, context=None)