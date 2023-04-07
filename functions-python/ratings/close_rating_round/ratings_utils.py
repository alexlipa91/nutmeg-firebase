from datetime import datetime
from typing import Dict, List

import dateutil
from firebase_admin import firestore


class MatchStats:
    def __init__(self,
                 id,
                 going: List[str],
                 raw_scores: Dict[str, Dict[str, float]],
                 skills_scores: Dict[str, Dict[str, List[str]]]):
        self.id = id
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
        return potms, potm_score

    def __repr__(self):
        return "{}\n{}\n{}".format(str(self.going), str(self.raw_scores), str(self.raw_skill_scores))


def recompute_users_stats():
    db = firestore.client()

    match_stats = {}
    match_data_cache = {}
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

            self.joined_matches = {}
            self.score_matches = {}
            self.skill_scores = {}

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
            get_stat_object(u).joined_matches[m.id] = match_data_cache[m.id]['dateTime']

        if m.get_potms():
            for u in m.get_potms()[0]:
                get_stat_object(u).num_potm += 1

        user_scores = m.get_user_scores()
        for u in user_scores:
            get_stat_object(u).add_score(user_scores[u])
            get_stat_object(u).score_matches[m.id] = user_scores[u]

        user_skills = m.get_user_skills()
        for u in user_skills:
            for s in user_skills[u]:
                get_stat_object(u).add_skills(s, user_skills[u][s])

    for u in user_stats:
        print(u)

        updates = {
            "num_matches_joined": user_stats[u].num_played,
            "potm_count": user_stats[u].num_potm,
            "skills_count": user_stats[u].skills,
            "scores.total_sum": user_stats[u].sum_of_all_scores,
            "scores.number_of_scored_games": user_stats[u].number_of_scored_games
        }
        secondary_stats_updates = {
            "joinedMatches": user_stats[u].joined_matches,
            "scoreMatches": user_stats[u].score_matches,
        }
        print(updates)
        print(secondary_stats_updates)

        try:
            db.collection("users").document(u).update(updates)
            db.collection("users").document(u).collection("stats").document("match_votes").update(secondary_stats_updates)
        except Exception as e:
            print("Error writing to user {}".format(u))
            print(e)
