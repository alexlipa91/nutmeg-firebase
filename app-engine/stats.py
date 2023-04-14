import dateutil.parser
import firebase_admin
from flask import Blueprint, Flask
from flask import current_app as app

from typing import Dict, List

import dateutil.tz
from firebase_admin import firestore
from datetime import datetime

bp = Blueprint('stats', __name__, url_prefix='/stats')


class MatchStats:

    # @staticmethod
    # def from_ratings_doc(match_id):
    #     db = firestore.client()
    #     raw_scores_doc = db.collection("ratings").document(match_id).get().to_dict()
    #     if not raw_scores_doc:
    #         return None
    #     return MatchStats(match_id, None, [], raw_scores_doc.get("scores", {}), raw_scores_doc.get("skills", {}))

    def __init__(self,
                 match_id,
                 date,
                 going: List[str],
                 raw_scores: Dict[str, Dict[str, float]],
                 skills_scores: Dict[str, Dict[str, List[str]]]):
        self.id = match_id
        self.date = date
        self.going = going
        self.raw_scores = raw_scores
        self.raw_skill_scores = skills_scores

    def get_user_scores(self) -> Dict[str, float]:
        user_scores = {}
        for u in self.raw_scores:
            positive_scores = [v for v in self.raw_scores[u].values() if v > 0]
            if len(positive_scores) > 1:
                user_scores[u] = sum(positive_scores) / len(positive_scores)
        return user_scores

    def get_user_skills(self) -> Dict[str, Dict[str, int]]:
        user_skill_scores = {}

        for u in self.raw_skill_scores:
            if len(self.raw_scores[u]) > 1:
                for _, skills in self.raw_skill_scores[u].items():
                    for s in skills:
                        if u not in user_skill_scores:
                            user_skill_scores[u] = {}
                        user_skill_scores[u][s] = user_skill_scores[u].get(s, 0) + 1

        return user_skill_scores

    def get_potms(self) -> (List[str], float):
        if len(self.get_user_scores()) == 0:
            return None
        sorted_user_scores = sorted(self.get_user_scores().items(), reverse=True, key=lambda x: x[1])
        potm_score = sorted_user_scores[0][1]
        potms = [x[0] for x in sorted_user_scores if x[1] == potm_score]
        # for now, one POTM
        if len(potms) > 1:
            return None
        return potms, potm_score

    def __repr__(self):
        return "{}\n{}\n{}".format(str(self.get_user_scores()), str(self.get_potms()), str(self.get_user_skills()))


class UserStats:
    def __init__(self):
        self.num_played = 0
        self.scores: List[(datetime, float)] = []
        self.sum_of_all_scores = 0
        self.number_of_scored_games = 0
        self.num_potm = 0
        self.skills = {}

        self.joined_matches = {}
        self.score_matches = {}
        self.skill_scores = {}

    def add_score(self, date, score):
        self.scores.append((date, score))
        self.sum_of_all_scores += score
        self.number_of_scored_games += 1

    def add_skills(self, s, count):
        self.skills[s] = self.skills.get(s, 0) + count

    def get_avg_score(self):
        if len(self.scores) == 0:
            return None
        return sum(self.scores) / len(self.scores)

    # it returns a dict: datetime -> score
    def get_last_x_scores(self, x=10):
        self.scores.sort(key=lambda t: t[0], reverse=True)
        top_ten = self.scores[:x]
        return dict([(d.strftime("%Y%m%d%H%M%S"), s) for d, s in top_ten])

    # get updates for documents in the `users` collection
    def get_user_updates(self):
        return {
            "num_matches_joined": self.num_played,
            "potm_count": self.num_potm,
            "skills_count": self.skills,
            "scores.total_sum": self.sum_of_all_scores,
            "scores.number_of_scored_games": self.number_of_scored_games,
            "last_date_scores": self.get_last_x_scores()
        }

    # get updates for documents in the `users_stats` collection
    def get_user_stats_updates(self):
        return {
            "joinedMatches": self.joined_matches,
            "scoreMatches": self.score_matches,
        }

    def __repr__(self):
        return "{}\n{}\n{}".format(str(self.num_played), str(self.scores), str(self.num_potm), str(self.skills))


@bp.route("/recompute/all", methods=["GET"])
def recompute_stats():
    db = app.db_client

    match_data_cache = {}

    # get match stats
    match_stats = {}
    for m in db.collection("matches").get():
        data = m.to_dict()
        match_data_cache[m.id] = data

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
            data["dateTime"],
            list(data.get("going", {}).keys()),
            raw_scores,
            skill_scores,
        )

    # generate users stats from these matches
    user_stats: Dict[str, UserStats] = {}

    def get_stat_object(user):
        if user not in user_stats:
            user_stats[user] = UserStats()
        return user_stats[user]

    for m in match_stats.values():
        print(m.id)
        for u in m.going:
            get_stat_object(u).num_played += 1
            get_stat_object(u).joined_matches[m.id] = match_data_cache[m.id]['dateTime']

        if m.get_potms():
            for u in m.get_potms()[0]:
                get_stat_object(u).num_potm += 1

        user_scores = m.get_user_scores()
        for u in user_scores:
            get_stat_object(u).add_score(m.date, user_scores[u])
            get_stat_object(u).score_matches[m.id] = user_scores[u]

        user_skills = m.get_user_skills()
        for u in user_skills:
            for s in user_skills[u]:
                get_stat_object(u).add_skills(s, user_skills[u][s])

    for u, s in user_stats.items():
        print(u)

        print(s.get_user_updates())
        print(s.get_user_stats_updates())

        try:
            db.collection("users").document(u).update(s.get_user_updates())
            db.collection("users").document(u).collection("stats").document("match_votes").update(s.get_user_stats_updates())
        except Exception as e:
            print("Error writing to user {}".format(u))
            print(e)


if __name__ == '__main__':
    firebase_admin.initialize_app()
    app = Flask("test_app")
    app.db_client = firestore.client()

    with app.app_context():
        recompute_stats()