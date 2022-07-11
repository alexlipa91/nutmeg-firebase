import asyncio
from datetime import datetime, timedelta

import firebase_admin
from firebase_admin import firestore
from flask_cors import cross_origin
from google.cloud.firestore import AsyncClient

from nutmeg_utils.schedule_function import schedule_function

firebase_admin.initialize_app()


def make_teams(request):
    request_json = request.get_json(silent=True)
    print("args {}, data {}".format(request.args, request_json))

    request_data = request_json["data"]

    asyncio.run(_set_team_recommendations(request_data["match_id"]))

    return {"data": {}}, 200


@cross_origin(origins=["*"], allow_headers=["firebase-instance-id-token", "content-type"])
def get_teams(request):
    request_json = request.get_json(silent=True)
    print("args {}, data {}".format(request.args, request_json))

    request_data = request_json["data"]
    match_id = request_data["match_id"]

    db = firestore.client()
    teams = db.collection("teams").document(match_id).get().to_dict()

    if teams:
        return {"data": {"teams": teams}}, 200
    return {"data": {}}, 200


def schedule_make_teams(data, context):
    trigger_resource = context.resource
    print('Function triggered by change to: %s' % trigger_resource)

    match_id = data["value"]["name"].split("/")[-1]
    date_time = datetime.strptime(data["value"]["fields"]["dateTime"]["timestampValue"], "%Y-%m-%dT%H:%M:%SZ")

    schedule_function(
        task_name="make_teams_{}".format(match_id),
        function_name="make_teams",
        function_payload={"match_id": match_id},
        date_time_to_execute=date_time - timedelta(hours=2)
    )


async def _set_team_recommendations(match_id):
    db = AsyncClient()
    match_doc = await db.collection('matches').document(match_id).get()
    match_data = match_doc.to_dict()

    if not match_data or match_data.get("cancelledAt", None):
        print("Match not existing or cancelled...skipping")
        return

    if len(match_data.get("going", {})) == 0:
        print("No one going yet...skipping")
        return

    scores = {}

    for u in match_data.get("going", {}):
        user_doc = await db.collection('users').document(u).get(field_paths=["avg_score"])
        avg_score = user_doc.to_dict().get("avg_score", 2.5)
        scores[u] = avg_score

    teams = await _split_teams(scores)

    match_updates = {}

    for u in teams[0]:
        match_updates["going.{}.team".format(u)] = "a"
    for u in teams[1]:
        match_updates["going.{}.team".format(u)] = "b"

    await db.collection("matches").document(match_id).update(match_updates)


async def _split_teams(scores):
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    teams = ([], [])
    teams_total_score = [0, 0]
    i = 0

    while i < len(sorted_scores):
        next_team_to_assign = 0 if teams_total_score[0] <= teams_total_score[1] else 1
        teams[next_team_to_assign].append(sorted_scores[i][0])
        teams_total_score[next_team_to_assign] += sorted_scores[i][1]

        i = i + 1
        if i < len(sorted_scores):
            teams[not next_team_to_assign].append(sorted_scores[i][0])
            teams_total_score[not next_team_to_assign] += sorted_scores[i][1]

        i = i + 1

    print("computed teams with total scores of {:.3f} and {:.3f}".format(teams_total_score[0], teams_total_score[1]))

    return teams


if __name__ == '__main__':
    asyncio.run(_set_team_recommendations("S85J9YSskjrW7jvioTuG"))