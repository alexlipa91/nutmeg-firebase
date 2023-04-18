import datetime
import json
import os

from firebase_admin import firestore
import firebase_admin
from nutmeg_utils.notifications import send_notification_to_users
from nutmeg_utils.ratings import MatchStats
import requests

firebase_admin.initialize_app()


def close_rating_round(request):
    request_json = request.get_json(silent=True)
    print("data {}".format(request_json))

    request_data = request_json["data"]
    resp = requests.post("https://nutmeg-9099c.ew.r.appspot.com/matches/{}/stats/freeze".format(request_data["match_id"]))
    print(resp)

    return {"data": {}}, 200


def _close_rating_round(match_id):
    calculations = _close_rating_round_calculations(match_id)

    db = firestore.client()

    match_doc_ref = db.collection('matches').document(match_id)
    users_docs_ref = {}
    users_stats_docs_ref = {}

    for u in calculations.user_stats_updates.keys():
        users_docs_ref[u] = db.collection("users").document(u)
        users_stats_docs_ref[u] = db.collection("users").document(u).collection("stats").document("match_votes")

    def dumper(obj):
        if isinstance(obj, datetime.datetime):
            return "date"
        try:
            return obj.toJSON()
        except:
            return obj.__dict__
    print(json.dumps(calculations, default=dumper, indent=2))
    _close_rating_round_transaction(db.transaction(), calculations, match_doc_ref, users_docs_ref, users_stats_docs_ref)


@firestore.transactional
def _close_rating_round_transaction(transaction, calculations, match_doc_ref, users_docs_ref, users_stats_docs_ref):
    match_data = match_doc_ref.get(transaction=transaction).to_dict()
    match_datetime = match_data["dateTime"]

    last_date_scores = {}
    for u in calculations.user_match_stats:
        last_date_scores[u] = users_docs_ref[u].get(transaction=transaction, field_paths=["last_date_scores"]).to_dict()\
            .get("last_date_scores", {})

    for u in calculations.user_match_stats:
        transaction.set(users_stats_docs_ref[u], calculations.user_match_stats[u], merge=True)
        transaction.set(users_docs_ref[u], calculations.user_stats_updates[u], merge=True)

        # add last score
        score = calculations.user_match_stats[u]["scoreMatches"][match_doc_ref.id]
        last_date_scores[u][match_datetime.strftime("%Y%m%d%H%M%S")] = score

        if len(last_date_scores[u]) > 10:
            top_ten_with_score = {}
            for d in sorted(last_date_scores[u], reverse=True)[:10]:
                top_ten_with_score[d] = last_date_scores[u][d]
            last_date_scores[u] = top_ten_with_score

        transaction.set(users_docs_ref[u], {"last_date_scores": last_date_scores[u]}, merge=True)

    transaction.set(match_doc_ref, calculations.match_udpates, merge=True)

    _send_close_voting_notification(match_doc_ref.id, calculations.get_going_users(), calculations.get_potms(),
                                    match_data.get("sportCenter", None))


class RatingsRoundResult:

    def __init__(self, match_updates, user_match_stats=None, user_stats_updates=None):
        self.user_match_stats = user_match_stats if user_match_stats else {}
        self.user_stats_updates = user_stats_updates if user_stats_updates else {}
        self.match_udpates = match_updates

    def get_potms(self):
        return [u for u in self.user_stats_updates if "potm_count" in self.user_stats_updates[u]]

    def get_going_users(self):
        return [u for u in self.user_stats_updates]

    def __repr__(self):
        return "user_match_stats: {}\nuser_stats_updates: {}\nmatch_updates: {}".format(self.user_match_stats,
                                                                                        self.user_stats_updates,
                                                                                        self.match_udpates)


def _close_rating_round_calculations(match_id):
    db = firestore.client()

    match_data = db.collection("matches").document(match_id).get().to_dict()
    match_updates = {"scoresComputedAt": datetime.datetime.utcnow()}

    ratings_doc = db.collection("ratings").document(match_id).get()
    if not ratings_doc.exists or len(ratings_doc.to_dict()["scores"]) == 0:
        print("No ratings for this match")
        # mark match as rated
        return RatingsRoundResult(match_updates=match_updates)

    match_stats = MatchStats(
        match_id,
        match_data.get("going", {}),
        ratings_doc.to_dict()["scores"],
        ratings_doc.to_dict().get("skills", {})
    )

    final_scores = match_stats.get_user_scores()
    potms = match_stats.get_potms()
    if potms:
        potms_map = {}
        for p in potms[0]:
            potms_map[p] = potms[1]
        match_updates["manOfTheMatch"] = potms_map

    skill_scores = match_stats.get_user_skills()

    all_users_match_stats = {}
    all_users_stats_updates = {}

    # store score for users
    for user, score in final_scores.items():
        user_match_stats = {
            "scoreMatches": {match_id: score},
        }
        if user in skill_scores:
            user_match_stats["skillScores"] = {match_id: skill_scores[user]}

        skill_scores_increment = {}
        for skill in skill_scores.get(user, {}):
            skill_scores_increment[skill] = firestore.firestore.Increment(skill_scores[user][skill])

        user_stats_increments = {
            "skills_count": skill_scores_increment,
            "scores.number_of_scored_games": firestore.firestore.Increment(1),
            "scores.total_sum": firestore.firestore.Increment(score)
        }
        if user in potms[0]:
            user_stats_increments["potm_count"] = firestore.firestore.Increment(1)

        # last 10 scores
        last_date_scores = db.collection("users").document(user).get(field_paths=["last_date_scores"])\
            .to_dict().get("last_date_scores", [])
        last_date_scores[match_data["dateTime"].strftime("%Y%m%d%H%M%S")] = score

        if len(last_date_scores) > 10:
            top_ten_with_score = {}
            for d in sorted(last_date_scores, reverse=True)[:10]:
                top_ten_with_score[d] = last_date_scores[d]
            last_date_scores = top_ten_with_score
        # todo add
        user_stats_increments["last_date_scores"] = last_date_scores

        all_users_match_stats[user] = user_match_stats
        all_users_stats_updates[user] = user_stats_increments

    return RatingsRoundResult(match_updates=match_updates, user_match_stats=all_users_match_stats,
                              user_stats_updates=all_users_stats_updates)


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


def _send_close_voting_notification(match_id, going_users, potms, sport_center):
    for p in potms:
        going_users.remove(p)

    sport_center_name = sport_center.get("name", "")

    send_notification_to_users(
        title="Match stats are available!",
        body="Check out the stats for the{} match".format(" " + sport_center_name),
        users=list(going_users),
        data={
            "click_action": "FLUTTER_NOTIFICATION_CLICK",
            "route": "/match/" + match_id,
            "match_id": match_id,
        }
    )

    send_notification_to_users(
        title="Congratulations! " + u"\U0001F3C6",
        body="You won the Player of the Match award for the{} match".format(" " + sport_center_name),
        users=list(potms),
        data={
            "click_action": "FLUTTER_NOTIFICATION_CLICK",
            "match_id": match_id,
            "route": "/match/" + match_id,
            "event": "potm",
        }
    )


if __name__ == '__main__':
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/Users/alessandrolipa/IdeaProjects/nutmeg-firebase/nutmeg-9099c-bf73c9d6b62a.json"
    _close_rating_round("zeY8v1qsJsXCZJ5e21Dm")

