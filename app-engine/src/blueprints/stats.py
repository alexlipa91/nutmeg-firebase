import firebase_admin
from flask import Blueprint, Flask
from flask import current_app as app

from typing import List, Dict

from firebase_admin import firestore
from datetime import datetime


from src.blueprints.matches import freeze_stats
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
def recompute_stats(write_user_doc=True, write_leaderboard=True, month=None) -> Dict[str, UserUpdates]:
    db = app.db_client

    # updates aggregate
    users_updates = {}

    num_analyzed = 0
    num_skipped = 0

    # get match stats
    for m in db.collection("matches").get():
        if not month or m.to_dict()["dateTime"].month == month:
            match_updates = freeze_stats(m.id, write=False, notify=False, local=True)
            if len(match_updates) == 0:
                num_skipped += 1
            else:
                num_analyzed += 1
            for u in match_updates:
                users_updates[u] = UserUpdates.sum(users_updates.get(u, UserUpdates.zero()), match_updates[u])
    print("Analyzed {} matches and skipped {} matches".format(num_analyzed, num_skipped))

    if write_user_doc:
        for u in users_updates:
            db.collection("users").document(u).update(users_updates[u].to_absolute_user_doc_update())
    if write_leaderboard:
        update = {}
        for u in users_updates:
            update[u] = users_updates[u].to_absolute_leaderboard_doc_update()
        db.collection("leaderboards").document("all-200001").set({"entries": update})

    return {}


@bp.route("/leaderboard/<group>/<from_time>", methods=["GET"])
def recompute_leaderboard(group, from_time):
    # from_time is a string of type YYYY-MM
    stats = recompute_stats()

    entries = {}
    for u in stats:
        v = stats[u].to_absolute_user_doc_update()
        num_scored = v.get("scores", {}).get("num_scored_games", 0)
        num_win = v.get("record", {}).get("num_win", 0)
        num_draw = v.get("record", {}).get("num_draw", 0)
        num_lost = v.get("record", {}).get("num_lost", 0)

        entries[u] = {
            "num_matches_joined": v["num_matches_joined"],
            "avg_score": None if num_scored == 0 else v["scores"]["total_sum_score"] / num_scored,
            "potm_count": v["potm_count"],
            "win_loss_ratio": None if num_win + num_draw + num_lost == 0 else num_win / (num_win + num_draw + num_lost)
        }
    app.db_client.collection("leaderboards").document("{}-{}".format(group, from_time)).set({
        "entries": entries
    })


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
        recompute_stats(write_user_doc=False)
