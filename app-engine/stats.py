import firebase_admin
from flask import Blueprint, Flask
from flask import current_app as app

from typing import List

from firebase_admin import firestore
from datetime import datetime

from matches import freeze_stats
from statistics.stats_utils import UserUpdates

bp = Blueprint('stats', __name__, url_prefix='/stats')


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

    # updates aggregate
    users_updates = {}

    # get match stats
    for m in db.collection("matches").get():
        match_updates = freeze_stats(m.id, write=False)
        for u in match_updates:
            users_updates[u] = UserUpdates.sum(users_updates.get(u, UserUpdates.zero()), match_updates[u])

    for u in users_updates:
        db.collection("users").document(u).update(users_updates[u].to_num_update())


if __name__ == '__main__':
    firebase_admin.initialize_app()
    app = Flask("test_app")
    app.db_client = firestore.client()

    with app.app_context():
        recompute_stats()