import logging
import json
from datetime import datetime

import google.api_core.datetime_helpers
from firebase_admin import messaging
from google.cloud import tasks_v2
from google.protobuf import timestamp_pb2
import requests
from os import environ


def _serialize_dates(data):
    for k in data:
        if type(data[k]) == dict:
            data[k] = _serialize_dates(data[k])
        elif type(data[k]) == google.api_core.datetime_helpers.DatetimeWithNanoseconds:
            data[k] = datetime.isoformat(data[k])
    return data


def delete_task(task_name):
    client = tasks_v2.CloudTasksClient()
    project = "nutmeg-9099c"
    location = "europe-west1"
    queue = "match-notifications"
    client.delete_task(name=client.task_path(project, location, queue, task_name))


def schedule_app_engine_call(
    task_name,
    endpoint,
    date_time_to_execute,
    function_payload=None,
    method=tasks_v2.HttpMethod.GET,
):
    # schedule task
    client = tasks_v2.CloudTasksClient()

    project = "nutmeg-9099c"
    queue = "match-notifications"
    location = "europe-west1"
    url = f"https://nutmeg-9099c.ew.r.appspot.com/{endpoint}"

    parent = client.queue_path(project, location, queue)

    # Create Timestamp protobuf.
    timestamp = timestamp_pb2.Timestamp()
    timestamp.FromDatetime(date_time_to_execute)

    # Construct the request body.
    task = {
        "http_request": {  # Specify the type of request.
            "http_method": method,
            "url": url,  # The full url path that the task will be sent to.
            "headers": {"Content-type": "application/json"},
        },
        "schedule_time": timestamp,
        "name": client.task_path(project, location, queue, task_name),
    }
    if function_payload:
        task["http_request"]["body"] = json.dumps({"data": function_payload}).encode()

    # Use the client to build and send the task.
    response = client.create_task(request={"parent": parent, "task": task})
    print(
        f"Created task {response.name} to call {endpoint} with params {function_payload} at {date_time_to_execute}"
    )


def build_dynamic_link(link):
    resp = requests.post(
        url=f'https://firebasedynamiclinks.googleapis.com/v1/shortLinks?key={environ["DYNAMIC_LINK_API_KEY"]}',
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "dynamicLinkInfo": {
                    "domainUriPrefix": "https://nutmegapp.page.link",
                    "link": link,
                    "androidInfo": {
                        "androidPackageName": "com.nutmeg.nutmeg",
                        "androidMinPackageVersionCode": "1",
                    },
                    "iosInfo": {
                        # "iosBundleId": "com.nutmeg.app",
                        # "iosAppStoreId": '1592985083',
                    },
                    "socialMetaTagInfo": {
                        "socialTitle": "Nutmeg",
                        "socialDescription": "Play Football in your city",
                        # "socialImageLink": string
                    },
                    "navigationInfo": {
                        "enableForcedRedirect": True,
                    },
                }
            }
        ),
    )
    print(json.loads(resp.text))
    return json.loads(resp.text)["shortLink"]


def send_notification_to_users(flask_app, title, body, data, users):
    db = flask_app.db_client

    for user_id in users:
        user_data = (
            db.collection("users")
            .document(user_id)
            .get(field_paths={"tokens"})
            .to_dict()
        )
        for t in user_data.get("tokens", []):
            try:
                message = messaging.Message(
                    notification=messaging.Notification(title=title, body=body),
                    data=data,
                    token=t,
                )
                response = messaging.send(message)
                logging.info(f"Notification to {t} sent with response {response}")
            except Exception as e:
                logging.error(f"Error sending notification to {t}: {e}")


def update_leaderboard(app, leaderboard_id, match_list, updates_map):
    print(f"updating leaderboard {leaderboard_id}")
    cache_user_data = {u: _get_user_basic_data(app, u) for u in updates_map.keys()}
    app.db_client.collection("leaderboards").document(leaderboard_id).set(
        {
            "entries": updates_map,
            "cache_user_data": cache_user_data,
            "matches": {match_id: True for match_id in match_list},
        },
        merge=True,
    )


def _get_user_basic_data(app, u):
    return (
        app.db_client.collection("users")
        .document(u)
        .get(field_paths={"name", "image"})
        .to_dict()
    )


def send_test_notification(app):
    # send to admin a test notification
    send_notification_to_users(
        app, "test", "test", {}, ["IwrZWBFb4LZl3Kto1V3oUKPnCni1"]
    )


if __name__ == "__main__":
    import os

    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = (
        "/Users/alessandrolipa/IdeaProjects/nutmeg-firebase/nutmeg-9099c-bf73c9d6b62a.json"
    )
