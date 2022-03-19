import json

import firebase_admin
from firebase_admin import firestore, messaging
from datetime import datetime, timedelta
import pytz
from google.cloud import tasks_v2
from google.protobuf import timestamp_pb2

tz = pytz.timezone('Europe/Amsterdam')
firebase_admin.initialize_app()


def run_post_match_tasks(request):
    request_json = request.get_json(silent=True)
    print("args {}, data {}".format(request.args, request_json))

    request_data = request_json["data"]

    match_id = request_data["match_id"]

    _run_post_match_tasks(match_id)

    return {"data": {}}, 200


def _run_post_match_tasks(match_id):
    db = firestore.client()

    match_data = db.collection("matches").document(match_id).get().to_dict()

    if match_data.get("cancelledAt", None) is not None:
        print("match cancelled...skipping")
        return

    # update stats
    field_name = "joined_matches" if not match_data["isTest"] else "joined_matches_test"
    for u in match_data["going"].keys():
        db.collection("users").document(u).update(
            {"{}.{}".format(field_name, match_id): match_data["dateTime"]})

    # send start voting notification
    users = match_data["going"].keys()

    _send_notification_to_users(
        title="Rate players! " + u"\u2B50\uFE0F",
        body="You have 24h to rate the players of today's match.",
        users=users,
        data={
            "click_action": "FLUTTER_NOTIFICATION_CLICK",
            "match_id": match_id
        }
    )


def _send_notification_to_users(title, body, data, users):
    db = firestore.client()

    tokens = set()
    for user_id in users:
        user_tokens = db.collection('users').document(user_id).get(field_paths={"tokens"}).to_dict()["tokens"]
        for t in user_tokens:
            tokens.add(t)
    _send_notification_to_tokens(title, body, data, list(tokens))


def _send_notification_to_tokens(title, body, data, tokens):
    message = messaging.MulticastMessage(
        notification=messaging.Notification(
            title=title,
            body=body
        ),
        data=data,
        tokens=tokens,
    )
    response = messaging.send_multicast(message)
    print('Successfully sent {} messages'.format(response.success_count))
    if response.failure_count > 0:
        [print(r.exception) for r in response.responses if r.exception]


def schedule_run_post_match_tasks(data, context):
    trigger_resource = context.resource
    print('Function triggered by change to: %s' % trigger_resource)

    match_id = data["value"]["name"].split("/")[-1]
    date_time = datetime.strptime(data["value"]["fields"]["dateTime"]["timestampValue"], "%Y-%m-%dT%H:%M:%SZ")

    _schedule_run_post_match_tasks(match_id, date_time, int(data["value"]["fields"]["duration"]["integerValue"]))


def _schedule_run_post_match_tasks(match_id, date_time, duration):
    # schedule task
    client = tasks_v2.CloudTasksClient()

    project = 'nutmeg-9099c'
    queue = 'match-notifications'
    location = 'europe-west1'
    url = 'https://europe-central2-nutmeg-9099c.cloudfunctions.net/run_post_match_tasks'
    payload = {'data': {"match_id": match_id}}
    task_name = "run_post_match_tasks_test_{}".format(match_id)

    parent = client.queue_path(project, location, queue)

    # Create Timestamp protobuf.
    date_time_task = date_time + timedelta(minutes=duration) + timedelta(hours=1)
    timestamp = timestamp_pb2.Timestamp()
    timestamp.FromDatetime(date_time_task)

    # Construct the request body.
    task = {
        "http_request": {  # Specify the type of request.
            "http_method": tasks_v2.HttpMethod.POST,
            "url": url,  # The full url path that the task will be sent to.
            "headers": {"Content-type": "application/json"},
            "body": json.dumps(payload).encode()
        },
        "schedule_time": timestamp,
        "name": client.task_path(project, location, queue, task_name)
    }
    # Use the client to build and send the task.
    response = client.create_task(request={"parent": parent, "task": task})
    print("Created task {}".format(response.name))


if __name__ == '__main__':
    _schedule_run_post_match_tasks("4zwpfdExqGQXDTWQGaLX", datetime(year=2022, month=4, day=1))
    # _run_post_match_tasks("RUYqgXuQmgG4XtevdyJO")