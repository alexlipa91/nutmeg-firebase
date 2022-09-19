import asyncio
import datetime

from firebase_admin import firestore
from google.cloud.firestore import AsyncClient
from decimal import Decimal
import firebase_admin
from nutmeg_utils.notifications import send_notification_to_users
from typing import Dict, List

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

    scores_raw = ratings_doc.to_dict()["scores"]
    skills_raw = ratings_doc.to_dict().get("skills", {})

    scores = {}
    skills = {}

    # Keep only users who received > 1 vote
    for u in scores_raw:
        if len(scores_raw[u]) > 1:
            scores[u] = scores_raw[u]
            skills[u] = skills_raw[u]

    if len(scores) == 0:
        print("No ratings for this match")
        # mark match as rated
        await db.collection("matches").document(match_id).set({"scoresComputedAt": timestamp}, merge=True)
        return

    # do calculations
    # user_id -> (avg_score, num_votes)
    final_scores = {}
    for u in scores:
        only_positive = list(filter(lambda s: s > 0, scores[u].values()))
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

    skill_scores = _compute_skill_scores(skills)
    print("skill scores: {}".format(skill_scores))

    # store score for users
    for user, score_and_count in final_scores.items():
        user_stats_updates = {"scoreMatches": {match_id: score_and_count[0]}}
        if len(skill_scores.get(user, {})) > 0:
            user_stats_updates["skillScores"] = {match_id: skill_scores[user]}
        print("\nuser {}".format(user))
        print("storing user stats for this match:\t\t{}".format(user_stats_updates))

        if should_store:
            await db.collection("users").document(user).collection("stats").document("match_votes")\
                .set(user_stats_updates, merge=True)
            add_score_to_last_scores(db, user, score_and_count[0])

        # update average score
        user_stat_doc = await db.collection("users").document(user).collection("stats").document("match_votes").get()
        scores = user_stat_doc.to_dict().get("scoreMatches", {}).values()
        match_skills_scores = user_stat_doc.to_dict().get("skillScores", {}).values()
        avg_score = sum(scores) / len(scores)

        # update skills percentages: we count how many users among the ones who voted rated a certain skill.
        # If a user voted but didn't select a skill, it will have an empty list of votes
        skills_scores = _compute_overall_skill_scores(match_skills_scores)

        print("updates on overall stats:\t\t\t avg_score {}, skills: {}".format(avg_score, skills_scores))

        if should_store:
            await db.collection("users").document(user).update({"avg_score": avg_score, "skills": skills_scores})

        # udpate potm count for user
        for user in potm_scores:
            if should_store:
                await db.collection("users").document(user).update(
                    {"potm_count": firestore.firestore.Increment(1)})

    # mark match as rated and store man_of_the_match
    await db.collection("matches").document(match_id).set({"scoresComputedAt": timestamp,
                                                           "manOfTheMatch": potm_scores},
                                                          merge=True)
    if send_notification:
        _send_close_voting_notification(match_id, set(match_data["going"].keys()),
                                        set(potm_scores.keys()), match_data["sportCenterId"])


def _compute_skill_scores(skill_scores: Dict[str, Dict[str, List[str]]]):
    users_score = {}
    for user, rates in skill_scores.items():
        totals = {
            "Speed": 0,
            "Shooting": 0,
            "Passing": 0,
            "Dribbling": 0,
            "Defending": 0,
            "Physicality": 0,
            "Goalkeeping": 0
        }
        num_received = len(skill_scores[user])

        for _, skill_list in skill_scores[user].items():
            for s in skill_list:
                totals[s] = totals.get(s, 0) + 1

        for s in totals:
            if user not in users_score:
                users_score[user] = {}
            users_score[user][s] = totals[s] / num_received
    return users_score


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


def _compute_overall_skill_scores(match_skill_score: List[Dict[str, int]]) -> Dict[str, int]:
    all_scores = {}
    for skill_scores in match_skill_score:
        for s in skill_scores:
            if s not in all_scores:
                all_scores[s] = []
            all_scores[s].append(skill_scores[s])

    averages = {}
    for s in all_scores:
        averages[s] = sum(all_scores[s]) / len(all_scores[s])

    return averages


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


def add_score_to_last_scores(db, user_id, score):
    scores = db.collection("users").document(user_id).get(field_paths=["last_scores"]) \
        .to_dict().get("last_scores", {})
    scores.append(score)
    if len(scores) > 10:
        scores = scores[-10:]

    db.collection("users").document(user_id).update({"last_scores": scores})


if __name__ == '__main__':
    asyncio.run(_close_rating_round_firestore("9k4TMLwo1B5ICQztKCM3"))