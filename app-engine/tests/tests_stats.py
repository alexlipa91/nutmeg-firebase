import datetime
import unittest
from datetime import timedelta
from unittest import mock

from mockfirestore import MockFirestore
from dateutil import tz

from src import _create_app

def notification_mock(match_id, going_users, potms, sport_center):
    print("skipping notification")

def get_basic_user_data_mock(app, u):
    return {"id": u}

def setup_logging_mock():
    print("setup logging mock")


class StatTests(unittest.TestCase):

    @staticmethod
    @mock.patch('src.matches._send_close_voting_notification', side_effect=notification_mock)
    @mock.patch('src.utils._get_user_basic_data', side_effect=get_basic_user_data_mock)
    @mock.patch('src._setup_logging', side_effect=setup_logging_mock)
    def test_stat_computation(mock_notifications, mock_user_data, mock_setup_logging):
        db = MockFirestore()
        flask_app = _create_app(db)

        now = datetime.datetime.utcnow().astimezone(tz.gettz("Europe/Amsterdam"))

        # add docs (it is needed because the mock won't work well with increments)
        [db.collection("users").document(u).set({"name": u}) for u in ["user_one", "user_two", "user_three"]]

        # add two matches
        db.collection("matches").document("match_one").set({
            "dateTime": now - timedelta(days=2),
            "going": {
                "user_one": None,
                "user_two": None,
                "user_three": None
            },
            "score": [3, 0],
            "teams": {
                "balanced": {
                    "players": {
                        "a": ["user_one", "user_two"],
                        "b": ["user_three"]
                    }
                }
            }
        })
        db.collection("matches").document("match_two").set({
            "dateTime": now - timedelta(days=3),
            "going": {
                "user_one": None,
                "user_two": None,
                "user_three": None
            }
        })
        # add ratings
        db.collection("ratings").document("match_one").set({
            "scores": {
                "user_one": {
                    "user_two": 2,
                    "user_three": 3,
                },
                "user_two": {
                    "user_one": 5,
                    "user_three": 3,
                }
            }
        })
        db.collection("ratings").document("match_two").set({
            "scores": {
                "user_one": {
                    "user_two": 1,
                    "user_three": 1,
                },
                "user_two": {
                    "user_one": 2,
                    "user_three": 3,
                }
            }
        })

        # freeze stats one match
        response = flask_app.test_client().post('/matches/match_one/stats/freeze')
        assert response.status_code == 200

        user_one = db.collection("users").document("user_one").get().to_dict()
        assert user_one["num_matches_joined"] == 1
        assert user_one["scores"] == {"total_sum": 2.5, "number_of_scored_games": 1}
        assert user_one["record"] == {"num_win": 1, "num_draw": 0, "num_loss": 0}
        assert user_one["potm_count"] == 0

        user_two = db.collection("users").document("user_two").get().to_dict()
        assert user_two["num_matches_joined"] == 1
        assert user_two["scores"] == {"total_sum": 4, "number_of_scored_games": 1}
        assert user_two["potm_count"] == 1
        assert user_two["record"] == {"num_win": 1, "num_draw": 0, "num_loss": 0}

        # freeze stats second match
        response = flask_app.test_client().post('/matches/match_two/stats/freeze')
        assert response.status_code == 200

        user_one = db.collection("users").document("user_one").get().to_dict()
        assert user_one["num_matches_joined"] == 2
        assert user_one["scores"] == {"total_sum": 3.5, "number_of_scored_games": 2}
        assert user_one["record"] == {"num_win": 1, "num_draw": 0, "num_loss": 0}

        user_two = db.collection("users").document("user_two").get().to_dict()
        assert user_two["num_matches_joined"] == 2
        assert user_two["scores"] == {"total_sum": 6.5, "number_of_scored_games": 2}
        assert user_two["record"] == {"num_win": 1, "num_draw": 0, "num_loss": 0}

        # try to recompute everything from scratch
        response = flask_app.test_client().get('/stats/recompute/all')
        assert response.status_code == 200

        user_one = db.collection("users").document("user_one").get().to_dict()
        assert user_one["num_matches_joined"] == 2
        assert user_one["scores"] == {"total_sum": 3.5, "number_of_scored_games": 2}
        assert user_one["record"] == {"num_win": 1, "num_draw": 0, "num_loss": 0}

        user_two = db.collection("users").document("user_two").get().to_dict()
        assert user_two["num_matches_joined"] == 2
        assert user_two["scores"] == {"total_sum": 6.5, "number_of_scored_games": 2}
        assert user_two["record"] == {"num_win": 1, "num_draw": 0, "num_loss": 0}
