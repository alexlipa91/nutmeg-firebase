import asyncio
import datetime

from firebase_admin import firestore
from google.cloud.firestore import AsyncClient
from decimal import Decimal
import firebase_admin
from nutmeg_utils.notifications import send_notification_to_users

firebase_admin.initialize_app()


def close_rating_round(request):
    request_json = request.get_json(silent=True)
    print("data {}".format(request_json))

    request_data = request_json["data"]

    # FIXME disable ratings
    # return {"reason": "disabled"}, 500

    asyncio.run(_close_rating_round_firestore(request_data["match_id"]))

    return {"data": {}}, 200


async def _close_rating_round_firestore(match_id, send_notification=True):
    db = AsyncClient()

    timestamp = datetime.datetime.utcnow()

    match_doc = await db.collection("matches").document(match_id).get()
    match_data = match_doc.to_dict()
    if match_data["cancelledAt"]:
        print("Match is canceled")
        return

    if match_data.get("scoresComputedAt", None):
        raise Exception("Scores already computed")

    ratings_doc = await db.collection("ratings").document(match_id).get()
    if not ratings_doc.exists:
        print("No ratings for this match")
        # mark match as rated
        await db.collection("matches").document(match_id).set({"scoresComputedAt": timestamp}, merge=True)
        return

    scores = ratings_doc.to_dict()["scores"]
    skills = ratings_doc.to_dict().get("skills", {})

    # do calculations
    # user_id -> (avg_score, num_votes)
    final_scores = {}
    for u in scores:
        only_positive = list(filter(lambda s: s > 0, scores[u].values()))
        if len(only_positive) == 0:
            final_scores[u] = (0, 0)
        else:
            s = Decimal(sum(only_positive) / len(only_positive))
            final_scores[u] = (float(round(s, 2)), len(only_positive))

    # who has the biggest dick(s) in the match?
    scores_sorted = sorted(final_scores.items(), key=lambda x: x[1])
    scores_sorted.reverse()
    top_score_and_count = scores_sorted[0][1]

    potm_scores = {}
    for e in scores_sorted:
        if e[1] == top_score_and_count:
            potm_scores[e[0]] = e[1][0]
    print("final scores {}; man(s) of the match: {}".format(final_scores, potm_scores))

    should_store = "isTest" not in match_data or not match_data["isTest"]

    # store score for users
    for user, score_and_count in final_scores.items():
        await db.collection("users_stats").document(user).set({"scoreMatches": {match_id: score_and_count[0]}},
                                                              merge=True)

        # update average score
        user_stat_doc = await db.collection("users_stats").document(user).get()
        scores = user_stat_doc.to_dict().get("scoreMatches", {}).values()
        avg_score = sum(scores) / len(scores)

        # update skills count with increments
        skills_count = {"total_rated": 1}
        for single_skill_rates in skills.get(user, {}).values():
            for s in single_skill_rates:
                skills_count[s] = skills_count.get(s, 0) + 1

        print("updates on user {}: avg_score {}, skills: {}".format(user, avg_score, skills_count))

        if should_store:
            await db.collection("users").document(user).update({"avg_score": avg_score, "skills": skills_count})

        # store man of the match info in user doc
        for user in potm_scores:
            if should_store:
                await db.collection("users").document(user).update(
                    {"manOfTheMatch": firestore.firestore.ArrayUnion([match_id])})

    # mark match as rated and store man_of_the_match
    await db.collection("matches").document(match_id).set({"scoresComputedAt": timestamp,
                                                           "manOfTheMatch": potm_scores},
                                                          merge=True)
    if send_notification:
        _send_close_voting_notification(match_id, set(match_data["going"].keys()),
                                        set(potm_scores.keys()), match_data["sportCenterId"])


def _send_close_voting_notification(match_id, going_users, potms, sport_center_id):
    db = firestore.client()

    sport_center = db.collection('sport_centers').document(sport_center_id).get().to_dict()["name"]

    for p in potms:
        going_users.remove(p)

    send_notification_to_users(
        title="Match stats are available!",
        body="Check out the stats from the match at {}".format(sport_center),
        users=list(going_users),
        data={
            "click_action": "FLUTTER_NOTIFICATION_CLICK",
            "route": "/match/" + match_id,
            "match_id": match_id,
        }
    )

    send_notification_to_users(
        title="Congratulations! " + u"\U0001F3C6",
        body="You won the Player of the Match award for the {} match".format(sport_center),
        users=list(potms),
        data={
            "click_action": "FLUTTER_NOTIFICATION_CLICK",
            "match_id": match_id,
            "route": "/match/" + match_id,
            "event": "potm",
        }
    )
