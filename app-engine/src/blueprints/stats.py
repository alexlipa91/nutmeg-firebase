import firebase_admin
from flask import Blueprint, Flask
from flask import current_app as app

from typing import List

from firebase_admin import firestore
from datetime import datetime


from src.blueprints.matches import _freeze_match_stats, delete_tests, freeze_match_stats
from src.utils import update_leaderboard
from statistics.stats_utils import UserUpdates

bp = Blueprint('stats', __name__, url_prefix='/stats')


class UserStats:
    def __init__(self):
        self.num_played = 0
        self.scores: List[(datetime, float)] = []
        self.sum_of_all_scores = 0
        self.number_of_scored_games = 0
        self.num_potm = 0

        self.joined_matches = {}
        self.score_matches = {}
        self.skill_scores = {}

    def add_score(self, date, score):
        self.scores.append((date, score))
        self.sum_of_all_scores += score
        self.number_of_scored_games += 1

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
            "scores.total_sum": self.sum_of_all_scores,
            "scores.number_of_scored_games": self.number_of_scored_games,
            "last_date_scores": self.get_last_x_scores()
        }

    def __repr__(self):
        return "{}\n{}\n{}".format(str(self.num_played), str(self.scores), str(self.num_potm))


@bp.route("/recompute/all", methods=["GET"])
def recompute_stats():
    db = app.db_client

    # updates aggregate
    all_time_users_updates = {}
    all_time_match_list = []
    per_month_update = {}
    per_month_match_list = {}

    log = {}

    # get match stats
    for m in db.collection("matches").get():
        print("Analyzing {}".format(m.id))
        year_month = m.to_dict()["dateTime"].strftime("%Y%m")
        user_updates, error = _freeze_match_stats(m.id, m.to_dict())
        if error:
            log[error] = log.get(error, 0) + 1
        else:
            log["success"] = log.get("success", 0) + 1
            for u in user_updates:
                # add to all time leaderboard
                all_time_users_updates[u] = UserUpdates.sum(all_time_users_updates.get(u, UserUpdates.zero()),
                                                            user_updates[u])
                all_time_match_list.append(m.id)

                # add to monthly leaderboard
                current = per_month_update.setdefault(year_month, {})
                current[u] = UserUpdates.sum(current.get(u, UserUpdates.zero()), user_updates[u])

                current_match_list = per_month_match_list.setdefault(year_month, [])
                current_match_list.append(m.id)
    print("recompute stats log: {}".format(log))

    for u in all_time_users_updates:
        db.collection("users").document(u).update(all_time_users_updates[u].to_absolute_user_doc_update())

    # update leaderboards
    update_leaderboard(app, "abs",
                       all_time_match_list,
                       {u: all_time_users_updates[u].to_absolute_leaderboard_doc_update() for u in all_time_users_updates})
    for m in per_month_update:
        update_leaderboard(app, m,
                           per_month_match_list[m],
                           {u: per_month_update[m][u].to_absolute_leaderboard_doc_update() for u in per_month_update[m]})

    return log


if __name__ == '__main__':
    firebase_admin.initialize_app()
    app = Flask("test_app")
    app.db_client = firestore.client()

    from dotenv import load_dotenv

    load_dotenv("../../scripts/.env.local")
    with app.app_context():
        recompute_stats()
