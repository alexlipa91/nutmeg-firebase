import firebase_admin
from google.cloud.firestore import AsyncClient


firebase_admin.initialize_app()


def make_teams(request):
    request_json = request.get_json(silent=True)
    print("args {}, data {}".format(request.args, request_json))

    request_data = request_json["data"]

    _set_team_recommendations(request_data["id"])

    return {"data": {}}, 200


async def _set_team_recommendations(match_id):
    db = AsyncClient()
    match_going_doc = await db.collection('matches').document(match_id).get(field_paths=["going"])

    scores = {}

    for u in match_going_doc.to_dict()["going"]:
        user_doc = await db.collection('users').document(u).get(field_paths=["avg_score"])
        avg_score = user_doc.to_dict().get("avg_score", 2.5)
        scores[u] = avg_score

    teams = await _split_teams(scores)
    await db.collection("teams").document(match_id).set({"a": teams[0], "b": teams[1]})


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
