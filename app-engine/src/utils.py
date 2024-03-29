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


def schedule_app_engine_call(task_name, endpoint, date_time_to_execute,
                             function_payload=None,
                             method=tasks_v2.HttpMethod.GET):
    # schedule task
    client = tasks_v2.CloudTasksClient()

    project = 'nutmeg-9099c'
    queue = 'match-notifications'
    location = 'europe-west1'
    url = 'https://nutmeg-9099c.ew.r.appspot.com/{}'.format(endpoint)

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
        "name": client.task_path(project, location, queue, task_name)
    }
    if function_payload:
        task["http_request"]["body"] = json.dumps({"data": function_payload}).encode()

    # Use the client to build and send the task.
    response = client.create_task(request={"parent": parent, "task": task})
    print("Created task {} to call {} with params {} at {}".format(response.name, endpoint, function_payload,
                                                                   date_time_to_execute))


def build_dynamic_link(link):
    resp = requests.post(
        url="https://firebasedynamiclinks.googleapis.com/v1/shortLinks?key={}".format(environ["DYNAMIC_LINK_API_KEY"]),
        headers={'Content-Type': 'application/json'},
        data=json.dumps({
            "dynamicLinkInfo": {
                "domainUriPrefix": "https://nutmegapp.page.link",
                "link": link,
                "androidInfo": {
                    "androidPackageName": 'com.nutmeg.nutmeg',
                    "androidMinPackageVersionCode": '1'
                },
                "iosInfo": {
                    "iosBundleId": "com.nutmeg.app",
                    "iosAppStoreId": '1592985083',
                },
                "socialMetaTagInfo": {
                    "socialTitle": "Nutmeg",
                    "socialDescription": "Play Football in your city",
                    # "socialImageLink": string
                }
            }
        }))
    return json.loads(resp.text)["shortLink"]


def send_notification_to_users(db, title, body, data, users):
    # normal send
    tokens = set()
    for user_id in users:
        user_data = db.collection('users').document(user_id).get(field_paths={"tokens"}).to_dict()
        if user_data:
            for t in user_data.get("tokens", []):
                tokens.add(t)
    _send_notification_to_tokens(title, body, data, list(tokens))

    # forward to admins
    admins = ["IwrZWBFb4LZl3Kto1V3oUKPnCni1", "bQHD0EM265V6GuSZuy1uQPHzb602"]
    admins_to_forward = set()
    [admins_to_forward.add(a) for a in admins if a not in users]

    tokens = set()
    for user_id in admins_to_forward:
        admins_tokens = db.collection('users').document(user_id).get(field_paths={"tokens"}).to_dict()["tokens"]
        for t in admins_tokens:
            tokens.add(t)
    _send_notification_to_tokens("[admin] {}".format(title), body, data, list(tokens))


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
    if response.failure_count > 0:
        for r in response.responses:
            if not r.success:
                print("Logging one error:\n{}".format(r.exception))
                break
    print('Sent: {}. Failed: {}'.format(response.success_count, response.failure_count))


def update_leaderboard(app, leaderboard_id, match_list, updates_map):
    print("updating leaderboard {}".format(leaderboard_id))
    cache_user_data = {u: _get_user_basic_data(app, u) for u in updates_map.keys()}
    app.db_client.collection("leaderboards").document(leaderboard_id) \
        .set({"entries": updates_map,
              "cache_user_data": cache_user_data,
              "matches": {match_id: True for match_id in match_list}},
             merge=True)

def _get_user_basic_data(app, u):
    return app.db_client.collection("users").document(u).get(field_paths={"name", "image"}).to_dict()


if __name__ == '__main__':
    import os
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/Users/alessandrolipa/IdeaProjects/nutmeg-firebase/nutmeg-9099c-bf73c9d6b62a.json"