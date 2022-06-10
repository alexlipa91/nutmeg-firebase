import firebase_admin
from firebase_admin import firestore
from datetime import datetime, timedelta
from nutmeg_utils.notifications import send_notification_to_users
from nutmeg_utils.schedule_function import schedule_function

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

    # update number of played stats
    summed_field_name = "num_matches_joined" if not match_data["isTest"] else "num_matches_joined_test"
    for u in match_data["going"].keys():
        db.collection("users").document(u).update(
            {summed_field_name: firestore.firestore.Increment(1)})

    # send start voting notification
    users = match_data["going"].keys()

    send_notification_to_users(
        title="Rate players! " + u"\u2B50\uFE0F",
        body="You have 24h to rate the players of today's match.",
        users=users,
        data={
            "click_action": "FLUTTER_NOTIFICATION_CLICK",
            "match_id": match_id
        }
    )

    # payout
    schedule_function(
        "payout_organizer_for_match_{}_attempt_number_{}".format(match_id, 1),
        "create_organizer_payout",
        {"match_id": match_id, "attempt": 1},
        datetime.now() + timedelta(days=3)
    )


def schedule_run_post_match_tasks(data, context):
    trigger_resource = context.resource
    print('Function triggered by change to: %s' % trigger_resource)

    match_id = data["value"]["name"].split("/")[-1]
    date_time = datetime.strptime(data["value"]["fields"]["dateTime"]["timestampValue"], "%Y-%m-%dT%H:%M:%SZ")
    duration = int(data["value"]["fields"]["duration"]["integerValue"])

    schedule_function(
        task_name="run_post_match_tasks_{}".format(match_id),
        function_name="run_post_match_tasks",
        function_payload={"match_id": match_id},
        date_time_to_execute=date_time + timedelta(minutes=duration) + timedelta(hours=1)
    )

