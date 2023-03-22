import os
from datetime import datetime

import dateutil.tz
import firebase_admin
import stripe
from firebase_admin import firestore
from firebase_admin import auth
from flask_cors import cross_origin

from nutmeg_utils.ratings import MatchStats

firebase_admin.initialize_app()


@cross_origin(origins=["*"], allow_headers=["firebase-instance-id-token", "content-type", "authorization"])
def add_user(request):
    request_json = request.get_json(silent=True)
    print("args {}, data {}".format(request.args, request_json))

    request_data = request_json["data"]

    _add_user_firestore(request_data["id"], request_data["data"])

    return {"data": {}}, 200


@cross_origin(origins=["*"], allow_headers=["firebase-instance-id-token", "content-type", "authorization"])
def edit_user(request):
    request_json = request.get_json(silent=True)

    auth_data = auth.verify_id_token(request.headers["Authorization"].split(" ")[1])
    uid = auth.get_user(auth_data["user_id"])

    print("args {}, data {}".format(request.args, request_json))

    request_data = request_json["data"]

    is_admin = False
    if uid.custom_claims and uid.custom_claims.get("isAdmin", False):
        is_admin = True

    _edit_user_firestore(request_data["id"], request_data["data"], is_admin)
    return {"data": {}}, 200


@cross_origin(origins=["*"], allow_headers=["firebase-instance-id-token", "content-type", "authorization"])
def get_user(request):
    request_json = request.get_json(silent=True)
    print("args {}, data {}".format(request.args, request_json))

    request_data = request_json["data"]

    return {"data": _get_user_firestore(request_data["id"])}, 200


@cross_origin(origins=["*"], allow_headers=["firebase-instance-id-token", "content-type", "authorization"])
def store_user_token(request):
    request_json = request.get_json(silent=True)
    print("args {}, data {}".format(request.args, request_json))

    request_data = request_json["data"]

    return {"data": _store_user_token_firestore(request_data["id"], request_data["token"])}, 200


@cross_origin(origins=["*"], allow_headers=["firebase-instance-id-token", "content-type", "authorization"])
def is_organizer_account_complete(request):
    request_json = request.get_json(silent=True)
    print("args {}, data {}".format(request.args, request_json))

    request_data = request_json["data"]

    user_id = request_data["user_id"]
    is_test = request_data["is_test"]

    field_name = "stripeConnectedAccountId" if not is_test else "stripeConnectedAccountTestId"
    account_id = _get_user_firestore(user_id)[field_name]

    stripe.api_key = os.environ["STRIPE_PROD_KEY" if not is_test else "STRIPE_TEST_KEY"]
    is_complete = len(stripe.Account.retrieve(account_id)["requirements"]["currently_due"]) == 0

    return {"data": {"is_complete": is_complete}}, 200


@cross_origin(origins=["*"], allow_headers=["firebase-instance-id-token", "content-type", "authorization"])
def get_last_user_scores(request):
    request_json = request.get_json(silent=True)
    print("args {}, data {}".format(request.args, request_json))

    request_data = request_json["data"]

    return {"data": {"scores": _get_last_user_scores(request_data["id"])}}, 200


def _store_user_token_firestore(user_id, token):
    db = firestore.client()

    doc_ref = db.collection("users").document(user_id)
    doc_ref.update({"tokens": firestore.firestore.ArrayUnion([token])})


def _edit_user_firestore(user_id, user_data, is_admin):
    db = firestore.client()

    doc_ref = db.collection("users").document(user_id)
    if not doc_ref.get().exists:
        raise Exception("User {} does not exists".format(user_id))

    if db.collection('users').document(user_id).get().to_dict()["credits"] != user_data["credits"]:
        if not is_admin:
            raise Exception("Not admin cannot update user credits")
        else:
            print("Modifying credit amount since caller is admin")

    doc_ref.update(user_data)


def _add_user_firestore(user_id, user_data):
    assert "email" in user_data, "Required field missing"

    user_data["createdAt"] = firestore.firestore.SERVER_TIMESTAMP

    db = firestore.client()

    doc_ref = db.collection('users').document(user_id)
    print(user_data)
    print(type(user_data))

    doc_ref.set(user_data)
    return doc_ref.id


def _get_user_firestore(user_id):
    db = firestore.client()
    data = db.collection('users').document(user_id).get().to_dict()

    if not data:
        return None

    if "scores" in data and data["scores"].get("number_of_scored_games", 0) != 0:
        data["avg_score"] = data["scores"]["total_sum"] / data["scores"]["number_of_scored_games"]

    return data


def _get_last_user_scores(user_id):
    db = firestore.client()
    data = db.collection("users").document(user_id).collection("stats").document("match_votes").get().to_dict()
    if not data:
        return []

    scores = data.get("scoreMatches", {})

    score_dates = []
    for m in scores:
        date = data["joinedMatches"][m]
        score_dates.append((scores[m], date))

    score_dates.sort(key=lambda x: x[1])

    last_n = score_dates[-10:]

    return [x[0] for x in last_n]


def _serialize_date(date):
    return datetime.isoformat(date)


def recompute_users_stats():
    db = firestore.client()

    match_stats = {}
    for m in db.collection("matches").get():
        data = m.to_dict()

        if datetime.now(dateutil.tz.UTC) < data["dateTime"] or data.get("cancelledAt", None):
            print("skipping match {}".format(m.id))
            continue

        ratings_doc = db.collection("ratings").document(m.id).get()
        raw_scores = {}
        skill_scores = {}
        if ratings_doc.exists:
            ratings_doc_data = ratings_doc.to_dict()
            raw_scores = ratings_doc_data.get("scores", {})
            skill_scores = ratings_doc_data.get("skills", {})

        match_stats[m.id] = MatchStats(
            m.id,
            list(data.get("going", {}).keys()),
            raw_scores,
            skill_scores,
        )

    # generate user stats
    class UserStats:
        def __init__(self):
            self.num_played = 0
            self.scores = []
            self.sum_of_all_scores = 0
            self.number_of_scored_games = 0
            self.num_potm = 0
            self.skills = {}

        def add_score(self, score):
            self.scores.append(score)
            self.sum_of_all_scores += score
            self.number_of_scored_games += 1

        def add_skills(self, s, count):
            self.skills[s] = self.skills.get(s, 0) + count

        def get_avg_score(self):
            if len(self.scores) == 0:
                return None
            return sum(self.scores) / len(self.scores)

        def __repr__(self):
            return "{}\n{}\n{}".format(str(self.num_played), str(self.scores), str(self.num_potm), str(self.skills))

    user_stats = {}

    def get_stat_object(user):
        if user not in user_stats:
            user_stats[user] = UserStats()
        return user_stats[user]

    for m in match_stats.values():
        print(m.id)
        for u in m.going:
            get_stat_object(u).num_played += 1

        if m.get_potms():
            for u in m.get_potms()[0]:
                get_stat_object(u).num_potm += 1

        user_scores = m.get_user_scores()
        for u in user_scores:
            get_stat_object(u).add_score(user_scores[u])

        user_skills = m.get_user_skills()
        for u in user_skills:
            for s in user_skills[u]:
                get_stat_object(u).add_skills(s, user_skills[u][s])

    for u in user_stats:
        print(u)

        updates = {
            "num_matches_joined": user_stats[u].num_played,
            "potm_count": user_stats[u].num_potm,
            "avg_score": user_stats[u].get_avg_score(),
            "skills_count": user_stats[u].skills,
            "scores.total_sum": user_stats[u].sum_of_all_scores,
            "scores.number_of_scored_games": user_stats[u].number_of_scored_games
        }
        print(updates)

        try:
            db.collection("users").document(u).update(updates)
        except Exception as e:
            print("Error writing to user {}".format(u))
            print(e)


if __name__ == '__main__':
    # recompute_users_stats()
    db = firestore.client()

    for u in db.collection("users").get():
        db.collection("users").document(u.id).update({
            "avg_score": firestore.firestore.DELETE_FIELD
        })
