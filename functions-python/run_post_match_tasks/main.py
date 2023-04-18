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

    if not match_data or match_data.get("cancelledAt", None) is not None:
        print("match deleted or cancelled...skipping")
        return

    going_users = match_data.get("going", {}).keys()
    organiser_id = match_data.get("organizerId", None)

    send_notification_to_users(
        title="Rate players! " + u"\u2B50\uFE0F",
        body="You have 24h to rate the players of today's match.",
        users=going_users,
        data={
            "click_action": "FLUTTER_NOTIFICATION_CLICK",
            "route": "/match/" + match_id,
            "match_id": match_id
        }
    )

    if organiser_id:
        send_notification_to_users(
            title="Add match result! " + u"\u2B50\uFE0F",
            body="Add the final score for your match.",
            users=organiser_id,
            data={
                "click_action": "FLUTTER_NOTIFICATION_CLICK",
                "route": "/match/" + match_id,
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


def debug_env(request):
    import pkg_resources
    installed_packages = pkg_resources.working_set
    for p in sorted(["%s==%s" % (i.key, i.version)for i in installed_packages]):
        print(p)
