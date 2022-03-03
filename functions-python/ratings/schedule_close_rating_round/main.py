import json
from datetime import datetime, timedelta

import pytz
from google.cloud import tasks_v2
from google.protobuf import timestamp_pb2

"""
gcloud functions deploy schedule_close_rating_round \
                         --runtime python37 \
                         --trigger-event "providers/cloud.firestore/eventTypes/document.create" \
                         --trigger-resource "projects/nutmeg-9099c/databases/(default)/documents/matches/{matchId}" \
                         --region europe-central2
"""
def schedule_close_rating_round(data, context):
    trigger_resource = context.resource
    print('Function triggered by change to: %s' % trigger_resource)

    match_id = data["value"]["name"].split("/")[-1]
    date_time = datetime.strptime(data["value"]["fields"]["dateTime"]["timestampValue"], "%Y-%m-%dT%H:%M:%SZ")

    _schedule_close_rating_round(match_id, date_time)


def _schedule_close_rating_round(match_id, date_time):
    # schedule task
    client = tasks_v2.CloudTasksClient()

    project = 'nutmeg-9099c'
    queue = 'match-notifications'
    location = 'europe-west1'
    url = 'https://europe-central2-nutmeg-9099c.cloudfunctions.net/close_rating_round'
    payload = {'data': {"match_id": match_id}}
    task_name = "close_rating_round_{}".format(match_id)

    parent = client.queue_path(project, location, queue)

    # Create Timestamp protobuf.
    date_time_task = date_time + timedelta(days=2)
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
    d = datetime.now().astimezone(tz=pytz.timezone("Europe/Amsterdam"))
    d = d - timedelta(days=1)
    d = d + timedelta(seconds=30)
    print(d)
    print(_schedule_close_rating_round("ZAEd7UF1ULPJyruQdUEi", d))