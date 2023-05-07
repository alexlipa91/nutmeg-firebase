import firebase_admin
from flask import Blueprint, Flask
from flask import current_app as app

from typing import List

from firebase_admin import firestore
from datetime import datetime


from src.blueprints.matches import _freeze_match_stats
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
    per_month_update = {}

    log = {}

    # get match stats
    for m in db.collection("matches").get():
        year_month = m.to_dict()["dateTime"].strftime("%Y%m")
        user_updates, error = _freeze_match_stats(m.id, m.to_dict())
        if error:
            log[error] = log.get(error, 0)
        else:
            log["success"] = log.get("success", 0) + 1
            for u in user_updates:
                # add to all time leaderboard
                all_time_users_updates[u] = UserUpdates.sum(all_time_users_updates.get(u, UserUpdates.zero()),
                                                            user_updates[u])
                # add to monthly leaderboard
                current = per_month_update.setdefault(year_month, {})
                current[u] = UserUpdates.sum(current.get(u, UserUpdates.zero()), user_updates[u])
    print("recompute stats log: {}".format(log))

    for u in all_time_users_updates:
        db.collection("users").document(u).update(all_time_users_updates[u].to_absolute_user_doc_update())

    # update leaderboards
    db.collection("leaderboards").document("abs")\
        .set({"entries": {u: all_time_users_updates[u].to_absolute_leaderboard_doc_update() for u in all_time_users_updates}},
             merge=True)
    for m in per_month_update:
        db.collection("leaderboards").document(m) \
            .set({"entries": {u: per_month_update[m][u].to_absolute_leaderboard_doc_update() for u in per_month_update[m]}},
                 merge=True)

    return log


if __name__ == '__main__':
    firebase_admin.initialize_app()
    app = Flask("test_app")
    app.db_client = firestore.client()

    from dotenv import load_dotenv

    load_dotenv("../../scripts/.env.local")
    with app.app_context():
        # updates = recompute_stats(write=False, month=4)
        # import csv
        #
        # with open('eggs.csv', 'w', newline='') as csvfile:
        #     spamwriter = csv.writer(csvfile, delimiter=',',
        #                             quotechar='|', quoting=csv.QUOTE_MINIMAL)
        #     for u in updates:
        #         values = updates[u].to_num_update()
        #         name = app.db_client.collection("users").document(u).get(field_paths={"name"}).to_dict().get("name",
        #                                                                                                      "name_unkown")
        #         print(name)
        #         total_record = values["record"]["num_win"] + values["record"]["num_loss"]
        #         num_scored_games = values["scores"]["number_of_scored_games"]
        #         spamwriter.writerow(
        #             [u, name, values["num_matches_joined"],
        #              None if num_scored_games == 0 else values["scores"]["total_sum"] / num_scored_games,
        #              values["potm_count"],
        #              None if total_record == 0 else values["record"]["num_win"] / total_record
        #              ]
        #         )
        recompute_stats()
