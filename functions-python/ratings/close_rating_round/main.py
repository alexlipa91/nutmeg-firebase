import asyncio
import datetime

from firebase_admin import firestore
from google.cloud.firestore import AsyncClient
import firebase_admin
from nutmeg_utils.notifications import send_notification_to_users
from nutmeg_utils.ratings import MatchStats

firebase_admin.initialize_app()


def close_rating_round(request):
    request_json = request.get_json(silent=True)
    print("data {}".format(request_json))

    request_data = request_json["data"]

    asyncio.run(_close_rating_round_firestore(request_data["match_id"]))

    return {"data": {}}, 200


async def _close_rating_round_firestore(match_id, send_notification=True):
    db = AsyncClient()

    timestamp = datetime.datetime.utcnow()

    match_doc = await db.collection("matches").document(match_id).get()
    match_data = match_doc.to_dict()
    if not match_data:
        print("Match does not exist")
        return

    if match_data.get("cancelledAt", None):
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

    raw_scores = ratings_doc.to_dict()["scores"]
    if len(raw_scores) == 0:
        print("No ratings for this match")
        # mark match as rated
        await db.collection("matches").document(match_id).set({"scoresComputedAt": timestamp}, merge=True)
        return

    match_stats = MatchStats(
        match_id,
        match_data.get("going", {}),
        raw_scores,
        ratings_doc.to_dict().get("skills", {})
    )

    final_scores = match_stats.get_user_scores()
    potms = match_stats.get_potms()
    print("final scores {}; man(s) of the match: {}".format(final_scores, potms))

    should_store = "isTest" not in match_data or not match_data["isTest"]

    skill_scores = match_stats.get_user_skills()
    print("skill scores: {}".format(skill_scores))

    # store score for users
    for user, score in final_scores.items():
        user_stats_updates = {
            "scoreMatches": {match_id: score},
            "skillScores": {match_id: skill_scores[user]}
        }

        print("storing user stats for this match:\t\t{}".format(user_stats_updates))

        if should_store:
            await db.collection("users").document(user).collection("stats").document("match_votes")\
                .update(user_stats_updates)
            await add_score_to_last_scores(db, user, score, match_data["dateTime"])

        # update average score
        user_stat_doc = await db.collection("users").document(user).collection("stats").document("match_votes").get()
        scores = user_stat_doc.to_dict().get("scoreMatches", {}).values()
        avg_score = sum(scores) / len(scores)

        # update skills counts
        skill_scores_totals = {}
        for skill in skill_scores[user]:
            skill_scores_totals[skill] = firestore.firestore.Increment(skill_scores[user][skill])
        print("updates on overall stats:\t\t\t avg_score {}, skills_count: {}".format(avg_score, skill_scores_totals))

        if should_store:
            await db.collection("users").document(user).update({"avg_score": avg_score,
                                                                "skills_count": skill_scores_totals})

        # udpate potm count for user
        for user in potms[0]:
            if should_store:
                await db.collection("users").document(user).update(
                    {"potm_count": firestore.firestore.Increment(1)})

    # mark match as rated and store man_of_the_match
    await db.collection("matches").document(match_id).update({"scoresComputedAt": timestamp, "manOfTheMatch": potms[0]})

    if send_notification:
        _send_close_voting_notification(match_id, set(match_data["going"].keys()),
                                        set(potms[0]), match_data["sportCenterId"])


def _compute_weighted_avg_score(user_id):
    db = firestore.client()
    user_stat_doc = db.collection("users").document(user_id).collection("stats").document("match_votes").get()

    match_joined = user_stat_doc.to_dict().get("joinedMatches", {})
    numerator = denominator = 0
    for m in match_joined:
        ratings_doc = db.collection("ratings").document(m).get().to_dict()
        if ratings_doc and user_id in ratings_doc["scores"]:
            received = ratings_doc["scores"][user_id]
            match_score = sum(received.values()) / len(received)
            score_weight = len(received)

            numerator += match_score * score_weight
            denominator += score_weight

    return numerator / denominator


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


async def add_score_to_last_scores(db, user_id, score, date_time):
    user_doc = await db.collection("users").document(user_id).get(field_paths=["last_date_scores"])
    scores = user_doc.to_dict().get("last_date_scores", {})
    scores[date_time.strftime("%Y%m%d%H%M%S")] = score

    if len(scores) > 10:
        top_ten_with_score = {}
        for d in sorted(scores, reverse=True)[:10]:
            top_ten_with_score[d] = scores[d]
        scores = top_ten_with_score

    await db.collection("users").document(user_id).update({"last_date_scores": scores})