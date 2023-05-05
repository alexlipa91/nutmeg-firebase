import json
from datetime import datetime
from typing import Dict

from firebase_admin import firestore


class UserUpdates:

    @staticmethod
    def from_single_game(date, score, wdl, is_potm):
        return UserUpdates(
            date_score={date: score},
            total_sum_score=score if score else 0,
            num_win=1 if wdl == "w" else 0,
            num_draw=1 if wdl == "d" else 0,
            num_loss=1 if wdl == "l" else 0,
            num_scored_games=1 if score else 0,
            num_matches_joined=1,
            num_potms=1 if is_potm else 0
        )

    def __init__(self,
                 date_score: Dict,
                 total_sum_score,
                 num_potms,
                 num_win,
                 num_draw,
                 num_loss,
                 num_scored_games,
                 num_matches_joined):
        self.num_matches_joined = num_matches_joined
        self.num_scored_games = num_scored_games
        self.total_sum_score = total_sum_score
        self.num_potms = num_potms
        self.date_score = date_score
        self.num_win = num_win
        self.num_draw = num_draw
        self.num_loss = num_loss

    def to_user_document_update(self):
        base_fields = self.to_leaderboard_document_update()
        base_fields["last_date_scores"] = {
            d.strftime("%Y%m%d%H%M%S"): v for d, v in self.date_score.items() if v
        }
        return base_fields

    def to_leaderboard_document_update(self):
        return {
            "num_matches_joined": firestore.firestore.Increment(self.num_matches_joined),
            "scores": {
                "number_of_scored_games": firestore.firestore.Increment(self.num_scored_games),
                "total_sum": firestore.firestore.Increment(self.total_sum_score)
            },
            'potm_count': firestore.firestore.Increment(self.num_potms),
            "record": {
                "num_win": firestore.firestore.Increment(self.num_win),
                "num_draw": firestore.firestore.Increment(self.num_draw),
                "num_loss": firestore.firestore.Increment(self.num_loss),
            }
        }

    def to_absolute_user_doc_update(self):
        base_updates = self.to_absolute_leaderboard_doc_update()
        base_updates["last_date_scores"] = {
            d.strftime("%Y%m%d%H%M%S"): v for d, v in self.date_score.items() if v
        }
        return base_updates

    def to_absolute_leaderboard_doc_update(self):
        return {
            "num_matches_joined": self.num_matches_joined,
            "scores": {
                "number_of_scored_games": self.num_scored_games,
                "total_sum": self.total_sum_score,
            },
            'potm_count': self.num_potms,
            "record": {
                "num_win": self.num_win,
                "num_draw": self.num_draw,
                "num_loss": self.num_loss,
            }
        }

    @staticmethod
    def dumper(obj):
        if isinstance(obj, datetime):
            return obj.strftime("%Y-%m-%d %H:%M:%S")
        try:
            return obj.toJSON()
        except:
            return obj.__dict__

    @staticmethod
    def sum(a, b):
        return UserUpdates(
            date_score=dict(list(a.date_score.items()) + list(b.date_score.items())),
            num_win=a.num_win + b.num_win,
            num_draw=a.num_draw + b.num_draw,
            num_loss=a.num_loss + b.num_loss,
            num_matches_joined=a.num_matches_joined + b.num_matches_joined,
            num_scored_games=a.num_scored_games + b.num_scored_games,
            total_sum_score=a.total_sum_score + b.total_sum_score,
            num_potms=a.num_potms + b.num_potms
        )

    @staticmethod
    def zero():
        return UserUpdates(
            date_score={},
            num_win=0,
            num_loss=0,
            num_draw=0,
            num_scored_games=0,
            num_matches_joined=0,
            total_sum_score=0,
            num_potms=0
        )

    def __repr__(self):
        return json.dumps(self.to_absolute_user_doc_update(), default=self.dumper, indent=2)
