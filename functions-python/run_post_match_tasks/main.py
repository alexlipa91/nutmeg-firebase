import json

import firebase_admin
from firebase_admin import firestore
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

    if not match_data["isTest"]:
        for u in match_data["going"].keys():
            db.collection("users").document(u).update(
                {"joined_matches": {match_id: match_data["dateTime"]}})


def schedule_run_post_match_tasks(data, context):
    trigger_resource = context.resource
    print('Function triggered by change to: %s' % trigger_resource)

    match_id = data["value"]["name"].split("/")[-1]
    date_time = datetime.strptime(data["value"]["fields"]["dateTime"]["timestampValue"], "%Y-%m-%dT%H:%M:%SZ")

    _schedule_run_post_match_tasks(match_id, date_time)


def _schedule_run_post_match_tasks(match_id, date_time):
    # schedule task
    client = tasks_v2.CloudTasksClient()

    project = 'nutmeg-9099c'
    queue = 'match-notifications'
    location = 'europe-west1'
    url = 'https://europe-central2-nutmeg-9099c.cloudfunctions.net/run_post_match_tasks'
    payload = {'data': {"match_id": match_id}}
    task_name = "run_post_match_tasks_{}".format(match_id)

    parent = client.queue_path(project, location, queue)

    # Create Timestamp protobuf.
    date_time_task = date_time + timedelta(hours=1)
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
